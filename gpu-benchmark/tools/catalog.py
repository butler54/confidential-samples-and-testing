#!/usr/bin/env python3
"""gpu-benchmark declarative benchmark catalog (feature 005, FR-012).

Pure logic, no cluster or heavy dependencies (stdlib + PyYAML only) so the
CI static environment can validate the catalog contract through this exact
module (tests/run.sh). bench.py imports it for real runs.

Contract: specs/005-gpu-confidential-benchmark/contracts/benchmark-catalog.md
Adding a benchmark = adding one YAML file in benchmarks/ — nothing else
changes (SC-004).
"""
from __future__ import annotations

import math
import re
from pathlib import Path

import yaml

CHART_DIR = Path(__file__).resolve().parent.parent
CATALOG_DIR = CHART_DIR / "benchmarks"

_PRECISIONS = ("fp64", "mixed")
_ID_RE = re.compile(r"^[a-z][a-z0-9-]*$")


class DefinitionValidationError(ValueError):
    """A benchmark definition does not satisfy the catalog contract."""


def validate_definition(raw: object, source: str = "") -> dict:
    """Validate one catalog definition; returns the normalized definition.

    Raises DefinitionValidationError with an actionable message on any
    contract violation (missing parser/verification fields included — a
    benchmark without a verification verdict cannot produce results,
    FR-007/SC-003).
    """
    where = f" ({source})" if source else ""
    if not isinstance(raw, dict):
        raise DefinitionValidationError(f"definition{where} must be a mapping")

    for key in ("id", "precision", "version", "docs_ref", "parameter_inputs",
                "command_template", "parser"):
        if key not in raw:
            raise DefinitionValidationError(f"definition{where} missing required key {key!r}")

    did = raw["id"]
    if not isinstance(did, str) or not _ID_RE.fullmatch(did):
        raise DefinitionValidationError(f"definition{where} id {did!r} must match {_ID_RE.pattern}")
    if raw["precision"] not in _PRECISIONS:
        raise DefinitionValidationError(f"definition{where} precision must be one of {_PRECISIONS}")
    if not isinstance(raw["version"], str) or not raw["version"].strip():
        raise DefinitionValidationError(f"definition{where} version must be a non-empty string")
    if not isinstance(raw["docs_ref"], str) or not raw["docs_ref"].strip():
        raise DefinitionValidationError(f"definition{where} docs_ref must be a non-empty string")

    pi = raw["parameter_inputs"]
    if not isinstance(pi, dict):
        raise DefinitionValidationError(f"definition {did}: parameter_inputs must be a mapping")
    for key in ("memory_fill", "default_nb", "process_grid"):
        if key not in pi:
            raise DefinitionValidationError(f"definition {did}: parameter_inputs missing {key!r}")
    try:
        fill = float(pi["memory_fill"])
    except (TypeError, ValueError) as exc:
        raise DefinitionValidationError(f"definition {did}: memory_fill must be numeric") from exc
    if not 0.0 < fill <= 1.0:
        raise DefinitionValidationError(f"definition {did}: memory_fill must be in (0, 1]")
    try:
        nb = int(pi["default_nb"])
    except (TypeError, ValueError) as exc:
        raise DefinitionValidationError(f"definition {did}: default_nb must be an integer") from exc
    if nb < 1:
        raise DefinitionValidationError(f"definition {did}: default_nb must be >= 1")
    if not isinstance(pi["process_grid"], str) or not pi["process_grid"].strip():
        raise DefinitionValidationError(f"definition {did}: process_grid must be a non-empty string")

    cmd = raw["command_template"]
    if not isinstance(cmd, str) or not cmd.strip():
        raise DefinitionValidationError(f"definition {did}: command_template must be non-empty")
    for ph in ("{n}", "{nb}", "{p}", "{q}"):
        if ph not in cmd:
            raise DefinitionValidationError(
                f"definition {did}: command_template must contain the {ph} placeholder")

    parser = raw["parser"]
    if not isinstance(parser, dict):
        raise DefinitionValidationError(f"definition {did}: parser must be a mapping")
    for part in ("metric", "verification"):
        if not isinstance(parser.get(part), dict):
            raise DefinitionValidationError(f"definition {did}: parser.{part} must be a mapping")
    for part in ("metric", "verification"):
        spec = parser[part]
        for key in ("pattern", "group"):
            if key not in spec:
                raise DefinitionValidationError(
                    f"definition {did}: parser.{part} missing {key!r}")
        try:
            re.compile(spec["pattern"])
        except re.error as exc:
            raise DefinitionValidationError(
                f"definition {did}: parser.{part} pattern invalid: {exc}") from exc
        try:
            group = int(spec["group"])
        except (TypeError, ValueError) as exc:
            raise DefinitionValidationError(
                f"definition {did}: parser.{part} group must be an integer") from exc
        if group < 1:
            raise DefinitionValidationError(
                f"definition {did}: parser.{part} group must be >= 1")
    if not str(parser["verification"].get("pass_value", "")).strip():
        raise DefinitionValidationError(
            f"definition {did}: parser.verification.pass_value must be non-empty "
            "(a benchmark without a verification verdict cannot produce results, FR-007)")

    return {
        "id": did,
        "precision": raw["precision"],
        "version": raw["version"],
        "docs_ref": raw["docs_ref"],
        "parameter_inputs": {"memory_fill": fill, "default_nb": nb,
                             "process_grid": pi["process_grid"]},
        "command_template": cmd.strip(),
        "parser": {"metric": dict(parser["metric"]),
                   "verification": dict(parser["verification"])},
        "source": source,
    }


