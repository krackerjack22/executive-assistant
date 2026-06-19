"""Layer 1 preflight checks — machine-verifiable environment facts only."""

from __future__ import annotations

import importlib.metadata
import json
import platform
import shutil
import socket
import sys
import tempfile
from pathlib import Path

from lib import env as _env

SCHEMA_VERSION = "1.0"

_SANDBOX_PATH_PATTERNS = ["/sessions/", "/tmp/cowork", "/workspace/session"]


def _python_version() -> str:
    return platform.python_version()


def _sandbox_indicators() -> list[str]:
    indicators = []
    home = str(Path.home())
    for pattern in _SANDBOX_PATH_PATTERNS:
        if pattern in home or pattern in sys.prefix:
            indicators.append(f"{pattern!r} path present")
    return indicators


def _module_version(name: str) -> str | None:
    try:
        return importlib.metadata.version(name)
    except importlib.metadata.PackageNotFoundError:
        return None


def _check_profiles(output_dir: Path) -> tuple[dict, list[dict], list[dict]]:
    paths_info: dict = {}
    issues: list[dict] = []
    warnings: list[dict] = []

    # Resolve profiles dir
    try:
        p = _env.profiles_dir()
        source = _env.profiles_dir_source()
        paths_info["profiles_dir"] = str(p)
        paths_info["profiles_dir_source"] = source
        paths_info["profiles_dir_readable"] = True
    except FileNotFoundError as exc:
        p_raw = (Path.home() / "Assets_Library" / "Executive-Assistant" / "profiles").resolve()
        paths_info["profiles_dir"] = str(p_raw)
        paths_info["profiles_dir_source"] = _env.profiles_dir_source()
        paths_info["profiles_dir_readable"] = False
        paths_info["profiles_index_parsed"] = False
        paths_info["profiles_count"] = 0
        issues.append({
            "code": "PROFILES_DIR_MISSING",
            "message": str(exc),
            "fix": f"Create '{p_raw}' or set EXEC_ASSISTANT_PROFILES_DIR to your actual profiles directory.",
        })
        return paths_info, issues, warnings

    # Check readability + index parseable + at least 1 profile
    index_path = p / "profiles_index.json"
    if not index_path.exists():
        paths_info["profiles_index_parsed"] = False
        paths_info["profiles_count"] = 0
        issues.append({
            "code": "PROFILES_INDEX_MISSING",
            "message": f"profiles_index.json not found in '{p}'.",
            "fix": f"Place profiles_index.json in '{p}'.",
        })
    else:
        try:
            with index_path.open() as f:
                index_data = json.load(f)
            count = len(index_data.get("profiles", {}))
            paths_info["profiles_index_parsed"] = True
            paths_info["profiles_count"] = count
        except (json.JSONDecodeError, OSError) as exc:
            paths_info["profiles_index_parsed"] = False
            paths_info["profiles_count"] = 0
            issues.append({
                "code": "PROFILES_INDEX_UNPARSEABLE",
                "message": f"profiles_index.json parse failed: {exc}",
                "fix": (
                    f"If on Google Drive, mark the folder 'Available offline' so files are local. "
                    f"Otherwise inspect '{index_path}' for corruption."
                ),
            })

    # Check output dir writable
    od = output_dir.resolve()
    paths_info["output_dir"] = str(od)
    try:
        od.mkdir(parents=True, exist_ok=True)
        test_file = od / ".preflight_write_test"
        test_file.touch()
        test_file.unlink()
        paths_info["output_dir_writable"] = True
    except OSError as exc:
        paths_info["output_dir_writable"] = False
        issues.append({
            "code": "OUTPUT_DIR_NOT_WRITABLE",
            "message": f"Cannot write to output dir '{od}': {exc}",
            "fix": f"Create '{od}' or pass --output-dir <writable_path>.",
        })

    return paths_info, issues, warnings


def run(output_dir: Path | None = None) -> dict:
    """Run all preflight checks. Returns the stable JSON-serialisable result dict."""
    if output_dir is None:
        output_dir = Path.cwd()

    issues: list[dict] = []
    warnings: list[dict] = []

    platform_info = {
        "os_family": platform.system(),
        "python_version": _python_version(),
        "hostname": socket.gethostname(),
        "sandbox_indicators": _sandbox_indicators(),
        "_note": "sandbox_indicators is descriptive only; never used for routing decisions inside the script",
    }

    paths_info, path_issues, path_warnings = _check_profiles(output_dir)
    issues.extend(path_issues)
    warnings.extend(path_warnings)

    # Required modules
    required_modules = {}
    for mod in ("pypdf", "pdfplumber"):
        ver = _module_version(mod)
        required_modules[mod] = ver
        if ver is None:
            issues.append({
                "code": "MISSING_REQUIRED_MODULE",
                "message": f"Required module '{mod}' is not importable.",
                "fix": f"Install with `pip install {mod}` in the Python interpreter at '{sys.executable}'.",
            })

    optional_modules = {
        "reportlab": _module_version("reportlab"),
    }

    optional_binaries = {
        "pdftk": shutil.which("pdftk"),
        "bw": shutil.which("bw"),
    }

    tools_info = {
        "required": required_modules,
        "optional": {**optional_modules, **optional_binaries},
    }

    actionable = list(dict.fromkeys(
        item["fix"] for item in (issues + warnings) if item.get("fix")
    ))

    return {
        "schema_version": SCHEMA_VERSION,
        "ok": len(issues) == 0,
        "platform": platform_info,
        "paths": paths_info,
        "tools": tools_info,
        "issues": issues,
        "warnings": warnings,
        "actionable": actionable,
    }


def assert_ok(output_dir: Path | None = None) -> dict:
    """Run preflight and raise SystemExit(1) if any issues found. Returns result dict."""
    result = run(output_dir=output_dir)
    if not result["ok"]:
        msg = "Preflight failed:\n" + "\n".join(
            f"  [{i['code']}] {i['message']}" for i in result["issues"]
        )
        print(msg, file=sys.stderr)
        sys.exit(1)
    return result


def human_report(result: dict) -> str:
    """Format the preflight result as a human-readable text report."""
    lines = []
    status = "PASS" if result["ok"] else "FAIL"
    lines.append(f"Preflight: {status}")
    lines.append(f"  OS: {result['platform']['os_family']}  Python: {result['platform']['python_version']}  Host: {result['platform']['hostname']}")
    if result["platform"]["sandbox_indicators"]:
        lines.append(f"  Sandbox indicators: {', '.join(result['platform']['sandbox_indicators'])}")
    p = result["paths"]
    lines.append(f"  Profiles dir: {p.get('profiles_dir', '?')} ({p.get('profiles_dir_source', '?')})  readable={p.get('profiles_dir_readable')}  index_parsed={p.get('profiles_index_parsed')}  count={p.get('profiles_count')}")
    lines.append(f"  Output dir: {p.get('output_dir', '?')}  writable={p.get('output_dir_writable')}")
    t = result["tools"]
    lines.append(f"  Required: {t['required']}")
    lines.append(f"  Optional: {t['optional']}")
    if result["issues"]:
        lines.append("ISSUES:")
        for i in result["issues"]:
            lines.append(f"  [{i['code']}] {i['message']}")
            lines.append(f"    Fix: {i['fix']}")
    if result["warnings"]:
        lines.append("WARNINGS:")
        for w in result["warnings"]:
            lines.append(f"  [{w['code']}] {w['message']}")
    return "\n".join(lines)
