#!/usr/bin/env python3
"""Bounded process bridge between the Omarchy panel and its bundled companion."""
from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path
import subprocess
import sys
import tempfile


ACTIONS = {"status", "setup", "repair", "refresh", "remove"}
SUPPORTED_AGENTS = {"codex", "claude", "opencode", "gemini", "agy"}
WHEEL_NAME = "omarchy_community_knowledge_tools-0.4.1-py3-none-any.whl"
SETUP_NAME = "omarchy-knowledge-setup.py"
OUTPUT_LIMIT = 16 * 1024


def _read_bounded(stream) -> str:
    stream.seek(0)
    data = stream.read(OUTPUT_LIMIT + 1)
    truncated = len(data) > OUTPUT_LIMIT
    text = data[:OUTPUT_LIMIT].decode("utf-8", "replace").strip()
    return text + ("\n[output truncated]" if truncated else "")


def run_process(argv, *, timeout):
    """Run argv without a shell and retain at most OUTPUT_LIMIT bytes per stream."""
    with tempfile.TemporaryFile() as stdout, tempfile.TemporaryFile() as stderr:
        try:
            process = subprocess.run(
                [str(value) for value in argv], stdin=subprocess.DEVNULL,
                stdout=stdout, stderr=stderr, timeout=timeout, check=False,
                env={**os.environ, "PYTHONUNBUFFERED": "1"},
            )
        except subprocess.TimeoutExpired:
            return subprocess.CompletedProcess(argv, 124, "", f"Command timed out after {timeout} seconds")
        return subprocess.CompletedProcess(
            argv, process.returncode, _read_bounded(stdout), _read_bounded(stderr),
        )


def _run(argv, *, timeout, runner):
    try:
        return runner(argv, timeout=timeout)
    except (OSError, subprocess.SubprocessError) as error:
        return subprocess.CompletedProcess(argv, 1, "", str(error))


def _cache_age(synced_at, now):
    if not isinstance(synced_at, str) or not synced_at:
        return None
    try:
        synced = datetime.fromisoformat(synced_at.replace("Z", "+00:00"))
    except ValueError:
        return None
    if synced.tzinfo is None:
        synced = synced.replace(tzinfo=timezone.utc)
    return max(0, int((now - synced.astimezone(timezone.utc)).total_seconds()))


def _status(*, home, runner, now):
    detected = _run(["omarchy-default-agent"], timeout=10, runner=runner)
    agent = detected.stdout.strip().casefold() if detected.returncode == 0 else ""
    supported = agent in SUPPORTED_AGENTS
    launcher = home / ".local/bin/omarchy-knowledge"
    result = {
        "ok": supported,
        "action": "status",
        "agent": agent or None,
        "agent_supported": supported,
        "installed": launcher.is_file() or launcher.is_symlink(),
        "revision": None,
        "synced_at": None,
        "cache_age_seconds": None,
        "count": 0,
        "refresh_error": None,
    }
    if not agent:
        result.update(ok=False, error=(detected.stderr.strip() or "Could not detect Omarchy's default agent"),
                      action_required="Choose a supported agent or install the skills manually.")
    elif not supported:
        result.update(ok=False, action_required=(
            f"{agent} is not supported automatically; install both skills manually for that agent."
        ))
    if not result["installed"]:
        return result

    status = _run([str(launcher), "status"], timeout=15, runner=runner)
    if status.returncode != 0:
        result.update(ok=False, error=status.stderr.strip() or status.stdout.strip() or "Status failed",
                      action_required="Use Repair if the installed companion no longer runs.")
        return result
    try:
        payload = json.loads(status.stdout)
    except (TypeError, json.JSONDecodeError):
        result.update(ok=False, error="Installed companion returned invalid status JSON",
                      action_required="Use Repair to restore the installed companion.")
        return result
    for key in ("revision", "synced_at", "count", "refresh_error"):
        result[key] = payload.get(key)
    result["cache_age_seconds"] = _cache_age(result["synced_at"], now)
    if result["refresh_error"]:
        result["ok"] = False
        result["action_required"] = "Refresh again when the network is available; prior accepted data remains usable."
    return result


