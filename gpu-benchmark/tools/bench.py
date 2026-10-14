#!/usr/bin/env python3
"""gpu-benchmark serial case runner.

Explicitly-approved control-side tool (spec 005-gpu-confidential-benchmark
FR-015, constitution v2.0.0 II): preflight (H100-or-newer model gate, GPU
count, NVLink, runtime classes, device-plugin resource) -> serial per-case
lifecycle (Helm render/apply/wait/remove) -> per-repeat in-pod benchmark
execution via bounded `oc exec` -> device evidence -> output parsing with
residual-check verification gating -> Markdown comparison summary + Apache
Iceberg appends.

Runs ONLY on the operator's control machine; nothing here executes
in-cluster. See specs/005-gpu-confidential-benchmark/contracts/operator-surface.md
for the CLI and gpu-benchmark/docs/benchmark-selection.md for why HPL and
HPL-MxP own every number.

Dependencies are declared and pinned in ../pyproject.toml (imported
statically; a missing dependency fails at import time, not mid-run).
Catalog logic (pure, CI-validatable) lives in catalog.py.
"""
from __future__ import annotations

import dataclasses
import datetime as dt
import json
import random
import re
import shutil
import signal
import statistics
import subprocess
import sys
import time
from pathlib import Path
from typing import Annotated

import typer
import yaml

from catalog import (DefinitionValidationError, compute_params, load_catalog,
                     parse_output, render_command)

VERSION = "0.1.0"
TIER_ORDER = ["plain", "kata", "coco"]
TIER_RUNTIME = {"plain": "", "kata": "kata-nvidia-gpu", "coco": "kata-cc-nvidia-gpu"}
EXIT_OK, EXIT_PREFLIGHT, EXIT_CASE_FAILED, EXIT_USAGE, EXIT_CLEANUP_FAILED = 0, 1, 2, 3, 4
CHART_DIR = Path(__file__).resolve().parent.parent

# GFD node labels (research R3)
LABEL_PRODUCT = "nvidia.com/gpu.product"
LABEL_COUNT = "nvidia.com/gpu.count"
LABEL_MEM = "nvidia.com/gpu.memory.total"
LABEL_NVLINK = "nvidia.com/nvlink.present"

# FR-002: H100-or-newer only — the confidential-GPU-capable models. GFD
# product labels look like "NVIDIA-H100-80GB-HBM3"; a model passes when an
# allowlist token is a substring of the normalized label. Extend via
# --gpu-model-allowlist (semantics stay H100-or-newer per spec).
CC_CAPABLE_MODELS = ["H100", "H200", "B100", "B200", "GB200", "GB300",
                     "RTX-PRO-6000-BLACKWELL", "RTX-PRO-6000-BSE"]

DEFAULT_IMAGE = "nvcr.io/nvidia/hpc-benchmarks:26.02.01"

# ---------------------------------------------------------------- utilities


def utcnow() -> dt.datetime:
    return dt.datetime.now(dt.timezone.utc)


def ts() -> str:
    return utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")


_PREFLIGHT_LOG: Path | None = None


def say(level: str, check: str, detail: str) -> None:
    """Fixed-format machine-greppable line (contracts/operator-surface.md)."""
    line = f"PREFLIGHT {level} {check} {detail}"
    print(line, flush=True)
    if _PREFLIGHT_LOG is not None:
        with open(_PREFLIGHT_LOG, "a", encoding="utf-8") as fh:
            fh.write(line + "\n")


def cmark(slug: str, phase: str) -> None:
    print(f"CASE {slug} {phase}", flush=True)


def run(cmd: list[str], timeout: int, capture: bool = True,
        stdin: str | None = None) -> subprocess.CompletedProcess:
    try:
        return subprocess.run(cmd, timeout=timeout, capture_output=capture,
                              text=True, input=stdin)
    except (subprocess.TimeoutExpired, OSError) as exc:
        return subprocess.CompletedProcess(cmd, 124,
                                           stdout="", stderr=f"timeout/error: {exc}")


def logline(path: Path, line: str) -> None:
    with open(path, "a", encoding="utf-8") as fh:
        fh.write(line.rstrip("\n") + "\n")


def git_sha() -> str:
    cp = run(["git", "rev-parse", "--short", "HEAD"], 15)
    return cp.stdout.strip() if cp.returncode == 0 else ""


def quantity_milli_cpu(q: str) -> int:
    """Kubernetes CPU quantity -> millicores."""
    s = str(q).strip()
    return int(float(s[:-1])) if s.endswith("m") else int(float(s) * 1000)


def quantity_mib(q: str) -> int:
    """Kubernetes memory quantity -> MiB (best-effort)."""
    s = str(q).strip()
    if s.endswith("Mi"):
        return int(float(s[:-2]))
    if s.endswith("Gi"):
        return int(float(s[:-2]) * 1024)
    if s.endswith("Ki"):
        return int(float(s[:-2]) / 1024)
    return int(float(s) / 1024 / 1024)


def scale_cpu(q: str, mult: int) -> str:
    return f"{quantity_milli_cpu(q) * max(1, mult)}m"


def scale_mem(q: str, mult: int) -> str:
    return f"{quantity_mib(q) * max(1, mult)}Mi"


# ------------------------------------------------------- run configuration


@dataclasses.dataclass
class Config:
    """Resolved operator inputs (populated by the Typer entrypoint)."""
    run_tag: str = ""
    node: str = ""
    namespace: str = "default"
    benchmarks: str = "hpl,hpl-mxp"
    tiers: str = "plain,coco"
    gpu_config: str = "single"
    repeats: int = 1
    pod_cpu: str = "8"          # per MPI process; scaled by GPU count for the pod
    pod_mem: str = "32768Mi"    # per MPI process
    workload_image: str = DEFAULT_IMAGE
    results_root: str = "./results"
    gpu_model_allowlist: str = ""
    memory_fill: float = 0.8
    hpl_n: int = 0
    hpl_nb: int = 0
    hpl_p: int = 0
    hpl_q: int = 0
    expect_gpu_count: int = 0
    exec_timeout: int = 14400
    pod_wait: int = 1800
    image_pull_secret: str = ""
    cleanup_only: str = ""
    dry_run: bool = False
    yes: bool = False


