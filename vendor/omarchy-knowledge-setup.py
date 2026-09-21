#!/usr/bin/env python3
"""Explicit setup for a locally reviewed Omarchy Community Knowledge wheel."""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import uuid


SKILL_NAMES = ("omarchy-knowledge-research", "omarchy-knowledge-contribution")
AGENT_SKILL_PATHS = {
    "codex": Path(".agents/skills"),
    "claude": Path(".claude/skills"),
    "opencode": Path(".agents/skills"),
    "gemini": Path(".agents/skills"),
    "agy": Path(".gemini/antigravity-cli/skills"),
}
AGENT_LABELS = {
    "codex": "Codex", "claude": "Claude Code", "opencode": "OpenCode",
    "gemini": "Gemini CLI", "agy": "Antigravity CLI",
}


class SetupConflict(ValueError):
    """Setup would overwrite or traverse an unsafe path."""


def setup_receipt_path(home: Path) -> Path:
    return Path(home).absolute() / ".local/state/omarchy-knowledge-next/setup.json"


def _exposure_receipt_path(home: Path) -> Path:
    return Path(home).absolute() / ".local/state/omarchy-knowledge-next/skill-exposure.json"


def _default_detection_command(argv):
    return subprocess.run(
        argv, check=True, text=True, stdout=subprocess.PIPE,
        stderr=subprocess.PIPE, timeout=10,
    ).stdout


def _resolve_agent(agent: str, command=None) -> str:
    if agent != "auto":
        if agent not in AGENT_SKILL_PATHS:
            raise SetupConflict(f"Unsupported agent {agent!r}; pass --agent with a supported target")
        return agent
    try:
        detected = (command or _default_detection_command)(["omarchy-default-agent"])
    except (OSError, subprocess.SubprocessError) as error:
        raise SetupConflict(
            "Omarchy's default agent could not be detected; pass --agent "
            "codex, claude, opencode, gemini, or agy"
        ) from error
    if hasattr(detected, "stdout"):
        detected = detected.stdout
    detected = str(detected).strip().casefold()
    if not detected:
        raise SetupConflict(
            "Omarchy's default agent could not be detected; pass --agent "
            "codex, claude, opencode, gemini, or agy"
        )
    if detected not in AGENT_SKILL_PATHS:
        raise SetupConflict(
            f"Omarchy's default agent {detected!r} is not supported; pass --agent "
            "codex, claude, opencode, gemini, or agy, or install the skills manually"
        )
    return detected


def _skill_plan(home: Path, agent: str) -> dict:
    home = Path(home).absolute()
    actions = []
    for name in SKILL_NAMES:
        path = home / AGENT_SKILL_PATHS[agent] / name
        legacy = home / ".codex/skills" / name
        _check_parent(path.parent, create=False)
        if agent == "codex":
            _check_parent(legacy.parent, create=False)
        result = (
            "legacy-occupied" if agent == "codex" and _lexists(legacy)
            else "occupied" if _lexists(path) else "would-install"
        )
        actions.append({"agent": agent, "name": name, "path": str(path), "result": result})
    return {"mode": "dry-run", "actions": actions}


def _skills_intact(home: Path, agent: str) -> bool:
    path = _exposure_receipt_path(home)
    _check_parent(path.parent, create=False)
    if path.is_symlink() or not path.is_file():
        return False
    try:
        receipt = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError):
        return False
    if (type(receipt) is not dict or receipt.get("version") != 1
            or type(receipt.get("links")) is not list
            or len(receipt["links"]) > len(SKILL_NAMES) * len(set(AGENT_SKILL_PATHS.values()))):
        return False
    expected = {str(Path(home).absolute() / AGENT_SKILL_PATHS[agent] / name) for name in SKILL_NAMES}
    recorded = {item.get("path") for item in receipt["links"] if type(item) is dict}
    if len(recorded) != len(receipt["links"]) or not expected.issubset(recorded):
        return False
    for item in receipt["links"]:
        if (set(item) != {"agent", "name", "path", "target"}
                or item["agent"] not in AGENT_SKILL_PATHS or item["name"] not in SKILL_NAMES
                or Path(item["path"]) != Path(home).absolute() / AGENT_SKILL_PATHS[item["agent"]] / item["name"]):
            return False
        link = Path(item["path"])
        target = Path(item["target"])
        if not target.is_absolute() or target.parts[-3:] != ("omarchy_knowledge", "skills", item["name"]):
            return False
        _check_parent(link.parent, create=False)
        if not link.is_symlink() or os.readlink(link) != item["target"]:
            return False
    return True


