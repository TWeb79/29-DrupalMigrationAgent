"""
DrupalMind Agent API
FastAPI server exposing agent orchestration endpoints.
"""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI(title="DrupalMind Agents", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/health")
def health():
    return {"status": "ok", "agents": "ready"}

@app.post("/build")
def start_build(payload: dict):
    """
    Start a new build job.
    Payload: { "url": "https://...", "mode": "migrate|describe", "description": "..." }
    """
    # TODO: trigger OrchestratorAgent
    return {"job_id": "placeholder", "status": "queued"}

@app.get("/build/{job_id}")
def get_build_status(job_id: str):
    """Get status and logs for a build job."""
    return {"job_id": job_id, "status": "in_progress", "logs": []}