class OC:
    """All oc/helm invocations funnel here so timeouts apply uniformly."""

    def oc(self, *args: str, timeout: int = 120) -> subprocess.CompletedProcess:
        return run(["oc", *args], timeout)

    def helm(self, *args: str, timeout: int = 120) -> subprocess.CompletedProcess:
        return run(["helm", *args], timeout)


# ---------------------------------------------------------------- preflight


def model_allows(label: str, extra: list[str]) -> bool:
    normalized = label.upper().replace("_", "-")
    tokens = [t.upper().replace("_", "-") for t in CC_CAPABLE_MODELS + extra if t]
    return any(t in normalized for t in tokens)


def preflight(a: Config, oc: OC, catalog: dict, tiers: list[str],
              gpu_config: str) -> tuple[bool, dict]:
    """Returns (fatal, node_facts). Emits fixed-format PREFLIGHT lines (FR-010)."""
    fatal = False
    facts: dict = {}

    if shutil.which("oc") is None:
        say("FAIL", "tooling", "oc not on PATH")
        return True, facts
    if shutil.which("helm") is None:
        say("FAIL", "tooling", "helm not on PATH")
        return True, facts
    say("OK", "tooling", "oc + helm present; Python deps imported statically "
        "(declared+pinned in tools/pyproject.toml)")

    cp = oc.oc("cluster-info", timeout=30)
    if cp.returncode == 0:
        say("OK", "cluster", "API reachable")
    else:
        say("FAIL", "cluster", (cp.stderr or "").strip()[:160] or "unreachable")
        fatal = True

    cp = oc.oc("get", "node", a.node, "-o", "json", timeout=60)
    if cp.returncode != 0:
        say("FAIL", "node", f"node {a.node!r} not found")
        return True, facts
    node = json.loads(cp.stdout)
    labels = node.get("metadata", {}).get("labels", {})

    # GFD labels present? (research R3)
    missing = [lbl for lbl in (LABEL_PRODUCT, LABEL_COUNT, LABEL_MEM)
               if lbl not in labels]
    if missing:
        say("FAIL", "gfd-labels",
            f"missing {missing} on {a.node}; install NFD + NVIDIA GPU Operator "
            "(GPU Feature Discovery) — preflight refuses to guess")
        return True, facts

    product = str(labels[LABEL_PRODUCT])
    facts["gpu_model"] = product
    try:
        gpu_count = int(labels[LABEL_COUNT])
    except ValueError:
        say("FAIL", "gfd-labels", f"{LABEL_COUNT}={labels[LABEL_COUNT]!r} not an integer")
        return True, facts
    try:
        gpu_mem_mib = int(labels[LABEL_MEM])
    except ValueError:
        say("FAIL", "gfd-labels", f"{LABEL_MEM}={labels[LABEL_MEM]!r} not an integer")
        return True, facts
    facts["gpu_count"] = gpu_count
    facts["gpu_mem_mib"] = gpu_mem_mib
    nvlink = str(labels.get(LABEL_NVLINK, "")).lower() == "true"
    facts["nvlink"] = nvlink

    # FR-002: H100-or-newer gate.
    extra_models = [m.strip() for m in a.gpu_model_allowlist.split(",") if m.strip()]
    if model_allows(product, extra_models):
        say("OK", "gpu-model",
            f"{product} is H100-or-newer (confidential-GPU capable, FR-002)")
    else:
        say("FAIL", "gpu-model",
            f"{product} is not H100-or-newer — only confidential-GPU-capable "
            f"models are supported (FR-002); allowlist: "
            f"{CC_CAPABLE_MODELS + extra_models}")
        fatal = True

    say("OK", "gpu-count", f"{gpu_count} GPU(s), {gpu_mem_mib} MiB each on {a.node}")

    # Full-system gates (US2 scenarios 2-3).
    if gpu_config == "full":
        if not nvlink:
            say("FAIL", "nvlink",
                f"full-system cases require NVLink ({LABEL_NVLINK}!=true on "
                f"{a.node}); run single-GPU cases or use an NVLink node")
            fatal = True
        else:
            say("OK", "nvlink", f"{LABEL_NVLINK}=true on {a.node}")
        if a.expect_gpu_count and a.expect_gpu_count != gpu_count:
            say("FAIL", "gpu-count-expectation",
                f"--expect-gpu-count={a.expect_gpu_count} but node has "
                f"{gpu_count}; refusing to silently benchmark a subset (US2)")
            fatal = True
        elif a.expect_gpu_count:
            say("OK", "gpu-count-expectation",
                f"node GPU count {gpu_count} matches --expect-gpu-count")

    # Runtime classes for selected tiers.
    for tier in tiers:
        rc = TIER_RUNTIME[tier]
        if not rc:
            continue
        cp = oc.oc("get", "runtimeclass", rc, timeout=30)
        if cp.returncode == 0:
            say("OK", "runtimeclass", f"{rc} present (tier {tier})")
        else:
            say("FAIL", "runtimeclass",
                f"{rc} missing (needed by tier {tier}); the OpenShift sandboxed "
                "containers operator creates it when GPU Operator CC support "
                "is installed")
            fatal = True

    # Device-plugin GPU resource detection (research R2).
    alloc = node.get("status", {}).get("allocatable", {})
    resource = ""
    if "nvidia.com/gpu" in alloc:
        resource = "nvidia.com/gpu"
    elif "nvidia.com/pgpu" in alloc:
        resource = "nvidia.com/pgpu"
    if not resource:
        say("FAIL", "gpu-resource",
            "node serves neither nvidia.com/gpu nor nvidia.com/pgpu; the GPU "
            "device plugin must be running (NVIDIA GPU Operator)")
        fatal = True
    else:
        try:
            available = int(alloc[resource])
        except ValueError:
            available = 0
        needed = gpu_count if gpu_config == "full" else 1
        facts["gpu_resource"] = resource
        if available < needed:
            say("FAIL", "gpu-resource",
                f"{resource} allocatable={available} < needed={needed}; GPUs "
                "are held by other pods — free them (the harness never "
                "cordons/evicts, FR-009)")
            fatal = True
        else:
            say("OK", "gpu-resource", f"{resource} allocatable={available} >= needed={needed}")

    # Tenant census (warn-only, FR-009).
    cp = oc.oc("get", "pods", "-A", "--field-selector",
               f"spec.nodeName={a.node}", "-o", "json", timeout=60)
    tenant_lines: list[str] = []
    if cp.returncode == 0:
        pods = json.loads(cp.stdout).get("items", [])
        tenants = [f"{p['metadata']['namespace']}/{p['metadata']['name']}"
                   for p in pods
                   if not p['metadata']['namespace'].startswith(("openshift", "kube", "default"))]
        if tenants:
            say("WARN", "tenant-census",
                f"{len(tenants)} non-system pods on node (results may be "
                f"contaminated): {', '.join(tenants[:10])}")
            tenant_lines = tenants
        else:
            say("OK", "tenant-census", "no non-system pods on node")
    else:
        say("WARN", "tenant-census", "could not enumerate node pods")
    facts["tenant_warns"] = tenant_lines

    # Results root + image (FR-010: image availability gate).
    root = Path(a.results_root)
    try:
        root.mkdir(parents=True, exist_ok=True)
        probe = root / ".preflight-write-probe"
        probe.write_text("ok")
        probe.unlink()
        say("OK", "results-root", f"{root} writable")
    except OSError as exc:
        say("FAIL", "results-root", f"{root} not writable: {exc}")
        fatal = True
    ref = a.workload_image
    # A reference is pinned when it carries a non-latest tag or a digest, and
    # malformed when it lacks a registry/repository separator.
    pinned = bool(re.search(r"@sha256:[0-9a-f]{64}$", ref) or
                  re.search(r":[^:@/]+$", ref)) and "/" in ref
    if not pinned or ref.endswith(":latest"):
        say("FAIL", "image-reference",
            f"{ref!r} is malformed or unpinned; supply a full reference with a "
            "version tag or sha256 digest (override mirrors via --workload-image, FR-017)")
        fatal = True
    else:
        say("OK", "image-reference", f"{ref} is a pinned reference")
        # Best-effort reachability probe (warn-only: registry auth and offline
        # control machines are legitimate; hard failures still surface at pod
        # wait as env-failed with pod logs).
        skopeo = shutil.which("skopeo")
        if skopeo:
            cp = run([skopeo, "inspect", f"docker://{ref}"], 60)
            if cp.returncode == 0:
                say("OK", "image-availability", f"{ref} reachable via skopeo")
            else:
                say("WARN", "image-availability",
                    f"skopeo could not inspect {ref} (registry auth or offline?): "
                    f"{(cp.stderr or '').strip()[:120]}; proceeding — pull failures "
                    "surface at pod wait; override with --workload-image")
        else:
            say("WARN", "image-availability",
                "skopeo not on PATH; skipping reachability probe — pull failures "
                "surface at pod wait with logs; override with --workload-image")
    return fatal, facts


