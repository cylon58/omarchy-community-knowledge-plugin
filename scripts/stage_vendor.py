#!/usr/bin/env python3
"""Copy reviewed release inputs into a plugin export's vendor directory."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import re
import shutil


WHEEL_NAME = "omarchy_community_knowledge_tools-0.4.1-py3-none-any.whl"


def stage(wheel: Path, setup: Path, destination: Path, *, toolkit_revision: str):
    wheel, setup, destination = Path(wheel), Path(setup), Path(destination)
    if wheel.name != WHEEL_NAME or not wheel.is_file():
        raise ValueError(f"wheel must be the reviewed {WHEEL_NAME}")
    if not setup.is_file():
        raise ValueError("setup script does not exist")
    if not re.fullmatch(r"[0-9a-f]{40}", toolkit_revision):
        raise ValueError("toolkit_revision must be a full published commit SHA")
    destination.mkdir(parents=True, exist_ok=True)
    targets = [destination / WHEEL_NAME, destination / "omarchy-knowledge-setup.py"]
    shutil.copyfile(wheel, targets[0])
    shutil.copyfile(setup, targets[1])
    hashes = [hashlib.sha256(path.read_bytes()).hexdigest() for path in targets]
    release = {
        "toolkit_repository": "cylon58/omarchy-community-knowledge-tools",
        "toolkit_revision": toolkit_revision,
        "version": WHEEL_NAME.split("-")[1],
        "wheel_sha256": hashes[0],
        "setup_sha256": hashes[1],
    }
    (destination / "RELEASE.json").write_text(
        json.dumps(release, indent=2) + "\n", encoding="utf-8",
    )
    (destination / "SHA256SUMS").write_text(
        "".join(f"{digest}  {path.name}\n" for digest, path in zip(hashes, targets)),
        encoding="utf-8",
    )
    return targets


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--wheel", required=True, type=Path)
    parser.add_argument("--setup", required=True, type=Path)
    parser.add_argument("--toolkit-revision", required=True,
                        help="Full published tools commit used to build the artifacts")
    parser.add_argument("--destination", default=Path("vendor"), type=Path)
    options = parser.parse_args(argv)
    for path in stage(options.wheel, options.setup, options.destination,
                      toolkit_revision=options.toolkit_revision):
        print(path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