def _paths(home: Path, prefix: Path) -> dict[str, Path]:
    return {
        "venv": prefix / "share/omarchy-knowledge-next/venv",
        "launcher": prefix / "bin/omarchy-knowledge",
        "cache": home / ".cache/omarchy-knowledge-next",
        "receipt": setup_receipt_path(home),
    }


def _lexists(path: Path) -> bool:
    return os.path.lexists(path)


def _check_parent(path: Path, *, create: bool) -> None:
    missing = []
    current = path.absolute()
    while not _lexists(current):
        missing.append(current)
        current = current.parent
    if current.is_symlink() or not current.is_dir():
        raise SetupConflict(f"Unsafe parent path: {current}")
    for candidate in reversed(missing):
        if create:
            candidate.mkdir()
    current = path.absolute()
    while current != current.parent:
        if _lexists(current) and (current.is_symlink() or not current.is_dir()):
            raise SetupConflict(f"Unsafe parent path: {current}")
        current = current.parent


def _validate_inputs(wheel: Path, agent: str, home: Path, prefix: Path) -> dict[str, Path]:
    if sys.version_info < (3, 11):
        raise SetupConflict("Python 3.11 or newer is required")
    wheel = Path(wheel).absolute()
    if wheel.is_symlink() or not wheel.is_file() or wheel.suffix != ".whl":
        raise SetupConflict("--wheel must name a real local wheel file")
    home = Path(home).absolute()
    prefix = Path(prefix).absolute()
    if home.is_symlink() or not home.is_dir():
        raise SetupConflict("--home must be a real directory")
    if shutil.which("git") is None:
        raise SetupConflict("Git is required")
    paths = _paths(home, prefix)
    parents = [
        paths["venv"].parent, paths["launcher"].parent, paths["receipt"].parent,
        home / AGENT_SKILL_PATHS[agent],
    ]
    if agent == "codex":
        parents.append(home / ".codex/skills")
    for parent in parents:
        _check_parent(parent, create=False)
    return paths


def plan(wheel: Path, *, agent="codex", home: Path, prefix: Path, detect_command=None) -> dict:
    agent = _resolve_agent(agent, detect_command)
    paths = _validate_inputs(wheel, agent, home, prefix)
    skills = _skill_plan(Path(home), agent)
    actions = [
        f"Create isolated Python environment: {paths['venv']}",
        f"Install reviewed wheel with pip: {Path(wheel).absolute()}",
        f"Create owned launcher: {paths['launcher']}",
        f"Install two {AGENT_LABELS[agent]} skills under: {Path(home).absolute() / AGENT_SKILL_PATHS[agent]}",
        f"Attempt initial public knowledge refresh and plugin catalog refresh into: {paths['cache']}",
        f"Record owned setup paths in: {paths['receipt']}",
    ]
    return {"mode": "dry-run", "actions": actions, "skills": skills}


def _default_command(argv, **kwargs):
    return subprocess.run(
        [str(value) for value in argv], check=True, text=True,
        stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=180, **kwargs,
    )


def _write_receipt(path: Path, value: dict) -> None:
    _check_parent(path.parent, create=True)
    descriptor, name = tempfile.mkstemp(prefix=".setup-", dir=path.parent)
    temporary = Path(name)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as stream:
            json.dump(value, stream, sort_keys=True, indent=2)
            stream.write("\n")
        os.replace(temporary, path)
    finally:
        if _lexists(temporary):
            temporary.unlink()


