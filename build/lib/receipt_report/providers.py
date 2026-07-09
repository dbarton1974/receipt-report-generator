"""Loads mail-server presets from providers.json (metadata-driven configuration)."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

# providers.json is bundled inside the package (works from source and when pip-installed).
_PROVIDERS_PATH = Path(__file__).resolve().parent / "providers.json"


@dataclass(frozen=True)
class Provider:
    key: str
    label: str
    imap_host: str
    imap_port: int
    smtp_host: str
    smtp_port: int
    smtp_security: str
    setup: str


def load_providers() -> dict[str, Provider]:
    """Reads providers.json and returns a mapping of key -> Provider."""
    with open(_PROVIDERS_PATH, encoding="utf-8") as f:
        raw = json.load(f)

    providers: dict[str, Provider] = {}
    for key, val in raw.items():
        if key.startswith("_"):  # skip _comment and similar metadata keys
            continue
        providers[key] = Provider(
            key=key,
            label=val["label"],
            imap_host=val["imap_host"],
            imap_port=int(val["imap_port"]),
            smtp_host=val["smtp_host"],
            smtp_port=int(val["smtp_port"]),
            smtp_security=val.get("smtp_security", "ssl"),
            setup=val.get("setup", ""),
        )
    return providers


def get_provider(key: str) -> Provider | None:
    return load_providers().get(key.strip().lower())
