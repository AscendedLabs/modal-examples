import { FastAPI, HTTPException, BackgroundTasks, File, UploadFile } from "fastapi";
from fastapi.responses import JSONResponse, FileResponse, StreamingResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from typing import Optional, List
from enum import Enum
import uuid
from datetime import datetime
import os
import json
import asyncio
import modal
from pathlib import Path

# ============================================================================
# MODAL SETUP (Cloud GPU Workers)
# ============================================================================

image = modal.Image.debian_slim().pip_install(
    "fastapi",
    "uvicorn",
    "librosa",
    "numpy",
    "scipy",
    "torch",
    "torchaudio",
    "diffusers",
    "transformers",
    "pydantic",
)

app_modal = modal.App("ai-song-generator-backend")

# ============================================================================
# DATA MODELS
# ============================================================================

class GenreEnum(str, Enum):
    """Supported music genres"""
    POP = "pop"
    HIP_HOP = "hip_hop"
    ROCK = "rock"
    ELECTRONIC = "electronic"
    JAZZ = "jazz"
    CLASSICAL = "classical"
    AMBIENT = "ambient"
    LOFI = "lofi"

class GenerationRequest(BaseModel):
    """AI Song Generation Request"""
    prompt: str = Field(..., min_length=5, max_length=500, description="Music generation prompt")
    genre: GenreEnum = Field(default=GenreEnum.POP)
    bpm: int = Field(default=120, ge=40, le=200)
    duration: int = Field(default=30, ge=10, le=120, description="Duration in seconds")
    key: str = Field(default="C", description="Musical key (C, Dm, Em, etc)")
    style: Optional[str] = Field(default=None, description="Optional style modifier")

class StemInfo(BaseModel):
    """Individual audio stem"""
    stem_type: str  # "vocals", "bass", "drums", "melody", "other"
    url: Optional[str] = None
    duration: float

class GenerationJob(BaseModel):
    """AI Generation Job Status"""
    job_id: str
    status: str  # "queued", "processing", "completed", "failed"
    request: GenerationRequest
    stems: Optional[List[StemInfo]] = None
    error: Optional[str] = None
    created_at: datetime
    completed_at: Optional[datetime] = None
    progress: float = Field(default=0.0, ge=0, le=100)

class Project(BaseModel):
    """Music project metadata"""
    project_id: str
    name: str
    created_at: datetime
    generation_job_id: Optional[str] = None
    stems: List[StemInfo] = []
    bpm: int
    key: str

# ============================================================================
# IN-MEMORY JOB STORE (Replace with DB for production)
# ============================================================================

jobs_store: dict[str, GenerationJob] = {}
projects_store: dict[str, Project] = {}

# ============================================================================
# FASTAPI APP
# ============================================================================

