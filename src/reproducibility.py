"""Hashes and run manifest. Artifacts stay out of Git; the manifest is the evidence."""

from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path
from typing import Any

from src.mlflow.tracking import current_environment, current_git_commit


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def sha256_json(payload: Any) -> str:
    encoded = json.dumps(payload, sort_keys=True, default=str).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def write_manifest(path: Path, payload: dict[str, Any]) -> dict[str, Any]:
    path.parent.mkdir(parents=True, exist_ok=True)
    document = {
        "python": sys.version.split()[0],
        "git_commit": current_git_commit(),
        "environment": current_environment({}),
        **payload,
    }
    path.write_text(json.dumps(document, indent=2, default=str), encoding="utf-8")
    return document