# ---------------------------------------------------------------- iceberg

IBG_FIELDS = {
    "metadata": [
        ("run_id", "string"), ("run_tag", "string"), ("utc_start", "timestamptz"),
        ("utc_end", "timestamptz"), ("node", "string"), ("gpu_model", "string"),
        ("gpu_count_total", "long"), ("gpu_config", "string"),
        ("nvlink_present", "boolean"), ("namespace", "string"),
        ("pod_cpu_per_proc", "string"), ("pod_mem_per_proc", "string"),
        ("repeats", "long"), ("tiers", "string"), ("benchmarks_requested", "string"),
        ("cases_completed", "string"), ("images_workload", "string"),
        ("params_json", "string"), ("tool_version", "string"), ("repo_git_sha", "string"),
    ],
    "case_iterations": [
        ("run_id", "string"), ("case", "string"), ("benchmark", "string"),
        ("tier", "string"), ("runtime_class", "string"), ("gpu_config", "string"),
        ("gpu_count", "long"), ("pod_name", "string"),
        ("utc_start", "timestamptz"), ("utc_end", "timestamptz"),
        ("status", "string"), ("failed_stage", "string"),
        ("metric_gflops", "double"), ("verified", "boolean"),
    ],
    "datapoints": [
        ("run_id", "string"), ("case", "string"), ("benchmark", "string"),
        ("precision", "string"), ("tier", "string"), ("gpu_config", "string"),
        ("gpu_count", "long"), ("repeat_idx", "long"), ("metric_gflops", "double"),
        ("verified", "boolean"), ("status", "string"),
        ("assigned_devices", "string"), ("duration_s", "double"),
        ("collected_at", "timestamptz"),
    ],
    "case_aggregates": [
        ("run_id", "string"), ("case", "string"), ("benchmark", "string"),
        ("tier", "string"), ("gpu_config", "string"), ("n_repeats", "long"),
        ("gflops_min", "double"), ("gflops_max", "double"),
        ("gflops_mean", "double"), ("gflops_stddev", "double"),
        ("spread_rel_gflops", "double"), ("status", "string"),
    ],
}


def iceberg_open(warehouse: Path):
    import pyarrow as pa  # noqa: F401  (import check mirroring io-bench)
    from pyiceberg import catalog, exceptions

    warehouse.mkdir(parents=True, exist_ok=True)
    cat = catalog.load_catalog("runs", **{
        "type": "sql",
        "uri": f"sqlite:///file:{warehouse / 'catalog.db'}?uri=true&busy_timeout=5000",
        "warehouse": f"file://{warehouse}",
    })
    try:
        cat.create_namespace("runs")
    except exceptions.NamespaceAlreadyExistsError:
        pass
    return cat


