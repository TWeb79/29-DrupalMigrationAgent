"""
DrupalMind — Agent API Server
FastAPI app exposing REST + WebSocket endpoints.
WebSocket streams all agent events to the UI in real time.
"""
import json
import asyncio
import uuid
from typing import Optional

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from memory import memory
from orchestrator import OrchestratorAgent


# ── In-memory job store ───────────────────────────────────────
jobs: dict = {}


# ── WebSocket connection manager ──────────────────────────────
class ConnectionManager:
    def __init__(self):
        self.active: dict[str, set] = {}

    async def connect(self, job_id: str, ws: WebSocket):
        await ws.accept()
        self.active.setdefault(job_id, set()).add(ws)

    def disconnect(self, job_id: str, ws: WebSocket):
        if job_id in self.active:
            self.active[job_id].discard(ws)

    async def broadcast(self, job_id: str, message: dict):
        if job_id not in self.active:
            return
        dead = set()
        for ws in list(self.active.get(job_id, set())):
            try:
                await ws.send_json(message)
            except Exception:
                dead.add(ws)
        for ws in dead:
            self.active[job_id].discard(ws)


manager = ConnectionManager()


# ── App ───────────────────────────────────────────────────────
app = FastAPI(title="DrupalMind Agents", version="0.1.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ── Models ────────────────────────────────────────────────────
class BuildRequest(BaseModel):
    source: str
    mode: str = "url"
    scope: str = "full"


# ── Routes ────────────────────────────────────────────────────
@app.get("/health")
async def health():
    from drupal_client import DrupalClient
    drupal_ok = DrupalClient().health_check()
    return {
        "status": "ok",
        "drupal": "connected" if drupal_ok else "disconnected",
        "memory": memory.backend,
        "agents": "ready",
    }


@app.post("/build")
async def start_build(request: BuildRequest, background_tasks: BackgroundTasks):
    job_id = str(uuid.uuid4())[:8]
    jobs[job_id] = {"job_id": job_id, "status": "queued", "source": request.source, "mode": request.mode, "logs": []}
    background_tasks.add_task(run_build_job, job_id, request.source, request.mode)
    return {"job_id": job_id, "status": "queued", "ws_url": f"/ws/{job_id}"}


@app.get("/build/{job_id}")
async def get_build(job_id: str):
    if job_id not in jobs:
        raise HTTPException(404, "Job not found")
    return {**jobs[job_id], "result": memory.get(f"job_{job_id}_result")}


@app.get("/build/{job_id}/content-stats")
async def get_content_migration_stats(job_id: str):
    """Get detailed content migration statistics."""
    if job_id not in jobs:
        raise HTTPException(404, "Job not found")
    
    # Get migration result from memory
    result = memory.get(f"job_{job_id}_result")
    
    if not result:
        return {
            "job_id": job_id,
            "status": "no_result",
            "message": "No migration result available yet"
        }
    
    # Extract content stats from result
    stats = {
        "job_id": job_id,
        "status": result.get("status", "unknown"),
        "content_types": result.get("content_types", []),
        "total_nodes": result.get("total_nodes", 0),
        "successful_migrations": result.get("successful_migrations", 0),
        "failed_migrations": result.get("failed_migrations", 0),
        "media_files": result.get("media_files", {}),
        "templates_used": result.get("templates_used", []),
        "validation_errors": result.get("validation_errors", []),
        "warnings": result.get("warnings", []),
    }
    
    return stats


@app.get("/jobs")
async def list_jobs():
    return {"jobs": list(jobs.values())}


@app.get("/memory")
async def get_memory():
    return {"keys": memory.list_keys(), "backend": memory.backend}


@app.get("/memory/{key:path}")
async def get_memory_key(key: str):
    val = memory.get(key)
    if val is None:
        raise HTTPException(404, "Key not found")
    return {"key": key, "value": val}


@app.delete("/memory/reset")
async def reset_memory():
    memory.clear_job()
    return {"reset": True}


# ── WebSocket ─────────────────────────────────────────────────
@app.websocket("/ws/{job_id}")
async def ws_endpoint(websocket: WebSocket, job_id: str):
    await manager.connect(job_id, websocket)
    if job_id in jobs:
        await websocket.send_json({"type": "connected", "job": jobs[job_id]})
        for log in jobs[job_id].get("logs", []):
            await websocket.send_json(log)
    try:
        while True:
            data = await websocket.receive_text()
            if data == "ping":
                await websocket.send_json({"type": "pong"})
    except WebSocketDisconnect:
        manager.disconnect(job_id, websocket)


# ── Background pipeline ───────────────────────────────────────
async def run_build_job(job_id: str, source: str, mode: str):
    jobs[job_id]["status"] = "running"

    async def broadcast(event: dict):
        event["job_id"] = job_id
        jobs[job_id].setdefault("logs", []).append(event)
        if len(jobs[job_id]["logs"]) > 300:
            jobs[job_id]["logs"] = jobs[job_id]["logs"][-300:]
        await manager.broadcast(job_id, event)

    orch = OrchestratorAgent(broadcast_cb=broadcast)
    try:
        result = await orch.run(source=source, mode=mode, job_id=job_id)
        jobs[job_id]["status"] = result.get("status", "complete")
        jobs[job_id]["result"] = result
    except Exception as e:
        jobs[job_id]["status"] = "error"
        jobs[job_id]["error"] = str(e)
        await broadcast({"type": "error", "message": str(e)})
