"""
DrupalMind — OrchestratorAgent
Central coordinator. Manages the build plan, dispatches
to specialist agents, and streams progress events.
"""
import json
import asyncio
import time
import uuid
import logging
from typing import Callable, Optional

from memory import memory
from analyzer import AnalyzerAgent
from train_agent import TrainAgent
from build_agent import BuildAgent
from agents import ThemeAgent, ContentAgent, TestAgent, QAAgent

# Configure logging for OrchestratorAgent
logger = logging.getLogger("drupalmind.orchestrator")


BUILD_PHASES = [
    {"id": 1, "section": "Discovery",  "task": "Scrape & analyze source site",        "agent": "analyzer"},
    {"id": 2, "section": "Knowledge",  "task": "Discover Drupal components",           "agent": "train"},
    {"id": 3, "section": "Build",      "task": "Build site structure & pages",         "agent": "build"},
    {"id": 4, "section": "Theme",      "task": "Apply design tokens & custom CSS",     "agent": "theme"},
    {"id": 5, "section": "Content",    "task": "Migrate text & media content",         "agent": "content"},
    {"id": 6, "section": "Verify",     "task": "Compare built site to source",         "agent": "test"},
    {"id": 7, "section": "QA",         "task": "Run accessibility & quality checks",   "agent": "qa"},
]