def iceberg_table(cat, name: str):
    from pyiceberg import exceptions, schema, types

    full = f"runs.{name}"
    iceberg_types = {
        "string": types.StringType(), "long": types.LongType(),
        "double": types.DoubleType(), "boolean": types.BooleanType(),
        "timestamptz": types.TimestamptzType(),
    }
    try:
        return cat.load_table(full)
    except exceptions.NoSuchTableError:
        sch = schema.Schema(*[
            types.NestedField(i + 1, fname, iceberg_types[ftype], required=False)
            for i, (fname, ftype) in enumerate(IBG_FIELDS[name])
        ])
        return cat.create_table(identifier=full, schema=sch)


def iceberg_append(cat, name: str, rows: list[dict], attempts: int = 5) -> None:
    import pyarrow as pa

    if not rows:
        return
    tbl = iceberg_table(cat, name)
    pa_types = {"string": pa.string(), "long": pa.int64(), "double": pa.float64(),
                "boolean": pa.bool_(), "timestamptz": pa.timestamp("us", tz="UTC")}
    sch = pa.schema([(f, pa_types[t]) for f, t in IBG_FIELDS[name]])
    data = {f: [r.get(f) for r in rows] for f, _ in IBG_FIELDS[name]}
    for f, ftype in IBG_FIELDS[name]:
        if ftype == "timestamptz":
            vals = []
            for v in data[f]:
                if isinstance(v, dt.datetime):
                    vals.append(v.astimezone(dt.timezone.utc))
                elif v is not None:
                    vals.append(dt.datetime.fromisoformat(v).astimezone(dt.timezone.utc))
                else:
                    vals.append(None)
            data[f] = vals
    arrow = pa.table(data, schema=sch)
    last_exc: Exception | None = None
    for attempt in range(1, attempts + 1):
        try:
            tbl.append(arrow)
            return
        except Exception as exc:  # lock contention on the shared SQLite catalog
            last_exc = exc
            time.sleep(min(0.5 * attempt + random.uniform(0, 0.3), 3.0))
    raise RuntimeError(f"iceberg append to runs.{name} failed after {attempts} attempts: {last_exc}")


# -------------------------------------------------------------- aggregation


def aggregate(points: list[dict]) -> list[dict]:
    groups: dict[tuple, list[dict]] = {}
    for p in points:
        groups.setdefault((p["case"], p["tier"]), []).append(p)
    out = []
    for (case, tier), pts in sorted(groups.items()):
        ok = [p for p in pts if p["status"] == "verified" and p["metric_gflops"] is not None]
        vals = [p["metric_gflops"] for p in ok]
        if vals:
            mn, mx, mean = min(vals), max(vals), statistics.fmean(vals)
            sd = statistics.pstdev(vals) if len(vals) > 1 else 0.0
            spread = (mx - mn) / mean if mean > 0 else 0.0
        else:
            mn = mx = mean = sd = spread = 0.0
        out.append({
            "run_id": pts[0]["run_id"], "case": case, "benchmark": pts[0]["benchmark"],
            "tier": tier, "gpu_config": pts[0]["gpu_config"],
            "n_repeats": len(ok),
            "gflops_min": mn, "gflops_max": mx, "gflops_mean": mean,
            "gflops_stddev": sd, "spread_rel_gflops": spread,
            "status": "verified" if len(ok) == len(pts) else
                      ("no-verified" if not ok else "partial"),
        })
    return out


def delta_rows(aggs: list[dict]) -> list[dict]:
    """Confidential-vs-standard pairs per (benchmark, gpu_config); only from
    verified aggregates (FR-007/SC-003 — gaps never masquerade as numbers)."""
    rows = []
    keys = sorted({(a["benchmark"], a["gpu_config"]) for a in aggs})
    for benchmark, gpu_config in keys:
        pair = {a["tier"]: a for a in aggs
                if a["benchmark"] == benchmark and a["gpu_config"] == gpu_config}
        plain, coco = pair.get("plain"), pair.get("coco")
        row = {"benchmark": benchmark, "gpu_config": gpu_config,
               "plain_gflops": None, "coco_gflops": None, "delta": None,
               "pair_status": "incomplete"}
        if plain and plain["n_repeats"] and plain["gflops_mean"] > 0:
            row["plain_gflops"] = plain["gflops_mean"]
        if coco and coco["n_repeats"] and coco["gflops_mean"] > 0:
            row["coco_gflops"] = coco["gflops_mean"]
        if row["plain_gflops"] and row["coco_gflops"]:
            row["delta"] = (row["coco_gflops"] - row["plain_gflops"]) / row["plain_gflops"]
            row["pair_status"] = "verified-pair"
        rows.append(row)
    return rows


# ------------------------------------------------------------------ summary


