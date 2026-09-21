#!/usr/bin/env python3
"""Copy reviewed release inputs into a plugin export's vendor directory."""
from __future__ import annotations

import argparse
from pathlib import Path
import shutil


WHEEL_NAME = "omarchy_community_knowledge_tools-0.3.1-py3-none-any.whl"


def stage(wheel: Path, setup: Path, destination: Path):
    wheel, setup, destination = Path(wheel), Path(setup), Path(destination)
    if wheel.name != WHEEL_NAME or not wheel.is_file():
        raise ValueError(f"wheel must be the reviewed {WHEEL_NAME}")
    if not setup.is_file():
        raise ValueError("setup script does not exist")
    destination.mkdir(parents=True, exist_ok=True)
    targets = [destination / WHEEL_NAME, destination / "omarchy-knowledge-setup.py"]
    shutil.copyfile(wheel, targets[0])
    shutil.copyfile(setup, targets[1])
    return targets


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--wheel", required=True, type=Path)
    parser.add_argument("--setup", required=True, type=Path)
    parser.add_argument("--destination", default=Path("vendor"), type=Path)
    options = parser.parse_args(argv)
    for path in stage(options.wheel, options.setup, options.destination):
        print(path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
