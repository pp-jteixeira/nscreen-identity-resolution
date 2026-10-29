"""Resolve the external PulsePoint Trino skill without machine-specific paths."""

import os
import sys
from pathlib import Path


def bootstrap():
    override = os.environ.get("PP_TRINO_SCRIPTS")
    candidates = (
        [Path(override).expanduser()]
        if override
        else [
            Path.home() / ".codex/skills/pulsepoint-trino/scripts",
            Path.home() / ".claude/skills/pulsepoint-trino/scripts",
        ]
    )
    for folder in candidates:
        if (folder / "ppconfig.py").is_file():
            sys.path.insert(0, str(folder))
            from ppconfig import bootstrap as configured_bootstrap

            return configured_bootstrap()
    raise RuntimeError(
        "PulsePoint Trino skill missing. Set PP_TRINO_SCRIPTS to its scripts directory; see README.md."
    )