def _owned_receipt(home: Path, prefix: Path) -> tuple[dict, dict[str, Path]]:
    paths = _paths(Path(home).absolute(), Path(prefix).absolute())
    path = paths["receipt"]
    _check_parent(path.parent, create=False)
    if path.is_symlink() or not path.is_file():
        raise SetupConflict(f"No safe setup ownership record exists: {path}")
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as error:
        raise SetupConflict(f"Invalid setup ownership record: {path}") from error
    expected = {
        "version": 1,
        "venv": str(paths["venv"]),
        "launcher": str(paths["launcher"]),
        "launcher_target": str(paths["venv"] / "bin/omarchy-knowledge"),
    }
    if value != expected:
        raise SetupConflict("Setup ownership record does not match the selected home and prefix")
    return value, paths


def _error_text(error: Exception) -> str:
    message = str(error)
    stderr = getattr(error, "stderr", None)
    if isinstance(stderr, bytes):
        stderr = stderr.decode("utf-8", "replace")
    if isinstance(stderr, str) and stderr.strip() and stderr.strip() not in message:
        message += ": " + stderr.strip()
    return message


def _skill_cleanup_confirmed(home: Path) -> bool:
    receipt = _exposure_receipt_path(home)
    _check_parent(receipt.parent, create=False)
    if _lexists(receipt):
        return False
    for name in SKILL_NAMES:
        link = Path(home).absolute() / ".agents/skills" / name
        _check_parent(link.parent, create=False)
        if _lexists(link):
            return False
    return True


def install(wheel: Path, *, agent="codex", home: Path, prefix: Path, command=_default_command,
            detect_command=None) -> dict:
    agent = _resolve_agent(agent, detect_command)
    paths = _validate_inputs(wheel, agent, home, prefix)
    if _lexists(paths["receipt"]):
        receipt, owned_paths = _owned_receipt(home, prefix)
        launcher = Path(receipt["launcher"])
        target = receipt["launcher_target"]
        _check_parent(launcher.parent, create=False)
        _check_parent(owned_paths["venv"].parent, create=False)
        _check_parent(Path(target).parent, create=False)
        environment_intact = (
            launcher.is_symlink()
            and os.readlink(launcher) == target
            and owned_paths["venv"].is_dir()
            and not owned_paths["venv"].is_symlink()
            and Path(target).is_file()
        )
        if environment_intact:
            if not _skills_intact(Path(home), agent):
                try:
                    command([target, "skills", "install", "--agent", agent,
                             "--home", str(Path(home).absolute())])
                except Exception as error:
                    raise RuntimeError(f"Could not safely update installed skills: {_error_text(error)}") from error
            return {"status": "already-installed", "refresh": "not-attempted", "refresh_error": None,
                    "launcher": str(launcher), "venv": str(owned_paths["venv"])}
        raise SetupConflict("Existing setup-owned paths were modified; preserving them")
    skill_plan = _skill_plan(Path(home), agent)
    if any(item["result"] != "would-install" for item in skill_plan["actions"]):
        raise SetupConflict(f"{AGENT_LABELS[agent]} skill destinations are already occupied; preserving them")
    for label in ("venv", "launcher"):
        if _lexists(paths[label]):
            raise SetupConflict(f"Refusing to overwrite existing {label}: {paths[label]}")
    created_launcher = False
    skills_attempted = False
    ownership_recorded = False
    try:
        _check_parent(paths["venv"].parent, create=True)
        command([sys.executable, "-m", "venv", paths["venv"]])
        python = paths["venv"] / "bin/python"
        executable = paths["venv"] / "bin/omarchy-knowledge"
        command([python, "-m", "pip", "install", "--disable-pip-version-check", str(Path(wheel).absolute())])
        if not python.is_file() or not executable.is_file():
            raise RuntimeError("Installed environment did not provide the expected launcher")
        _check_parent(paths["launcher"].parent, create=True)
        paths["launcher"].symlink_to(executable)
        created_launcher = True
        receipt = {
            "version": 1,
            "venv": str(paths["venv"]),
            "launcher": str(paths["launcher"]),
            "launcher_target": str(executable),
        }
        _write_receipt(paths["receipt"], receipt)
        ownership_recorded = True
        skills_attempted = True
        command([executable, "skills", "install", "--agent", agent, "--home", str(Path(home).absolute())])
    except Exception as error:
        cleanup_error = None
        if skills_attempted:
            try:
                _check_parent((paths["venv"] / "bin/omarchy-knowledge").parent, create=False)
                command([paths["venv"] / "bin/omarchy-knowledge", "skills", "remove", "--agent", agent,
                         "--home", str(Path(home).absolute())])
                if not _skill_cleanup_confirmed(Path(home)):
                    raise RuntimeError("skill cleanup could not be confirmed")
            except Exception as cleanup:
                cleanup_error = cleanup
        if cleanup_error is not None:
            raise RuntimeError(
                f"Setup failed: {_error_text(error)}; skill cleanup failed: "
                f"{_error_text(cleanup_error)}; preserved the launcher and environment for recovery"
            ) from error
        _check_parent(paths["launcher"].parent, create=False)
        if created_launcher and paths["launcher"].is_symlink() and os.readlink(paths["launcher"]) == str(paths["venv"] / "bin/omarchy-knowledge"):
            paths["launcher"].unlink()
        _check_parent(paths["venv"].parent, create=False)
        if paths["venv"].is_dir() and not paths["venv"].is_symlink():
            shutil.rmtree(paths["venv"])
        if ownership_recorded:
            _check_parent(paths["receipt"].parent, create=False)
            paths["receipt"].unlink()
        if isinstance(error, SetupConflict):
            raise
        raise RuntimeError(f"Setup failed: {_error_text(error)}") from error

    refresh = "complete"
    refresh_error = None
    try:
        _check_parent(paths["launcher"].parent, create=False)
        command([paths["launcher"], "sync", "--plugins", "--cache", str(paths["cache"])])
    except Exception as error:
        refresh = "pending"
        refresh_error = str(error)
    return {"status": "installed", "refresh": refresh, "refresh_error": refresh_error,
            "launcher": str(paths["launcher"]), "venv": str(paths["venv"])}