def load_catalog(directory: Path | str | None = None) -> dict[str, dict]:
    """Discover and validate every benchmarks/*.yaml definition.

    The extensibility mechanism itself (FR-012): a new YAML file in the
    catalog directory is a new selectable benchmark — no code change.
    """
    cat_dir = Path(directory) if directory is not None else CATALOG_DIR
    catalog: dict[str, dict] = {}
    files = sorted(cat_dir.glob("*.yaml")) if cat_dir.is_dir() else []
    if not files:
        raise DefinitionValidationError(f"no benchmark definitions found in {cat_dir}")
    for path in files:
        with open(path, encoding="utf-8") as fh:
            raw = yaml.safe_load(fh)
        definition = validate_definition(raw, source=str(path))
        if definition["id"] in catalog:
            raise DefinitionValidationError(
                f"duplicate benchmark id {definition['id']!r} "
                f"({catalog[definition['id']]['source']} and {path})")
        catalog[definition["id"]] = definition
    return catalog


# ------------------------------------------------------------- parameters

def process_grid(gpu_count: int) -> tuple[int, int]:
    """Factor pair of gpu_count with P <= Q, closest to square (1->1x1,
    4->2x2, 8->2x4; primes degrade to 1xN)."""
    if gpu_count < 1:
        raise ValueError("gpu_count must be >= 1")
    best = (1, gpu_count)
    for p in range(1, math.isqrt(gpu_count) + 1):
        if gpu_count % p == 0:
            best = (p, gpu_count // p)
    return best


def compute_params(definition: dict, gpu_count: int, gpu_mem_mib: int, *,
                   n: int = 0, nb: int = 0, p: int = 0, q: int = 0,
                   memory_fill: float | None = None) -> dict:
    """Compute the benchmark parameters for one (benchmark, GPU configuration).

    Computed ONCE per run by the runner and reused verbatim across runtime
    classes (FR-004). N fills `memory_fill` of aggregate GPU memory and is
    rounded down to a multiple of 8*NB (docs/sizing-guidance.md).
    """
    pi = definition["parameter_inputs"]
    fill = float(memory_fill if memory_fill is not None else pi["memory_fill"])
    nbv = int(nb or pi["default_nb"])
    if not 0.0 < fill <= 1.0:
        raise ValueError("memory_fill must be in (0, 1]")
    if nbv < 1:
        raise ValueError("nb must be >= 1")
    if gpu_mem_mib < 1:
        raise ValueError("gpu_mem_mib must be >= 1")
    if n:
        nv = int(n)
    else:
        total_bytes = float(gpu_mem_mib) * 1024 * 1024 * gpu_count
        nv = int(math.sqrt(fill * total_bytes / 8.0))
        nv -= nv % (8 * nbv)
    if nv <= 0:
        raise ValueError(f"computed problem size N={nv} is not positive")
    pv, qv = process_grid(gpu_count)
    if p:
        pv = int(p)
    if q:
        qv = int(q)
    if pv * qv != gpu_count:
        raise ValueError(f"process grid {pv}x{qv} must cover gpu_count={gpu_count}")
    return {"n": nv, "nb": nbv, "p": pv, "q": qv, "memory_fill": fill,
            "gpu_count": gpu_count, "gpu_mem_mib": gpu_mem_mib}


def render_command(definition: dict, params: dict) -> str:
    """Fill the definition's command_template with computed parameters."""
    return definition["command_template"].format(
        n=params["n"], nb=params["nb"], p=params["p"], q=params["q"],
        nprocs=params["gpu_count"])


def parse_output(definition: dict, text: str) -> tuple[float | None, str | None]:
    """Extract (metric, verdict) from benchmark output per the definition's
    parser mapping. The LAST metric match wins (progress rows precede the
    final summary row). Returns (None, None) when nothing matches."""
    metric: float | None = None
    verdict: str | None = None
    mspec = definition["parser"]["metric"]
    vspec = definition["parser"]["verification"]
    for line in text.splitlines():
        m = re.search(mspec["pattern"], line)
        if m:
            try:
                metric = float(m.group(int(mspec["group"])))
            except (ValueError, IndexError):
                pass
        v = re.search(vspec["pattern"], line)
        if v:
            try:
                verdict = v.group(int(vspec["group"])).strip().upper()
            except (ValueError, IndexError):
                pass
    return metric, verdict