def render_markdown(meta: dict, aggs: list[dict], cases_status: dict,
                    deltas: list[dict], tenant_lines: list[str]) -> str:
    lines = ["# GPU Benchmark Summary", ""]
    lines += ["| key | value |", "|---|---|"]
    for k in ("run_id", "node", "gpu_model", "gpu_count_total", "gpu_config",
              "nvlink_present", "namespace", "pod_cpu_per_proc", "pod_mem_per_proc",
              "repeats", "tiers", "images_workload", "params_json", "tool_version"):
        lines.append(f"| {k} | {meta.get(k, '')} |")
    if tenant_lines:
        lines.append(f"| tenant-census (warn-only) | {'; '.join(tenant_lines)} |")

    lines += ["", "## Per-case results (verified iterations only, FR-007)", "",
              "| case | benchmark | tier | gpus | Gflops mean | spread | verified n | status |",
              "|---|---|---|---|---|---|---|---|"]
    for slug in sorted(cases_status):
        rows = [x for x in aggs if x["case"] == slug]
        if rows:
            for x in rows:
                mean = f"{x['gflops_mean']:.1f}" if x["n_repeats"] else "—"
                lines.append(
                    f"| {slug} | {x['benchmark']} | {x['tier']} | "
                    f"{x['gpu_config']} | {mean} | {x['spread_rel_gflops']:.2%} | "
                    f"{x['n_repeats']} | {x['status']} |")
        else:
            lines.append(f"| {slug} | — | — | — | — | — | 0 | {cases_status[slug]} |")

    lines += ["", "## Confidential vs standard (per benchmark; fp64 and mixed are "
              "never compared to each other)", "",
              "| benchmark | gpu config | plain Gflops | confidential Gflops | delta | pair status |",
              "|---|---|---|---|---|---|"]
    for d in deltas:
        plain = f"{d['plain_gflops']:.1f}" if d["plain_gflops"] else "— (no verified run)"
        coco = f"{d['coco_gflops']:.1f}" if d["coco_gflops"] else "— (no verified run)"
        delta = f"{d['delta']:+.2%}" if d["delta"] is not None else "—"
        lines.append(f"| {d['benchmark']} | {d['gpu_config']} | {plain} | {coco} | "
                     f"{delta} | {d['pair_status']} |")
    lines += ["", "Deltas are measured outcomes, not promises (spec assumption). "
              "Read docs/sizing-guidance.md before quoting.", ""]

    lines += ["## Case artifacts (raw logs — FR-008)", "",
              "| case | values | manifest | case log | pod log | repeats dir |",
              "|---|---|---|---|---|---|"]
    for slug in sorted(cases_status):
        lines.append(
            f"| {slug} | [`values-{slug}.yaml`](values-{slug}.yaml) | "
            f"[`manifest-{slug}.yaml`](manifest-{slug}.yaml) | "
            f"[`exec-{slug}.log`](exec-{slug}.log) | "
            f"[`LOGS/case-pod-{slug}.log`](LOGS/case-pod-{slug}.log) | "
            f"[{slug}/]({slug}/) |")
    return "\n".join(lines) + "\n"


# ------------------------------------------------------------------ cleanup


def resource_name(a: Config, slug: str) -> str:
    return f"gpu-bench-{a.run_tag[:20]}-{slug}".lower()


def cleanup_resources(a: Config, slug: str | None) -> bool:
    rc_ok = True
    for kind in ("pod", "configmap"):
        if slug:
            args = ["delete", kind, "-n", a.namespace, "-l",
                    f"gpu-benchmark/case={slug},gpu-benchmark/run-tag={a.run_tag}",
                    "--ignore-not-found", "--wait=true", "--timeout=600s"]
        else:
            args = ["delete", kind, "-n", a.namespace, "-l",
                    f"gpu-benchmark/run-tag={a.run_tag}",
                    "--ignore-not-found", "--wait=true", "--timeout=600s"]
        cp = run(["oc", *args], 660)
        if cp.returncode != 0:
            print(f"cleanup {kind} WARN: {cp.stderr.strip()[:160]}")
            rc_ok = False
    return rc_ok


def cleanup_only(a: Config) -> int:
    print(f"cleanup run-tag={a.cleanup_only}")
    a.run_tag = a.cleanup_only
    ok = cleanup_resources(a, None)
    return EXIT_OK if ok else EXIT_CLEANUP_FAILED


# -------------------------------------------------------------------- case


def parse_devices(nvidia_smi_csv: str) -> list[str]:
    devices = []
    for line in nvidia_smi_csv.splitlines()[1:]:
        parts = [p.strip() for p in line.split(",")]
        if len(parts) >= 3:
            devices.append(f"{parts[0]}:{parts[1]}:{parts[2]}")
    return devices