def repair(wheel: Path, *, agent="codex", home: Path, prefix: Path, command=_default_command,
           detect_command=None) -> dict:
    """Replace only a receipt-owned environment with rollback to its preserved backup."""
    agent = _resolve_agent(agent, detect_command)
    paths = _validate_inputs(wheel, agent, home, prefix)
    receipt, owned_paths = _owned_receipt(home, prefix)
    launcher = Path(receipt["launcher"])
    target = receipt["launcher_target"]
    _check_parent(launcher.parent, create=False)
    _check_parent(owned_paths["venv"].parent, create=False)
    if not launcher.is_symlink() or os.readlink(launcher) != target:
        raise SetupConflict("Owned launcher was modified; preserving the existing installation")
    if not owned_paths["venv"].is_dir() or owned_paths["venv"].is_symlink():
        raise SetupConflict("Owned environment is not a real directory; preserving it")

    backup = owned_paths["venv"].parent / (".venv-backup-" + uuid.uuid4().hex)
    moved_old = False
    try:
        owned_paths["venv"].rename(backup)
        moved_old = True
        command([sys.executable, "-m", "venv", owned_paths["venv"]])
        replacement_python = owned_paths["venv"] / "bin/python"
        replacement_executable = owned_paths["venv"] / "bin/omarchy-knowledge"
        command([replacement_python, "-m", "pip", "install", "--disable-pip-version-check",
                 str(Path(wheel).absolute())])
        if not replacement_python.is_file() or not replacement_executable.is_file():
            raise RuntimeError("Replacement environment did not provide the expected launcher")
        command([replacement_executable, "--help"])
        command([replacement_executable, "skills", "install",
                 "--agent", agent, "--home", str(Path(home).absolute())])
    except Exception as error:
        if moved_old:
            if _lexists(owned_paths["venv"]):
                if not owned_paths["venv"].is_dir() or owned_paths["venv"].is_symlink():
                    raise RuntimeError(
                        f"Repair failed: {_error_text(error)}; replacement path changed and the old environment "
                        f"was preserved at {backup}"
                    ) from error
                shutil.rmtree(owned_paths["venv"])
            backup.rename(owned_paths["venv"])
        if isinstance(error, SetupConflict):
            raise
        raise RuntimeError(f"Repair failed: {_error_text(error)}") from error
    if backup.is_dir() and not backup.is_symlink():
        try:
            shutil.rmtree(backup)
        except OSError as error:
            raise RuntimeError(
                f"Repair completed and the replacement is working, but the prior environment backup was "
                f"retained at {backup}; inspect it, then remove that backup manually: {_error_text(error)}"
            ) from error
    return {"status": "repaired", "refresh": "not-attempted", "refresh_error": None,
            "launcher": str(launcher), "venv": str(owned_paths["venv"])}


