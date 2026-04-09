"""Validation tools for generated code artifacts."""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

PYTHON_TIMEOUT = int(os.getenv("OPTIBENCH_PY_TIMEOUT", "120"))
LEAN_TIMEOUT = int(os.getenv("OPTIBENCH_LEAN_TIMEOUT", "300"))
LEAN_PROJECT_DIR = os.getenv("OPTIBENCH_LEAN_PROJECT_DIR", "")


def validate_python_code(code: str) -> str:
    tmp = tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False, prefix="optibench_")
    try:
        tmp.write(code)
        tmp.flush()
        tmp.close()
        py_exec = sys.executable or "python"
        result = subprocess.run([py_exec, tmp.name], capture_output=True, text=True, timeout=PYTHON_TIMEOUT)
        if result.returncode == 0:
            stdout = result.stdout.strip()
            return f"SUCCESS\nstdout:\n{stdout}" if stdout else "SUCCESS"
        return f"FAILURE (exit code {result.returncode})\n{result.stderr.strip()}"
    except subprocess.TimeoutExpired:
        return f"FAILURE\nExecution timed out after {PYTHON_TIMEOUT}s."
    except FileNotFoundError:
        return "FAILURE\nPython interpreter not found on PATH."
    finally:
        Path(tmp.name).unlink(missing_ok=True)


def validate_lean_code(code: str) -> str:
    project_dir = LEAN_PROJECT_DIR
    if project_dir and Path(project_dir).is_dir():
        return _validate_in_existing_project(code, Path(project_dir))
    return _validate_in_temp_project(code)


def _validate_in_existing_project(code: str, project: Path) -> str:
    target = project / "OptiBenchCheck.lean"
    target.write_text(code, encoding="utf-8")
    try:
        result = subprocess.run(["lake", "build", "OptiBenchCheck"], capture_output=True, text=True, timeout=LEAN_TIMEOUT, cwd=project)
        if result.returncode == 0:
            return "SUCCESS\nLean 4 compilation passed."
        return f"FAILURE\n{result.stderr.strip()}\n{result.stdout.strip()}"
    except subprocess.TimeoutExpired:
        return f"FAILURE\nlake build timed out after {LEAN_TIMEOUT}s."
    except FileNotFoundError:
        return "FAILURE\nlake (Lean 4) not found on PATH."
    finally:
        target.unlink(missing_ok=True)


_LAKEFILE_TEMPLATE = """\
import Lake
open Lake DSL

package OptiBenchCheck where
  leanOptions := #[⟨`autoImplicit, false⟩]

@[default_target]
lean_lib OptiBenchCheck where
  srcDir := "."

require mathlib from git
  "https://github.com/leanprover-community/mathlib4" @ "master"
"""

_TOOLCHAIN = "leanprover/lean4:v4.14.0"


def _validate_in_temp_project(code: str) -> str:
    tmpdir = tempfile.mkdtemp(prefix="optibench_lean_")
    try:
        Path(tmpdir, "lakefile.lean").write_text(_LAKEFILE_TEMPLATE, encoding="utf-8")
        Path(tmpdir, "lean-toolchain").write_text(_TOOLCHAIN, encoding="utf-8")
        Path(tmpdir, "OptiBenchCheck.lean").write_text(code, encoding="utf-8")
        init = subprocess.run(["lake", "update"], capture_output=True, text=True, timeout=LEAN_TIMEOUT, cwd=tmpdir)
        if init.returncode != 0:
            return f"FAILURE\nlake update failed:\n{init.stderr.strip()}"
        result = subprocess.run(["lake", "build", "OptiBenchCheck"], capture_output=True, text=True, timeout=LEAN_TIMEOUT, cwd=tmpdir)
        if result.returncode == 0:
            return "SUCCESS\nLean 4 compilation passed."
        return f"FAILURE\n{result.stderr.strip()}\n{result.stdout.strip()}"
    except subprocess.TimeoutExpired:
        return f"FAILURE\nlake build timed out after {LEAN_TIMEOUT}s."
    except FileNotFoundError:
        return "FAILURE\nlake (Lean 4) not found on PATH. Install elan first."
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)
