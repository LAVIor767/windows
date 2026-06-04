import os
import json
import time
from pathlib import Path
from typing import Any, Optional

PROJECT_FOLDER = os.environ.get("PROJECT_FOLDER", os.path.dirname(__file__))
CACHE_DIR = Path(PROJECT_FOLDER) / "cache"
CACHE_DIR.mkdir(parents=True, exist_ok=True)

def _path_for(key: str) -> Path:
    safe_key = key.replace("/", "_").replace(":", "_")
    return CACHE_DIR / f"{safe_key}.json"


# ===== WRITE (atomic) =====
def cache_set_disk(key: str, value: Any, ttl: int = 300) -> None:
    payload = {
        "expiry": time.time() + ttl,
        "value": value
    }

    p = _path_for(key)
    tmp = p.with_suffix(".tmp")

    try:
        with tmp.open("w", encoding="utf-8") as f:
            json.dump(payload, f)

        # atomic replace
        tmp.replace(p)

    except Exception:
        try:
            tmp.unlink(missing_ok=True)
        except Exception:
            pass


# ===== READ =====
def cache_get_disk(key: str) -> Optional[Any]:
    p = _path_for(key)

    if not p.exists():
        return None

    try:
        with p.open("r", encoding="utf-8") as f:
            payload = json.load(f)

        expiry = payload.get("expiry", 0)

        if time.time() < expiry:
            return payload.get("value")

        # expired
        try:
            p.unlink(missing_ok=True)
        except Exception:
            pass

        return None

    except Exception:
        # corrupted cache → delete
        try:
            p.unlink(missing_ok=True)
        except Exception:
            pass
        return None


# ===== DELETE =====
def cache_clear(key: str) -> None:
    p = _path_for(key)
    try:
        p.unlink(missing_ok=True)
    except Exception:
        pass