def remove(*, agent="codex", home: Path, prefix: Path, command=_default_command,
           detect_command=None) -> dict:
    agent = _resolve_agent(agent, detect_command)
    receipt, paths = _owned_receipt(home, prefix)
    launcher = Path(receipt["launcher"])
    target = receipt["launcher_target"]
    _check_parent(launcher.parent, create=False)
    if not launcher.is_symlink() or os.readlink(launcher) != target:
        return {"status": "preserved-modified", "launcher": str(launcher)}
    executable = Path(target)
    _check_parent(paths["venv"].parent, create=False)
    _check_parent(executable.parent, create=False)
    if not executable.is_file() or paths["venv"].is_symlink():
        return {"status": "preserved-modified", "launcher": str(launcher)}
    try:
        command([executable, "skills", "remove", "--agent", agent, "--home", str(Path(home).absolute())])
    except Exception as error:
        raise RuntimeError(f"Could not safely remove installed skills: {error}") from error
    exposure_receipt = _exposure_receipt_path(home)
    _check_parent(exposure_receipt.parent, create=False)
    if exposure_receipt.exists():
        return {"status": "preserved-modified", "launcher": str(launcher)}
    _check_parent(launcher.parent, create=False)
    launcher.unlink()
    _check_parent(paths["venv"].parent, create=False)
    if not paths["venv"].is_dir() or paths["venv"].is_symlink():
        raise SetupConflict("Owned environment changed during removal; preserving it")
    shutil.rmtree(paths["venv"])
    _check_parent(paths["receipt"].parent, create=False)
    paths["receipt"].unlink()
    return {"status": "removed", "launcher": str(launcher)}


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--wheel", type=Path)
    parser.add_argument(
        "--agent", default="auto", choices=("auto", "codex", "claude", "opencode", "gemini", "agy")
    )
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--remove", action="store_true")
    parser.add_argument("--repair", action="store_true")
    parser.add_argument("--home", type=Path, default=Path.home())
    parser.add_argument("--prefix", type=Path)
    options = parser.parse_args(argv)
    prefix = options.prefix or options.home / ".local"
    try:
        if options.remove:
            if options.wheel is not None or options.dry_run or options.repair:
                parser.error("--remove cannot be combined with --wheel, --dry-run, or --repair")
            result = remove(agent=options.agent, home=options.home, prefix=prefix)
        else:
            if options.wheel is None:
                parser.error("--wheel is required for setup")
            if options.repair and options.dry_run:
                parser.error("--repair cannot be combined with --dry-run")
            if options.dry_run:
                result = plan(options.wheel, agent=options.agent, home=options.home, prefix=prefix)
            elif options.repair:
                result = repair(options.wheel, agent=options.agent, home=options.home, prefix=prefix)
            else:
                result = install(options.wheel, agent=options.agent, home=options.home, prefix=prefix)
    except (SetupConflict, RuntimeError, ValueError) as error:
        print(str(error), file=sys.stderr)
        return 1
    if result.get("mode") == "dry-run":
        print("Dry run — no changes were made.")
        for action in result["actions"]:
            print("- " + action)
    elif result["status"] in {"installed", "already-installed", "repaired"}:
        if result["status"] == "installed":
            print("Installation succeeded.")
        elif result["status"] == "repaired":
            print("Repair succeeded.")
        else:
            print("Installation is already complete; no changes were made.")
        if result["refresh"] == "pending":
            print("Knowledge or plugin refresh is pending; installed tools remain usable with prior cached data.")
    else:
        print("Removal result: " + result["status"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