def run_case(a: Config, oc: OC, run_dir: Path, slug: str, definition: dict,
             tier: str, params: dict, command: str, gpu_resource: str,
             cat, all_points: list[dict]) -> tuple[str, str]:
    """One serial case. Returns (status, failed_stage) where status is
    verified | invalid | env-failed (data-model case state machine)."""
    benchmark = definition["id"]
    gpu_count = params["gpu_count"]
    status, failed = "env-failed", ""
    case_dir = run_dir / slug
    case_dir.mkdir(parents=True, exist_ok=True)
    case_log = run_dir / f"exec-{slug}.log"
    name = resource_name(a, slug)

    def note(line: str) -> None:
        logline(case_log, line)

    note(f"BEGIN {ts()} benchmark={benchmark} tier={tier} gpus={gpu_count} "
         f"params={json.dumps(params)}")

    values = {
        "case": {"slug": slug, "runtimeClassName": TIER_RUNTIME[tier],
                 "gpuResource": gpu_resource, "gpuCount": gpu_count},
        "node": {"name": a.node},
        "pod": {"cpu": scale_cpu(a.pod_cpu, gpu_count),
                "mem": scale_mem(a.pod_mem, gpu_count)},
        "benchmark": {"id": benchmark, "command": command,
                      "paramsJson": json.dumps(params, sort_keys=True)},
        "images": {"workload": a.workload_image},
        "namespace": a.namespace,
        "runTag": a.run_tag,
        "coco": {"skipInitdata": True},
    }
    if a.image_pull_secret:
        values["imagePullSecrets"] = [{"name": a.image_pull_secret}]
    values_file = run_dir / f"values-{slug}.yaml"
    values_file.write_text(yaml.safe_dump(values, sort_keys=False), encoding="utf-8")

    cp = oc.helm("template", "gpu", str(CHART_DIR), "-f", str(values_file))
    if cp.returncode != 0:
        note(f"helm template failed: {cp.stderr.strip()[:400]}")
        cmark(slug, "render FAILED")
        return "env-failed", "render"
    manifest = run_dir / f"manifest-{slug}.yaml"
    manifest.write_text(cp.stdout, encoding="utf-8")

    cp = run(["oc", "apply", "-f", str(manifest)], 120)
    if cp.returncode != 0:
        note(f"oc apply failed: {cp.stderr.strip()[:400]}")
        cleanup_resources(a, slug)
        cmark(slug, "apply FAILED")
        return "env-failed", "apply"
    cmark(slug, "applied")
    note("applied")

    cp = oc.oc("wait", "--for=condition=Ready", "pod", name, "-n", a.namespace,
               f"--timeout={a.pod_wait}s", timeout=a.pod_wait + 30)
    if cp.returncode != 0:
        note(f"pod wait failed: {cp.stderr.strip()[:400]}")
        plog = run(["oc", "logs", name, "-n", a.namespace, "--all-containers"], 60)
        note(f"pod-logs: {(plog.stdout or plog.stderr).strip()[:800]}")
        cleanup_resources(a, slug)
        cmark(slug, "pod FAILED (environment — not a benchmark result)")
        return "env-failed", "pod"
    cmark(slug, "READY")
    note("READY")

    logs_dir = run_dir / "LOGS"
    logs_dir.mkdir(parents=True, exist_ok=True)
    cpl = run(["oc", "logs", name, "-n", a.namespace, "--all-containers"], 60)
    (logs_dir / f"case-pod-{slug}.log").write_text(cpl.stdout or cpl.stderr,
                                                   encoding="utf-8")

    # Assigned-device evidence (FR-005 / research R10).
    cp = run(["oc", "exec", name, "-n", a.namespace, "-c", "benchmark", "--",
              "nvidia-smi", "--query-gpu=index,name,uuid,memory.total",
              "--format=csv"], 120)
    devices: list[str] = []
    if cp.returncode == 0 and cp.stdout.strip():
        (case_dir / "devices.txt").write_text(cp.stdout, encoding="utf-8")
        devices = parse_devices(cp.stdout)
        note(f"devices: {devices}")
    else:
        note(f"nvidia-smi evidence failed: {(cp.stderr or '').strip()[:200]}")

    # Case state machine (data-model): a repeat that never executed is an
    # ENV failure, distinct from a repeat that ran and failed verification
    # (FR-007 invalid). Priority after the loop: any verified repeat makes
    # the case verified; otherwise any env failure makes it env-failed;
    # only repeats that all ran-but-did-not-verify leave it invalid.
    saw_verified = False
    saw_env_failed = False
    env_failed_stage = ""
    status, failed = "invalid", "no-iterations"
    for rep in range(1, a.repeats + 1):
        rdir = case_dir / f"rep{rep}"
        rdir.mkdir(exist_ok=True)
        cmark(slug, f"bench rep{rep}/{a.repeats}")
        started = time.monotonic()
        cp = run(["oc", "exec", name, "-n", a.namespace, "-c", "benchmark", "--",
                  "sh", "-c",
                  f"export OMPI_ALLOW_RUN_AS_ROOT=1 OMPI_ALLOW_RUN_AS_ROOT_CONFIRM=1; "
                  f"{command} > /tmp/bench-rep{rep}.out 2>&1"], a.exec_timeout)
        duration = time.monotonic() - started
        if cp.returncode != 0:
            note(f"bench rep{rep} rc={cp.returncode}: {cp.stderr.strip()[:300]}")
            cmark(slug, f"bench rep{rep} EXEC-FAILED (environment — not a benchmark result)")
            saw_env_failed = True
            env_failed_stage = env_failed_stage or "bench-exec"
            continue
        cp2 = run(["oc", "exec", name, "-n", a.namespace, "-c", "benchmark", "--",
                   "cat", f"/tmp/bench-rep{rep}.out"], 300)
        if cp2.returncode != 0 or not cp2.stdout.strip():
            note(f"bench rep{rep} output read-back failed")
            saw_env_failed = True
            env_failed_stage = env_failed_stage or "bench-output-readback"
            continue
        out_path = rdir / "bench-output.txt"
        out_path.write_text(cp2.stdout, encoding="utf-8")
        metric, verdict = parse_output(definition, cp2.stdout)
        pass_value = str(definition["parser"]["verification"]["pass_value"]).upper()
        if metric is not None and verdict == pass_value:
            rep_status = "verified"
        elif metric is not None:
            rep_status = "invalid"  # ran, residual check did not pass (FR-007)
            note(f"bench rep{rep} verification verdict={verdict!r} "
                 f"(needs {pass_value!r}) — excluded from performance results")
        else:
            rep_status = "invalid"
            note(f"bench rep{rep} no metric parsed from output")
        point = {
            "run_id": a.run_tag, "case": slug, "benchmark": benchmark,
            "precision": definition["precision"], "tier": tier,
            "gpu_config": params["gpu_config"], "gpu_count": gpu_count,
            "repeat_idx": rep, "metric_gflops": metric,
            "verified": rep_status == "verified", "status": rep_status,
            "assigned_devices": ";".join(devices), "duration_s": round(duration, 3),
            "collected_at": utcnow(),
        }
        all_points.append(point)
        iceberg_append(cat, "datapoints", [point])
        if rep_status == "verified":
            saw_verified = True
        status, failed = rep_status, ""

    if saw_verified:
        status, failed = "verified", ""
    elif saw_env_failed:
        status, failed = "env-failed", env_failed_stage

    cmark(slug, f"DONE status={status}")
    note(f"DONE {ts()} status={status}")

    run(["oc", "delete", "-f", str(manifest), "--wait=true", "--timeout=600s"], 660)
    ok = cleanup_resources(a, slug)
    if not ok:
        print(f"CASE {slug} CLEANUP-WARN: remnants may remain; "
              f"run --cleanup-only {a.run_tag}")
    return status, failed


# -------------------------------------------------------------------- main


def _usage_error(msg: str):
    print(f"usage error: {msg}", file=sys.stderr)
    raise typer.Exit(code=EXIT_USAGE)