def perform(action, *, plugin_root=None, home=None, runner=run_process, now=None):
    plugin_root = Path(plugin_root or Path(__file__).resolve().parent.parent)
    home = Path(home or Path.home())
    now = now or datetime.now(timezone.utc)
    if action not in ACTIONS:
        return {"ok": False, "action": action, "error": f"Unknown action: {action}"}
    if action == "status":
        return _status(home=home, runner=runner, now=now)

    setup = plugin_root / "vendor" / SETUP_NAME
    wheel = plugin_root / "vendor" / WHEEL_NAME
    launcher = home / ".local/bin/omarchy-knowledge"
    if action == "refresh":
        if not (launcher.is_file() or launcher.is_symlink()):
            return {"ok": False, "action": action, "error": "Companion is not installed; choose Setup first."}
        argv, timeout = [str(launcher), "sync", "--plugins"], 180
    else:
        if not setup.is_file():
            return {"ok": False, "action": action, "error": "Release is missing the bundled setup script."}
        if action in {"setup", "repair"} and not wheel.is_file():
            return {"ok": False, "action": action, "error": "Release is missing the bundled wheel."}
        argv = ["python3", str(setup)]
        if action in {"setup", "repair"}:
            argv.extend(["--wheel", str(wheel), "--agent", "auto"])
            if action == "repair":
                argv.append("--repair")
        else:
            # Removal follows the ownership receipt, not the selected agent.
            # An explicit supported selector avoids failing if the user's
            # default changed or disappeared after installation.
            argv.extend(["--agent", "codex", "--remove"])
        # The helper gives each subprocess its own 180-second deadline. Setup,
        # repair, and rollback can legitimately execute several in sequence;
        # this outer guard must not interrupt the helper before it can clean up.
        timeout = 1800

    completed = _run(argv, timeout=timeout, runner=runner)
    if action == "refresh":
        return refresh_result(completed)
    if completed.returncode != 0:
        return {
            "ok": False, "action": action, "exit_code": completed.returncode,
            "error": completed.stderr.strip() or completed.stdout.strip() or f"{action.title()} failed",
        }
    messages = {
        "setup": "Your agent is connected. Start a new agent conversation to use the research and contribution skills.",
        "repair": "Agent skills updated. Start a new agent conversation to use them.",
        "remove": "Agent connection removed. Saved community data and your drafts were kept.",
    }
    message = messages[action]
    if "pending" in completed.stdout.lower():
        message += " Some data could not be refreshed. Try Refresh data when you are online."
    return {"ok": True, "action": action, "message": message}


def refresh_result(completed):
    """Translate machine output into a bounded result suitable for a small popup."""
    result = {"ok": False, "action": "refresh", "exit_code": completed.returncode}
    try:
        value = json.loads(completed.stdout)
        knowledge, plugins, errors = value.get("knowledge", {}), value.get("plugins", {}), value["errors"]
        if not isinstance(errors, list):
            raise ValueError("Invalid error list")
        counts = [knowledge.get("count"), plugins.get("count")]
        if any(n is not None and (type(n) is not int or not 0 <= n <= 1_000_000) for n in counts):
            raise ValueError("Invalid counts")
        warnings = plugins.get("warnings", [])
        if not isinstance(warnings, list):
            raise ValueError("Invalid warnings")
        if completed.returncode or errors or plugins.get("state") == "stale":
            message = "Some data could not be refreshed. Previously saved data is still available, if present. Try Refresh data again when you are online."
        elif None in counts or plugins.get("state") not in {"refreshed", "unchanged", "not-modified"}:
            raise ValueError("Incomplete refresh result")
        else:
            result["ok"] = True
            message = f"Up to date: {counts[0]:,} community records and {counts[1]:,} plugins."
            if warnings:
                message += f" The marketplace reports {len(warnings):,} listing warnings; these remain visible to your agent."
        result["message"] = result["display_message"] = message
    except (ValueError, TypeError, KeyError, AttributeError):
        result["display_message"] = "Could not confirm the refresh result. Try Update agent, then Refresh data again."
    if not result["ok"]:
        result["error"] = result["display_message"]
        result["diagnostics"] = (completed.stderr or completed.stdout)[:OUTPUT_LIMIT]
    return result


def main(argv=None, *, output=sys.stdout) -> int:
    arguments = list(sys.argv[1:] if argv is None else argv)
    action = arguments[0] if len(arguments) == 1 else ""
    result = perform(action)
    json.dump(result, output, ensure_ascii=False, sort_keys=True)
    output.write("\n")
    return 0 if result.get("ok") else (2 if action not in ACTIONS else 1)


if __name__ == "__main__":
    raise SystemExit(main())
