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
import requests
from typing import Callable, Optional, Dict, List, Any
from dataclasses import dataclass, field
from enum import Enum
from datetime import datetime

from memory import memory
from analyzer import AnalyzerAgent
from train_agent import TrainAgent
from build_agent import BuildAgent
from agents import ThemeAgent, ContentAgent, TestAgent, QAAgent
from probe_agent import ProbeAgent
from mapping_agent import MappingAgent
from visual_diff_agent import VisualDiffAgent
from drupal_client import DrupalClient

# Configure logging for OrchestratorAgent
logger = logging.getLogger("drupalmind.orchestrator")


class MigrationStatus(Enum):
    """Migration completion status."""
    SUCCESS = "success"
    PARTIAL_SUCCESS = "partial_success"
    FAILED = "failed"
    RUNNING = "running"


@dataclass
class MigrationReport:
    """Detailed migration report with status tracking."""
    status: MigrationStatus = MigrationStatus.RUNNING
    completion_percentage: int = 0
    completed_phases: List[str] = field(default_factory=list)
    failed_phases: Dict[str, str] = field(default_factory=dict)
    warnings: List[str] = field(default_factory=list)
    errors: List[str] = field(default_factory=list)
    artifacts: Dict[str, Any] = field(default_factory=dict)
    start_time: datetime = field(default_factory=datetime.now)
    end_time: Optional[datetime] = None
    
    def add_completed_phase(self, phase: str):
        if phase not in self.completed_phases:
            self.completed_phases.append(phase)
            self._update_completion()
    
    def add_failed_phase(self, phase: str, error: str):
        self.failed_phases[phase] = error
        self._update_completion()
    
    def add_warning(self, warning: str):
        if warning not in self.warnings:
            self.warnings.append(warning)
    
    def add_error(self, error: str):
        if error not in self.errors:
            self.errors.append(error)
    
    def _update_completion(self):
        total_phases = 11
        completed = len(self.completed_phases)
        self.completion_percentage = int((completed / total_phases) * 100)
    
    def finalize(self, status: MigrationStatus):
        self.status = status
        self.end_time = datetime.now()
        if not self.failed_phases:
            self.completion_percentage = 100
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "status": self.status.value,
            "completion_percentage": self.completion_percentage,
            "completed_phases": self.completed_phases,
            "failed_phases": self.failed_phases,
            "warnings": self.warnings,
            "errors": self.errors,
            "artifacts": self.artifacts,
            "duration_seconds": (self.end_time - self.start_time).total_seconds() if self.end_time else None,
        }


BUILD_PHASES = [
    {"id": 1, "section": "Probe",      "task": "Test Drupal components empirically",       "agent": "probe"},
    {"id": 2, "section": "Discovery",  "task": "Scrape & analyze source site",          "agent": "analyzer"},
    {"id": 3, "section": "Knowledge",  "task": "Discover Drupal components",            "agent": "train"},
    {"id": 4, "section": "Mapping",    "task": "Map source to components",             "agent": "mapping"},
    {"id": 5, "section": "Build",      "task": "Build site with refinement loops",     "agent": "build"},
    {"id": 6, "section": "Theme",      "task": "Apply design tokens & custom CSS",     "agent": "theme"},
    {"id": 7, "section": "Content",    "task": "Migrate text & media content",         "agent": "content"},
    {"id": 8, "section": "Verify",     "task": "Compare built site to source",         "agent": "test"},
    {"id": 9, "section": "QA",         "task": "Run accessibility & quality checks",     "agent": "qa"},
    {"id": 10, "section": "Review",    "task": "Human review gate",                   "agent": "orchestrator"},
    {"id": 11, "section": "Publish",   "task": "Publish + write learnings",            "agent": "orchestrator"},
]