def main(
    run_tag: Annotated[str, typer.Option("--run-tag", help="Run identity; defaults to a UTC timestamp.")] = "",
    node: Annotated[str, typer.Option("--node", help="Nominated node (required unless --cleanup-only).")] = "",
    namespace: Annotated[str, typer.Option("--namespace")] = "default",
    benchmarks: Annotated[str, typer.Option("--benchmarks", help="Comma-separated catalog ids (benchmarks/*.yaml).")] = "hpl,hpl-mxp",
    tiers: Annotated[str, typer.Option("--tiers", help="plain,coco default; kata where the cluster serves it.")] = "plain,coco",
    gpu_config: Annotated[str, typer.Option("--gpu-config", help="single or full (all node GPUs over NVLink).")] = "single",
    repeats: Annotated[int, typer.Option("--repeats")] = 1,
    pod_cpu: Annotated[str, typer.Option("--pod-cpu", help="CPU per MPI process (pod request scaled by GPU count).")] = "8",
    pod_mem: Annotated[str, typer.Option("--pod-mem", help="Memory per MPI process.")] = "32768Mi",
    workload_image: Annotated[str, typer.Option("--workload-image", help="Full immutable reference override (FR-017).")] = DEFAULT_IMAGE,
    results_root: Annotated[str, typer.Option("--results-root")] = "./results",
    gpu_model_allowlist: Annotated[str, typer.Option("--gpu-model-allowlist", help="Extra CC-capable model tokens to accept (FR-002 stays H100-or-newer).")] = "",
    memory_fill: Annotated[float, typer.Option("--memory-fill", help="Fraction of aggregate GPU memory the problem fills.")] = 0.8,
    hpl_n: Annotated[int, typer.Option("--hpl-n", help="Problem-size override (all tiers alike, FR-004).")] = 0,
    hpl_nb: Annotated[int, typer.Option("--hpl-nb", help="Block-size override.")] = 0,
    hpl_p: Annotated[int, typer.Option("--hpl-p", help="Process-grid rows override (P*Q must equal GPU count).")] = 0,
    hpl_q: Annotated[int, typer.Option("--hpl-q", help="Process-grid columns override.")] = 0,
    expect_gpu_count: Annotated[int, typer.Option("--expect-gpu-count", help="Full-system: fail if node GPU count differs (US2).")] = 0,
    exec_timeout: Annotated[int, typer.Option("--exec-timeout", help="Seconds per benchmark repeat (full-fill HPL runs are hours).")] = 14400,
    pod_wait: Annotated[int, typer.Option("--pod-wait", help="Seconds to wait for pod Ready (image pull + kata VM boot).")] = 1800,
    image_pull_secret: Annotated[str, typer.Option("--image-pull-secret")] = "",
    cleanup_only: Annotated[str, typer.Option("--cleanup-only", help="Delete leftovers for RUN_TAG and exit.")] = "",
    dry_run: Annotated[bool, typer.Option("--dry-run", help="Preflight + parameter preview; nothing provisioned.")] = False,
    yes: Annotated[bool, typer.Option("--yes", help="Skip the interactive provisioning confirmation.")] = False,
) -> None:
    """gpu-benchmark serial case runner (spec 005-gpu-confidential-benchmark FR-015)."""
    a = Config(run_tag=run_tag, node=node, namespace=namespace, benchmarks=benchmarks,
               tiers=tiers, gpu_config=gpu_config, repeats=repeats, pod_cpu=pod_cpu,
               pod_mem=pod_mem, workload_image=workload_image, results_root=results_root,
               gpu_model_allowlist=gpu_model_allowlist, memory_fill=memory_fill,
               hpl_n=hpl_n, hpl_nb=hpl_nb, hpl_p=hpl_p, hpl_q=hpl_q,
               expect_gpu_count=expect_gpu_count, exec_timeout=exec_timeout,
               pod_wait=pod_wait, image_pull_secret=image_pull_secret,
               cleanup_only=cleanup_only, dry_run=dry_run, yes=yes)
    if a.cleanup_only:
        raise typer.Exit(code=cleanup_only(a))
    if not a.node:
        _usage_error("--node is required (or use --cleanup-only RUN_TAG)")
    if a.gpu_config not in ("single", "full"):
        _usage_error("--gpu-config must be single|full")
    if a.repeats < 1:
        _usage_error("--repeats must be >= 1")
    if not 0.0 < a.memory_fill <= 1.0:
        _usage_error("--memory-fill must be in (0, 1]")
    if not a.run_tag:
        a.run_tag = utcnow().strftime("%Y%m%dT%H%M%SZ")
    if not re.fullmatch(r"[a-zA-Z0-9.-]{1,40}", a.run_tag):
        _usage_error("--run-tag must match [a-zA-Z0-9.-]{1,40}")

    # Catalog (FR-012): discovery + validation, unknown ids fail with the
    # available catalog listed.
    try:
        catalog = load_catalog()
    except DefinitionValidationError as exc:
        _usage_error(f"catalog invalid: {exc}")
    requested_benchmarks = [b.strip() for b in a.benchmarks.split(",") if b.strip()]
    bad = [b for b in requested_benchmarks if b not in catalog]
    if bad:
        _usage_error(f"unknown benchmark(s): {bad}; catalog: {sorted(catalog)}")
    benchmark_order = [b for b in catalog if b in requested_benchmarks]

    requested_tiers = [t.strip() for t in a.tiers.split(",") if t.strip()]
    bad_tiers = [t for t in requested_tiers if t not in TIER_ORDER]
    if bad_tiers:
        _usage_error(f"unknown tier(s): {bad_tiers}; valid {TIER_ORDER}")
    tier_list = [t for t in TIER_ORDER if t in requested_tiers]

    oc = OC()
    root = Path(a.results_root)
    run_dir = root / a.run_tag
    run_dir.mkdir(parents=True, exist_ok=True)
    global _PREFLIGHT_LOG
    _PREFLIGHT_LOG = run_dir / "preflight.log"

    print(f"run_tag={a.run_tag} benchmarks={benchmark_order} tiers={tier_list} "
          f"gpu_config={a.gpu_config} UTC start {ts()}")
    fatal, facts = preflight(a, oc, catalog, tier_list, a.gpu_config)
    if fatal:
        raise typer.Exit(code=EXIT_PREFLIGHT)

    gpu_count = facts["gpu_count"]
    case_gpu_count = gpu_count if a.gpu_config == "full" else 1

    # Parameters computed ONCE per benchmark for this run and reused verbatim
    # across tiers (FR-004).
    params_by_bench: dict[str, dict] = {}
    commands_by_bench: dict[str, str] = {}
    for bid in benchmark_order:
        try:
            params = compute_params(
                catalog[bid], case_gpu_count, facts["gpu_mem_mib"],
                n=a.hpl_n, nb=a.hpl_nb, p=a.hpl_p, q=a.hpl_q,
                memory_fill=a.memory_fill)
        except ValueError as exc:
            _usage_error(f"benchmark {bid}: {exc}")
        params["gpu_config"] = a.gpu_config
        params_by_bench[bid] = params
        commands_by_bench[bid] = render_command(catalog[bid], params)
        say("OK", "params", f"{bid}: {json.dumps(params, sort_keys=True)}")
        print(f"  {bid} command: {commands_by_bench[bid]}")

    if a.dry_run:
        print("DRY RUN: preflight + parameter preview complete; nothing provisioned.")
        return

    if not a.yes:
        try:
            confirmed = typer.confirm(
                f"About to run {len(benchmark_order) * len(tier_list)} serial "
                f"benchmark cases ({a.repeats} repeat(s) each) on node {a.node} "
                f"({facts['gpu_model']}, {case_gpu_count} GPU(s) per case, "
                f"exec timeout {a.exec_timeout}s). Continue?", default=False)
        except typer.Abort:
            confirmed = False
        if not confirmed:
            print("aborted by operator (use --yes to pre-confirm)", file=sys.stderr)
            raise typer.Exit(code=EXIT_USAGE)

    meta = {
        "run_id": a.run_tag, "run_tag": a.run_tag,
        "utc_start": utcnow(), "utc_end": None,
        "node": a.node, "gpu_model": facts["gpu_model"],
        "gpu_count_total": gpu_count, "gpu_config": a.gpu_config,
        "nvlink_present": facts["nvlink"], "namespace": a.namespace,
        "pod_cpu_per_proc": a.pod_cpu, "pod_mem_per_proc": a.pod_mem,
        "repeats": a.repeats, "tiers": ",".join(tier_list),
        "benchmarks_requested": ",".join(benchmark_order), "cases_completed": "",
        "images_workload": a.workload_image,
        "params_json": json.dumps(params_by_bench, sort_keys=True),
        "tool_version": VERSION, "repo_git_sha": git_sha(),
    }
    (run_dir / "run.env").write_text(
        "\n".join(f"{k.upper()}={v}" for k, v in meta.items() if v is not None) + "\n",
        encoding="utf-8")

    cat = iceberg_open(root / "iceberg-warehouse")

    cases_status: dict[str, str] = {}
    all_points: list[dict] = []

    def on_sig(*_):
        raise KeyboardInterrupt

    signal.signal(signal.SIGINT, on_sig)
    signal.signal(signal.SIGTERM, on_sig)

    case_specs = [(bid, tier) for bid in benchmark_order for tier in tier_list]
    try:
        for bid, tier in case_specs:
            slug = f"{bid}-{tier}-{a.gpu_config}"
            ctime = utcnow()
            cmark(slug, "BEGIN")
            try:
                status, failed = run_case(a, oc, run_dir, slug, catalog[bid], tier,
                                          params_by_bench[bid], commands_by_bench[bid],
                                          facts["gpu_resource"], cat, all_points)
            except Exception as exc:  # per-case isolation
                print(f"CASE {slug} ERROR: {exc.__class__.__name__}: {exc}")
                status, failed = "env-failed", "runner-exception"
            cases_status[slug] = failed or status
            pts = [p for p in all_points if p["case"] == slug]
            metric = next((p["metric_gflops"] for p in reversed(pts)
                           if p["metric_gflops"] is not None), None)
            iceberg_append(cat, "case_iterations", [{
                "run_id": a.run_tag, "case": slug, "benchmark": bid, "tier": tier,
                "runtime_class": TIER_RUNTIME[tier], "gpu_config": a.gpu_config,
                "gpu_count": case_gpu_count, "pod_name": resource_name(a, slug),
                "utc_start": ctime, "utc_end": utcnow(),
                "status": status, "failed_stage": failed,
                "metric_gflops": metric, "verified": status == "verified",
            }])
    except KeyboardInterrupt:
        print("interrupted: running cleanup for in-flight resources", file=sys.stderr)
        cleanup_resources(a, None)
        write_summary(a, run_dir, root, cat, meta, all_points, cases_status, facts)
        raise typer.Exit(code=EXIT_CASE_FAILED)

    raise typer.Exit(code=finalize(a, run_dir, root, cat, meta, all_points,
                                   cases_status, facts))


