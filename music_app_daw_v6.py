# Prompt2Jam Studio v0.0.6 - ACE Studio Clone
# Professional DAW with mixer, effects, piano roll, and vocal editor

from typing import Optional, List, Dict
from uuid import uuid4
from datetime import datetime
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

app = modal.App("prompt-2-jam-v6-ace")

@app.cls(gpu="l40s", image=image, volumes={cache_dir: model_cache}, timeout=1800)
class MusicGenerator:
    model: Optional[object] = None

    def init(self):
        pass

    @modal.method()
    def run(
        self,
        prompt: str,
        lyrics: str,
        duration: float = 60.0,
        format: str = "wav",
        manual_seeds: Optional[int] = 1,
        inference_steps: int = 60,
        guidance_scale: float = 15.0,
    ) -> bytes:
        import uuid
        if self.model is None:
            from acestep.pipeline_ace_step import ACEStepPipeline
            self.model = ACEStepPipeline(dtype="bfloat16", cpu_offload=False, overlapped_decode=True)
        
        output_path = f"/dev/shm/output_{uuid.uuid4().hex}.{format}"
        print(f"🎵 Generating: {prompt} ({duration}s)")
        
        self.model(
            audio_duration=duration,
            prompt=prompt,
            lyrics=lyrics,
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

    fastapi_app = FastAPI(title="Prompt2Jam Studio v0.0.6 (ACE Clone)")
    music_generator = MusicGenerator()
    generate = music_generator.run.remote

    class GenerateRequest(BaseModel):
        prompt: str
        lyrics: str = ""
        duration: float = 30.0
        tempo: Optional[int] = None
        genre: Optional[str] = None
        mood: Optional[str] = None
        vocal_type: str = "vocal"
        format: str = "wav"
        inference_steps: int = 60
        guidance_scale: float = 15.0
        seed: Optional[int] = None

    @fastapi_app.get("/", response_class=HTMLResponse)
    async def root():
        return HTML_ACE_STUDIO

    @fastapi_app.get("/manifest.json")
    async def manifest():
        return {
            "name": "Prompt2Jam Studio Pro",
            "short_name": "P2J Studio",
            "description": "Professional AI Music Production DAW",
            "start_url": "/",
            "display": "standalone",
            "background_color": "#0f172a",
            "theme_color": "#6366f1",
            "icons": [
                {"src": "/icon-192.png", "sizes": "192x192", "type": "image/png"},
                {"src": "/icon-512.png", "sizes": "512x512", "type": "image/png"}
            ]
        }

    @fastapi_app.post("/api/generate")
    async def generate_music_api(request: GenerateRequest):
        try:
            if not request.prompt or not request.prompt.strip():
                return JSONResponse({"error": "Prompt cannot be empty"}, status_code=400)
            if request.duration < 5 or request.duration > 240:
                return JSONResponse({"error": "Duration must be 5-240 seconds"}, status_code=400)
            
            enhanced_prompt = request.prompt
            if request.genre:
                enhanced_prompt = f"{request.genre}, {enhanced_prompt}"
            if request.mood:
                enhanced_prompt = f"{request.mood}, {enhanced_prompt}"
            if request.tempo:
                enhanced_prompt = f"{request.tempo} BPM, {enhanced_prompt}"
            
            lyrics = request.lyrics.strip() if request.lyrics else ""
            if request.vocal_type == "instrumental":
                lyrics = "[inst]"
            
            audio_bytes = await generate.aio(
                prompt=enhanced_prompt,
                lyrics=lyrics or "[inst]",
                duration=request.duration,
                format=request.format,
                manual_seeds=request.seed or 1,
                inference_steps=request.inference_steps,
                guidance_scale=request.guidance_scale,
            )
            
            media_types = {"wav": "audio/wav", "mp3": "audio/mpeg", "flac": "audio/flac"}
            fmt = request.format if request.format in media_types else "wav"
            session_id = str(uuid4())[:8]
            
            return StreamingResponse(
                iter([audio_bytes]),
                media_type=media_types.get(fmt, "audio/wav"),
                headers={
                    "Content-Disposition": f"attachment; filename=p2j_{session_id}.{fmt}",
                    "X-Session-ID": session_id
                }
            )
        except Exception as e:
            import traceback
            print(f"❌ {traceback.format_exc()}")
            return JSONResponse({"error": str(e)}, status_code=500)

    return fastapi_app

HTML_ACE_STUDIO = """<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <meta name="theme-color" content="#0f172a" />
  <title>Prompt2Jam Studio - ACE Clone</title>
  <link rel="manifest" href="/manifest.json" />
  <style>
    * { box-sizing: border-box; margin: 0; padding: 0; }
    :root {
      --bg-dark: #0a0e1a; --bg-main: #0f172a; --bg-panel: #1e293b; --bg-hover: #334155;
      --text-bright: #f8fafc; --text-main: #e2e8f0; --text-dim: #94a3b8; --text-muted: #64748b;
      --accent: #6366f1; --accent-hover: #4f46e5; --accent-bright: #818cf8;
      --success: #10b981; --warning: #f59e0b; --danger: #ef4444;
      --border: #334155; --border-light: #475569;
    }
    body {
      font-family: Inter, -apple-system, BlinkMacSystemFont, Segoe UI, Roboto, sans-serif;
      background: var(--bg-dark); color: var(--text-main);
      height: 100vh; overflow: hidden;
    }
    
    /* Main Layout */
    .daw-container { display: flex; flex-direction: column; height: 100vh; }
    
    /* Top Menu Bar */
    .menu-bar {
      display: flex; align-items: center; justify-content: space-between;
      background: var(--bg-panel); border-bottom: 1px solid var(--border);
      padding: 8px 16px; height: 48px; z-index: 200;
    }
    .menu-left { display: flex; gap: 20px; align-items: center; }
    .app-title { font-weight: 700; font-size: 16px; color: var(--accent-bright); }
    .menu-item {
      color: var(--text-dim); font-size: 13px; padding: 6px 12px;
      border-radius: 6px; cursor: pointer; transition: all .2s;
    }
    .menu-item:hover { background: var(--bg-hover); color: var(--text-bright); }
    .menu-right { display: flex; gap: 8px; }
    .icon-btn {
      background: var(--bg-hover); border: 1px solid var(--border);
      color: var(--text-dim); padding: 6px 10px; border-radius: 6px;
      cursor: pointer; font-size: 13px; transition: all .2s;
    }
    .icon-btn:hover { background: var(--accent); color: white; border-color: var(--accent); }
    
    /* Main Content Area */
    .main-content { display: flex; flex: 1; overflow: hidden; }
    
    /* Left Sidebar - Track List */
    .track-panel {
      width: 240px; background: var(--bg-panel); border-right: 1px solid var(--border);
      display: flex; flex-direction: column; overflow-y: auto;
    }
    .track-header {
      padding: 12px; border-bottom: 1px solid var(--border);
      font-weight: 600; font-size: 12px; color: var(--text-dim);
      text-transform: uppercase; letter-spacing: .5px;
    }
    .track-item {
      display: flex; align-items: center; gap: 10px; padding: 10px 12px;
      border-bottom: 1px solid var(--border); cursor: pointer;
      transition: background .2s;
    }
    .track-item:hover { background: var(--bg-hover); }
    .track-item.selected { background: var(--accent); color: white; }
    .track-icon { font-size: 18px; }
    .track-info { flex: 1; }
    .track-name { font-size: 13px; font-weight: 500; }
    .track-type { font-size: 11px; color: var(--text-muted); }
    .track-controls { display: flex; gap: 4px; }
    .track-btn {
      width: 24px; height: 24px; border-radius: 4px;
      background: rgba(255,255,255,.05); border: none;
      color: var(--text-dim); cursor: pointer; font-size: 11px;
    }
    .track-btn:hover { background: var(--accent); color: white; }
    
    /* Center - Timeline/Arrangement */
    .timeline-panel {
      flex: 1; display: flex; flex-direction: column; background: var(--bg-main);
      overflow: hidden;
    }
    .timeline-toolbar {
      display: flex; align-items: center; gap: 12px; padding: 10px 16px;
      background: var(--bg-panel); border-bottom: 1px solid var(--border);
    }
    .transport-controls { display: flex; gap: 6px; }
    .transport-btn {
      width: 32px; height: 32px; border-radius: 6px; border: none;
      background: var(--bg-hover); color: var(--text-main);
      cursor: pointer; font-size: 16px; transition: all .2s;
    }
    .transport-btn:hover { background: var(--accent); color: white; }
    .transport-btn.play { background: var(--accent); color: white; }
    .time-display {
      background: var(--bg-dark); padding: 6px 12px; border-radius: 6px;
      font-family: monospace; font-size: 14px; min-width: 90px; text-align: center;
    }
    .timeline-content {
      flex: 1; overflow: auto; position: relative;
      background: linear-gradient(to bottom, var(--bg-main), var(--bg-dark));
    }
    .timeline-ruler {
      height: 32px; background: var(--bg-panel); border-bottom: 1px solid var(--border);
      position: sticky; top: 0; z-index: 10; display: flex;
    }
    .timeline-marker {
      flex: 1; border-right: 1px solid var(--border); padding: 6px 8px;
      font-size: 11px; color: var(--text-muted);
    }
    .timeline-tracks { padding: 16px; }
    .timeline-track {
      height: 80px; margin-bottom: 12px; position: relative;
      background: rgba(255,255,255,.02); border: 1px solid var(--border);
      border-radius: 8px; overflow: hidden;
    }
    .track-label {
      position: absolute; left: 8px; top: 8px;
      font-size: 11px; color: var(--text-dim); font-weight: 500;
    }
    .timeline-clip {
      position: absolute; height: 60px; top: 10px;
      background: linear-gradient(135deg, var(--accent), #8b5cf6);
      border-radius: 6px; padding: 8px; color: white;
      box-shadow: 0 2px 8px rgba(0,0,0,.3); cursor: move;
    }
    .clip-name { font-size: 12px; font-weight: 600; margin-bottom: 4px; }
    .clip-waveform {
      height: 24px; opacity: .6;
      background: repeating-linear-gradient(
        90deg, rgba(255,255,255,.3) 0px, transparent 2px,
        transparent 4px, rgba(255,255,255,.3) 6px
      );
    }
    
    /* Right Sidebar - Inspector/Effects */
    .inspector-panel {
      width: 300px; background: var(--bg-panel); border-left: 1px solid var(--border);
      display: flex; flex-direction: column; overflow-y: auto;
    }
    .inspector-tabs {
      display: flex; border-bottom: 1px solid var(--border);
    }
    .inspector-tab {
      flex: 1; padding: 10px; text-align: center; font-size: 12px;
      color: var(--text-dim); cursor: pointer; border-bottom: 2px solid transparent;
      transition: all .2s;
    }
    .inspector-tab:hover { color: var(--text-main); }
    .inspector-tab.active {
      color: var(--accent); border-bottom-color: var(--accent);
    }
    .inspector-content { padding: 16px; }
    .inspector-section {
      margin-bottom: 20px; padding-bottom: 16px;
      border-bottom: 1px solid var(--border);
    }
    .section-title {
      font-size: 11px; font-weight: 600; color: var(--text-dim);
      text-transform: uppercase; letter-spacing: .5px; margin-bottom: 12px;
    }
    .param-group { margin-bottom: 14px; }
    .param-label {
      display: flex; justify-content: space-between; align-items: center;
      font-size: 12px; color: var(--text-main); margin-bottom: 6px;
    }
    .param-value { color: var(--accent-bright); font-weight: 600; }
    input[type="range"] {
      width: 100%; height: 4px; border-radius: 2px;
      background: var(--bg-hover); outline: none;
      -webkit-appearance: none;
    }
    input[type="range"]::-webkit-slider-thumb {
      -webkit-appearance: none; width: 14px; height: 14px;
      border-radius: 50%; background: var(--accent); cursor: pointer;
    }
    select, input[type="text"], textarea {
      width: 100%; background: var(--bg-hover); color: var(--text-main);
      border: 1px solid var(--border); border-radius: 6px;
      padding: 8px 10px; font-size: 13px;
    }
    select:focus, input:focus, textarea:focus {
      outline: none; border-color: var(--accent);
    }
    textarea { min-height: 80px; resize: vertical; font-family: inherit; }
    
    /* Piano Roll */
    .piano-roll {
      display: none; /* Toggle visibility */
      height: 300px; background: var(--bg-dark);
      border: 1px solid var(--border); border-radius: 8px;
      margin: 12px 0; position: relative; overflow: auto;
    }
    .piano-roll-grid {
      display: grid; grid-template-columns: 40px 1fr;
      height: 100%;
    }
    .piano-keys {
      background: var(--bg-panel); border-right: 1px solid var(--border);
    }
    .piano-key {
      height: 20px; border-bottom: 1px solid var(--border);
      padding: 2px 6px; font-size: 10px; color: var(--text-muted);
    }
    .piano-grid {
      position: relative; background: repeating-linear-gradient(
        to bottom, var(--bg-main) 0px, var(--bg-main) 19px,
        var(--border) 19px, var(--border) 20px
      );
    }
    .piano-note {
      position: absolute; height: 18px; top: 1px;
      background: var(--accent); border-radius: 3px;
      cursor: pointer; opacity: .9;
    }
    
    /* Mixer View */
    .mixer-view {
      display: none; /* Toggle */
      padding: 20px; background: var(--bg-main);
      border: 1px solid var(--border); border-radius: 8px;
      margin: 12px 0;
    }
    .mixer-channels {
      display: flex; gap: 12px; overflow-x: auto;
    }
    .mixer-channel {
      width: 80px; background: var(--bg-panel);
      border: 1px solid var(--border); border-radius: 8px;
      padding: 12px 8px; text-align: center;
    }
    .channel-fader {
      height: 120px; margin: 12px auto;
      background: var(--bg-hover); width: 12px;
      border-radius: 6px; position: relative;
    }
    .fader-thumb {
      position: absolute; width: 24px; height: 8px;
      background: var(--accent); border-radius: 4px;
      left: -6px; cursor: ns-resize;
    }
    .channel-meter {
      width: 8px; height: 80px; background: var(--bg-hover);
      border-radius: 4px; margin: 8px auto;
    }
    
    /* Buttons */
    .btn {
      padding: 8px 14px; border-radius: 6px; border: none;
      font-weight: 600; font-size: 13px; cursor: pointer;
      transition: all .2s;
    }
    .btn-primary { background: var(--accent); color: white; }
    .btn-primary:hover { background: var(--accent-hover); }
    .btn-secondary {
      background: var(--bg-hover); color: var(--text-main);
      border: 1px solid var(--border);
    }
    .btn-secondary:hover { background: var(--accent); color: white; }
    .btn-group { display: flex; gap: 8px; margin-top: 12px; }
    
    /* Effects Rack */
    .effects-rack { margin-top: 12px; }
    .effect-slot {
      background: var(--bg-hover); border: 1px solid var(--border);
      border-radius: 6px; padding: 10px; margin-bottom: 8px;
      display: flex; justify-content: space-between; align-items: center;
    }
    .effect-name { font-size: 12px; font-weight: 500; }
    .effect-toggle {
      width: 36px; height: 20px; background: var(--bg-dark);
      border-radius: 10px; position: relative; cursor: pointer;
    }
    .effect-toggle.on { background: var(--accent); }
    .effect-toggle::after {
      content: ''; position: absolute; width: 16px; height: 16px;
      background: white; border-radius: 50%; top: 2px; left: 2px;
      transition: left .2s;
    }
    .effect-toggle.on::after { left: 18px; }
    
    /* Status Messages */
    .status-bar {
      padding: 8px 16px; background: var(--bg-panel);
      border-top: 1px solid var(--border); font-size: 12px;
      color: var(--text-dim); display: flex; justify-content: space-between;
    }
    .status-msg { display: none; }
    .status-msg.show { display: block; }
    .status-msg.info { color: var(--accent-bright); }
    .status-msg.success { color: var(--success); }
    .status-msg.error { color: var(--danger); }
    
    /* Responsive */
    @media (max-width: 1200px) {
      .track-panel { width: 200px; }
      .inspector-panel { width: 260px; }
    }
    @media (max-width: 900px) {
      .track-panel, .inspector-panel { display: none; }
    }
  </style>
</head>
<body>
  <div class="daw-container">
    <!-- Top Menu -->
    <div class="menu-bar">
      <div class="menu-left">
        <div class="app-title">🎵 Prompt2Jam Studio</div>
        <div class="menu-item">File</div>
        <div class="menu-item">Edit</div>
        <div class="menu-item">View</div>
        <div class="menu-item">Track</div>
      </div>
      <div class="menu-right">
        <button class="icon-btn" id="shareBtn">🔗 Share</button>
        <button class="icon-btn" id="exportBtn">📥 Export</button>
        <button class="icon-btn">⚙️</button>
      </div>
    </div>
    
    <div class="main-content">
      <!-- Left: Track List -->
      <div class="track-panel">
        <div class="track-header">Tracks</div>
        <div id="trackList">
          <div class="track-item selected">
            <div class="track-icon">🎤</div>
            <div class="track-info">
              <div class="track-name">Vocals</div>
              <div class="track-type">AI Generated</div>
            </div>
            <div class="track-controls">
              <button class="track-btn">M</button>
              <button class="track-btn">S</button>
            </div>
          </div>
          <div class="track-item">
            <div class="track-icon">🎹</div>
            <div class="track-info">
              <div class="track-name">Piano</div>
              <div class="track-type">Instrumental</div>
            </div>
            <div class="track-controls">
              <button class="track-btn">M</button>
              <button class="track-btn">S</button>
            </div>
          </div>
        </div>
        <button class="btn btn-primary" style="margin: 12px;" id="addTrackBtn">+ Add Track</button>
      </div>
      
      <!-- Center: Timeline -->
      <div class="timeline-panel">
        <div class="timeline-toolbar">
          <div class="transport-controls">
            <button class="transport-btn">⏮</button>
            <button class="transport-btn play" id="playBtn">▶</button>
            <button class="transport-btn">⏭</button>
            <button class="transport-btn">⏹</button>
            <button class="transport-btn">⏺</button>
          </div>
          <div class="time-display" id="timeDisplay">00:00.000</div>
          <div style="flex: 1"></div>
          <button class="icon-btn" id="mixerToggle">🎚️ Mixer</button>
          <button class="icon-btn" id="pianoRollToggle">🎹 Piano Roll</button>
        </div>
        
        <div class="mixer-view" id="mixerView">
          <div class="mixer-channels">
            <div class="mixer-channel">
              <div style="font-size: 11px; margin-bottom: 8px;">Track 1</div>
              <div class="channel-fader">
                <div class="fader-thumb" style="bottom: 60%"></div>
              </div>
              <div class="channel-meter"></div>
              <div style="font-size: 10px; color: var(--text-muted)">-12 dB</div>
            </div>
            <div class="mixer-channel">
              <div style="font-size: 11px; margin-bottom: 8px;">Track 2</div>
              <div class="channel-fader">
                <div class="fader-thumb" style="bottom: 70%"></div>
              </div>
              <div class="channel-meter"></div>
              <div style="font-size: 10px; color: var(--text-muted)">-6 dB</div>
            </div>
            <div class="mixer-channel" style="background: var(--accent); opacity: .8;">
              <div style="font-size: 11px; margin-bottom: 8px;">Master</div>
              <div class="channel-fader">
                <div class="fader-thumb" style="bottom: 80%"></div>
              </div>
              <div class="channel-meter"></div>
              <div style="font-size: 10px; color: white">0 dB</div>
            </div>
          </div>
        </div>
        
        <div class="piano-roll" id="pianoRoll">
          <div class="piano-roll-grid">
            <div class="piano-keys" id="pianoKeys"></div>
            <div class="piano-grid" id="pianoGrid"></div>
          </div>
        </div>
        
        <div class="timeline-content">
          <div class="timeline-ruler">
            <div class="timeline-marker">0:00</div>
            <div class="timeline-marker">0:15</div>
            <div class="timeline-marker">0:30</div>
            <div class="timeline-marker">0:45</div>
            <div class="timeline-marker">1:00</div>
            <div class="timeline-marker">1:15</div>
            <div class="timeline-marker">1:30</div>
            <div class="timeline-marker">1:45</div>
          </div>
          <div class="timeline-tracks" id="timelineTracks">
            <div class="timeline-track">
              <div class="track-label">Track 1: Vocals</div>
              <div class="timeline-clip" style="left: 10%; width: 40%;">
                <div class="clip-name">Vocals.wav</div>
                <div class="clip-waveform"></div>
              </div>
            </div>
            <div class="timeline-track">
              <div class="track-label">Track 2: Piano</div>
              <div class="timeline-clip" style="left: 30%; width: 50%;">
                <div class="clip-name">Piano.wav</div>
                <div class="clip-waveform"></div>
              </div>
            </div>
          </div>
        </div>
      </div>
      
      <!-- Right: Inspector/Effects -->
      <div class="inspector-panel">
        <div class="inspector-tabs">
          <div class="inspector-tab active" data-tab="generate">Generate</div>
          <div class="inspector-tab" data-tab="effects">Effects</div>
          <div class="inspector-tab" data-tab="vocal">Vocal</div>
        </div>
        
        <div class="inspector-content">
          <div id="tab-generate" class="tab-content">
            <div class="inspector-section">
              <div class="section-title">🎨 Create Track</div>
              <div class="param-group">
                <label class="param-label">Prompt</label>
                <textarea id="prompt" placeholder="Upbeat electronic dance with synth melodies"></textarea>
              </div>
              <div class="param-group">
                <label class="param-label">Genre</label>
                <select id="genre">
                  <option value="">Auto</option>
                  <option>Pop</option><option>Rock</option><option>Jazz</option>
                  <option>Electronic</option><option>Hip-Hop</option><option>Classical</option>
                </select>
              </div>
              <div class="param-group">
                <label class="param-label">
                  <span>Duration</span>
                  <span class="param-value"><span id="durationValue">30</span>s</span>
                </label>
                <input type="range" id="duration" min="5" max="240" value="30" />
              </div>
              <div class="btn-group">
                <button class="btn btn-primary" style="flex:1" id="generateBtn">🎵 Generate</button>
              </div>
              <div id="statusMsg" class="status-msg"></div>
            </div>
            
            <div class="inspector-section">
              <div class="section-title">🎧 Player</div>
              <audio id="audio" controls style="width: 100%; margin-top: 8px;"></audio>
              <div class="btn-group">
                <button class="btn btn-secondary" id="saveBtn">💾 Save</button>
                <button class="btn btn-secondary" id="downloadBtn">⬇️ Download</button>
              </div>
            </div>
          </div>
          
          <div id="tab-effects" class="tab-content" style="display:none;">
            <div class="inspector-section">
              <div class="section-title">🎛️ Effects Rack</div>
              <div class="effects-rack">
                <div class="effect-slot">
                  <div class="effect-name">🎚️ EQ (3-Band)</div>
                  <div class="effect-toggle on"></div>
                </div>
                <div class="effect-slot">
                  <div class="effect-name">🗜️ Compressor</div>
                  <div class="effect-toggle"></div>
                </div>
                <div class="effect-slot">
                  <div class="effect-name">🌊 Reverb</div>
                  <div class="effect-toggle on"></div>
                </div>
              </div>
              <button class="btn btn-secondary" style="width: 100%; margin-top: 12px;">+ Add Effect</button>
            </div>
            
            <div class="inspector-section">
              <div class="section-title">EQ Settings</div>
              <div class="param-group">
                <label class="param-label">
                  <span>Low</span>
                  <span class="param-value"><span id="eqLowValue">0</span> dB</span>
                </label>
                <input type="range" id="eqLow" min="-12" max="12" value="0" step="0.5" />
              </div>
              <div class="param-group">
                <label class="param-label">
                  <span>Mid</span>
                  <span class="param-value"><span id="eqMidValue">0</span> dB</span>
                </label>
                <input type="range" id="eqMid" min="-12" max="12" value="0" step="0.5" />
              </div>
              <div class="param-group">
                <label class="param-label">
                  <span>High</span>
                  <span class="param-value"><span id="eqHighValue">0</span> dB</span>
                </label>
                <input type="range" id="eqHigh" min="-12" max="12" value="0" step="0.5" />
              </div>
            </div>
          </div>
          
          <div id="tab-vocal" class="tab-content" style="display:none;">
            <div class="inspector-section">
              <div class="section-title">🎤 Vocal Editor</div>
              <div class="param-group">
                <label class="param-label">
                  <span>Pitch Correction</span>
                  <span class="param-value"><span id="pitchCorrectionValue">50</span>%</span>
                </label>
                <input type="range" id="pitchCorrection" min="0" max="100" value="50" />
              </div>
              <div class="param-group">
                <label class="param-label">
                  <span>Vibrato</span>
                  <span class="param-value"><span id="vibratoValue">30</span>%</span>
                </label>
                <input type="range" id="vibrato" min="0" max="100" value="30" />
              </div>
              <div class="param-group">
                <label class="param-label">Lyrics</label>
                <textarea id="lyrics" placeholder="[verse] Walking down the road..."></textarea>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
    
    <div class="status-bar">
      <div>Ready • BPM: 120 • Key: C Major</div>
      <div>Prompt2Jam Studio v0.0.6</div>
    </div>
  </div>
  
  <script>
    // Tab switching
    document.querySelectorAll('.inspector-tab').forEach(tab => {
      tab.addEventListener('click', () => {
        document.querySelectorAll('.inspector-tab').forEach(t => t.classList.remove('active'));
        document.querySelectorAll('.tab-content').forEach(c => c.style.display = 'none');
        tab.classList.add('active');
        document.getElementById(`tab-${tab.dataset.tab}`).style.display = 'block';
      });
    });
    
    // Toggle views
    document.getElementById('mixerToggle').addEventListener('click', () => {
      const mixer = document.getElementById('mixerView');
      mixer.style.display = mixer.style.display === 'none' ? 'block' : 'none';
    });
    
    document.getElementById('pianoRollToggle').addEventListener('click', () => {
      const piano = document.getElementById('pianoRoll');
      piano.style.display = piano.style.display === 'none' ? 'block' : 'none';
      if (piano.style.display === 'block') initPianoRoll();
    });
    
    // Piano roll initialization
    function initPianoRoll() {
      const keys = document.getElementById('pianoKeys');
      const grid = document.getElementById('pianoGrid');
      if (keys.children.length > 0) return;
      const notes = ['C', 'B', 'A#', 'A', 'G#', 'G', 'F#', 'F', 'E', 'D#', 'D', 'C#'];
      for (let oct = 5; oct >= 3; oct--) {
        notes.forEach(note => {
          const div = document.createElement('div');
          div.className = 'piano-key';
          div.textContent = `${note}${oct}`;
          keys.appendChild(div);
        });
      }
    }
    
    // Slider updates
    ['duration', 'eqLow', 'eqMid', 'eqHigh', 'pitchCorrection', 'vibrato'].forEach(id => {
      const slider = document.getElementById(id);
      if (slider) {
        slider.addEventListener('input', e => {
          const valueSpan = document.getElementById(id + 'Value');
          if (valueSpan) valueSpan.textContent = e.target.value;
        });
      }
    });
    
    // Generation
    function showStatus(msg, type = 'info') {
      const status = document.getElementById('statusMsg');
      status.textContent = msg;
      status.className = `status-msg show ${type}`;
      setTimeout(() => status.className = 'status-msg', 5000);
    }
    
    document.getElementById('generateBtn').addEventListener('click', async () => {
      const prompt = document.getElementById('prompt').value.trim();
      if (!prompt) {
        showStatus('Enter a prompt', 'error');
        return;
      }
      
      showStatus('Generating... (30-60s)', 'info');
      
      try {
        const res = await fetch('/api/generate', {
          method: 'POST',
          headers: {'Content-Type': 'application/json'},
          body: JSON.stringify({
            prompt,
            genre: document.getElementById('genre').value,
            duration: parseInt(document.getElementById('duration').value),
            format: 'wav',
            lyrics: document.getElementById('lyrics').value || '[inst]'
          })
        });
        
        if (!res.ok) throw new Error('Generation failed');
        
        const blob = await res.blob();
        const url = URL.createObjectURL(blob);
        document.getElementById('audio').src = url;
        document.getElementById('audio').play();
        
        showStatus('✅ Ready!', 'success');
      } catch (error) {
        showStatus(`❌ ${error.message}`, 'error');
      }
    });
    
    // Effect toggles
    document.querySelectorAll('.effect-toggle').forEach(toggle => {
      toggle.addEventListener('click', () => {
        toggle.classList.toggle('on');
      });
    });
    
    // Transport controls
    let isPlaying = false;
    document.getElementById('playBtn').addEventListener('click', () => {
      isPlaying = !isPlaying;
      document.getElementById('playBtn').textContent = isPlaying ? '⏸' : '▶';
    });
  </script>
</body>
</html>
"""
