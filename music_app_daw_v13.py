# ---
# cmd: ["modal", "serve", "music_app_daw_v13.py"]
# ---
# Prompt2Jam Studio v0.0.13 – Complete DAW with All Features
# Landing Page (Create) from v9_fixed + Arrange Page from v11
# Timeline with inline track headers, full mixer bottom, piano roll, signal flow wired

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

app = modal.App("prompt-2-jam-v13-complete")

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

@app.function(image=web_image, timeout=1800)
@modal.asgi_app()
def web_ui():
    from fastapi import FastAPI
    from fastapi.responses import StreamingResponse, HTMLResponse, JSONResponse
    from pydantic import BaseModel

    fastapi_app = FastAPI(title="Prompt2Jam Studio v0.0.13")
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
        return HTML_V13

    @fastapi_app.get("/manifest.json")
    async def manifest():
        return {
            "name": "Prompt2Jam Studio v0.0.13",
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

    return fastapi_app

HTML_V13 = """<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=5.0" />
  <meta name="theme-color" content="#0f172a" />
  <title>Prompt2Jam Studio v0.0.13</title>
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
    
    /* HEADER */
    header {
      display: flex;
      align-items: center;
      justify-content: space-between;
      padding: 12px 16px;
      background: var(--bg-secondary);
      border-bottom: 1px solid var(--border);
      flex-shrink: 0;
      position: sticky;
      top: 0;
      z-index: 100;
    }
    
    .logo {
      font-size: 16px;
      font-weight: 700;
      letter-spacing: 0.3px;
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
    
    /* MAIN CONTENT */
    main {
      flex: 1;
      display: flex;
      overflow: hidden;
      position: relative;
    }
    
    .view {
      display: none;
      flex: 1;
      overflow-y: auto;
      padding: 16px;
      width: 100%;
    }
    
    .view.active {
      display: flex;
      flex-direction: column;
    }
    
    /* CARDS */
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
    
    /* FORMS */
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
    
    /* BUTTONS */
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
    
    /* AUDIO PLAYER */
    audio {
      width: 100%;
      margin: 12px 0;
    }
    
    /* STATUS MESSAGES */
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
    
    /* ARRANGE PAGE STYLES */
    #view-arrange {
      flex-direction: column;
      gap: 0;
      padding: 0;
    }
    
    .arrange-top {
      display: flex;
      align-items: center;
      gap: 8px;
      padding: 8px 12px;
      background: var(--bg-secondary);
      border-bottom: 1px solid var(--border);
      flex-shrink: 0;
    }
    
    .arrange-top .btn {
      height: 32px;
      padding: 0 10px;
      font-size: 12px;
    }
    
    .timeline-wrapper {
      flex: 1;
      overflow: hidden;
      display: flex;
      flex-direction: column;
      border-bottom: 1px solid var(--border);
    }
    
    .timeline-scroller {
      flex: 1;
      overflow-y: auto;
      overflow-x: auto;
    }
    
    .timeline-inner {
      display: flex;
      flex-direction: column;
      gap: 8px;
      padding: 8px;
      min-width: 800px;
    }
    
    .timeline-row {
      display: grid;
      grid-template-columns: 200px 1fr;
      align-items: stretch;
      gap: 8px;
      min-height: 60px;
    }
    
    .track-header {
      background: var(--bg-secondary);
      border: 1px solid var(--border);
      border-radius: 6px;
      padding: 8px;
      display: grid;
      grid-template-rows: auto auto;
      gap: 6px;
    }
    
    .track-name {
      font-weight: 600;
      font-size: 12px;
      color: var(--text-primary);
    }
    
    .track-controls {
      display: flex;
      gap: 4px;
    }
    
    .track-ctl-btn {
      height: 24px;
      padding: 0 8px;
      border-radius: 4px;
      background: var(--bg-primary);
      border: 1px solid var(--border);
      color: var(--text-secondary);
      cursor: pointer;
      font-size: 10px;
      font-weight: 600;
      transition: all 0.2s;
    }
    
    .track-ctl-btn:hover {
      background: var(--accent);
      color: white;
      border-color: var(--accent);
    }
    
    .track-ctl-btn.active {
      background: var(--accent);
      color: white;
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
    
    /* PIANO ROLL */
    .piano-roll {
      display: grid;
      grid-template-rows: auto 1fr;
      border-top: 1px solid var(--border);
      height: 200px;
    }
    
    .piano-toolbar {
      height: 36px;
      display: flex;
      align-items: center;
      gap: 8px;
      padding: 6px 12px;
      background: var(--bg-secondary);
      border-bottom: 1px solid var(--border);
      flex-shrink: 0;
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
    }
    
    .piano-keys {
      background: var(--bg-secondary);
      border-right: 1px solid var(--border);
      overflow-y: auto;
    }
    
    .key {
      height: 20px;
      border-bottom: 1px solid var(--border);
      display: grid;
      place-items: center;
      color: var(--text-muted);
      font-size: 10px;
    }
    
    .grid {
      position: relative;
      background: #0f1218;
      overflow: auto;
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
    
    /* MIXER */
    .mixer-container {
      display: grid;
      grid-template-rows: auto 1fr;
      height: 160px;
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
    
    .mixer-top .label {
      font-weight: 600;
      font-size: 12px;
    }
    
    .mixer-top .btn {
      height: 26px;
      padding: 0 10px;
      font-size: 11px;
      margin-left: auto;
    }
    
    .mixer-channels {
      display: flex;
      gap: 10px;
      padding: 8px 12px;
      overflow-x: auto;
    }
    
    .mixer-channel {
      min-width: 100px;
      display: flex;
      flex-direction: column;
      gap: 6px;
      padding: 8px;
      background: var(--bg-primary);
      border: 1px solid var(--border);
      border-radius: 6px;
    }
    
    .ch-name {
      font-size: 11px;
      font-weight: 600;
      color: var(--text-muted);
      text-align: center;
    }
    
    .ch-ctls {
      display: flex;
      gap: 4px;
    }
    
    .ch-btn {
      flex: 1;
      height: 20px;
      border-radius: 4px;
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
    
    .fader-vu {
      display: flex;
      gap: 4px;
      align-items: flex-end;
    }
    
    .fader {
      width: 100%;
      height: 80px;
      background: #0f1218;
      border: 1px solid var(--border);
      border-radius: 4px;
      position: relative;
    }
    
    .fader-thumb {
      position: absolute;
      left: 0;
      right: 0;
      bottom: 35%;
      height: 8px;
      background: var(--accent);
      border-radius: 3px;
    }
    
    .vu {
      width: 4px;
      height: 80px;
      background: #0f1218;
      border: 1px solid var(--border);
      border-radius: 4px;
      position: relative;
    }
    
    .vu-fill {
      position: absolute;
      left: 0;
      right: 0;
      bottom: 0;
      height: 25%;
      background: var(--success);
      border-radius: 4px;
    }
    
    /* LIBRARY */
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
    
    /* BOTTOM NAV */
    nav.bottom-nav {
      display: flex;
      height: 56px;
      background: var(--bg-secondary);
      border-top: 1px solid var(--border);
      flex-shrink: 0;
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
    
    /* MOBILE RESPONSIVE */
    @media (max-width: 768px) {
      header {
        padding: 10px 12px;
      }
      
      .logo {
        font-size: 14px;
      }
      
      .card {
        padding: 12px;
        margin-bottom: 12px;
      }
      
      .form-row.cols-2 {
        grid-template-columns: 1fr;
      }
      
      .view {
        padding: 12px;
      }
      
      .timeline-row {
        grid-template-columns: 150px 1fr;
      }
      
      .mixer-channel {
        min-width: 90px;
      }
    }
    
    @media (max-width: 480px) {
      body {
        font-size: 13px;
      }
      
      header {
        padding: 8px 12px;
      }
      
      .logo {
        font-size: 13px;
      }
      
      .card {
        padding: 12px;
        margin-bottom: 12px;
      }
      
      input, select, textarea {
        padding: 10px;
        font-size: 16px;
      }
      
      .btn {
        padding: 10px 12px;
        font-size: 12px;
      }
      
      .btn-group {
        flex-direction: column;
      }
      
      .btn-group .btn {
        width: 100%;
      }
      
      .timeline-row {
        grid-template-columns: 1fr;
      }
      
      .track-header {
        grid-column: 1 / -1;
      }
      
      .track-lane {
        grid-column: 1 / -1;
      }
      
      .mixer-channel {
        min-width: 80px;
      }
    }
  </style>
</head>
<body>
  <div class="app">
    <header>
      <div class="logo">🎵 Prompt2Jam v0.0.13</div>
      <div class="header-actions">
        <button class="header-btn" id="shareBtn">📤 Share</button>
        <button class="header-btn" id="exportBtn">⬇️ Export</button>
      </div>
    </header>
    
    <main>
      <!-- CREATE VIEW (v0.0.9 style) -->
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
                  <option value="classical">Classical</option>
                  <option value="ambient">Ambient</option>
                  <option value="funk">Funk</option>
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
                  <option value="epic">Epic</option>
                  <option value="dark">Dark</option>
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
                <textarea id="lyrics" placeholder="[verse] verse lyrics... [chorus] chorus lyrics... or leave blank for instrumental"></textarea>
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
        <div class="arrange-top">
          <button class="btn btn-secondary" id="playBtn">▶️ Play</button>
          <button class="btn btn-secondary" id="pauseBtn">⏸ Pause</button>
          <button class="btn btn-secondary" id="stopBtn">⏹ Stop</button>
          <span style="margin-left:auto;color:var(--text-muted);font-size:12px">1:1:00</span>
        </div>
        
        <div class="timeline-wrapper">
          <div class="timeline-scroller">
            <div class="timeline-inner" id="timelineInner"></div>
          </div>
        </div>
        
        <div class="piano-roll">
          <div class="piano-toolbar">
            <button class="btn btn-secondary">✎ Select</button>
            <button class="btn btn-secondary">✏️ Draw</button>
            <button class="btn btn-secondary">❌ Erase</button>
            <button class="btn btn-secondary">🔲 Quantize</button>
            <button class="btn btn-secondary">📐 Scale</button>
          </div>
          <div class="piano-body">
            <div class="piano-keys" id="pianoKeys"></div>
            <div class="grid" id="pianoGrid">
              <div class="note"></div>
            </div>
          </div>
        </div>
        
        <div class="mixer-container">
          <div class="mixer-top">
            <div class="label">🎚️ Mixer</div>
            <button id="toggleMixer" class="btn btn-secondary">Collapse</button>
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
    let lastSeed = 1;
    
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
      showStatus('Generating your music... (30-60 seconds)', 'info');
      
      try {
        const res = await fetch('/api/generate', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ prompt, genre, mood, duration, format, lyrics })
        });
        
        if (!res.ok) throw new Error('Generation failed');
        
        const blob = await res.blob();
        const url = URL.createObjectURL(blob);
        const audio = document.getElementById('audio');
        audio.src = url;
        
        currentAudio = { url, blob, prompt, genre, mood, duration, format };
        lastSeed = Math.floor(Math.random() * 1000000);
        
        showStatus('✅ Track generated! Ready to download or add to arrange', 'success');
      } catch (err) {
        showStatus(`❌ Error: ${err.message}`, 'error');
      } finally {
        btn.disabled = false;
        btn.textContent = '🎵 Generate Music';
      }
    });
    
    // Variation
    document.getElementById('variationBtn').addEventListener('click', async () => {
      if (!currentAudio) {
        showStatus('Generate a track first', 'error');
        return;
      }
      lastSeed = Math.floor(Math.random() * 1000000);
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
    
    // Add to Arrange / Timeline
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
      
      // Switch to arrange view
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
    
    // Piano keys init
    function initPianoKeys() {
      const pianoKeys = document.getElementById('pianoKeys');
      pianoKeys.innerHTML = '';
      for (let i = 0; i < 24; i++) {
        const k = document.createElement('div');
        k.className = 'key';
        k.textContent = i % 12 === 0 ? 'C' : '';
        pianoKeys.appendChild(k);
      }
    }
    
    // Piano grid init
    function initPianoGrid() {
      const pianoGrid = document.getElementById('pianoGrid');
      pianoGrid.innerHTML = '';
      for (let i = 0; i < 24; i++) {
        const r = document.createElement('div');
        r.className = 'grid-row';
        pianoGrid.appendChild(r);
      }
      const note = document.createElement('div');
      note.className = 'note';
      pianoGrid.appendChild(note);
    }
    
    // Timeline rendering
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
              <button class="track-ctl-btn" onclick="toggleMute('${track.id}')">M</button>
              <button class="track-ctl-btn" onclick="toggleSolo('${track.id}')">S</button>
              <button class="track-ctl-btn" onclick="deleteTrack('${track.id}')">🗑</button>
            </div>
          </div>
          <div class="track-lane">
            <div class="clip" onclick="selectClip('${track.id}')">${track.name.substring(0, 20)}</div>
          </div>
        </div>
      `).join('');
    }
    
    // Mixer rendering
    function renderMixer() {
      const container = document.getElementById('mixerChannels');
      if (timeline.length === 0) {
        container.innerHTML = '<div style="color: var(--text-muted); font-size: 12px; padding: 20px;">No channels</div>';
        return;
      }
      
      container.innerHTML = timeline.map((track, idx) => `
        <div class="mixer-channel">
          <div class="ch-name">${track.name.substring(0, 12)}</div>
          <div class="ch-ctls">
            <button class="ch-btn">M</button>
            <button class="ch-btn">S</button>
          </div>
          <div class="fader-vu">
            <div class="fader">
              <div class="fader-thumb"></div>
            </div>
            <div class="vu">
              <div class="vu-fill"></div>
            </div>
          </div>
        </div>
      `).join('');
    }
    
    // Library rendering
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
    
    function selectClip(id) {
      showStatus('Clip selected: ' + id, 'info');
    }
    
    function showStatus(msg, type) {
      const el = document.getElementById('status');
      el.textContent = msg;
      el.className = `show ${type}`;
      setTimeout(() => el.classList.remove('show'), 5000);
    }
    
    // Mixer toggle
    document.getElementById('toggleMixer').addEventListener('click', () => {
      const mixer = document.querySelector('.mixer-container');
      if (mixer.style.height === '36px') {
        mixer.style.height = '160px';
      } else {
        mixer.style.height = '36px';
      }
    });
    
    // Initialize
    initPianoKeys();
    initPianoGrid();
    renderTimeline();
    renderLibrary();
  </script>
</body>
</html>
"""

if __name__ == "__main__":
    app.deploy("music-app-v13-complete")