app = FastAPI(
    title="AI Song Generator API",
    description="Generate music stems using AI models",
    version="0.1.0",
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ============================================================================
# UTILITY FUNCTIONS
# ============================================================================

def create_local_storage():
    """Ensure storage directories exist"""
    Path("./output_stems").mkdir(exist_ok=True)
    Path("./projects").mkdir(exist_ok=True)

# ============================================================================
# MODAL WORKERS (GPU-based AI models)
# ============================================================================

@app_modal.function(
    image=image,
    gpu="T4",
    timeout=600,
    retries=modal.Retries(max_retries=1),
)
def generate_music_stems(
    job_id: str,
    prompt: str,
    bpm: int,
    duration: int,
    genre: str,
    key: str,
):
    """
    Generate music stems using AI models.
    
    This runs on Modal GPU workers.
    In production, this would use:
    - MusicLM / AudioCraft for generation
    - Demucs for stem separation
    - Or Replicate API for hosted models
    """
    import librosa
    import numpy as np
    from scipy.io import wavfile
    
    try:
        print(f"[Worker] Processing job {job_id}: {prompt}")
        
        # STEP 1: Generate base audio (placeholder - use MusicLM/AudioCraft in production)
        sample_rate = 44100
        num_samples = sample_rate * duration
        
        # Simulate music generation with procedural audio
        t = np.linspace(0, duration, num_samples)
        
        # Base frequency from BPM
        base_freq = bpm / 60  # Convert BPM to Hz
        
        # Simple harmonic content based on genre
        if genre == "electronic":
            audio = np.sin(2 * np.pi * 440 * t) * 0.3
            audio += np.sin(2 * np.pi * 220 * t) * 0.2
        elif genre == "lofi":
            audio = np.sin(2 * np.pi * 110 * t) * 0.2
            audio += np.sin(2 * np.pi * 220 * t) * 0.15
        else:
            audio = np.sin(2 * np.pi * 261.63 * t) * 0.25
            audio += np.sin(2 * np.pi * 329.63 * t) * 0.2
        
        # Simulate stem separation
        # In production: use Demucs or OpenUnmix
        
        stems_output = {
            "vocals": audio * 0.6,
            "bass": np.sin(2 * np.pi * 110 * t) * 0.4,
            "drums": audio * 0.7,
            "melody": audio * 0.5,
            "other": audio * 0.3,
        }
        
        # Save stems
        stem_urls = {}
        for stem_name, stem_audio in stems_output.items():
            stem_audio = np.clip(stem_audio, -1, 1)
            output_path = f"./output_stems/{job_id}_{stem_name}.wav"
            wavfile.write(output_path, sample_rate, (stem_audio * 32767).astype(np.int16))
            stem_urls[stem_name] = f"/api/stems/{job_id}/{stem_name}.wav"
        
        print(f"[Worker] Completed job {job_id}")
        return {
            "status": "completed",
            "stems": stem_urls,
            "duration": duration,
        }
    
    except Exception as e:
        print(f"[Worker] Error in job {job_id}: {str(e)}")
        return {
            "status": "failed",
            "error": str(e),
        }

# ============================================================================
# API ENDPOINTS
# ============================================================================

@app.get("/")
async def root():
    """Health check"""
    return {"message": "AI Song Generator API v0.1.0", "status": "online"}

@app.post("/api/projects")
async def create_project(name: str) -> Project:
    """Create a new music project"""
    project_id = str(uuid.uuid4())
    project = Project(
        project_id=project_id,
        name=name,
        created_at=datetime.now(),
        bpm=120,
        key="C",
    )
    projects_store[project_id] = project
    return project

@app.get("/api/projects/{project_id}")
async def get_project(project_id: str) -> Project:
    """Fetch project details"""
    if project_id not in projects_store:
        raise HTTPException(status_code=404, detail="Project not found")
    return projects_store[project_id]

@app.post("/api/generate")
async def generate_stems(request: GenerationRequest, background_tasks: BackgroundTasks):
    """
    Submit a song generation job.
    
    Returns immediately with job_id.
    Client polls /api/jobs/{job_id} for status.
    """
    job_id = str(uuid.uuid4())
    
    job = GenerationJob(
        job_id=job_id,
        status="queued",
        request=request,
        created_at=datetime.now(),
    )
    
    jobs_store[job_id] = job
    
    # Submit to Modal GPU worker (non-blocking)
    background_tasks.add_task(
        process_generation_job,
        job_id,
        request,
    )
    
    return {"job_id": job_id, "status": "queued"}

async def process_generation_job(job_id: str, request: GenerationRequest):
    """
    Process generation job on Modal worker.
    Called in background.
    """
    try:
        jobs_store[job_id].status = "processing"
        jobs_store[job_id].progress = 10.0
        
        # Call Modal worker (GPU-based)
        result = generate_music_stems.remote(
            job_id=job_id,
            prompt=request.prompt,
            bpm=request.bpm,
            duration=request.duration,
            genre=request.genre,
            key=request.key,
        )
        
        if result["status"] == "completed":
            stems = [
                StemInfo(stem_type=key, url=value, duration=request.duration)
                for key, value in result["stems"].items()
            ]
            jobs_store[job_id].stems = stems
            jobs_store[job_id].status = "completed"
            jobs_store[job_id].progress = 100.0
            jobs_store[job_id].completed_at = datetime.now()
        else:
            jobs_store[job_id].status = "failed"
            jobs_store[job_id].error = result.get("error", "Unknown error")
    
    except Exception as e:
        jobs_store[job_id].status = "failed"
        jobs_store[job_id].error = str(e)

@app.get("/api/jobs/{job_id}")
async def get_job_status(job_id: str) -> GenerationJob:
    """
    Poll job status.
    
    Returns:
    - status: queued | processing | completed | failed
    - progress: 0-100%
    - stems: list of generated stems (when completed)
    """
    if job_id not in jobs_store:
        raise HTTPException(status_code=404, detail="Job not found")
    return jobs_store[job_id]

@app.get("/api/stems/{job_id}/{stem_name}.wav")
async def download_stem(job_id: str, stem_name: str):
    """Download a specific stem WAV file"""
    stem_path = f"./output_stems/{job_id}_{stem_name}.wav"
    if not os.path.exists(stem_path):
        raise HTTPException(status_code=404, detail="Stem not found")
    return FileResponse(stem_path, media_type="audio/wav")

@app.post("/api/projects/{project_id}/import-stems")
async def import_stems_to_project(project_id: str, job_id: str) -> Project:
    """
    Import generated stems from a job into a project.
    """
    if project_id not in projects_store:
        raise HTTPException(status_code=404, detail="Project not found")
    
    if job_id not in jobs_store:
        raise HTTPException(status_code=404, detail="Job not found")
    
    job = jobs_store[job_id]
    
    if job.status != "completed":
        raise HTTPException(status_code=400, detail="Job not completed")
    
    project = projects_store[project_id]
    project.generation_job_id = job_id
    project.stems = job.stems or []
    project.bpm = job.request.bpm
    project.key = job.request.key
    
    return project

# ============================================================================
# STARTUP / SHUTDOWN
# ============================================================================

@app.on_event("startup")
async def startup():
    """Initialize storage on startup"""
    create_local_storage()
    print("AI Song Generator API started")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