class OrchestratorAgent:
    def __init__(self, broadcast_cb: Callable = None):
        self._broadcast = broadcast_cb
        self.job_id: Optional[str] = None

        # Instantiate all agents
        self.analyzer  = AnalyzerAgent()
        self.trainer   = TrainAgent()
        self.builder   = BuildAgent()
        self.themer    = ThemeAgent()
        self.content   = ContentAgent()
        self.tester    = TestAgent()
        self.qa        = QAAgent()

        # Wire up log callbacks
        for agent in [self.analyzer, self.trainer, self.builder,
                      self.themer, self.content, self.tester, self.qa]:
            agent.set_log_callback(self._relay_log)

    # ── Broadcast helpers ─────────────────────────────────────

    async def _relay_log(self, event: dict):
        """Relay an agent log event to the WebSocket broadcast."""
        if self._broadcast:
            await self._broadcast(event)

    async def _emit(self, event: dict):
        if self._broadcast:
            await self._broadcast(event)

    async def _emit_status(self, status: str, message: str = ""):
        await self._emit({
            "type": "status",
            "status": status,
            "message": message,
            "tasks": memory.get_build_plan() or {},
            "agents": self._agent_states(),
        })

    async def _emit_progress(self):
        plan = memory.get_build_plan() or {"tasks": []}
        tasks = plan.get("tasks", [])
        done = sum(1 for t in tasks if t["status"] == "done")
        total = len(tasks) or 1
        await self._emit({
            "type": "progress",
            "percent": int((done / total) * 100),
            "done": done,
            "total": total,
            "tasks": tasks,
        })

    def _agent_states(self) -> dict:
        return {
            "orchestrator": "active",
            "analyzer": "pending",
            "train": "pending",
            "build": "pending",
            "theme": "pending",
            "content": "pending",
            "test": "pending",
            "qa": "pending",
        }

    # ── Build plan ────────────────────────────────────────────

    def _init_build_plan(self, source: str, mode: str) -> dict:
        tasks = [dict(t) for t in BUILD_PHASES]
        for t in tasks:
            t["status"] = "pending"
        plan = {
            "job_id": self.job_id,
            "source": source,
            "mode": mode,
            "tasks": tasks,
            "started_at": time.time(),
        }
        memory.set_build_plan(plan)
        return plan

    async def _mark_task(self, task_id: int, status: str, detail: str = ""):
        memory.update_task_status(task_id, status, detail)
        await self._emit_progress()

    # ── Main orchestration ────────────────────────────────────

    async def run(self, source: str, mode: str = "url", job_id: str = None) -> dict:
        """
        Full build pipeline.
        source: URL or description
        mode: "url" | "description"
        """
        logger.info(f"══════════════════════════════════════════════════════════════")
        logger.info(f"║ ORCHESTRATOR STARTING | Job ID: {job_id or 'auto'}")
        logger.info(f"║ Source: {source[:80]}... | Mode: {mode}")
        logger.info(f"══════════════════════════════════════════════════════════════")
        
        self.job_id = job_id or str(uuid.uuid4())[:8]
        memory.clear_job(self.job_id)

        plan = self._init_build_plan(source, mode)
        await self._emit({"type": "started", "job_id": self.job_id, "tasks": plan["tasks"]})
        await self._relay_log({
            "type": "log",
            "agent": "orchestrator",
            "message": f"Build started — mode: {mode}",
            "status": "active",
            "detail": f"Source: {source[:80]}",
        })

        result = {}

        try:
            # ── Phase 1: Analysis ──────────────────────────────
            logger.info("PHASE 1: ANALYSIS - Starting...")
            await self._mark_task(1, "active")
            blueprint = await self.analyzer.analyze(source, mode)
            await self._mark_task(1, "done", f"{len(blueprint.get('pages', []))} pages found")
            logger.info(f"PHASE 1: ANALYSIS - Complete ({len(blueprint.get('pages', []))} pages)")

            # ── Phase 2: Training ──────────────────────────────
            logger.info("PHASE 2: TRAINING - Starting...")
            await self._mark_task(2, "active")
            await self.trainer.train()
            await self._mark_task(2, "done", f"{len(memory.list_components())} components documented")
            logger.info(f"PHASE 2: TRAINING - Complete")

            # ── Phase 3: Build ─────────────────────────────────
            logger.info("PHASE 3: BUILD - Starting...")
            await self._mark_task(3, "active")
            build_result = await self.builder.build_site()
            built_pages = memory.get_or_default("built_pages", [])
            await self._mark_task(3, "done", f"{len(built_pages)} pages built")
            logger.info(f"PHASE 3: BUILD - Complete ({len(built_pages)} pages)")

            # ── Phase 4: Theme ─────────────────────────────────
            logger.info("PHASE 4: THEME - Starting...")
            await self._mark_task(4, "active")
            theme_result = await self.themer.apply_theme()
            await self._mark_task(4, "done", "CSS applied")
            logger.info("PHASE 4: THEME - Complete")

            # ── Phase 5: Content ───────────────────────────────
            logger.info("PHASE 5: CONTENT - Starting...")
            await self._mark_task(5, "active")
            content_result = await self.content.migrate_content()
            await self._mark_task(5, "done", f"{content_result.get('created', 0)} items migrated")
            logger.info(f"PHASE 5: CONTENT - Complete")

            # ── Phase 6: Test ──────────────────────────────────
            logger.info("PHASE 6: TEST - Starting...")
            await self._mark_task(6, "active")
            test_result = await self.tester.run_tests()
            score = test_result.get("overall_score", 0)
            await self._mark_task(6, "done", f"{score}% match score")
            logger.info(f"PHASE 6: TEST - Complete (Score: {score}%)")

            # If tests failed, attempt one more build pass
            if not test_result.get("ready_for_qa", False):
                fixes = test_result.get("fixes_needed", [])
                if fixes:
                    await self._relay_log({
                        "type": "log",
                        "agent": "orchestrator",
                        "message": f"TestAgent found {len(fixes)} issues — requesting fixes",
                        "status": "active",
                        "detail": "; ".join(fixes[:3]),
                    })
                    await self.builder.build_site()
                    test_result = await self.tester.run_tests()
                    await self._mark_task(6, "done", f"{test_result.get('overall_score', 0)}% after fixes")

            # ── Phase 7: QA ────────────────────────────────────
            await self._mark_task(7, "active")
            qa_result = await self.qa.run_qa()
            await self._mark_task(7, "done", f"{qa_result.get('score', 0)}% QA score")

            result = {
                "status": "complete",
                "job_id": self.job_id,
                "built_pages": built_pages,
                "test_score": test_result.get("overall_score", 0),
                "qa_score": qa_result.get("score", 0),
                "site_url": self.analyzer.drupal.get_site_url(),
                "summary": self._build_summary(blueprint, built_pages, test_result, qa_result),
            }

            await self._relay_log({
                "type": "log",
                "agent": "orchestrator",
                "message": f"✅ Build complete! {len(built_pages)} pages live.",
                "status": "done",
                "detail": f"Test: {test_result.get('overall_score', 0)}% | QA: {qa_result.get('score', 0)}%",
            })
            await self._emit({"type": "complete", **result})

        except Exception as e:
            result = {"status": "error", "error": str(e)}
            await self._relay_log({
                "type": "log",
                "agent": "orchestrator",
                "message": f"Pipeline error: {e}",
                "status": "error",
                "detail": str(e),
            })
            await self._emit({"type": "error", "message": str(e)})

        memory.set(f"job_{self.job_id}_result", result)
        return result

    def _build_summary(self, blueprint, built_pages, test_result, qa_result) -> str:
        pages_str = ", ".join(p["title"] for p in built_pages[:5])
        return (
            f"Built '{blueprint.get('title', 'site')}' with {len(built_pages)} pages ({pages_str}). "
            f"Match score: {test_result.get('overall_score', 0)}%. "
            f"QA score: {qa_result.get('score', 0)}%."
        )
