"""Config + path helpers."""
from __future__ import annotations

import functools
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
CONFIG_DIR = ROOT / "config"
DATA_DIR = ROOT / "data"
STATE_DIR = DATA_DIR / "state"
WEB_DATA_DIR = ROOT / "web" / "data"


@functools.lru_cache(maxsize=None)
def load_yaml(name: str) -> dict:
    with open(CONFIG_DIR / name, "r", encoding="utf-8") as fh:
        return yaml.safe_load(fh)


def load_taxonomy() -> dict:
    return load_yaml("taxonomy.yaml")


def load_employers() -> list[dict]:
    return load_yaml("employers.yaml")["employers"]


def load_queries() -> dict:
    return load_yaml("queries.yaml")
