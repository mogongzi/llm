from __future__ import annotations

import json
import os
import shlex
import subprocess
from typing import Any, Dict, List, Optional


class RailsRunnerError(RuntimeError):
    pass


def run_script_json(
    script_path: str,
    args: Optional[List[str]] = None,
    *,
    rails_root: str,
    env: Optional[Dict[str, str]] = None,
    timeout: float = 20.0,
) -> Dict[str, Any]:
    """
    Execute a Ruby script via `bin/rails runner` and parse JSON from stdout.

    Parameters:
        script_path: Absolute path to the Ruby script to execute
        args: Positional string arguments passed to the Ruby script
        rails_root: Path to the target Rails application root (contains bin/rails)
        env: Additional environment variables
        timeout: Process timeout in seconds

    Returns:
        Parsed JSON dict produced by the script
    """
    if not os.path.isabs(script_path):
        script_path = os.path.abspath(script_path)

    bin_rails = os.path.join(rails_root, "bin", "rails")
    if not os.path.exists(bin_rails):
        raise RailsRunnerError(f"bin/rails not found at: {bin_rails}")

    cmd = [bin_rails, "runner", script_path]
    if args:
        cmd.extend(args)

    env_vars = os.environ.copy()
    if env:
        env_vars.update(env)

    try:
        proc = subprocess.run(
            cmd,
            cwd=rails_root,
            env=env_vars,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            timeout=timeout,
        )
    except subprocess.TimeoutExpired as e:
        raise RailsRunnerError(f"rails runner timed out after {timeout}s") from e
    except Exception as e:  # pragma: no cover - defensive
        raise RailsRunnerError(str(e))

    if proc.returncode != 0:
        raise RailsRunnerError(
            f"rails runner failed (code {proc.returncode}): {proc.stderr.strip() or proc.stdout.strip()}"
        )

    out = (proc.stdout or "").strip()
    if not out:
        raise RailsRunnerError("rails runner produced no output")

    # Best-effort JSON parse: try direct, otherwise attempt to find last JSON object
    try:
        return json.loads(out)
    except json.JSONDecodeError:
        # Try to locate the last opening brace and parse from there
        last_open = out.rfind("{")
        last_close = out.rfind("}")
        if last_open != -1 and last_close != -1 and last_close > last_open:
            snippet = out[last_open : last_close + 1]
            try:
                return json.loads(snippet)
            except json.JSONDecodeError as e:  # pragma: no cover - fallback
                raise RailsRunnerError(f"failed to parse JSON from rails runner output: {e}\nOutput: {out}")
        raise RailsRunnerError(f"unexpected rails runner output (not JSON): {out}")

