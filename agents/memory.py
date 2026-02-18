"""
DrupalMind — Memory Store
Redis-backed shared memory for all agents.
Falls back to in-memory dict if Redis is unavailable.
"""
import os
import json
import time
from typing import Any, Optional

try:
    import redis
    REDIS_AVAILABLE = True
except ImportError:
    REDIS_AVAILABLE = False


class MemoryStore:
    """
    Shared key-value memory for all agents.
    All values are JSON-serialized.
    """

    def __init__(self):
        self._local: dict = {}
        self._redis: Optional[Any] = None
        self._prefix = "drupalmind:"

        if REDIS_AVAILABLE:
            try:
                redis_url = os.getenv("REDIS_URL", "redis://redis:6379")
                self._redis = redis.from_url(redis_url, decode_responses=True)
                self._redis.ping()
            except Exception:
                self._redis = None

    @property
    def backend(self) -> str:
        return "redis" if self._redis else "local"

    def _key(self, key: str) -> str:
        return f"{self._prefix}{key}"

    def set(self, key: str, value: Any, ttl: int = None) -> bool:
        try:
            serialized = json.dumps(value, default=str)
            if self._redis:
                if ttl:
                    self._redis.setex(self._key(key), ttl, serialized)
                else:
                    self._redis.set(self._key(key), serialized)
            else:
                self._local[key] = {"value": serialized, "ts": time.time()}
            return True
        except Exception as e:
            return False

    def get(self, key: str) -> Optional[Any]:
        try:
            if self._redis:
                raw = self._redis.get(self._key(key))
            else:
                entry = self._local.get(key)
                raw = entry["value"] if entry else None

            if raw is None:
                return None
            return json.loads(raw)
        except Exception:
            return None

    def delete(self, key: str) -> bool:
        if self._redis:
            return bool(self._redis.delete(self._key(key)))
        else:
            return bool(self._local.pop(key, None))

    def list_keys(self, prefix: str = "") -> list[str]:
        """List all keys, optionally filtered by prefix."""
        if self._redis:
            pattern = f"{self._prefix}{prefix}*"
            keys = self._redis.keys(pattern)
            return [k[len(self._prefix):] for k in keys]
        else:
            return [k for k in self._local.keys() if k.startswith(prefix)]

    def append_to_list(self, key: str, item: Any) -> int:
        """Append an item to a list stored at key."""
        current = self.get(key) or []
        if not isinstance(current, list):
            current = [current]
        current.append(item)
        self.set(key, current)
        return len(current)

    def get_or_default(self, key: str, default: Any) -> Any:
        val = self.get(key)
        return val if val is not None else default

    def update_dict(self, key: str, updates: dict) -> dict:
        """Merge updates into an existing dict at key."""
        current = self.get(key) or {}
        current.update(updates)
        self.set(key, current)
        return current

    # ── Convenience helpers ───────────────────────────────────

    def get_blueprint(self) -> Optional[dict]:
        return self.get("site_blueprint")

    def set_blueprint(self, blueprint: dict):
        self.set("site_blueprint", blueprint)

    def get_component(self, name: str) -> Optional[dict]:
        return self.get(f"components/{name}")

    def set_component(self, name: str, docs: dict):
        self.set(f"components/{name}", docs)

    def list_components(self) -> list[str]:
        return [k.replace("components/", "", 1) for k in self.list_keys("components/")]

    def get_build_plan(self) -> Optional[dict]:
        return self.get("build_plan")

    def set_build_plan(self, plan: dict):
        self.set("build_plan", plan)

    def update_task_status(self, task_id: int, status: str, detail: str = ""):
        plan = self.get_build_plan() or {"tasks": []}
        for task in plan.get("tasks", []):
            if task["id"] == task_id:
                task["status"] = status
                task["detail"] = detail
                break
        self.set_build_plan(plan)

    def get_test_report(self) -> Optional[dict]:
        return self.get("test_report")

    def set_test_report(self, report: dict):
        self.set("test_report", report)

    def get_qa_report(self) -> Optional[dict]:
        return self.get("qa_report")

    def set_qa_report(self, report: dict):
        self.set("qa_report", report)

    def clear_job(self, job_id: str = None):
        """Clear all memory for a job (or all memory)."""
        keys = self.list_keys()
        for key in keys:
            self.delete(key)


# Singleton instance shared across agents in the same process
memory = MemoryStore()
