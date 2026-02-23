"""
DrupalMind — Memory Store
Redis-backed shared memory for all agents.
Falls back to in-memory dict if Redis is unavailable.
"""
import os
import json
import time
import logging
from typing import Any, Optional

logger = logging.getLogger(__name__)

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
        plan = self.get_build_plan()
        
        # Ensure plan is a dict
        if not isinstance(plan, dict):
            logger.warning(f"build_plan is not a dict: {type(plan)}, recreating")
            plan = {"tasks": []}
        
        tasks = plan.get("tasks", [])
        if not isinstance(tasks, list):
            tasks = []
            
        for task in tasks:
            if isinstance(task, dict) and task.get("id") == task_id:
                task["status"] = status
                task["detail"] = detail
                break
        
        plan["tasks"] = tasks
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
        """Clear memory for a specific job, or all if no job_id provided."""
        if job_id:
            # Only clear keys related to this job
            prefix = f"job_{job_id}"
            keys = self.list_keys(prefix)
            for key in keys:
                self.delete(key)
        else:
            # Clear all memory
            keys = self.list_keys()
            for key in keys:
                self.delete(key)

    # ── v2: Capability Envelopes (ProbeAgent) ───────────────────

    def get_capability_envelope(self, component: str) -> Optional[dict]:
        """Get capability envelope for a specific component."""
        return self.get(f"capability_envelopes/{component}")

    def set_capability_envelope(self, component: str, envelope: dict):
        """Store capability envelope for a component (persists in Redis)."""
        self.set(f"capability_envelopes/{component}", envelope)

    def list_capability_envelopes(self) -> list[str]:
        """List all available capability envelopes."""
        return [k.replace("capability_envelopes/", "", 1) for k in self.list_keys("capability_envelopes/")]

    # ── v2: Mapping Manifest (MappingAgent) ────────────────────

    def get_mapping_manifest(self) -> Optional[dict]:
        """Get the current mapping manifest from MappingAgent."""
        return self.get("mapping_manifest")

    def set_mapping_manifest(self, manifest: dict):
        """Store mapping manifest with confidence scores."""
        self.set("mapping_manifest", manifest)

    def get_mapping_for_element(self, element_id: str) -> Optional[dict]:
        """Get mapping for a specific source element."""
        manifest = self.get_mapping_manifest()
        if manifest and "mappings" in manifest:
            for m in manifest["mappings"]:
                if m.get("element_id") == element_id:
                    return m
        return None

    # ── v2: Gap Report (QAAgent) ─────────────────────────────────

    def get_gap_report(self) -> Optional[dict]:
        """Get the current gap report."""
        return self.get("gap_report")

    def set_gap_report(self, report: dict):
        """Store gap report with compromises and screenshots."""
        self.set("gap_report", report)

    def add_gap_item(self, element: str, component: str, fidelity: float, compromise: str):
        """Add an item to the gap report."""
        report = self.get_gap_report() or {"items": [], "total_fidelity": 0}
        report["items"].append({
            "element": element,
            "component_used": component,
            "fidelity_score": fidelity,
            "compromise": compromise,
        })
        # Recalculate average fidelity
        if report["items"]:
            scores = [i["fidelity_score"] for i in report["items"]]
            report["total_fidelity"] = sum(scores) / len(scores)
        self.set_gap_report(report)

    # ── v2: Global Knowledge Base (Cross-Migration Learning) ──

    def get_global_knowledge(self) -> dict:
        """Get global knowledge base with learnings from all migrations."""
        return self.get("global_knowledge_base") or {
            "successful_mappings": [],
            "component_tips": [],
            "failure_patterns": [],
            "fidelity_benchmarks": {},
        }

    def add_successful_mapping(self, source_element: str, drupal_component: str, tips: list):
        """Record a successful mapping for future reference."""
        knowledge = self.get_global_knowledge()
        knowledge["successful_mappings"].append({
            "source_element": source_element,
            "drupal_component": drupal_component,
            "tips": tips,
            "timestamp": time.time(),
        })
        # Keep only last 100 learnings
        if len(knowledge["successful_mappings"]) > 100:
            knowledge["successful_mappings"] = knowledge["successful_mappings"][-100:]
        self.set("global_knowledge_base", knowledge)

    def add_failure_pattern(self, pattern: str, root_cause: str, solution: str):
        """Record a failure pattern and its solution."""
        knowledge = self.get_global_knowledge()
        knowledge["failure_patterns"].append({
            "pattern": pattern,
            "root_cause": root_cause,
            "solution": solution,
            "timestamp": time.time(),
        })
        if len(knowledge["failure_patterns"]) > 50:
            knowledge["failure_patterns"] = knowledge["failure_patterns"][-50:]
        self.set("global_knowledge_base", knowledge)

    # ── v2: Visual Diff Results ──────────────────────────────────

    def get_visual_diff(self, scope: str) -> Optional[dict]:
        """Get visual diff results for a component or page scope."""
        return self.get(f"visual_diff/{scope}")

    def set_visual_diff(self, scope: str, diff_result: dict):
        """Store visual diff result (component or page)."""
        self.set(f"visual_diff/{scope}", diff_result)

    # ── v2: Human Review State ───────────────────────────────────

    def get_review_decisions(self) -> dict:
        """Get human review decisions for gap report items."""
        return self.get("review_decisions") or {}

    def set_review_decision(self, item_id: str, decision: str, detail: str = ""):
        """Store a review decision (accept/request_alternative/exclude/manual)."""
        decisions = self.get_review_decisions()
        decisions[item_id] = {
            "decision": decision,
            "detail": detail,
            "timestamp": time.time(),
        }
        self.set("review_decisions", decisions)

    def all_review_items_decided(self) -> bool:
        """Check if all gap report items have been reviewed."""
        report = self.get_gap_report()
        decisions = self.get_review_decisions()
        if not report or not report.get("items"):
            return True  # No items = nothing to review
        return len(decisions) >= len(report["items"])


# Singleton instance shared across agents in the same process
memory = MemoryStore()
