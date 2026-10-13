#!/usr/bin/env python3
"""io-benchmark serial case runner.

Explicitly-approved control-side tool (spec FR-018, constitution v2.0.0 II):
preflight -> serial per-case lifecycle (Helm render/apply/wait/remove) ->
per-repeat in-pod fio via bounded `oc exec` -> log collection -> fio JSON
parsing -> Markdown summary + Apache Iceberg appends.

Runs ONLY on the operator's control machine; nothing here executes in-cluster.
See specs/004-benchmark-harness/contracts/operator-surface.md for the CLI and
"io-benchmark/docs/benchmark-selection.md" for why fio owns every benchmark.
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import re
import shlex
import shutil
import signal
import statistics
import subprocess
import sys
from pathlib import Path

VERSION = "0.1.0"
CASE_ORDER = ["plain", "plain-luks", "kata", "kata-luks", "coco", "coco-luks"]
CASE_RUNTIME = {"plain": "", "plain-luks": "", "kata": "kata", "kata-luks": "kata",
                "coco": "kata-cc", "coco-luks": "kata-cc"}
CASE_ENCRYPTED = {"plain": False, "plain-luks": True, "kata": False,
                  "kata-luks": True, "coco": False, "coco-luks": True}
EXIT_OK, EXIT_PREFLIGHT, EXIT_CASE_FAILED, EXIT_USAGE, EXIT_CLEANUP_FAILED = 0, 1, 2, 3, 4
CHART_DIR = Path(__file__).resolve().parent.parent
RESULT_SIZE_MARGIN = 1.1  # FR-005 sizing rule multiplier

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


def run(cmd: list[str], timeout: int, capture: bool = True, stdin: str | None = None) -> subprocess.CompletedProcess:
    try:
        return subprocess.run(cmd, timeout=timeout, capture_output=capture,
                              text=True, input=stdin)
    except (subprocess.TimeoutExpired, OSError) as exc:
        return subprocess.CompletedProcess(cmd, 124,
                                           stdout="", stderr=f"timeout/error: {exc}")


def quantity_gib(q: str) -> float:
    """Kubernetes quantity -> GiB (best-effort for Gi/G/Ti/T/Mi + plain numbers)."""
    m = re.fullmatch(r"([0-9.]+)(Gi|G|Ti|T|Mi|M)?", str(q).strip())
    if not m:
        raise ValueError(f"cannot parse quantity: {q!r}")
    val, unit = float(m.group(1)), m.group(2) or "Gi"
    factor = {"Gi": 1.0, "G": 1000 / 1024, "Ti": 1024.0,
              "Mi": 1 / 1024}.get(unit)
    if factor is None:
        raise ValueError(f"unsupported unit in quantity: {q!r}")
    return val * factor


def fmt_path(p: Path) -> str:
    return str(p)


# ------------------------------------------------------------- CLI parsing

def parse_args(argv: list[str]) -> argparse.Namespace:
    p = argparse.ArgumentParser(prog="bench.py", description=__doc__.splitlines()[0])
    p.add_argument("--run-tag", default="")
    p.add_argument("--node")
    p.add_argument("--storage-class", dest="sc")
    p.add_argument("--namespace", default="default")
    p.add_argument("--cases", default=",".join(CASE_ORDER))
    p.add_argument("--pod-cpu", default="2")
    p.add_argument("--pod-mem", default="4096Mi")
    p.add_argument("--volume-size", default="512Gi")
    p.add_argument("--repeats", type=int, default=3)
    p.add_argument("--fio-jobfile", default="")
    p.add_argument("--workload-image", default="quay.io/rh-ee-chbutler/perf-utils:v0.1.0")
    p.add_argument("--results-root", default="./results")
    p.add_argument("--assume-cache-suspect", action="store_true")
    p.add_argument("--initdata", choices=["debug", "cluster-default"], default="debug")
    p.add_argument("--image-pull-secret", default="")
    p.add_argument("--cleanup-only", metavar="RUN_TAG", default="")
    p.add_argument("--coco-validate", choices=["proxy", "strong"], default="proxy")
    p.add_argument("--dry-run", action="store_true")
    p.add_argument("--yes", action="store_true")
    a = p.parse_args(argv)
    if a.cleanup_only:
        return a
    if not a.node or not a.sc:
        p.error("--node and --storage-class are required (or use --cleanup-only RUN_TAG)")
    return a


# ----------------------------------------------------------------- logging

def logline(path: Path, line: str) -> None:
    with open(path, "a", encoding="utf-8") as fh:
        fh.write(line.rstrip("\n") + "\n")


class OC:
    """All oc/helm invocations funnel here so timeouts apply uniformly (R10)."""

    def __init__(self, ns: str):
        self.ns = ns

    def oc(self, *args: str, timeout: int = 120, ok_rc: tuple = (0,)) -> subprocess.CompletedProcess:
        return self._fin(run(["oc", *args], timeout), ok_rc)

    def helm(self, *args: str, timeout: int = 120) -> subprocess.CompletedProcess:
        return run(["helm", *args], timeout)

    def _fin(self, cp: subprocess.CompletedProcess, ok_rc: tuple) -> subprocess.CompletedProcess:
        return cp if cp.returncode in ok_rc else cp


# -------------------------------------------------------------- preflight

def preflight(a: argparse.Namespace, oc: OC, cases: list[str]) -> tuple[bool, float, float, list[str]]:
    """Returns (fatal, node_mem_gib, suspect, tenant_warns). Emits fixed-format PREFLIGHT lines."""
    fatal = False
    tenant_warns: list[str] = []

    if shutil.which("oc") is None:
        say("FAIL", "tooling", "oc not on PATH")
        return True, 0.0, False, tenant_warns
    if shutil.which("helm") is None:
        say("FAIL", "tooling", "helm not on PATH")
        return True, 0.0, False, tenant_warns
    try:
        import pyiceberg  # noqa: F401
        say("OK", "tooling", "pyiceberg importable")
    except ImportError:
        say("FAIL", "tooling", "pyiceberg/pyarrow missing: pip install -r io-benchmark/requirements.txt")
        fatal = True
    say("OK", "tooling", "oc + helm present")

    cp = oc.oc("cluster-info", timeout=30)
    if cp.returncode == 0:
        say("OK", "cluster", "API reachable")
    else:
        say("FAIL", "cluster", (cp.stderr or "").strip()[:160] or "unreachable")
        fatal = True

    cp = oc.oc("get", "node", a.node, "-o", "json", timeout=60)
    if cp.returncode != 0:
        say("FAIL", "node", f"node {a.node!r} not found")
        return True, 0.0, False, tenant_warns
    node = json.loads(cp.stdout)
    sched = not node.get("spec", {}).get("unschedulable", False)
    say("OK" if sched else "WARN", "node schedulability",
        f"{a.node} {'schedulable' if sched else 'unschedulable'} (operator-controlled isolation, FR-016)")

    raw = node["status"]["capacity"]["memory"]
    if raw.endswith("Ki"):
        mem_gib = float(raw[:-2]) / 1024 / 1024
    elif raw.endswith("Mi"):
        mem_gib = float(raw[:-2]) / 1024
    elif raw.endswith("Gi"):
        mem_gib = float(raw[:-2])
    else:
        mem_gib = float(raw) / 1024**3
    say("OK", "node memory", f"{mem_gib:.1f} GiB detected on {a.node}")

    runtimes = sorted({CASE_RUNTIME[c] for c in cases if CASE_RUNTIME[c]})
    for rc in runtimes:
        cp = oc.oc("get", "runtimeclass", rc, timeout=30)
        if cp.returncode == 0:
            say("OK", "runtimeclass", f"{rc} present")
        else:
            say("FAIL", "runtimeclass", f"{rc} missing (needed by selected cases)")
            fatal = True

    if a.coco_validate == "strong" and any(c.startswith("coco") for c in cases):
        cp = oc.oc("debug", f"node/{a.node}", "--", "sh", "-cx",
                   "chroot /host grep -s tdx /proc/cpuinfo; rc=$?; exit $rc", timeout=140)
        (say("OK", "tdx-strong", "TDX flag visible")
         if cp.returncode == 0 and "tdx" in cp.stdout
         else say("WARN", "tdx-strong", "TDX not confirmed; kata-cc cases may spawn non-confidential VMs"))

    try:
        vol_gib = quantity_gib(a.volume_size)
    except ValueError as exc:
        say("FAIL", "volume-size-parse", str(exc))
        return True, mem_gib, False, tenant_warns
    required = round(mem_gib * RESULT_SIZE_MARGIN, 1)
    suspect = vol_gib < required or a.assume_cache_suspect
    if suspect:
        say("CACHE-SUSPECT", "sizing-rule",
            f"volume_size={a.volume_size} below required {required}Gi (node RAM x{RESULT_SIZE_MARGIN}); "
            "run proceeds (warn-only) and every summary is stamped cache-suspect (FR-005)")
    else:
        say("OK", "sizing-rule", f"volume_size={a.volume_size} >= required {required}Gi")

    # Tenant census (warn-only, FR-016).
    cp = oc.oc("get", "pods", "-A", "--field-selector",
               f"spec.nodeName={a.node}", "-o", "json", timeout=60)
    if cp.returncode == 0:
        pods = json.loads(cp.stdout).get("items", [])
        tenants = [f"{p['metadata']['namespace']}/{p['metadata']['name']}"
                   for p in pods
                   if not p['metadata']['namespace'].startswith(("openshift", "kube", "default"))]
        if tenants:
            say("WARN", "tenant-census", f"{len(tenants)} non-system pods on node: {', '.join(tenants[:10])}")
            tenant_warns.extend(tenants)
        else:
            say("OK", "tenant-census", "no non-system pods on node")
    else:
        say("WARN", "tenant-census", "could not enumerate node pods")

    root = Path(a.results_root)
    try:
        root.mkdir(parents=True, exist_ok=True)
        probe = root / ".preflight-write-probe"
        probe.write_text("ok"); probe.unlink()
        say("OK", "results-root", f"{root} writable")
    except OSError as exc:
        say("FAIL", "results-root", f"{root} not writable: {exc}")
        fatal = True

    if ":latest" in a.workload_image:
        say("WARN", "image", f"{a.workload_image} uses :latest; pin a tag/digest")
    say("OK", "image-default", f"workload image {a.workload_image} (override for mirrors, FR-017)")
    return fatal, mem_gib, suspect, tenant_warns


def probe_block_pvc(a: argparse.Namespace, oc: OC) -> bool:
    name = f"io-bench-probe-{a.run_tag}".lower()
    pvc = {
        "apiVersion": "v1", "kind": "PersistentVolumeClaim",
        "metadata": {"name": name, "namespace": a.namespace},
        "spec": {"accessModes": ["ReadWriteOnce"], "volumeMode": "Block",
                 "storageClassName": a.sc,
                 "resources": {"requests": {"storage": "1Gi"}}},
    }
    cp = run(["oc", "apply", "-f", "-"], 60, stdin=json.dumps(pvc))
    if cp.returncode != 0:
        say("WARN", "block-probe", f"probe PVC apply failed: {cp.stderr.strip()[:160]}")
        return False
    bound = False
    try:
        cp = oc.oc("wait", "--for=jsonpath={.status.phase}=Bound", "pvc", name,
                   "-n", a.namespace, "--timeout=30s")
        bound = cp.returncode == 0
        say("OK" if bound else "WARN", "block-probe",
            f"1Gi volumeMode=Block PVC {'bound' if bound else 'did not bind in 30s'} on {a.sc}")
    finally:
        run(["oc", "delete", "pvc", name, "-n", a.namespace,
             "--ignore-not-found", "--wait=false"], 60)
    return bound


# ------------------------------------------------------------ helm/render

def case_set_flags(a: argparse.Namespace, slug: str, working_set: str) -> list[str]:
    rt, enc = CASE_RUNTIME[slug], CASE_ENCRYPTED[slug]
    flags = ["--set", f"case.slug={slug}",
             "--set", f"case.runtimeClassName={rt}",
             "--set", f"case.encrypted={'true' if enc else 'false'}",
             "--set", f"node.name={a.node}",
             "--set", f"pvc.storageClass={a.sc}",
             "--set", f"pvc.size={a.volume_size}",
             "--set", f"pod.cpu={a.pod_cpu}",
             "--set", f"pod.mem={a.pod_mem}",
             "--set", f"images.workload={a.workload_image}",
             "--set", f"namespace={a.namespace}",
             "--set", f"runTag={a.run_tag}",
             "--set", f"fio.workingSetSize={working_set}",
             "--set", f"initdata.mode={a.initdata}",
             "--set-file", f"fioJobInline={a.job_sections_file}"]
    if a.image_pull_secret:
        flags += ["--set", f"imagePullSecrets[0].name={a.image_pull_secret}"]
    return flags


def resource_name(a: argparse.Namespace, slug: str) -> str:
    return f"io-bench-{a.run_tag[:20]}-{slug}"


# --------------------------------------------------------------- iceberg

def iceberg_open(warehouse: Path):
    from pyiceberg import catalog
    from pyiceberg import exceptions
    warehouse.mkdir(parents=True, exist_ok=True)
    cat = catalog.load_catalog("runs", **{
        "type": "sql",
        # busy_timeout absorbs short concurrent-writer contention;
        # retry layer in iceberg_append backs that up.
        "uri": f"sqlite:///{warehouse / 'catalog.db'}?busy_timeout=5000",
        "warehouse": f"file://{warehouse}",
    })
    try:
        cat.create_namespace("runs")
    except exceptions.NamespaceAlreadyExistsError:
        pass
    return cat


IBG_FIELDS = {    "metadata": [
        ("run_id", "string"), ("run_tag", "string"), ("utc_start", "timestamptz"),
        ("utc_end", "timestamptz"), ("node", "string"), ("storage_class", "string"),
        ("namespace", "string"), ("pod_cpu", "string"), ("pod_mem", "string"),
        ("volume_size", "string"), ("repeats", "long"), ("fio_job_name_list", "string"),
        ("images_workload", "string"), ("cases_requested", "string"),
        ("cases_completed", "string"), ("cache_suspect", "boolean"),
        ("sizing_rule_threshold", "string"), ("sizing_rule_actual", "string"),
        ("tool_version", "string"), ("repo_git_sha", "string"),
    ],
    "case_iterations": [
        ("run_id", "string"), ("case", "string"), ("runtime_class", "string"),
        ("encrypted", "boolean"), ("pvc_name", "string"), ("pod_name", "string"),
        ("utc_start", "timestamptz"), ("utc_end", "timestamptz"),
        ("status", "string"), ("failed_stage", "string"),
    ],
    "datapoints": [
        ("run_id", "string"), ("case", "string"), ("repeat_idx", "long"),
        ("job_name", "string"), ("pattern", "string"), ("block_size", "string"),
        ("bw_bytes", "double"), ("iops", "double"), ("lat_mean_us", "double"),
        ("lat_p95_us", "double"), ("lat_p99_us", "double"),
        ("runtime_s", "double"), ("ramp_s", "double"), ("iodepth", "long"),
        ("ioengine", "string"), ("direct", "boolean"), ("status", "string"),
        ("cache_suspect", "boolean"), ("collected_at", "timestamptz"),
    ],
    "case_aggregates": [
        ("run_id", "string"), ("case", "string"), ("job_name", "string"),
        ("n_repeats", "long"),
        ("bw_bytes_min", "double"), ("bw_bytes_max", "double"),
        ("bw_bytes_mean", "double"), ("bw_bytes_stddev", "double"),
        ("iops_min", "double"), ("iops_max", "double"),
        ("iops_mean", "double"), ("iops_stddev", "double"),
        ("lat_mean_us_min", "double"), ("lat_mean_us_max", "double"),
        ("lat_mean_us_mean", "double"), ("lat_mean_us_stddev", "double"),
        ("lat_p95_us_mean", "double"), ("lat_p99_us_mean", "double"),
        ("spread_rel_bw", "double"), ("spread_rel_iops", "double"),
        ("cache_suspect", "boolean"), ("status", "string"),
    ],
}


def iceberg_table(cat, name: str):
    from pyiceberg import schema, types
    from pyiceberg import exceptions
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
    """Append with bounded retry + jitter so two concurrent runs sharing the
    SQLite warehouse (FR-008 edge case) absorb lock contention instead of
    failing the case. Idempotent by caller-supplied row identity."""
    if not rows:
        return
    import random
    import time
    tbl = iceberg_table(cat, name)
    arrow = rows_to_arrow(rows, name)
    last_exc: Exception | None = None
    for attempt in range(1, attempts + 1):
        try:
            tbl.append(arrow)
            return
        except Exception as exc:  # OperationalError / lock contention
            last_exc = exc
            time.sleep(min(0.5 * attempt + random.uniform(0, 0.3), 3.0))
    raise RuntimeError(f"iceberg append to runs.{name} failed after {attempts} attempts: {last_exc}")


def rows_to_arrow(rows: list[dict], name: str):
    import pyarrow as pa
    from pyiceberg.types import TimestamptzType  # noqa: F401  (documents tz policy)
    colnames = [f for f, _ in IBG_FIELDS[name]]
    cols = {}
    for f, ftype in IBG_FIELDS[name]:
        values = [r.get(f) for r in rows]
        if ftype == "timestamptz":
            values = [v if isinstance(v, dt.datetime) or v is None else dt.datetime.fromisoformat(v)
                      for v in values]
            values = [v.astimezone(dt.timezone.utc) if isinstance(v, dt.datetime) else None
                      for v in values]
        cols[f] = values
    return pa.table(cols)


# ------------------------------------------------------------ fio parsing

BS_RE = re.compile(r"bs([0-9]+[a-z]*)$")


def parse_fio_repeat(path: Path, run_id: str, slug: str, rep: int,
                     cache_suspect: bool) -> list[dict]:
    with open(path, encoding="utf-8") as fh:
        payload = json.load(fh)
    rows = []
    for job in payload.get("jobs", []):
        name = job.get("jobname", "job")
        pattern = name.split("-")[0] if "-" in name else name
        bs = ""
        m = BS_RE.search(name)
        if m:
            bs = m.group(1)
        ropts = job.get("job options", {})
        read, write = job.get("read", {}), job.get("write", {})
        bw = (read.get("bw_bytes", 0) or 0) + (write.get("bw_bytes", 0) or 0)
        iops = (read.get("iops", 0) or 0) + (write.get("iops", 0) or 0)
        lat = read if float(read.get("total_ios", 0) or 0) >= float(write.get("total_ios", 0) or 0) else write
        clat = lat.get("clat_usec") or {}
        prec = clat.get("percentile") or {}
        rows.append({
            "run_id": run_id, "case": slug, "repeat_idx": rep,
            "job_name": name, "pattern": pattern, "block_size": bs,
            "bw_bytes": float(bw), "iops": float(iops),
            "lat_mean_us": float(clat.get("mean") or 0.0),
            "lat_p95_us": float(prec.get("95.000000") or 0.0),
            "lat_p99_us": float(prec.get("99.000000") or 0.0),            "runtime_s": float(ropts.get("runtime", 0) or 0),
            "ramp_s": float(ropts.get("ramp_time", 0) or 0),
            "iodepth": int(float(ropts.get("iodepth", 0) or 0)),
            "ioengine": str(ropts.get("ioengine", "")),
            "direct": str(ropts.get("direct", "1")) == "1",
            "status": "OK", "cache_suspect": cache_suspect,
            "collected_at": utcnow(),
        })
    return rows


def aggregate(points: list[dict]) -> list[dict]:
    groups: dict[tuple, list[dict]] = {}
    for p in points:
        groups.setdefault((p["case"], p["job_name"]), []).append(p)
    out = []
    for (case, job), pts in sorted(groups.items()):
        ok = [p for p in pts if p["status"] == "OK"]
        def stats(key):
            vals = [p[key] for p in ok]
            if not vals:
                return (0.0,) * 4
            return (min(vals), max(vals), statistics.fmean(vals),
                    statistics.pstdev(vals) if len(vals) > 1 else 0.0)
        bmn, bmx, bmean, bsd = stats("bw_bytes")
        imn, imx, imean, isd = stats("iops")
        lmn, lmx, lmean, lsd = stats("lat_mean_us")
        p95mean = statistics.fmean([p["lat_p95_us"] for p in ok]) if ok else 0.0
        p99mean = statistics.fmean([p["lat_p99_us"] for p in ok]) if ok else 0.0
        rel = lambda lo, hi, mean: (hi - lo) / mean if mean > 0 else 0.0  # noqa: E731
        out.append({
            "run_id": pts[0]["run_id"], "case": case, "job_name": job,
            "n_repeats": len(ok),
            "bw_bytes_min": bmn, "bw_bytes_max": bmx, "bw_bytes_mean": bmean,
            "bw_bytes_stddev": bsd,
            "iops_min": imn, "iops_max": imx, "iops_mean": imean, "iops_stddev": isd,
            "lat_mean_us_min": lmn, "lat_mean_us_max": lmx,
            "lat_mean_us_mean": lmean, "lat_mean_us_stddev": lsd,
            "lat_p95_us_mean": p95mean, "lat_p99_us_mean": p99mean,
            "spread_rel_bw": rel(bmn, bmx, bmean), "spread_rel_iops": rel(imn, imx, imean),
            "cache_suspect": any(p["cache_suspect"] for p in pts),
            "status": "OK" if len(ok) == len(pts) else "FAILED",
        })
    return out


# -------------------------------------------------------------- summary

def mbytes(b: float) -> str:
    return f"{b / 1e6:.1f} MB/s"


def render_markdown(meta: dict, aggs: list[dict], cases_status: dict,
                    cache_suspect: bool, tenant_lines: list[str]) -> str:
    lines = ["# IO Benchmark Summary", ""]
    if cache_suspect:
        lines += ["⚠ **CACHE-SUSPECT**: volume sizing rule violated "
                  "(FR-005) — treat read-heavy results as unreliable.", ""]
    lines += ["| key | value |", "|---|---|"]
    for k in ("run_id", "node", "storage_class", "namespace", "pod_cpu", "pod_mem",
              "volume_size", "repeats", "images_workload", "tool_version"):
        lines.append(f"| {k} | {meta.get(k, '')} |")
    if tenant_lines:
        lines.append(f"| tenant-census | {'; '.join(tenant_lines)} |")
    lines += ["", "| case | job | BW mean (MB/s) | BW spread | IOPS mean | "
              "IOPS spread | lat mean (µs) | lat p95 (µs) | lat p99 (µs) | n | status |",
              "|---|---|---|---|---|---|---|---|---|---|---|"]
    for slug in CASE_ORDER:
        rows = [a for a in aggs if a["case"] == slug]
        if not rows:
            if slug in cases_status and cases_status[slug] not in ("OK", ""):
                lines.append(f"| {slug} | — | — | — | — | — | — | — | — | 0 | "
                             f"FAILED ({cases_status[slug]}) |")
            continue
        for a in rows:
            lines.append(
                f"| {slug} | {a['job_name']} | {mbytes(a['bw_bytes_mean'])} | "
                f"{a['spread_rel_bw']:.2%} | {a['iops_mean']:.0f} | "
                f"{a['spread_rel_iops']:.2%} | {a['lat_mean_us_mean']:.1f} | "
                f"{a['lat_p95_us_mean']:.1f} | {a['lat_p99_us_mean']:.1f} | "
                f"{a['n_repeats']} | {a['status']} |")
    lines += ["", "## Case artifacts (raw logs — FR-008)", "",
              "| case | manifest | case log | pod log | repeats dir |",
              "|---|---|---|---|---|"]
    for slug in CASE_ORDER:
        if slug not in cases_status:
            continue
        lines.append(
            f"| {slug} | [`manifest-{slug}.yaml`](manifest-{slug}.yaml) | "
            f"[`exec-{slug}.log`](exec-{slug}.log) | "
            f"[`LOGS/case-pod-{slug}.log`](LOGS/case-pod-{slug}.log) | "
            f"[{slug}/]({slug}/) |")
    return "\n".join(lines) + "\n"


# ---------------------------------------------------------------- cleanup

def cleanup_resources(a: argparse.Namespace, slug: str) -> bool:
    name = resource_name(a, slug) if slug else None
    rc_ok = True
    for kind in ("pod", "pvc", "configmap"):
        sel = f"io-benchmark/run-tag={a.run_tag}"
        args = ["delete", kind, "-n", a.namespace, "-l", f"io-benchmark/case={slug},{sel}",
                "--ignore-not-found", "--wait=true", "--timeout=600s"] if slug else \
               ["delete", kind, "-n", a.namespace, "-l", sel,
                "--ignore-not-found", "--wait=true", "--timeout=600s"]
        cp = run(["oc", *args], 660)
        if cp.returncode != 0:
            print(f"cleanup {kind}{'/' + name if name else ''} WARN: {cp.stderr.strip()[:160]}")
            rc_ok = False
    return rc_ok


def cleanup_only(a: argparse.Namespace) -> int:
    print(f"cleanup run-tag={a.cleanup_only}")
    a.run_tag = a.cleanup_only
    ok = True
    for slug in CASE_ORDER:
        ok = cleanup_resources(a, slug) and ok
    # The raw-block probe PVC is unlabeled (created by raw JSON apply); remove
    # it by name so a control-process death mid-probe stays recoverable (FR-013).
    cp = run(["oc", "delete", "pvc", f"io-bench-probe-{a.cleanup_only}".lower(),
              "-n", a.namespace, "--ignore-not-found", "--wait=true",
              "--timeout=120s"], 150)
    if cp.returncode != 0:
        print(f"cleanup probe-pvc WARN: {cp.stderr.strip()[:160]}")
        ok = False
    return EXIT_OK if ok else EXIT_CLEANUP_FAILED


# ------------------------------------------------------------------ case

def run_case(a: argparse.Namespace, oc: OC, run_dir: Path, slug: str,
             working_set: str, jobfile_text: str, cache_suspect: bool,
             cat, all_points: list[dict]) -> tuple[str, str]:
    """Returns (status, failed_stage)."""
    status, failed = "OK", ""
    case_dir = run_dir / slug
    case_dir.mkdir(parents=True, exist_ok=True)
    case_log = run_dir / f"exec-{slug}.log"
    percase_log = case_dir / "case.log"
    name = resource_name(a, slug)

    def note(line: str) -> None:
        logline(case_log, line)
        logline(percase_log, line)

    note(f"BEGIN {ts()}")

    # SC-004: the [global] header injected by the chart supplies the cache-defeat
    # essentials (direct=1, invalidate=1, time_based); only explicit operator
    # countermands inside an overridden --fio-jobfile can strip them. Audit and
    # stamp loudly when found so numbers cannot be quoted without the caveat.
    audit_suspect = cache_suspect
    counters = re.findall(
        r"^\s*(direct\s*=\s*0|invalidate\s*=\s*0|buffered\s*=\s*1)\b",
        jobfile_text, flags=re.M | re.I)
    if counters:
        audit_suspect = True
        say("WARN", "job-audit",
            f"operator jobfile countermands cache-defeat globals ({counters}); "
            f"case {slug} datapoints stamped cache-suspect")
        logline(case_log, f"JOB-AUDIT-WARN cache-defeat settings countermanded: {counters}")

    m_flags = case_set_flags(a, slug, working_set)
    cp = oc.helm("template", "io", fmt_path(CHART_DIR), *m_flags)
    if cp.returncode != 0:
        note(f"helm template failed: {cp.stderr.strip()[:400]}")
        cmark(slug, "render FAILED"); return "FAILED", "render"
    manifest = run_dir / f"manifest-{slug}.yaml"
    manifest.write_text(cp.stdout, encoding="utf-8")

    cp = run(["oc", "apply", "-f", fmt_path(manifest)], 120)
    if cp.returncode != 0:
        note(f"oc apply failed: {cp.stderr.strip()[:400]}")
        cleanup_resources(a, slug)
        cmark(slug, "apply FAILED"); return "FAILED", "apply"
    cmark(slug, "applied")
    note("applied")

    # Wait PVC Bound (size-scaled heuristic per R10).
    vol_gib = quantity_gib(a.volume_size)
    pvc_wait = int(max(600, vol_gib * 30))
    cp = oc.oc("wait", "--for=jsonpath={.status.phase}=Bound", "pvc", name,
               "-n", a.namespace, f"--timeout={pvc_wait}s", timeout=pvc_wait + 30)
    if cp.returncode != 0:
        note(f"pvc wait failed: {cp.stderr.strip()[:400]}")
        cleanup_resources(a, slug)
        cmark(slug, "pvc FAILED"); return "FAILED", "pvc"
    note("pvc Bound")

    cp = oc.oc("wait", "--for=condition=Ready", "pod", name, "-n", a.namespace,
               "--timeout=900s", timeout=930)
    if cp.returncode != 0:
        note(f"pod wait failed: {cp.stderr.strip()[:400]}")
        plog = run(["oc", "logs", name, "-n", a.namespace, "--all-containers"], 60)
        note(f"pod-logs: {(plog.stdout or plog.stderr).strip()[:800]}")
        cleanup_resources(a, slug)
        cmark(slug, "pod FAILED"); return "FAILED", "pod"
    cmark(slug, "READY")
    note("READY")

    logs_dir = run_dir / "LOGS"; logs_dir.mkdir(parents=True, exist_ok=True)
    cpl = run(["oc", "logs", name, "-n", a.namespace, "--all-containers"], 60)
    (logs_dir / f"case-pod-{slug}.log").write_text(cpl.stdout or cpl.stderr, encoding="utf-8")

    # Per-repeat fio exec (R2/R5).
    for rep in range(1, a.repeats + 1):
        rdir = case_dir / f"rep{rep}"
        rdir.mkdir(exist_ok=True)
        cmark(slug, f"fio rep{rep}/{a.repeats}")
        est = est_exec_seconds(jobfile_text)
        cp = run(["oc", "exec", name, "-n", a.namespace, "-c", "benchmark", "--",
                  "fio", "--output-format=json",
                  f"--output=/tmp/fio-rep{rep}.json", "/etc/fio/fio.job"], est)
        if cp.returncode != 0:
            note(f"fio rep{rep} rc={cp.returncode}: {cp.stderr.strip()[:300]}")
            cmark(slug, f"fio rep{rep} FAILED"); status, failed = "FAILED", "fio-exec"
            continue
        cp2 = run(["oc", "exec", name, "-n", a.namespace, "-c", "benchmark", "--",
                   "cat", f"/tmp/fio-rep{rep}.json"], max(300, est // 2))
        if cp2.returncode != 0 or not cp2.stdout.strip():
            note(f"fio rep{rep} result read back failed")
            continue
        try:
            json.loads(cp2.stdout)  # sanity
            (rdir / "fio.json").write_text(cp2.stdout, encoding="utf-8")
            rows = parse_fio_repeat(rdir / "fio.json", a.run_tag, slug, rep, audit_suspect)
            all_points.extend(rows)
            iceberg_append(cat, "datapoints", rows)
        except (ValueError, OSError) as exc:
            note(f"fio rep{rep} parse failed: {exc}")
    cmark(slug, f"{'DONE' if status == 'OK' else 'DONE-with-failures'}")
    note(f"DONE {ts()} status={status}")

    # Delete + verify (FR-013).
    run(["oc", "delete", "-f", fmt_path(manifest), "--wait=true", "--timeout=600s"], 660)
    ok = cleanup_resources(a, slug)
    if not ok:
        print(f"CASE {slug} CLEANUP-WARN: remnants may remain; "
              f"run --cleanup-only {a.run_tag}")
    return status, failed


def est_exec_seconds(jobfile_text: str) -> int:
    """fio exec timeout = (ramp + runtime) x sections x 1.5 + 600 floor (R10)."""
    secs = re.findall(r"^\[.+]$", jobfile_text, flags=re.M)
    rt = re.search(r"\bruntime=(\d+)", DEFAULT_GLOBAL) or None
    runtime = 60
    sections = max(1, len([s for s in secs if "global" not in s.lower()]))
    return int((10 + runtime) * sections * 1.5) + 600


DEFAULT_GLOBAL = "runtime=60 ramp_time=10"


def git_sha() -> str:
    cp = run(["git", "rev-parse", "--short", "HEAD"], 15)
    return cp.stdout.strip() if cp.returncode == 0 else ""


# ------------------------------------------------------------------ main

def main(argv: list[str]) -> int:
    a = parse_args(argv)
    if a.cleanup_only:
        return cleanup_only(a)
    if a.repeats < 1:
        print("usage error: --repeats must be >= 1", file=sys.stderr)
        return EXIT_USAGE
    if not a.run_tag:
        a.run_tag = utcnow().strftime("%Y%m%dT%H%M%SZ")
    if not re.fullmatch(r"[a-zA-Z0-9.-]{1,40}", a.run_tag):
        print("usage error: --run-tag must match [a-zA-Z0-9.-]{1,40}", file=sys.stderr)
        return EXIT_USAGE

    requested = [c.strip() for c in a.cases.split(",") if c.strip()]
    bad = [c for c in requested if c not in CASE_ORDER]
    if bad:
        print(f"usage error: unknown case(s): {bad}; valid {CASE_ORDER}", file=sys.stderr)
        return EXIT_USAGE
    cases = [c for c in CASE_ORDER if c in requested]

    oc = OC(a.namespace)
    root = Path(a.results_root)
    run_dir = root / a.run_tag

    run_dir.mkdir(parents=True, exist_ok=True)
    global _PREFLIGHT_LOG
    _PREFLIGHT_LOG = run_dir / "preflight.log"

    print(f"run_tag={a.run_tag} cases={cases} UTC start {ts()}")
    fatal, mem_gib, cache_suspect, tenant_warns = preflight(a, oc, cases)

    if fatal:
        return EXIT_PREFLIGHT

    # Raw-block probe: transient 1Gi PVC, created+deleted here so dry-run output
    # also covers storage-class capability (research R8 / quickstart §3).
    probe_block_pvc(a, oc)

    if a.dry_run:
        print("DRY RUN: preflight complete; nothing provisioned (probe PVC transient).")
        return EXIT_OK

    if not a.yes:
        try:
            answer = input(
                f"About to provision {len(cases)} serial benchmark pods on node "
                f"{a.node} (pvc size {a.volume_size}, run-tag {a.run_tag}). "
                "Type 'yes' to continue: ")
        except EOFError:
            answer = ""
        if answer.strip().lower() != "yes":
            print("aborted by operator (use --yes to pre-confirm)", file=sys.stderr)
            return EXIT_USAGE

    # Working set: 90% of volume, <= 1Ti default ceiling documented in sizing doc.
    working_set = f"{max(1, int(quantity_gib(a.volume_size) * 0.9))}Gi"
    jobfile_text = (Path(a.fio_jobfile).read_text(encoding="utf-8")
                    if a.fio_jobfile
                    else (CHART_DIR / "values.yaml").read_text(encoding="utf-8").split(
                        "fioJobInline: |", 1)[1].strip())
    jobfile_text = "\n".join(
        ln[4:] if ln.startswith("    ") else ln.lstrip()
        for ln in jobfile_text.splitlines())
    a.job_sections_file = str(run_dir / "fio-job-sections.txt")
    Path(a.job_sections_file).write_text(jobfile_text + "\n", encoding="utf-8")

    job_names = ",".join(
        m.group(1) for m in re.finditer(r"^\[([^\]]+)]\s*$", jobfile_text, flags=re.M)
        if "global" not in m.group(1).lower())

    meta = {
        "run_id": a.run_tag, "run_tag": a.run_tag,
        "utc_start": utcnow(), "utc_end": None,
        "node": a.node, "storage_class": a.sc, "namespace": a.namespace,
        "pod_cpu": a.pod_cpu, "pod_mem": a.pod_mem, "volume_size": a.volume_size,
        "repeats": a.repeats, "fio_job_name_list": job_names or "(none)",
        "images_workload": a.workload_image,
        "cases_requested": ",".join(requested), "cases_completed": "",
        "cache_suspect": cache_suspect,
        "sizing_rule_threshold": f">{mem_gib * RESULT_SIZE_MARGIN:.1f}Gi",
        "sizing_rule_actual": a.volume_size,
        "tool_version": VERSION, "repo_git_sha": git_sha(),
    }
    (run_dir / "run.env").write_text(
        "\n".join(f"{k.upper()}={v}" for k, v in meta.items() if v is not None) + "\n",
        encoding="utf-8")

    cat = iceberg_open(root / "iceberg-warehouse")

    cases_status: dict[str, str] = {}
    all_points: list[dict] = []
    interrupted = {"flag": False}

    def on_sig(*_):
        interrupted["flag"] = True
        raise KeyboardInterrupt

    signal.signal(signal.SIGINT, on_sig)
    signal.signal(signal.SIGTERM, on_sig)

    try:
        for slug in cases:
            ctime = utcnow()
            cmark(slug, "BEGIN")
            try:
                status, failed = run_case(a, oc, run_dir, slug, working_set,
                                          jobfile_text, cache_suspect, cat, all_points)
            except Exception as exc:  # per-case isolation (FR-001)
                print(f"CASE {slug} ERROR: {exc.__class__.__name__}: {exc}")
                status, failed = "FAILED", "runner-exception"
            cases_status[slug] = failed or status
            iceberg_append(cat, "case_iterations", [{
                "run_id": a.run_tag, "case": slug, "runtime_class": CASE_RUNTIME[slug],
                "encrypted": CASE_ENCRYPTED[slug], "pvc_name": resource_name(a, slug),
                "pod_name": resource_name(a, slug),
                "utc_start": ctime, "utc_end": utcnow(),
                "status": "OK" if status == "OK" else "FAILED",
                "failed_stage": failed,
            }])
    except KeyboardInterrupt:
        print("interrupted: running cleanup for in-flight resources", file=sys.stderr)
        for slug in cases:
            cleanup_resources(a, slug)
        meta["utc_end"] = utcnow()
        meta["cases_completed"] = ",".join(k for k, v in cases_status.items() if v == "OK")
        # NOTE: still writes whatever was collected (FR-001 continuation).
        write_summary_and_meta(a, run_dir, root, cat, meta, all_points, cases_status, cache_suspect, tenant_warns)
        return EXIT_CASE_FAILED

    return finalize_and_exit(a, run_dir, root, cat, meta, all_points,
                             cases_status, cache_suspect, tenant_warns)


def write_summary_and_meta(a, run_dir, root, cat, meta, all_points,
                           cases_status, cache_suspect, tenant_lines) -> None:
    aggs = aggregate(all_points)
    meta["cases_completed"] = ",".join(k for k, v in cases_status.items() if v == "OK")
    iceberg_append(cat, "metadata", [meta])
    iceberg_append(cat, "case_aggregates", aggs)
    md = render_markdown(meta, aggs, cases_status, cache_suspect, tenant_lines)
    (run_dir / "summary.md").write_text(md, encoding="utf-8")
    # FR-008 / contract Outputs#1: the table goes to stdout; summary-echo.txt
    # is the durable copy of that stdout-side output.
    print("\n" + md, flush=True)
    (run_dir / "summary-echo.txt").write_text(md, encoding="utf-8")
    (run_dir / "parse-args.json").write_text(json.dumps({
        "run": a.run_tag, "results_root": a.results_root, "warehouse":
        fmt_path(root / "iceberg-warehouse")}, indent=2), encoding="utf-8")


def finalize_and_exit(a, run_dir, root, cat, meta, all_points,
                      cases_status, cache_suspect, tenant_warns) -> int:
    meta["utc_end"] = utcnow()
    write_summary_and_meta(a, run_dir, root, cat, meta, all_points,
                           cases_status, cache_suspect, tenant_warns)
    failed = [k for k, v in cases_status.items() if v != "OK"]
    print(f"\nDone. Summary: {run_dir / 'summary.md'}")
    print(f"Iceberg warehouse: {root / 'iceberg-warehouse'}")
    if failed:
        print(f"FAILED cases: {', '.join(failed)}", file=sys.stderr)
        return EXIT_CASE_FAILED
    return EXIT_OK


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