def write_summary(a: Config, run_dir: Path, root: Path, cat, meta: dict,
                  all_points: list[dict], cases_status: dict, facts: dict) -> None:
    aggs = aggregate(all_points)
    deltas = delta_rows(aggs)
    meta["cases_completed"] = ",".join(k for k, v in cases_status.items()
                                       if v in ("verified", ""))
    iceberg_append(cat, "metadata", [meta])
    iceberg_append(cat, "case_aggregates", aggs)
    md = render_markdown(meta, aggs, cases_status, deltas,
                         facts.get("tenant_warns", []))
    (run_dir / "summary.md").write_text(md, encoding="utf-8")
    print("\n" + md, flush=True)
    (run_dir / "summary-echo.txt").write_text(md, encoding="utf-8")


def finalize(a: Config, run_dir: Path, root: Path, cat, meta: dict,
             all_points: list[dict], cases_status: dict, facts: dict) -> int:
    meta["utc_end"] = utcnow()
    write_summary(a, run_dir, root, cat, meta, all_points, cases_status, facts)
    failed = [k for k, v in cases_status.items() if v not in ("verified", "")]
    print(f"\nDone. Summary: {run_dir / 'summary.md'}")
    print(f"Iceberg warehouse: {root / 'iceberg-warehouse'}")
    if failed:
        print(f"FAILED/invalid cases: {', '.join(failed)}", file=sys.stderr)
        return EXIT_CASE_FAILED
    return EXIT_OK


def cli() -> None:
    """Console-script / __main__ entry: single-command Typer app.

    `python3 bench.py ...` and the installed `gpu-bench` console script land
    here; exit codes are raised via typer.Exit(code=...).
    """
    typer.run(main)


if __name__ == "__main__":
    cli()
