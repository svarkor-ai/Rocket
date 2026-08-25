import json
from pathlib import Path
from typing import Any

CACHE_DIR = "cache"


def _cache_path(key: str, data_dir: str) -> Path:
    return Path(data_dir) / CACHE_DIR / f"{key}.json"


def cache_read(key: str, data_dir: str) -> Any:
    """Read a cached value. Returns None if missing or corrupt."""
    p = _cache_path(key, data_dir)
    if not p.exists():
        return None
    try:
        with open(p, 'r') as f:
            return json.load(f)
    except (json.JSONDecodeError, IOError):
        return None


def cache_write(key: str, value: Any, data_dir: str) -> None:
    """Write a value to the JSON cache."""
    p = _cache_path(key, data_dir)
    p.parent.mkdir(parents=True, exist_ok=True)
    with open(p, 'w') as f:
        json.dump(value, f, default=str)


def cache_invalidate(key: str, data_dir: str) -> None:
    """Remove a cached value."""
    p = _cache_path(key, data_dir)
    if p.exists():
        p.unlink()