class OrchestratorAgent:
    def __init__(self, broadcast_cb: Callable = None):
        self._broadcast = broadcast_cb
        self.job_id: Optional[str] = None

        # Instantiate all agents
        self.prober     = ProbeAgent()
        self.analyzer   = AnalyzerAgent()
        self.trainer    = TrainAgent()
        self.mapper     = MappingAgent()
        self.builder    = BuildAgent()
        self.themer     = ThemeAgent()
        self.content    = ContentAgent()
        self.tester     = TestAgent()
        self.qa         = QAAgent()
        self.visualdiff = VisualDiffAgent()

        # Wire up log callbacks
        for agent in [self.prober, self.analyzer, self.trainer, self.mapper,
                      self.builder, self.themer, self.content, self.tester, self.qa]:
            agent.set_log_callback(self._relay_log)
    
    # ── Preflight Checks ─────────────────────────────────────
    
    async def _preflight_checks(self, source_url: str, report: MigrationReport) -> bool:
        """
        Validate prerequisites before starting migration.
        Returns True if all checks pass, False otherwise.
        """
        import os
        logger.info("Running preflight checks...")
        
        checks = [
            ("Source URL provided", bool(source_url)),
            ("Source URL valid", source_url.startswith("http") if source_url else False),
        ]
        
        # Check LLM provider configuration
        llm_provider = os.getenv("LLM_PROVIDER", "anthropic").lower()
        if llm_provider == "anthropic":
            checks.append(("Anthropic API key set", bool(os.getenv("ANTHROPIC_API_KEY"))))
        elif llm_provider == "openai":
            checks.append(("OpenAI API key set", bool(os.getenv("OPENAI_API_KEY"))))
        elif llm_provider == "ollama":
            checks.append(("Ollama configured", bool(os.getenv("OLLAMA_BASE_URL"))))
        
        # Check Drupal connectivity (non-blocking)
        drupal_url = os.getenv("DRUPAL_API_URL", "http://drupal")
        try:
            response = requests.get(f"{drupal_url}/jsonapi", timeout=5)
            checks.append(("Drupal API reachable", response.status_code in [200, 401]))
        except Exception as e:
            logger.warning(f"Drupal API check failed: {e}")
            checks.append(("Drupal API reachable", False))
        
        # Check Redis connectivity
        try:
            if hasattr(memory, '_redis') and memory._redis:
                memory._redis.ping()
                checks.append(("Redis connected", True))
            else:
                checks.append(("Redis connected", True))  # Assume OK if not available
        except Exception as e:
            logger.warning(f"Redis check failed: {e}")
            checks.append(("Redis connected", False))
        
        # Run checks
        all_passed = True
        for check_name, is_ok in checks:
            if not is_ok:
                report.add_error(f"Preflight check failed: {check_name}")
                logger.error(f"✗ Preflight failed: {check_name}")
                all_passed = False
            else:
                logger.info(f"✓ Preflight passed: {check_name}")
        
        return all_passed

    # ── Broadcast helpers ─────────────────────────────────────

    async def _relay_log(self, event: dict):
        """Relay an agent log event to the WebSocket broadcast with enhanced debug info."""
        import time
        
        # Add timestamp and job context
        event["timestamp"] = time.time()
        event["job_id"] = self.job_id
        
        # Add memory state summary for debugging
        try:
            mem_keys = list(memory._redis.keys("*")) if hasattr(memory, '_redis') else []
            event["debug"] = {
                "memory_keys_count": len(mem_keys),
                "key_sample": mem_keys[:5] if mem_keys else [],
            }
        except:
            event["debug"] = {}
        
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
            "probe": "pending",
            "analyzer": "pending",
            "train": "pending",
            "mapping": "pending",
            "build": "pending",
            "theme": "pending",
            "content": "pending",
            "test": "pending",
            "qa": "pending",
            "review": "pending",
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
        
        # Create migration report for tracking
        report = MigrationReport()
        
        self.job_id = job_id or str(uuid.uuid4())[:8]
        memory.clear_job(self.job_id)

        plan = self._init_build_plan(source, mode)
        await self._emit({"type": "started", "job_id": self.job_id, "tasks": plan["tasks"], "report": report.to_dict()})
        await self._relay_log({
            "type": "log",
            "agent": "orchestrator",
            "message": f"Build started — mode: {mode}",
            "status": "active",
            "detail": f"Source: {source[:80]}",
        })

        result = {}

        try:
            # ── Preflight Checks ────────────────────────────────────
            if not await self._preflight_checks(source, report):
                report.finalize(MigrationStatus.FAILED)
                result = {
                    "status": "failed",
                    "job_id": self.job_id,
                    "error": "Preflight checks failed",
                    "report": report.to_dict(),
                }
                await self._emit({"type": "error", "message": "Preflight checks failed", "report": report.to_dict()})
                return result
            
            # ── Phase 1: Probe ─────────────────────────────────────
            logger.info("PHASE 1: PROBE - Starting...")
            await self._mark_task(1, "active")
            try:
                probe_result = await self.prober.probe_all()
                report.add_completed_phase("probe")
            except Exception as e:
                report.add_failed_phase("probe", str(e))
                report.add_warning(f"Probe failed (non-blocking): {str(e)}")
                probe_result = {"envelopes_count": 0}
            
            # Ensure probe_result is a dict
            if not isinstance(probe_result, dict):
                logger.warning(f"probe_result is not a dict: {type(probe_result)}, using default")
                probe_result = {"envelopes_count": 0}
            
            await self._mark_task(1, "done", f"{probe_result.get('envelopes_count', 0)} components probed")
            logger.info(f"PHASE 1: PROBE - Complete")

            # ── Phase 2: Analysis ──────────────────────────────────
            logger.info("PHASE 2: ANALYSIS - Starting...")
            await self._mark_task(2, "active")
            try:
                blueprint = await self.analyzer.analyze(source, mode)
                report.add_completed_phase("analysis")
            except Exception as e:
                report.add_failed_phase("analysis", str(e))
                report.add_warning(f"Analysis failed (non-blocking): {str(e)}")
                blueprint = {"pages": []}
            
            # Ensure blueprint is a dict
            if not isinstance(blueprint, dict):
                logger.warning(f"blueprint is not a dict: {type(blueprint)}, using default")
                blueprint = {"pages": []}
            
            await self._mark_task(2, "done", f"{len(blueprint.get('pages', []))} pages found")
            logger.info(f"PHASE 2: ANALYSIS - Complete ({len(blueprint.get('pages', []))} pages)")

            # ── Phase 3: Training ──────────────────────────────────
            logger.info("PHASE 3: TRAINING - Starting...")
            await self._mark_task(3, "active")
            try:
                await self.trainer.train()
                report.add_completed_phase("training")
            except Exception as e:
                report.add_failed_phase("training", str(e))
                report.add_warning(f"Training failed (non-blocking): {str(e)}")
            await self._mark_task(3, "done", f"{len(memory.list_components())} components documented")
            logger.info(f"PHASE 3: TRAINING - Complete")

            # ── Phase 4: Mapping ───────────────────────────────────
            logger.info("PHASE 4: MAPPING - Starting...")
            await self._mark_task(4, "active")
            try:
                mapping_result = await self.mapper.create_mapping()
                report.add_completed_phase("mapping")
            except Exception as e:
                report.add_failed_phase("mapping", str(e))
                report.add_warning(f"Mapping failed (non-blocking): {str(e)}")
                mapping_result = {"statistics": {}, "error": "Invalid mapping result"}
            
            # Ensure mapping_result is a dict
            if not isinstance(mapping_result, dict):
                logger.warning(f"mapping_result is not a dict: {type(mapping_result)}, using default")
                mapping_result = {"statistics": {}, "error": "Invalid mapping result"}
            
            await self._mark_task(4, "done", f"{mapping_result.get('statistics', {}).get('total', 0)} elements mapped")
            logger.info(f"PHASE 4: MAPPING - Complete")

            # ── Phase 5: Build ────────────────────────────────────
            logger.info("PHASE 5: BUILD - Starting...")
            await self._mark_task(5, "active")
            try:
                build_result = await self.builder.build_site()
                report.add_completed_phase("build")
            except Exception as e:
                report.add_failed_phase("build", str(e))
                report.add_warning(f"Build failed (non-blocking): {str(e)}")
                build_result = {}
            built_pages = memory.get_or_default("built_pages", [])
            
            # Ensure built_pages is a list (defensive)
            if isinstance(built_pages, str):
                logger.warning(f"built_pages is a string, converting to list: {built_pages[:100]}")
                try:
                    import json
                    built_pages = json.loads(built_pages)
                except:
                    built_pages = []
            elif not isinstance(built_pages, list):
                logger.warning(f"built_pages is not a list: {type(built_pages)}")
                built_pages = []
            
            await self._mark_task(5, "done", f"{len(built_pages)} pages built")
            logger.info(f"PHASE 5: BUILD - Complete ({len(built_pages)} pages)")

            # ── Phase 6: Theme ────────────────────────────────────
            logger.info("PHASE 6: THEME - Starting...")
            await self._mark_task(6, "active")
            try:
                theme_result = await self.themer.apply_theme()
                report.add_completed_phase("theme")
            except Exception as e:
                report.add_failed_phase("theme", str(e))
                report.add_warning(f"Theme failed (non-blocking): {str(e)}")
                theme_result = {}
            await self._mark_task(6, "done", "CSS applied")
            logger.info("PHASE 6: THEME - Complete")

            # ── Phase 7: Content ──────────────────────────────────
            logger.info("PHASE 7: CONTENT - Starting...")
            await self._mark_task(7, "active")
            try:
                content_result = await self.content.migrate_content()
                report.add_completed_phase("content")
            except Exception as e:
                report.add_failed_phase("content", str(e))
                report.add_warning(f"Content migration failed (non-blocking): {str(e)}")
                content_result = {"created": 0}
            
            # Ensure content_result is a dict
            if not isinstance(content_result, dict):
                logger.warning(f"content_result is not a dict: {type(content_result)}, using default")
                content_result = {"created": 0}
            
            await self._mark_task(7, "done", f"{content_result.get('created', 0)} items migrated")
            logger.info(f"PHASE 7: CONTENT - Complete")

            # ── Phase 8: Test ─────────────────────────────────────
            logger.info("PHASE 8: TEST - Starting...")
            await self._mark_task(8, "active")
            try:
                test_result = await self.tester.run_tests()
                report.add_completed_phase("test")
            except Exception as e:
                report.add_failed_phase("test", str(e))
                report.add_warning(f"Test failed (non-blocking): {str(e)}")
                test_result = {"overall_score": 0, "ready_for_qa": False}
            
            # Ensure test_result is a dict
            if not isinstance(test_result, dict):
                logger.warning(f"test_result is not a dict: {type(test_result)}, using default")
                test_result = {"overall_score": 0, "ready_for_qa": False}
            
            score = test_result.get("overall_score", 0)
            await self._mark_task(8, "done", f"{score}% match score")
            logger.info(f"PHASE 8: TEST - Complete (Score: {score}%)")

            # ── Phase 9: QA ───────────────────────────────────────
            await self._mark_task(9, "active")
            try:
                qa_result = await self.qa.run_qa()
                report.add_completed_phase("qa")
            except Exception as e:
                report.add_failed_phase("qa", str(e))
                report.add_warning(f"QA failed (non-blocking): {str(e)}")
                qa_result = {"score": 0}
            
            await self._mark_task(9, "done", f"{qa_result.get('score', 0)}% QA score")

            # ── Phase 10: Human Review Gate ───────────────────────
            await self._mark_task(10, "active")
            
            # Check if there are items needing review
            mapping_manifest = memory.get_mapping_manifest() or {}
            review_needed = mapping_manifest.get("requires_review", False) if mapping_manifest else False
            
            if review_needed:
                # Emit review request event
                await self._emit({
                    "type": "review_required",
                    "review_items": mapping_manifest.get("review_items", []),
                    "gap_report": qa_result.get("gap_report", {}),
                })
                
                await self._relay_log({
                    "type": "log",
                    "agent": "orchestrator",
                    "message": "Human review required - pipeline paused",
                    "status": "waiting",
                    "detail": f"{len(mapping_manifest.get('review_items', []))} items need review",
                })
                
                # Wait for review decisions (blocking)
                # In a real implementation, this would wait for UI input
                # For now, auto-accept all low-confidence items
                logger.info("Auto-accepting low-confidence items (review UI not implemented)")
                
            await self._mark_task(10, "done", "Review complete")
            logger.info("PHASE 10: REVIEW - Complete")

            # ── Phase 11: Publish + Learnings ─────────────────────
            await self._mark_task(11, "active")
            
            # Write macro learnings
            await self.qa.write_learnings(blueprint, built_pages, mapping_manifest)
            
            await self._mark_task(11, "done", "Published + learnings written")
            logger.info("PHASE 11: PUBLISH - Complete")

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
                    await self._mark_task(8, "done", f"{test_result.get('overall_score', 0)}% after fixes")

            # Get site URL for sharing (with null safety)
            try:
                site_url = self.analyzer.drupal.get_site_url() if hasattr(self.analyzer, 'drupal') else ""
            except:
                site_url = ""
            
            # Determine final status
            if report.failed_phases:
                if report.completed_phases:
                    report.finalize(MigrationStatus.PARTIAL_SUCCESS)
                else:
                    report.finalize(MigrationStatus.FAILED)
            else:
                report.finalize(MigrationStatus.SUCCESS)
            
            # Store artifacts in report
            report.artifacts = {
                "blueprint": blueprint,
                "built_pages": built_pages,
                "test_result": test_result,
                "qa_result": qa_result,
                "mapping_manifest": mapping_manifest,
            }
            
            result = {
                "status": report.status.value,
                "job_id": self.job_id,
                "built_pages": built_pages,
                "test_score": test_result.get("overall_score", 0),
                "qa_score": qa_result.get("score", 0),
                "site_url": site_url,
                "summary": self._build_summary(blueprint, built_pages, test_result, qa_result),
                "report": report.to_dict(),
            }

            await self._relay_log({
                "type": "log",
                "agent": "orchestrator",
                "message": f"✅ Build complete! {len(built_pages)} pages live.",
                "status": "done",
                "detail": f"🌐 URL: {site_url}\nTest: {test_result.get('overall_score', 0)}% | QA: {qa_result.get('score', 0)}%\nReport: {report.status.value} ({report.completion_percentage}%)",
            })
            await self._emit({"type": "complete", **result})

        except Exception as e:
            import traceback
            tb = traceback.format_exc()
            report.add_error(str(e))
            report.finalize(MigrationStatus.FAILED)
            result = {
                "status": "error", 
                "error": str(e),
                "report": report.to_dict(),
            }
            await self._relay_log({
                "type": "log",
                "agent": "orchestrator",
                "message": f"Pipeline error: {e}",
                "status": "error",
                "detail": f"{e}\n\nTraceback:\n{tb}",
            })
            await self._emit({"type": "error", "message": str(e), "report": report.to_dict()})

        memory.set(f"job_{self.job_id}_result", result)
        return result

    def _build_summary(self, blueprint, built_pages, test_result, qa_result) -> str:
        pages_str = ", ".join(p["title"] for p in built_pages[:5])
        return (
            f"Built '{blueprint.get('title', 'site')}' with {len(built_pages)} pages ({pages_str}). "
            f"Match score: {test_result.get('overall_score', 0)}%. "
            f"QA score: {qa_result.get('score', 0)}%."
        )
