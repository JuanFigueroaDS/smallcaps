"""Persistencia simple en JSON para deduplicar alertas y cachear market caps."""
import json
import os
import time
from typing import Any, Dict


def _ensure_dir(path: str) -> None:
    d = os.path.dirname(path)
    if d:
        os.makedirs(d, exist_ok=True)


def load_json(path: str) -> Dict[str, Any]:
    if not os.path.exists(path):
        return {}
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError):
        return {}


def save_json(path: str, data: Dict[str, Any]) -> None:
    _ensure_dir(path)
    tmp_path = path + ".tmp"
    with open(tmp_path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, sort_keys=True)
    os.replace(tmp_path, path)


def prune_seen(seen: Dict[str, float], retention_hours: int) -> Dict[str, float]:
    cutoff = time.time() - retention_hours * 3600
    return {k: v for k, v in seen.items() if v >= cutoff}


def prune_cache(cache: Dict[str, Dict[str, Any]], max_age_hours: int) -> Dict[str, Dict[str, Any]]:
    cutoff = time.time() - max_age_hours * 3600
    return {k: v for k, v in cache.items() if v.get("fetched_at", 0) >= cutoff}
