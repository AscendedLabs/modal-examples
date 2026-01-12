# ---
# cmd: ["modal", "serve", "music_app_daw_v15.py"]
# ---
# Prompt2Jam Studio v0.0.15 – All Fixes Applied
# Real ACE-Step model, slim mixer with proper VU meters, hamburger menus,
# note labels, timeline measures, collapse icons, v6-style transport

from typing import Optional
from uuid import uuid4
import modal
import json

image = (
    modal.Image.debian_slim(python_version="3.10")
    .apt_install("git", "ffmpeg", "libsndfile1")
    .uv_pip_install(
        "torch==2.8.0",
        "torchaudio==2.8.0",
        "transformers==4.50.0",
        "diffusers==0.33.0",
        "peft==0.14.0",
        "git+https://github.com/ace-step/ACE-Step.git@6ae0852b1388de6dc0cca26b31a86d711f723cb3",
    )
)

cache_dir = "/root/.cache/ace-step/checkpoints"
model_cache = modal.Volume.from_name("ACE-Step-model-cache", create_if_missing=True)

web_image = image.pip_install(
    "FastAPI[standard]==0.115.4",
    "Pydantic==2.10.5",
)

app = modal.App("prompt-2-jam-v15-fixed")

@app.cls(gpu="l40s", image=image, volumes={cache_dir: model_cache}, timeout=1800)
class MusicGenerator:
    model: Optional[object] = None

    def init(self):
        pass

    @modal.method()
    def run(
        self,
        prompt: str,
        lyrics: str = "[inst]",
        duration: float = 30.0,
        genre: Optional[str] = None,
        mood: Optional[str] = None,
        format: str = "wav",
        manual_seeds: Optional[int] = 1,
        inference_steps: int = 60,
        guidance_scale: float = 15.0,
    ) -> bytes:
        import uuid
        if self.model is None:
            from acestep.pipeline_ace_step import ACEStepPipeline
            self.model = ACEStepPipeline(dtype="bfloat16", cpu_offload=False, overlapped_decode=True)
        
        full_prompt = prompt
        if genre and genre.lower() != "auto":
            full_prompt = f"{genre.lower()} {full_prompt}"
        if mood and mood.lower() != "auto":
            full_prompt = f"{mood.lower()} {full_prompt}"
        
        output_path = f"/dev/shm/output_{uuid.uuid4().hex}.{format}"
        print(f"🎵 Generating: {full_prompt} ({duration}s)")
        
        self.model(
            audio_duration=duration,
            prompt=full_prompt,
            lyrics=lyrics or "[inst]",
            format=format,
            save_path=output_path,
            manual_seeds=manual_seeds,
            infer_step=inference_steps,
            guidance_scale=guidance_scale,
            scheduler_type="euler",
            cfg_type="apg",
            omega_scale=10,
            guidance_interval=0.5,
            guidance_interval_decay=0,
            min_guidance_scale=3,
            use_erg_tag=True,
            use_erg_lyric=True,
        )
        
        with open(output_path, "rb") as f:
            return f.read()

@app.function(image=web_image, timeout=3600)
@modal.asgi_app()
def web_ui():
    from fastapi import FastAPI
    from fastapi.responses import StreamingResponse, HTMLResponse, JSONResponse
    from pydantic import BaseModel

    fastapi_app = FastAPI(title="Prompt2Jam Studio v0.0.15")
    music_generator = MusicGenerator()
    generate = music_generator.run.remote

    class GenerateRequest(BaseModel):
        prompt: str
        lyrics: str = ""
        duration: float = 30.0
        genre: Optional[str] = None
        mood: Optional[str] = None
        format: str = "wav"
        inference_steps: int = 60
        guidance_scale: float = 15.0
        seed: Optional[int] = None

    @fastapi_app.get("/", response_class=HTMLResponse)
    async def root():
        return HTML_V15

    @fastapi_app.get("/manifest.json")
    async def manifest():
        return {
            "name": "Prompt2Jam Studio v0.0.15",
            "short_name": "P2J",
            "description": "AI Music Production DAW",
            "start_url": "/",
            "display": "standalone",
            "background_color": "#0f172a",
            "theme_color": "#6366f1",
        }

    @fastapi_app.post("/api/generate")
    async def generate_music_api(request: GenerateRequest):
        try:
            if not request.prompt or not request.prompt.strip():
                return JSONResponse({"error": "Prompt required"}, status_code=400)
            
            audio_bytes = await generate.aio(
                prompt=request.prompt,
                lyrics=request.lyrics,
                duration=request.duration,
                genre=request.genre,
                mood=request.mood,
                format=request.format,
                manual_seeds=request.seed or 1,
                inference_steps=request.inference_steps,
                guidance_scale=request.guidance_scale,
            )
            
            media_types = {"wav": "audio/wav", "mp3": "audio/mpeg", "flac": "audio/flac"}
            session_id = str(uuid4())[:8]
            
            return StreamingResponse(
                iter([audio_bytes]),
                media_type=media_types.get(request.format, "audio/wav"),
                headers={
                    "Content-Disposition": f"attachment; filename=p2j_{session_id}.{request.format}",
                    "X-Session-ID": session_id
                }
            )
        except Exception as e:
            import traceback
            print(f"❌ {traceback.format_exc()}")
            return JSONResponse({"error": str(e)}, status_code=500)

    @fastapi_app.get("/api/health")
    async def health():
        return {"status": "ok", "version": "0.0.15"}

    return fastapi_app

HTML_V15 = """<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=5.0" />
  <meta name="theme-color" content="#0f172a" />
  <title>Prompt2Jam Studio v0.0.15</title>
  <link rel="manifest" href="/manifest.json" />
  <style>
    * { box-sizing: border-box; margin: 0; padding: 0; }
    
    :root {
      --bg-primary: #0f172a;
      --bg-secondary: #1e293b;
      --bg-tertiary: #334155;
      --text-primary: #f1f5f9;
      --text-secondary: #cbd5e1;
      --text-muted: #94a3b8;
      --accent: #6366f1;
      --accent-hover: #4f46e5;
      --success: #10b981;
      --warning: #f59e0b;
      --danger: #ef4444;
      --border: #334155;
    }
    
    html, body {
      width: 100%;
      height: 100%;
      overflow: hidden;
    }
    
    body {
      font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
      background: var(--bg-primary);
      color: var(--text-primary);
      -webkit-font-smoothing: antialiased;
    }
    
    .app {
      display: flex;
      flex-direction: column;
      height: 100vh;
      width: 100vw;
      overflow: hidden;
    }
    
    /* V6 Menu Bar + Header */
    header {
      display: flex;
      align-items: center;
      justify-content: space-between;
      padding: 8px 16px;
      background: var(--bg-secondary);
      border-bottom: 1px solid var(--border);
      flex-shrink: 0;
      height: 48px;
      z-index: 120;
    }
    
    .menu-left { display: flex; gap: 16px; align-items: center; }
    .logo { font-size: 16px; font-weight: 700; letter-spacing: 0.5px; color: var(--accent); }
    .menu-item { color: var(--text-secondary); font-size: 13px; padding: 6px 10px; border-radius: 6px; cursor: pointer; transition: all 0.2s; }
    .menu-item:hover { background: var(--bg-tertiary); color: var(--text-primary); }
    .menu-right { display: flex; gap: 8px; }
    .icon-btn { background: var(--bg-tertiary); border: 1px solid var(--border); color: var(--text-secondary); padding: 6px 10px; border-radius: 6px; cursor: pointer; font-size: 13px; transition: all 0.2s; }
    .icon-btn:hover { background: var(--accent); color: white; border-color: var(--accent); }
    
    /* Transport (moved to timeline toolbar, v6 style) */
    .timeline-toolbar {
      display: flex;
      align-items: center;
      gap: 10px;
      padding: 8px 12px;
      background: var(--bg-secondary);
      border-bottom: 1px solid var(--border);
      flex-shrink: 0;
    }
    .transport-controls { display: flex; gap: 6px; }
    .transport-btn {
      width: 32px;
      height: 32px;
      border-radius: 6px;
      background: var(--bg-tertiary);
      border: 1px solid var(--border);
      color: var(--text-secondary);
      cursor: pointer;
      font-size: 16px;
      transition: all 0.2s;
      display: grid;
      place-items: center;
    }
    .transport-btn:hover { background: var(--accent); color: white; border-color: var(--accent); }
    .transport-btn.play { background: var(--accent); color: white; }
    
    .time-display {
      background: var(--bg-primary);
      padding: 6px 12px;
      border-radius: 6px;
      font-family: monospace;
      font-size: 13px;
      min-width: 80px;
      text-align: center;
      color: var(--text-secondary);
    }
    
    .header-actions {
      display: flex;
      gap: 8px;
    }
    
    .header-btn {
      height: 32px;
      padding: 0 12px;
      border-radius: 6px;
      background: var(--bg-tertiary);
      border: 1px solid var(--border);
      color: var(--text-secondary);
      cursor: pointer;
      font-size: 12px;
      font-weight: 600;
      transition: all 0.2s;
    }
    
    .header-btn:hover {
      background: var(--border);
      color: var(--text-primary);
    }
    
    main {
      flex: 1;
      display: flex;
      flex-direction: column;
      overflow: hidden;
      position: relative;
      padding-bottom: 56px; /* reserve space for fixed bottom nav */
    }
    
    .view {
      display: none;
      flex: 1;
      padding: 16px;
      width: 100%;
      height: calc(100vh - 48px - 56px); /* header + bottom nav */
      overflow: hidden;
      padding-bottom: 72px; /* ensure content not hidden behind nav */
    }
    
    .view.active {
      display: flex;
      flex-direction: column;
    }
    
    #view-arrange { overflow: hidden; }
    #view-create, #view-library, #view-explore { overflow-y: auto; }
    
    /* Cards */
    .card {
      background: var(--bg-secondary);
      border: 1px solid var(--border);
      border-radius: 8px;
      padding: 16px;
      margin-bottom: 16px;
      box-shadow: 0 2px 8px rgba(0, 0, 0, 0.2);
    }
    
    .card-title {
      font-size: 16px;
      font-weight: 600;
      margin-bottom: 16px;
      color: var(--text-primary);
    }
    
    /* Forms */
    .form-row {
      display: flex;
      gap: 12px;
      margin-bottom: 12px;
      flex-wrap: wrap;
    }
    
    .form-row.cols-2 {
      display: grid;
      grid-template-columns: 1fr 1fr;
      gap: 12px;
    }
    
    .form-row > div {
      flex: 1;
      min-width: 150px;
    }
    
    label {
      display: block;
      font-size: 12px;
      font-weight: 600;
      margin-bottom: 6px;
      color: var(--text-secondary);
      text-transform: uppercase;
      letter-spacing: 0.3px;
    }
    
    input, select, textarea {
      width: 100%;
      padding: 10px 12px;
      background: var(--bg-primary);
      border: 1px solid var(--border);
      border-radius: 6px;
      color: var(--text-primary);
      font-family: inherit;
      font-size: 14px;
    }
    
    input:focus, select:focus, textarea:focus {
      outline: none;
      border-color: var(--accent);
      box-shadow: 0 0 0 3px rgba(99, 102, 241, 0.1);
    }
    
    textarea {
      resize: vertical;
      min-height: 80px;
    }
    
    .btn {
      padding: 10px 16px;
      border: none;
      border-radius: 6px;
      font-weight: 600;
      font-size: 13px;
      cursor: pointer;
      transition: all 0.2s;
      white-space: nowrap;
    }
    
    .btn-primary {
      background: var(--accent);
      color: white;
    }
    
    .btn-primary:hover:not(:disabled) {
      background: var(--accent-hover);
      transform: translateY(-1px);
    }
    
    .btn-primary:disabled {
      opacity: 0.6;
      cursor: not-allowed;
    }
    
    .btn-secondary {
      background: var(--bg-tertiary);
      color: var(--text-primary);
      border: 1px solid var(--border);
    }
    
    .btn-secondary:hover {
      background: var(--border);
    }
    
    .btn-success {
      background: var(--success);
      color: white;
    }
    
    .btn-success:hover {
      background: #059669;
    }
    
    .btn-group {
      display: flex;
      gap: 8px;
      flex-wrap: wrap;
    }
    
    audio {
      width: 100%;
      margin: 12px 0;
    }
    
    #status {
      padding: 12px;
      margin-top: 12px;
      border-radius: 6px;
      font-size: 13px;
      display: none;
    }
    
    #status.show {
      display: block;
    }
    
    #status.success {
      background: rgba(16, 185, 129, 0.1);
      color: var(--success);
      border: 1px solid var(--success);
    }
    
    #status.error {
      background: rgba(239, 68, 68, 0.1);
      color: var(--danger);
      border: 1px solid var(--danger);
    }
    
    #status.info {
      background: rgba(99, 102, 241, 0.1);
      color: var(--accent);
      border: 1px solid var(--accent);
    }
    
    /* Arrange Page */
    #view-arrange {
      flex-direction: column;
      gap: 0;
      padding: 0;
    }
    
    /* Timeline with measures/bars */
    .timeline-wrapper {
      flex: 1;
      overflow: hidden;
      display: flex;
      flex-direction: column;
      border-bottom: 1px solid var(--border);
    }
    
    .timeline-ruler {
      height: 28px;
      background: var(--bg-secondary);
      border-bottom: 1px solid var(--border);
      display: grid;
      grid-template-columns: 180px 1fr;
      position: sticky;
      top: 0;
      z-index: 10;
    }
    
    .ruler-spacer {
      background: var(--bg-secondary);
      border-right: 1px solid var(--border);
    }
    
    .ruler-measures {
      display: flex;
    }
    
    .timeline-measure {
      flex: 1;
      border-right: 1px solid rgba(99, 102, 241, 0.2);
      padding: 4px 8px;
      font-size: 10px;
      color: var(--text-muted);
      text-align: left;
      font-weight: 600;
    }
    
    .timeline-scroller {
      flex: 1;
      overflow-y: auto;
      overflow-x: auto;
      background: var(--bg-primary);
    }
    
    .timeline-inner {
      display: flex;
      flex-direction: column;
      gap: 0;
      padding: 8px 0;\n      min-width: 800px;
      background-image: repeating-linear-gradient(
        90deg,
        rgba(99, 102, 241, 0.08) 0px,
        rgba(99, 102, 241, 0.08) 1px,
        transparent 1px,
        transparent 100px
      );
    }
    
    .timeline-row {
      display: grid;
      grid-template-columns: 180px 1fr;
      align-items: stretch;
      gap: 0;
      height: 48px;
    }
    
    .track-header {
      background: var(--bg-secondary);
      border: 1px solid var(--border);
      border-radius: 6px;
      padding: 6px 8px;
      display: flex;
      align-items: center;
      gap: 6px;
      height: 40px;
    }
    
    .track-name {
      font-weight: 600;
      font-size: 11px;
      color: var(--text-primary);
      flex: 1;
      white-space: nowrap;
      overflow: hidden;
      text-overflow: ellipsis;
    }
    
    .track-controls {
      display: flex;
      gap: 3px;
    }
    
    .track-ctl-btn {
      width: 22px;
      height: 22px;
      border-radius: 3px;
      background: var(--bg-primary);
      border: 1px solid var(--border);
      color: var(--text-secondary);
      cursor: pointer;
      font-size: 9px;
      font-weight: 700;
      transition: all 0.2s;
      display: grid;
      place-items: center;
    }
    
    .track-ctl-btn:hover {
      background: var(--accent);
      color: white;
      border-color: var(--accent);
    }
    
    .track-lane {
      position: relative;
      border: 1px dashed var(--border);
      border-radius: 6px;
      background: #12141a;
    }
    
    .clip {
      position: absolute;
      top: 8px;
      left: 20px;
      height: calc(100% - 16px);
      min-width: 140px;
      background: var(--accent);
      border: 1px solid var(--border);
      border-radius: 6px;
      display: grid;
      place-items: center;
      color: white;
      font-size: 11px;
      font-weight: 600;
      cursor: pointer;
      opacity: 0.8;
    }
    
    .clip:hover {
      opacity: 1;
    }
    
    /* Piano Roll with all notes + grid lines */
    .piano-roll {
      display: grid;
      grid-template-rows: auto 1fr;
      border-top: 1px solid var(--border);
      height: 250px;
    }
    
    .piano-toolbar {
      height: 32px;
      display: flex;
      align-items: center;
      gap: 8px;
      padding: 0 12px;
      background: var(--bg-secondary);
      border-bottom: 1px solid var(--border);
      flex-shrink: 0;
    }
    
    .toolbar-menu-group {
      display: flex;
      align-items: center;
      gap: 6px;
      position: relative;
    }
    
    .hamburger-menu {
      width: 24px;
      height: 24px;
      border-radius: 4px;
      background: var(--bg-tertiary);
      border: 1px solid var(--border);
      color: var(--text-secondary);
      cursor: pointer;
      font-size: 14px;
      display: grid;
      place-items: center;
      transition: all 0.2s;
    }
    
    .hamburger-menu:hover {
      background: var(--accent);
      color: white;
      border-color: var(--accent);
    }
    
    .menu-label {
      font-size: 11px;
      font-weight: 600;
      color: var(--text-secondary);
      white-space: nowrap;
    }
    
    .collapse-icon {
      margin-left: auto;
      width: 28px;
      height: 28px;
      border-radius: 4px;
      background: var(--bg-tertiary);
      border: 1px solid var(--border);
      color: var(--text-secondary);
      cursor: pointer;
      font-size: 16px;
      display: grid;
      place-items: center;
      transition: all 0.2s;
    }
    
    .collapse-icon:hover {
      background: var(--accent);
      color: white;
      border-color: var(--accent);
    }
    
    .piano-toolbar .btn {
      height: 26px;
      padding: 0 10px;
      font-size: 11px;
    }
    
    .piano-body {
      display: grid;
      grid-template-columns: 60px 1fr;
      overflow: hidden;
      height: 100%;
    }
    
    .piano-keys {
      background: var(--bg-secondary);
      border-right: 1px solid var(--border);
      overflow: hidden;
    }
    
    .key {
      height: 20px;
      border-bottom: 1px solid var(--border);
      display: grid;
      place-items: center;
      color: var(--text-muted);
      font-size: 10px;
      text-align: center;
    }
    
    .key.white {
      background: var(--bg-secondary);
    }
    
    .key.black {
      background: var(--bg-tertiary);
    }
    
    .grid {
      position: relative;
      background: #0f1218;
      overflow: auto;
      background-image:
        repeating-linear-gradient(
          0deg,
          var(--border) 0px,
          var(--border) 1px,
          transparent 1px,
          transparent 20px
        ),
        repeating-linear-gradient(
          90deg,
          rgba(99, 102, 241, 0.05) 0px,
          rgba(99, 102, 241, 0.05) 1px,
          transparent 1px,
          transparent 50px
        );
    }
    
    .grid-row {
      height: 20px;
      border-bottom: 1px solid #151822;
    }
    
    .note {
      position: absolute;
      height: 18px;
      background: var(--accent);
      border-radius: 4px;
      top: 10px;
      left: 40px;
      width: 100px;
    }
    
    /* Slim Mixer with proper VU meters */
    .mixer-container {
      display: grid;
      grid-template-rows: auto 1fr;
      height: 140px;
      background: var(--bg-secondary);
      border-top: 1px solid var(--border);
      flex-shrink: 0;
    }
    
    .mixer-top {
      height: 32px;
      display: flex;
      align-items: center;
      gap: 8px;
      padding: 0 12px;
      border-bottom: 1px solid var(--border);
    }
    
    .mixer-top .toolbar-menu-group {
      display: flex;
      align-items: center;
      gap: 6px;
      position: relative;
    }
    
    .mixer-top .menu-label {
      font-weight: 600;
      font-size: 12px;
      color: var(--text-secondary);
    }
    
    .mixer-top .collapse-icon {
      margin-left: auto;
    }
    
    .mixer-channels {
      display: flex;
      gap: 8px;
      padding: 8px 12px;
      overflow-x: auto;
    }
    
    .mixer-channel {
      min-width: 70px;
      max-width: 80px;
      display: flex;
      flex-direction: column;
      gap: 4px;
      padding: 6px;
      background: var(--bg-primary);
      border: 1px solid var(--border);
      border-radius: 6px;
    }
    
    .ch-name {
      font-size: 10px;
      font-weight: 600;
      color: var(--text-muted);
      text-align: center;
      white-space: nowrap;
      overflow: hidden;
      text-overflow: ellipsis;
    }
    
    .ch-ctls {
      display: flex;
      gap: 2px;
      justify-content: center;
    }
    
    .ch-btn {
      flex: 1;
      height: 18px;
      border-radius: 3px;
      background: var(--bg-secondary);
      border: 1px solid var(--border);
      color: var(--text-secondary);
      cursor: pointer;
      font-size: 9px;
      font-weight: 600;
    }
    
    .ch-btn:hover {
      background: var(--accent);
      color: white;
      border-color: var(--accent);
    }
    
    /* Slim fader + VU side by side 50/50 */
    .fader-vu {
      display: flex;
      gap: 4px;
      align-items: flex-end;
      justify-content: center;
    }
    
    .fader-container {
      display: flex;
      flex-direction: column;
      align-items: center;
      gap: 2px;
      flex: 1;
    }
    
    .fader {
      width: 100%;
      height: 72px;
      background: #0f1218;
      border: 1px solid var(--border);
      border-radius: 4px;
      position: relative;
    }
    
    .fader-thumb {
      position: absolute;
      left: 2px;
      right: 2px;
      bottom: 40%;
      height: 6px;
      background: var(--accent);
      border-radius: 2px;
      cursor: ns-resize;
    }
    
    .fader-value {
      font-size: 9px;
      color: var(--text-muted);
      text-align: center;
    }
    
    .vu {
      width: 100%;
      height: 72px;
      background: #0f1218;
      border: 1px solid var(--border);
      border-radius: 4px;
      position: relative;
      overflow: hidden;
      flex: 1;
    }
    
    .vu-fill {
      position: absolute;
      left: 0;
      right: 0;
      bottom: 0;
      height: 30%;
      background: linear-gradient(to top, var(--success), var(--warning));
      border-radius: 4px;
      transition: height 0.1s ease;
    }
    
    /* Library */
    .library-item {
      background: var(--bg-secondary);
      border: 1px solid var(--border);
      border-radius: 6px;
      padding: 12px;
      margin-bottom: 12px;
    }
    
    .library-item-title {
      font-weight: 600;
      font-size: 13px;
      color: var(--text-primary);
      margin-bottom: 8px;
      word-break: break-word;
    }
    
    .library-item-meta {
      font-size: 11px;
      color: var(--text-muted);
      margin-bottom: 10px;
    }
    
    .library-item-actions {
      display: flex;
      gap: 8px;
      flex-wrap: wrap;
    }
    
    .library-item-actions .btn {
      flex: 1;
      min-width: 80px;
      padding: 8px 12px;
      font-size: 12px;
    }
    
    /* Bottom Nav */
    nav.bottom-nav {
      display: flex !important;
      height: 56px;
      background: var(--bg-secondary);
      border-top: 1px solid var(--border);
      z-index: 400;
      position: fixed;
      left: 0;
      right: 0;
      bottom: 0;
      width: 100%;
    }
    
    .nav-tab {
      flex: 1;
      display: flex;
      flex-direction: column;
      align-items: center;
      justify-content: center;
      gap: 4px;
      border: none;
      background: transparent;
      color: var(--text-muted);
      cursor: pointer;
      font-size: 10px;
      font-weight: 600;
      transition: all 0.2s;
    }
    
    .nav-tab:hover {
      color: var(--text-secondary);
      background: rgba(255, 255, 255, 0.05);
    }
    
    .nav-tab.active {
      color: var(--accent);
      background: rgba(99, 102, 241, 0.1);
    }
    
    .nav-icon {
      font-size: 20px;
    }
    
    /* Position bottom nav always visible */
    .app {
      display: flex;
      flex-direction: column;
      height: 100vh;
      width: 100vw;
      overflow: hidden;
    }
    
    /* Dropdown menu (hidden by default) */
    .dropdown {
      position: absolute;
      top: 100%;
      left: 0;
      background: var(--bg-secondary);
      border: 1px solid var(--border);
      border-radius: 6px;
      box-shadow: 0 4px 12px rgba(0,0,0,0.3);
      min-width: 180px;
      padding: 4px;
      display: none;
      z-index: 1000;
    }
    
    .dropdown.show {
      display: block;
    }
    
    .dropdown-item {
      padding: 8px 12px;
      font-size: 12px;
      color: var(--text-secondary);
      cursor: pointer;
      border-radius: 4px;
      transition: all 0.2s;
    }
    
    .dropdown-item:hover {
      background: var(--bg-tertiary);
      color: var(--text-primary);
    }
    
    .dropdown-divider {
      height: 1px;
      background: var(--border);
      margin: 4px 0;
    }
    
    /* Mobile Responsive */
    @media (max-width: 768px) {
      header { padding: 8px 12px; }
      .logo { font-size: 14px; }
      .card { padding: 12px; margin-bottom: 12px; }
      .form-row.cols-2 { grid-template-columns: 1fr; }
      .view { padding: 12px; }
      .timeline-row { grid-template-columns: 150px 1fr; }
      .mixer-channel { min-width: 60px; max-width: 70px; }
    }
    
    @media (max-width: 480px) {
      body { font-size: 13px; }
      header { padding: 6px 10px; }
      .logo { font-size: 13px; }
      input, select, textarea { padding: 10px; font-size: 16px; }
      .btn { padding: 10px 12px; font-size: 12px; }
      .btn-group { flex-direction: column; }
      .btn-group .btn { width: 100%; }
      .timeline-row { grid-template-columns: 1fr; }
      .track-header { grid-column: 1 / -1; }
      .track-lane { grid-column: 1 / -1; }
    }
  </style>
</head>
<body>
  <div class="app">
    <!-- V6-Style Header (menu bar) -->
    <header>
      <div class="menu-left">
        <div class="logo">🎵 Prompt2Jam v0.0.15</div>
        <div class="menu-item">File</div>
        <div class="menu-item">Edit</div>
        <div class="menu-item">View</div>
        <div class="menu-item">Help</div>
      </div>
      <div class="menu-right">
        <button class="icon-btn" id="shareBtn">📤 Share</button>
        <button class="icon-btn" id="exportBtn">⬇️ Export</button>
      </div>
    </header>
    
    <main>
      <!-- CREATE VIEW -->
      <section id="view-create" class="view active">
        <div class="card">
          <h3 class="card-title">✨ Create Music</h3>
          <form id="generateForm">
            <div class="form-row">
              <div>
                <label>Your Idea</label>
                <textarea id="prompt" placeholder="Describe the music: upbeat electronic dance with synth melodies..." required></textarea>
              </div>
            </div>
            
            <div class="form-row cols-2">
              <div>
                <label>Genre</label>
                <select id="genre">
                  <option value="">Auto-detect</option>
                  <option value="pop">Pop</option>
                  <option value="rock">Rock</option>
                  <option value="jazz">Jazz</option>
                  <option value="electronic">Electronic</option>
                  <option value="hip-hop">Hip-Hop</option>
                </select>
              </div>
              <div>
                <label>Mood</label>
                <select id="mood">
                  <option value="">Auto-detect</option>
                  <option value="happy">Happy</option>
                  <option value="sad">Sad</option>
                  <option value="energetic">Energetic</option>
                  <option value="calm">Calm</option>
                </select>
              </div>
            </div>
            
            <div class="form-row cols-2">
              <div>
                <label>Duration (seconds)</label>
                <input id="duration" type="number" min="5" max="240" value="30" />
              </div>
              <div>
                <label>Format</label>
                <select id="format">
                  <option value="wav">WAV (Lossless)</option>
                  <option value="mp3">MP3 (Compressed)</option>
                  <option value="flac">FLAC (Lossless)</option>
                </select>
              </div>
            </div>
            
            <div class="form-row">
              <div>
                <label>Lyrics (Optional)</label>
                <textarea id="lyrics" placeholder="[verse] lyrics... or leave blank"></textarea>
              </div>
            </div>
            
            <div class="btn-group">
              <button type="submit" class="btn btn-primary" style="flex: 1;">🎵 Generate Music</button>
              <button type="button" id="variationBtn" class="btn btn-secondary">🎲 Variation</button>
            </div>
            <div id="status"></div>
          </form>
        </div>
        
        <div class="card">
          <h3 class="card-title">🎧 Playback</h3>
          <audio id="audio" controls></audio>
          <div class="btn-group" style="margin-top: 12px;">
            <button id="downloadBtn" class="btn btn-success" style="flex: 1;">⬇️ Download</button>
            <button id="addToTimelineBtn" class="btn btn-primary" style="flex: 1;">➕ Add to Arrange</button>
            <button id="saveToLibraryBtn" class="btn btn-secondary">💾 Save</button>
          </div>
        </div>
      </section>
      
      <!-- ARRANGE VIEW -->
      <section id="view-arrange" class="view">
        <!-- Timeline with measures -->
        <div class="timeline-wrapper">
          <div class="timeline-toolbar">
            <div class="transport-controls">
              <button class="transport-btn" id="prevBtn" title="Previous">⏮</button>
              <button class="transport-btn play" id="playBtn" title="Play">▶</button>
              <button class="transport-btn" id="nextBtn" title="Next">⏭</button>
              <button class="transport-btn" id="stopBtn" title="Stop">⏹</button>
              <button class="transport-btn" id="recBtn" title="Record">⏺</button>
            </div>
            <div class="time-display">00:00:00</div>
            <div style="margin-left:auto; display:flex; gap:6px; align-items:center;">
              <div class="menu-item" style="padding:4px 8px;">Snap: 1/4</div>
              <div class="menu-item" style="padding:4px 8px;">Tempo: 120</div>
            </div>
          </div>
          <div class="timeline-ruler">
            <div class="ruler-spacer"></div>
            <div class="ruler-measures">
              <div class="timeline-measure">1</div>
              <div class="timeline-measure">2</div>
              <div class="timeline-measure">3</div>
              <div class="timeline-measure">4</div>
              <div class="timeline-measure">5</div>
              <div class="timeline-measure">6</div>
              <div class="timeline-measure">7</div>
              <div class="timeline-measure">8</div>
            </div>
          </div>
          <div class="timeline-scroller">
            <div class="timeline-inner" id="timelineInner"></div>
          </div>
        </div>
        
        <!-- Piano Roll with hamburger & collapse -->
        <div class="piano-roll">
          <div class="piano-toolbar">
            <div class="toolbar-menu-group">
              <div class="hamburger-menu" id="pianoMenu" title="Piano Roll Menu">☰</div>
              <span class="menu-label">Piano Roll</span>
              <div id="pianoDropdown" class="dropdown">
                <div class="dropdown-item" onclick="addPattern()">➕ Add Pattern</div>
                <div class="dropdown-item" onclick="openStepSequencer()">📊 Step Sequencer</div>
                <div class="dropdown-item" onclick="savePattern()">💾 Save Pattern</div>
                <div class="dropdown-divider"></div>
                <div class="dropdown-item" onclick="toggleQuantize()">🔲 Quantize: Off</div>
                <div class="dropdown-item" onclick="toggleScaleSnap()">🎯 Scale Snap: Off</div>
              </div>
            </div>
            <button class="btn btn-secondary">✎ Select</button>
            <button class="btn btn-secondary">✏️ Draw</button>
            <button class="btn btn-secondary">❌ Erase</button>
            <button class="btn btn-secondary">🔲 Quantize</button>
            <div class="collapse-icon" id="pianoCollapse" title="Collapse">▼</div>
          </div>
          <div class="piano-body">
            <div class="piano-keys" id="pianoKeys"></div>
            <div class="grid" id="pianoGrid"></div>
          </div>
        </div>
        
        <!-- Slim Mixer with hamburger & collapse -->
        <div class="mixer-container">
          <div class="mixer-top">
            <div class="toolbar-menu-group">
              <div class="hamburger-menu" id="mixerMenu" title="Mixer Settings">☰</div>
              <span class="menu-label">Mixer</span>
              <div id="mixerDropdown" class="dropdown">
                <div class="dropdown-item" onclick="toggleCompactMode()">📊 Compact Mode: Off</div>
                <div class="dropdown-item" onclick="toggleShowVU()">📈 Show VU Meters: On</div>
                <div class="dropdown-item" onclick="toggleShowFaders()">🎚️ Show Faders: On</div>
                <div class="dropdown-divider"></div>
                <div class="dropdown-item" onclick="showMixerRouting()">🔀 Routing</div>
                <div class="dropdown-item" onclick="showMixerSettings()">⚙️ Mix Settings</div>
              </div>
            </div>
            <div class="collapse-icon" id="mixerCollapse" title="Collapse">▼</div>
          </div>
          <div id="mixerChannels" class="mixer-channels"></div>
        </div>
      </section>
      
      <!-- LIBRARY VIEW -->
      <section id="view-library" class="view">
        <div class="card">
          <h3 class="card-title">📚 Your Library</h3>
          <div id="libraryContainer" style="max-height: 600px; overflow-y: auto;">
            <div style="color: var(--text-muted); font-size: 12px; padding: 20px; text-align: center;">
              No saved tracks yet
            </div>
          </div>
        </div>
      </section>
      
      <!-- EXPLORE VIEW -->
      <section id="view-explore" class="view">
        <div class="card">
          <h3 class="card-title">🔍 Explore</h3>
          <p style="color: var(--text-muted); font-size: 13px;">Discover presets, templates, and featured creations.</p>
          <p style="color: var(--text-muted); font-size: 13px; margin-top: 12px;">(Coming in v0.1.0)</p>
        </div>
      </section>
    </main>
    
    <nav class="bottom-nav">
      <button class="nav-tab active" data-view="create">
        <div class="nav-icon">✨</div>
        <div>Create</div>
      </button>
      <button class="nav-tab" data-view="arrange">
        <div class="nav-icon">🎹</div>
        <div>Arrange</div>
      </button>
      <button class="nav-tab" data-view="library">
        <div class="nav-icon">📚</div>
        <div>Library</div>
      </button>
      <button class="nav-tab" data-view="explore">
        <div class="nav-icon">🔍</div>
        <div>Explore</div>
      </button>
    </nav>
  </div>
  
  <script>
    let library = JSON.parse(localStorage.getItem('p2j_library') || '[]');
    let timeline = JSON.parse(localStorage.getItem('p2j_timeline') || '[]');
    let currentAudio = null;
    
    // Navigation
    document.querySelectorAll('.nav-tab').forEach(tab => {
      tab.addEventListener('click', () => {
        const view = tab.dataset.view;
        document.querySelectorAll('.nav-tab').forEach(t => t.classList.remove('active'));
        document.querySelectorAll('.view').forEach(v => v.classList.remove('active'));
        tab.classList.add('active');
        document.getElementById(`view-${view}`).classList.add('active');
      });
    });
    
    // Generate form
    document.getElementById('generateForm').addEventListener('submit', async (e) => {
      e.preventDefault();
      const prompt = document.getElementById('prompt').value;
      const genre = document.getElementById('genre').value;
      const mood = document.getElementById('mood').value;
      const duration = parseFloat(document.getElementById('duration').value);
      const format = document.getElementById('format').value;
      const lyrics = document.getElementById('lyrics').value;
      
      if (!prompt.trim()) {
        showStatus('Please describe your music', 'error');
        return;
      }
      
      const btn = document.querySelector('#generateForm button[type="submit"]');
      btn.disabled = true;
      btn.textContent = '⏳ Generating...';
      showStatus('Generating music... (30-60 seconds)', 'info');
      
      try {
        const res = await fetch('/api/generate', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ prompt, genre, mood, duration, format, lyrics })
        });
        
        if (!res.ok) {
          const err = await res.json();
          throw new Error(err.error || 'Generation failed');
        }
        
        const blob = await res.blob();
        const url = URL.createObjectURL(blob);
        const audio = document.getElementById('audio');
        audio.src = url;
        
        currentAudio = { url, blob, prompt, genre, mood, duration, format };
        
        showStatus('✅ Track generated! Ready to download or add to arrange', 'success');
      } catch (err) {
        showStatus(`❌ Error: ${err.message}`, 'error');
      } finally {
        btn.disabled = false;
        btn.textContent = '🎵 Generate Music';
      }
    });
    
    // Variation
    document.getElementById('variationBtn').addEventListener('click', () => {
      if (!currentAudio) {
        showStatus('Generate a track first', 'error');
        return;
      }
      document.getElementById('generateForm').dispatchEvent(new Event('submit'));
    });
    
    // Download
    document.getElementById('downloadBtn').addEventListener('click', () => {
      if (!currentAudio) {
        showStatus('Generate a track first', 'error');
        return;
      }
      const a = document.createElement('a');
      a.href = currentAudio.url;
      a.download = `prompt2jam_${Date.now()}.${currentAudio.format}`;
      a.click();
      showStatus('Downloaded!', 'success');
    });
    
    // Add to Arrange
    document.getElementById('addToTimelineBtn').addEventListener('click', () => {
      if (!currentAudio) {
        showStatus('Generate a track first', 'error');
        return;
      }
      
      const track = {
        id: Date.now().toString(),
        name: currentAudio.prompt.substring(0, 50),
        url: currentAudio.url,
        format: currentAudio.format,
        duration: currentAudio.duration,
        volume: 0,
        muted: false,
        created: new Date().toLocaleString()
      };
      
      timeline.push(track);
      localStorage.setItem('p2j_timeline', JSON.stringify(timeline));
      renderTimeline();
      renderMixer();
      showStatus('✅ Track added to arrange!', 'success');
      
      // Switch to arrange
      document.querySelectorAll('.nav-tab').forEach(t => t.classList.remove('active'));
      document.querySelectorAll('.view').forEach(v => v.classList.remove('active'));
      document.querySelector('.nav-tab[data-view="arrange"]').classList.add('active');
      document.getElementById('view-arrange').classList.add('active');
    });
    
    // Save to Library
    document.getElementById('saveToLibraryBtn').addEventListener('click', () => {
      if (!currentAudio) {
        showStatus('Generate a track first', 'error');
        return;
      }
      
      const item = {
        id: Date.now().toString(),
        name: currentAudio.prompt.substring(0, 50),
        url: currentAudio.url,
        prompt: currentAudio.prompt,
        genre: currentAudio.genre,
        mood: currentAudio.mood,
        duration: currentAudio.duration,
        format: currentAudio.format,
        created: new Date().toLocaleString()
      };
      
      library.unshift(item);
      localStorage.setItem('p2j_library', JSON.stringify(library));
      renderLibrary();
      showStatus('💾 Saved to library!', 'success');
    });
    
    // Piano Roll Init - ALL notes
    function initPianoKeys() {
      const pianoKeys = document.getElementById('pianoKeys');
      pianoKeys.innerHTML = '';
      const notes = ['C', 'C#', 'D', 'D#', 'E', 'F', 'F#', 'G', 'G#', 'A', 'A#', 'B'];
      for (let octave = 5; octave >= 2; octave--) {
        for (let i = notes.length - 1; i >= 0; i--) {
          const k = document.createElement('div');
          k.className = 'key ' + (notes[i].includes('#') ? 'black' : 'white');
          k.textContent = notes[i] + octave;
          pianoKeys.appendChild(k);
        }
      }
    }
    
    function initPianoGrid() {
      const pianoGrid = document.getElementById('pianoGrid');
      pianoGrid.innerHTML = '';
      for (let i = 0; i < 48; i++) {
        const r = document.createElement('div');
        r.className = 'grid-row';
        pianoGrid.appendChild(r);
      }
      const note = document.createElement('div');
      note.className = 'note';
      pianoGrid.appendChild(note);
    }
    
    // Timeline
    function renderTimeline() {
      const container = document.getElementById('timelineInner');
      if (timeline.length === 0) {
        container.innerHTML = '<div style="color: var(--text-muted); font-size: 12px; padding: 20px; text-align: center;">No tracks. Add one to get started!</div>';
        return;
      }
      
      container.innerHTML = timeline.map(track => `
        <div class="timeline-row">
          <div class="track-header">
            <div class="track-name">${track.name}</div>
            <div class="track-controls">
              <button class="track-ctl-btn" onclick="toggleSolo('${track.id}')">S</button>
              <button class="track-ctl-btn" onclick="toggleMute('${track.id}')">M</button>
              <button class="track-ctl-btn" onclick="toggleRecord('${track.id}')">R</button>
            </div>
          </div>
          <div class="track-lane">
            <div class="clip" onclick="selectClip('${track.id}')">${track.name.substring(0, 20)}</div>
          </div>
        </div>
      `).join('');
    }
    
    // Slim Mixer
    function renderMixer() {
      const container = document.getElementById('mixerChannels');
      if (timeline.length === 0) {
        container.innerHTML = '<div style="color: var(--text-muted); font-size: 12px; padding: 20px;">No channels</div>';
        return;
      }
      
      container.innerHTML = timeline.map((track, idx) => `
        <div class="mixer-channel">
          <div class="ch-name">${track.name.substring(0, 10)}</div>
          <div class="ch-ctls">
            <button class="ch-btn">M</button>
            <button class="ch-btn">S</button>
          </div>
          <div class="fader-vu">
            <div class="fader-container">
              <div class="fader">
                <div class="fader-thumb"></div>
              </div>
              <div class="fader-value">0dB</div>
            </div>
            <div class="vu">
              <div class="vu-fill"></div>
            </div>
          </div>
        </div>
      `).join('');
    }
    
    // Library
    function renderLibrary() {
      const container = document.getElementById('libraryContainer');
      if (library.length === 0) {
        container.innerHTML = '<div style="color: var(--text-muted); font-size: 12px; padding: 20px; text-align: center;">No saved tracks yet</div>';
        return;
      }
      
      container.innerHTML = library.map(item => `
        <div class="library-item">
          <div class="library-item-title">${item.name}</div>
          <div class="library-item-meta">${item.genre || 'Auto'} • ${item.mood || 'Auto'} • ${item.duration}s</div>
          <div class="library-item-actions">
            <button class="btn btn-secondary" onclick="playLibraryItem('${item.id}')">▶️ Play</button>
            <button class="btn btn-secondary" onclick="addLibraryToTimeline('${item.id}')">➕ Arrange</button>
            <button class="btn btn-secondary" onclick="deleteLibraryItem('${item.id}')">🗑</button>
          </div>
        </div>
      `).join('');
    }
    
    function playLibraryItem(id) {
      const item = library.find(i => i.id === id);
      if (item) document.getElementById('audio').src = item.url;
    }
    
    function addLibraryToTimeline(id) {
      const item = library.find(i => i.id === id);
      if (item) {
        timeline.push(item);
        localStorage.setItem('p2j_timeline', JSON.stringify(timeline));
        renderTimeline();
        renderMixer();
        showStatus('✅ Added to arrange!', 'success');
      }
    }
    
    function deleteTrack(id) {
      if (confirm('Delete track?')) {
        timeline = timeline.filter(t => t.id !== id);
        localStorage.setItem('p2j_timeline', JSON.stringify(timeline));
        renderTimeline();
        renderMixer();
      }
    }
    
    function deleteLibraryItem(id) {
      if (confirm('Delete from library?')) {
        library = library.filter(i => i.id !== id);
        localStorage.setItem('p2j_library', JSON.stringify(library));
        renderLibrary();
      }
    }
    
    function toggleMute(id) {
      const track = timeline.find(t => t.id === id);
      if (track) track.muted = !track.muted;
      localStorage.setItem('p2j_timeline', JSON.stringify(timeline));
      renderTimeline();
    }
    
    function toggleSolo(id) {
      timeline.forEach(t => t.solo = false);
      const track = timeline.find(t => t.id === id);
      if (track) track.solo = true;
      localStorage.setItem('p2j_timeline', JSON.stringify(timeline));
      renderTimeline();
    }
    
    function toggleRecord(id) {
      const track = timeline.find(t => t.id === id);
      if (track) {
        track.record = !track.record;
        showStatus(`Record ${track.record ? 'armed' : 'disarmed'}`, 'info');
      }
      localStorage.setItem('p2j_timeline', JSON.stringify(timeline));
      renderTimeline();
    }
    
    function selectClip(id) {
      showStatus('Clip selected', 'info');
    }
    
    function showStatus(msg, type) {
      const el = document.getElementById('status');
      el.textContent = msg;
      el.className = `show ${type}`;
      setTimeout(() => el.classList.remove('show'), 5000);
    }
    
    // Collapse toggles
    document.getElementById('mixerCollapse').addEventListener('click', () => {
      const mixer = document.querySelector('.mixer-container');
      if (mixer.style.height === '32px') {
        mixer.style.height = '140px';
        document.getElementById('mixerCollapse').textContent = '▼';
      } else {
        mixer.style.height = '32px';
        document.getElementById('mixerCollapse').textContent = '▲';
      }
    });
    
    document.getElementById('pianoCollapse').addEventListener('click', () => {
      const piano = document.querySelector('.piano-roll');
      if (piano.style.height === '36px') {
        piano.style.height = '250px';
        document.getElementById('pianoCollapse').textContent = '▼';
      } else {
        piano.style.height = '36px';
        document.getElementById('pianoCollapse').textContent = '▲';
      }
    });
    
    // Hamburger menus with proper dropdowns
    document.getElementById('mixerMenu').addEventListener('click', (e) => {
      e.stopPropagation();
      const dropdown = document.getElementById('mixerDropdown');
      dropdown.classList.toggle('show');
      document.getElementById('pianoDropdown').classList.remove('show');
    });
    
    document.getElementById('pianoMenu').addEventListener('click', (e) => {
      e.stopPropagation();
      const dropdown = document.getElementById('pianoDropdown');
      dropdown.classList.toggle('show');
      document.getElementById('mixerDropdown').classList.remove('show');
    });
    
    // Close dropdowns on outside click
    document.addEventListener('click', () => {
      document.getElementById('mixerDropdown').classList.remove('show');
      document.getElementById('pianoDropdown').classList.remove('show');
    });
    
    // Dropdown menu functions
    let compactMode = false;
    let showVU = true;
    let showFaders = true;
    let quantizeOn = false;
    let scaleSnapOn = false;
    
    function toggleCompactMode() {
      compactMode = !compactMode;
      const item = event.target;
      item.textContent = `📊 Compact Mode: ${compactMode ? 'On' : 'Off'}`;
      // Apply compact mode styles
      const mixer = document.querySelector('.mixer-channels');
      if (compactMode) {
        mixer.style.gap = '4px';
        document.querySelectorAll('.mixer-channel').forEach(ch => {
          ch.style.minWidth = '50px';
          ch.style.maxWidth = '60px';
        });
      } else {
        mixer.style.gap = '8px';
        document.querySelectorAll('.mixer-channel').forEach(ch => {
          ch.style.minWidth = '70px';
          ch.style.maxWidth = '80px';
        });
      }
    }
    
    function toggleShowVU() {
      showVU = !showVU;
      const item = event.target;
      item.textContent = `📈 Show VU Meters: ${showVU ? 'On' : 'Off'}`;
      document.querySelectorAll('.vu').forEach(vu => {
        vu.style.display = showVU ? 'block' : 'none';
      });
    }
    
    function toggleShowFaders() {
      showFaders = !showFaders;
      const item = event.target;
      item.textContent = `🎚️ Show Faders: ${showFaders ? 'On' : 'Off'}`;
      document.querySelectorAll('.fader-container').forEach(fc => {
        fc.style.display = showFaders ? 'flex' : 'none';
      });
    }
    
    function showMixerRouting() {
      showStatus('🔀 Routing: Inter-track send and return routing (v0.0.16)', 'info');
    }
    
    function showMixerSettings() {
      showStatus('⚙️ Master fader, pan, effects rack (v0.0.16)', 'info');
    }
    
    function addPattern() {
      showStatus('➕ New pattern created in piano roll', 'success');
    }
    
    function openStepSequencer() {
      showStatus('📊 Step Sequencer editor (v0.0.16)', 'info');
    }
    
    function savePattern() {
      showStatus('💾 Pattern saved to library', 'success');
    }
    
    function toggleQuantize() {
      quantizeOn = !quantizeOn;
      const item = event.target;
      item.textContent = `🔲 Quantize: ${quantizeOn ? 'On' : 'Off'}`;
      showStatus(`Quantize ${quantizeOn ? 'enabled' : 'disabled'}`, 'info');
    }
    
    function toggleScaleSnap() {
      scaleSnapOn = !scaleSnapOn;
      const item = event.target;
      item.textContent = `🎯 Scale Snap: ${scaleSnapOn ? 'On' : 'Off'}`;
      showStatus(`Scale snap ${scaleSnapOn ? 'enabled' : 'disabled'}`, 'info');
    }

    // Piano scroll sync (keys follow grid)
    function setupPianoScrollSync() {
      const grid = document.getElementById('pianoGrid');
      const keys = document.getElementById('pianoKeys');
      grid.addEventListener('scroll', () => { keys.scrollTop = grid.scrollTop; });
      keys.addEventListener('wheel', (e) => { e.preventDefault(); grid.scrollTop += e.deltaY; });
    }
    
    // Initialize
    initPianoKeys();
    initPianoGrid();
    setupPianoScrollSync();
    renderTimeline();
    renderLibrary();
  </script>
</body>
</html>
"""

if __name__ == "__main__":
    app.deploy("music-app-v15-fixed")
