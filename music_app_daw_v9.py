# Prompt2Jam Studio v0.0.9 - Professional DAW (ACE-STUDIO Quality)
# Enterprise-grade production DAW following modern DAW standards
# Mobile-first, collapsible panels, proper navigation

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

app = modal.App("prompt-2-jam-v9-professional")

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

    fastapi_app = FastAPI(title="Prompt2Jam Studio v0.0.9 Professional")
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
        return HTML_V9_PRO

    @fastapi_app.get("/manifest.json")
    async def manifest():
        return {
            "name": "Prompt2Jam Studio v0.0.9",
            "short_name": "P2J Pro",
            "description": "Professional AI Music Production DAW",
            "start_url": "/",
            "display": "standalone",
            "background_color": "#0a0e1a",
            "theme_color": "#6366f1",
        }

    @fastapi_app.post("/api/generate")
    async def generate_music_api(request: GenerateRequest):
        try:
            if not request.prompt or not request.prompt.strip():
                return JSONResponse({"error": "Prompt cannot be empty"}, status_code=400)
            
            enhanced_prompt = request.prompt
            if request.genre:
                enhanced_prompt = f"{request.genre}, {enhanced_prompt}"
            if request.mood:
                enhanced_prompt = f"{request.mood}, {enhanced_prompt}"
            
            audio_bytes = await generate.aio(
                prompt=enhanced_prompt,
                lyrics=request.lyrics or "[inst]",
                duration=request.duration,
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

HTML_V9_PRO = """<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no" />
  <meta name="theme-color" content="#0a0e1a" />
  <title>Prompt2Jam Studio v0.0.9 Professional</title>
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
    html, body { height: 100%; width: 100%; -webkit-font-smoothing: antialiased; }
    body {
      font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Oxygen, Ubuntu, sans-serif;
      background: var(--bg-dark); color: var(--text-main);
      overflow: hidden;
    }
    
    .app-container {
      display: flex; flex-direction: column; height: 100vh;
    }
    
    /* MAIN CONTENT */
    .main-viewport {
      flex: 1; display: flex; overflow: hidden; position: relative;
    }
    
    /* LEFT SIDEBAR - COLLAPSIBLE */
    .left-sidebar {
      width: 260px; background: var(--bg-panel); border-right: 1px solid var(--border);
      display: flex; flex-direction: column; transition: transform 0.3s ease;
      overflow-y: auto; flex-shrink: 0;
    }
    .left-sidebar.collapsed {
      transform: translateX(-100%); position: absolute; z-index: 50; left: 0;
    }
    .sidebar-header {
      padding: 16px; border-bottom: 1px solid var(--border);
      display: flex; justify-content: space-between; align-items: center;
    }
    .sidebar-title { font-weight: 600; font-size: 13px; color: var(--text-dim); text-transform: uppercase; }
    .sidebar-close-btn {
      display: none; width: 24px; height: 24px; background: transparent;
      border: none; color: var(--text-dim); cursor: pointer; font-size: 16px;
    }
    @media (max-width: 1024px) {
      .left-sidebar.collapsed .sidebar-close-btn { display: block; }
    }
    
    /* TRACK LIST */
    .track-list {
      flex: 1; overflow-y: auto; padding: 8px 0;
    }
    .track-item {
      display: flex; align-items: center; gap: 10px; padding: 8px 12px;
      border-bottom: 1px solid var(--border); cursor: pointer;
      transition: background 0.2s;
    }
    .track-item:hover { background: var(--bg-hover); }
    .track-item.selected { background: var(--accent); color: white; }
    .track-icon { font-size: 18px; flex-shrink: 0; }
    .track-info { flex: 1; min-width: 0; }
    .track-name { font-size: 13px; font-weight: 500; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
    .track-type { font-size: 11px; color: var(--text-muted); }
    .track-controls { display: flex; gap: 4px; }
    .track-btn { width: 24px; height: 24px; border-radius: 4px; background: rgba(255,255,255,.05); border: none; color: var(--text-dim); cursor: pointer; font-size: 11px; }
    .track-btn:hover { background: var(--accent); color: white; }
    .track-btn.active { background: var(--accent); color: white; }
    
    .add-track-btn {
      padding: 12px; margin: 8px;
      background: var(--accent); color: white; border: none;
      border-radius: 6px; cursor: pointer; font-weight: 600; font-size: 13px;
    }
    .add-track-btn:hover { background: var(--accent-hover); }
    
    /* CENTER - MAIN WORKSPACE */
    .center-workspace {
      flex: 1; display: flex; flex-direction: column; background: var(--bg-main);
      overflow: hidden;
    }
    
    .tab-bar {
      display: flex; height: 36px; background: var(--bg-panel);
      border-bottom: 1px solid var(--border); align-items: center;
    }
    .tab { padding: 0 16px; height: 36px; display: flex; align-items: center;
      font-size: 13px; color: var(--text-dim); cursor: pointer; border-bottom: 2px solid transparent;
      transition: all 0.2s; border-bottom-color: transparent;
    }
    .tab:hover { background: var(--bg-hover); color: var(--text-main); }
    .tab.active { color: var(--accent); border-bottom-color: var(--accent); }
    
    .tab-content { flex: 1; overflow: hidden; display: none; }
    .tab-content.active { display: flex; flex-direction: column; }
    
    /* ARRANGE VIEW - TIMELINE & RULER */
    .arrange-view {
      display: flex; flex-direction: column; height: 100%;
    }
    .timeline-toolbar {
      display: flex; align-items: center; gap: 12px; padding: 8px 16px;
      background: var(--bg-panel); border-bottom: 1px solid var(--border);
      flex-shrink: 0;
    }
    .transport-controls { display: flex; gap: 4px; }
    .transport-btn { width: 32px; height: 32px; border-radius: 4px; border: none;
      background: var(--bg-hover); color: var(--text-main); cursor: pointer; font-size: 16px;
      transition: all 0.2s;
    }
    .transport-btn:hover { background: var(--accent); color: white; }
    .transport-btn.playing { background: var(--accent); color: white; }
    .time-display { background: var(--bg-dark); padding: 4px 10px; border-radius: 4px;
      font-family: monospace; font-size: 13px; min-width: 80px; text-align: center;
    }
    
    .timeline-ruler {
      height: 28px; background: var(--bg-panel); border-bottom: 1px solid var(--border);
      display: flex; flex-shrink: 0; font-size: 11px; color: var(--text-muted);
    }
    .ruler-marker { flex: 1; border-right: 1px solid var(--border); padding: 4px 6px; }
    
    .timeline-content { flex: 1; overflow-y: auto; background: linear-gradient(to bottom, var(--bg-main), var(--bg-dark)); }
    .timeline-track {
      height: 64px; margin-bottom: 8px; background: rgba(255,255,255,.02);
      border: 1px solid var(--border); border-radius: 6px; margin: 8px;
      position: relative; overflow: hidden;
    }
    .track-label { position: absolute; left: 8px; top: 6px; font-size: 11px;
      color: var(--text-dim); font-weight: 500;
    }
    .timeline-clip { position: absolute; height: 48px; top: 8px;
      background: linear-gradient(135deg, var(--accent), #8b5cf6);
      border-radius: 4px; padding: 6px; color: white; box-shadow: 0 2px 8px rgba(0,0,0,.3);
      cursor: move; font-size: 11px; font-weight: 600;
    }
    
    /* CREATE VIEW - GENERATOR PANEL */
    .create-view {
      display: flex; align-items: center; justify-content: center;
      padding: 32px;
    }
    .generator-panel {
      background: var(--bg-panel); border: 1px solid var(--border);
      border-radius: 12px; padding: 32px; max-width: 500px; width: 100%;
      box-shadow: 0 8px 32px rgba(0,0,0,.3);
    }
    .generator-title { font-size: 24px; font-weight: 700; margin-bottom: 8px; }
    .generator-subtitle { font-size: 13px; color: var(--text-dim); margin-bottom: 24px; }
    .form-group { margin-bottom: 18px; }
    .form-label { display: block; font-size: 12px; font-weight: 600; margin-bottom: 8px;
      color: var(--text-main); text-transform: uppercase; letter-spacing: 0.5px;
    }
    input, select, textarea {
      width: 100%; background: var(--bg-hover); color: var(--text-main);
      border: 1px solid var(--border); border-radius: 6px;
      padding: 10px 12px; font-size: 13px; font-family: inherit;
    }
    input:focus, select:focus, textarea:focus {
      outline: none; border-color: var(--accent); box-shadow: 0 0 0 3px rgba(99, 102, 241, 0.1);
    }
    textarea { resize: vertical; min-height: 80px; }
    
    .form-row { display: grid; grid-template-columns: 1fr 1fr; gap: 12px; }
    @media (max-width: 480px) { .form-row { grid-template-columns: 1fr; } }
    
    .slider-group { }
    .slider-label { display: flex; justify-content: space-between; font-size: 12px;
      margin-bottom: 6px; color: var(--text-main);
    }
    .slider-value { color: var(--accent-bright); font-weight: 600; }
    input[type="range"] { width: 100%; height: 4px; border-radius: 2px;
      background: var(--border); outline: none; -webkit-appearance: none;
    }
    input[type="range"]::-webkit-slider-thumb {
      -webkit-appearance: none; width: 14px; height: 14px;
      border-radius: 50%; background: var(--accent); cursor: pointer;
    }
    
    .btn { padding: 10px 16px; border-radius: 6px; border: none;
      font-weight: 600; font-size: 13px; cursor: pointer; transition: all 0.2s;
    }
    .btn-primary { background: var(--accent); color: white; }
    .btn-primary:hover { background: var(--accent-hover); }
    .btn-primary:disabled { opacity: 0.5; cursor: not-allowed; }
    .btn-secondary { background: var(--bg-hover); color: var(--text-main); border: 1px solid var(--border); }
    .btn-secondary:hover { background: var(--accent); color: white; }
    
    .btn-group { display: flex; gap: 8px; margin-top: 20px; }
    .btn-full { width: 100%; }
    
    .audio-player { width: 100%; margin-top: 16px; }
    .status-msg { margin-top: 12px; padding: 10px; border-radius: 6px; font-size: 12px;
      background: rgba(99, 102, 241, 0.1); color: var(--accent-bright);
    }
    .status-msg.success { background: rgba(16, 185, 129, 0.1); color: var(--success); }
    .status-msg.error { background: rgba(239, 68, 68, 0.1); color: var(--danger); }
    
    /* RIGHT SIDEBAR - INSPECTOR/EFFECTS */
    .right-sidebar {
      width: 300px; background: var(--bg-panel); border-left: 1px solid var(--border);
      display: flex; flex-direction: column; transition: transform 0.3s ease;
      overflow-y: auto; flex-shrink: 0;
    }
    .right-sidebar.collapsed {
      transform: translateX(100%); position: absolute; z-index: 50; right: 0;
    }
    
    .inspector-tabs { display: flex; border-bottom: 1px solid var(--border); }
    .inspector-tab { flex: 1; padding: 10px; text-align: center; font-size: 11px;
      color: var(--text-dim); cursor: pointer; border-bottom: 2px solid transparent;
      transition: all 0.2s;
    }
    .inspector-tab:hover { color: var(--text-main); }
    .inspector-tab.active { color: var(--accent); border-bottom-color: var(--accent); }
    
    .inspector-content { padding: 12px; flex: 1; overflow-y: auto; }
    .inspector-section { margin-bottom: 16px; padding-bottom: 12px; border-bottom: 1px solid var(--border); }
    .section-title { font-size: 10px; font-weight: 600; color: var(--text-dim);
      text-transform: uppercase; letter-spacing: 0.5px; margin-bottom: 10px;
    }
    
    /* BOTTOM NAVIGATION BAR */
    .bottom-nav-bar {
      display: flex; height: 56px; background: var(--bg-panel);
      border-top: 1px solid var(--border); flex-shrink: 0;
    }
    .nav-item {
      flex: 1; display: flex; flex-direction: column; align-items: center;
      justify-content: center; cursor: pointer; transition: all 0.2s;
      color: var(--text-dim); font-size: 10px; gap: 4px;
    }
    .nav-item:hover { background: var(--bg-hover); color: var(--text-main); }
    .nav-item.active { color: var(--accent); }
    .nav-item-icon { font-size: 22px; }
    .nav-item-label { font-size: 10px; font-weight: 500; }
    
    /* MOBILE RESPONSIVE */
    @media (max-width: 1024px) {
      .left-sidebar { position: absolute; left: 0; height: calc(100vh - 56px); z-index: 100; }
      .right-sidebar { position: absolute; right: 0; height: calc(100vh - 56px); z-index: 100; }
      .left-sidebar.collapsed { transform: translateX(-100%); }
      .right-sidebar.collapsed { transform: translateX(100%); }
    }
    @media (max-width: 480px) {
      .left-sidebar { width: 100%; }
      .right-sidebar { width: 100%; }
      .generator-panel { padding: 24px 16px; }
      .tab { padding: 0 12px; }
    }
    
    .toggle-sidebar-btn {
      width: 32px; height: 32px; background: transparent; border: none;
      color: var(--text-dim); cursor: pointer; font-size: 16px;
      display: none;
    }
    @media (max-width: 1024px) {
      .toggle-sidebar-btn { display: flex; align-items: center; justify-content: center; }
    }
  </style>
</head>
<body>
  <div class="app-container">
    <div class="main-viewport">
      <!-- LEFT SIDEBAR -->
      <div class="left-sidebar" id="leftSidebar">
        <div class="sidebar-header">
          <div class="sidebar-title">Tracks</div>
          <button class="sidebar-close-btn" onclick="toggleLeftSidebar()">✕</button>
        </div>
        <div class="track-list" id="trackList"></div>
        <button class="add-track-btn" onclick="addTrack()">+ Add Track</button>
      </div>
      
      <!-- CENTER WORKSPACE -->
      <div class="center-workspace">
        <div class="tab-bar">
          <button class="tab active" data-tab="arrange" onclick="switchTab('arrange')">📋 Arrange</button>
          <button class="tab" data-tab="create" onclick="switchTab('create')">✨ Create</button>
          <button class="tab" data-tab="library" onclick="switchTab('library')">📚 Library</button>
          <button class="toggle-sidebar-btn" onclick="toggleLeftSidebar()">☰</button>
          <button class="toggle-sidebar-btn" onclick="toggleRightSidebar()" style="margin-left:auto;">⚙️</button>
        </div>
        
        <!-- ARRANGE TAB -->
        <div class="tab-content active" data-tab="arrange">
          <div class="arrange-view">
            <div class="timeline-toolbar">
              <div class="transport-controls">
                <button class="transport-btn" onclick="seekStart()">⏮</button>
                <button class="transport-btn" id="playBtn" onclick="togglePlay()">▶</button>
                <button class="transport-btn" onclick="stop()">⏹</button>
              </div>
              <div class="time-display" id="timeDisplay">00:00</div>
            </div>
            <div class="timeline-ruler">
              <div class="ruler-marker">0:00</div>
              <div class="ruler-marker">0:30</div>
              <div class="ruler-marker">1:00</div>
              <div class="ruler-marker">1:30</div>
            </div>
            <div class="timeline-content" id="timelineContent"></div>
          </div>
        </div>
        
        <!-- CREATE TAB -->
        <div class="tab-content" data-tab="create">
          <div class="generator-panel">
            <div class="generator-title">🎵 Create Music</div>
            <div class="generator-subtitle">Generate AI music with a simple prompt</div>
            
            <div class="form-group">
              <label class="form-label">Your Idea</label>
              <textarea id="prompt" placeholder="Describe the music you want. Example: Upbeat electronic dance with synth leads"></textarea>
            </div>
            
            <div class="form-row">
              <div class="form-group">
                <label class="form-label">Genre</label>
                <select id="genre">
                  <option value="">Auto</option>
                  <option>Pop</option><option>Rock</option><option>Electronic</option>
                  <option>Hip-Hop</option><option>Jazz</option><option>Classical</option>
                </select>
              </div>
              <div class="form-group">
                <label class="form-label">Mood</label>
                <select id="mood">
                  <option value="">Auto</option>
                  <option>Happy</option><option>Sad</option><option>Energetic</option>
                  <option>Calm</option><option>Epic</option>
                </select>
              </div>
            </div>
            
            <div class="form-group">
              <div class="slider-group">
                <div class="slider-label">
                  <span>Duration</span>
                  <span class="slider-value"><span id="durationValue">30</span>s</span>
                </div>
                <input type="range" id="duration" min="5" max="120" value="30" oninput="updateValue('duration')" />
              </div>
            </div>
            
            <div class="form-group">
              <label class="form-label">Format</label>
              <select id="format">
                <option value="wav">WAV (Lossless)</option>
                <option value="mp3">MP3 (Compressed)</option>
                <option value="flac">FLAC (Lossless)</option>
              </select>
            </div>
            
            <button class="btn btn-primary btn-full" id="generateBtn" onclick="generateMusic()">🎵 Generate Music</button>
            
            <audio id="audio" class="audio-player" controls></audio>
            
            <div class="btn-group">
              <button class="btn btn-secondary" style="flex:1" onclick="downloadAudio()">⬇️ Download</button>
              <button class="btn btn-secondary" style="flex:1" onclick="addToArrange()">➕ Add to Arrange</button>
            </div>
            
            <div id="statusMsg" class="status-msg" style="display:none;"></div>
          </div>
        </div>
        
        <!-- LIBRARY TAB -->
        <div class="tab-content" data-tab="library">
          <div style="padding:16px;">
            <h2 style="margin-bottom:16px;">📚 Your Library</h2>
            <div id="libraryList"></div>
          </div>
        </div>
      </div>
      
      <!-- RIGHT SIDEBAR -->
      <div class="right-sidebar" id="rightSidebar">
        <div class="sidebar-header">
          <div class="sidebar-title">Effects & Mixer</div>
          <button class="sidebar-close-btn" onclick="toggleRightSidebar()">✕</button>
        </div>
        
        <div class="inspector-tabs">
          <button class="inspector-tab active" onclick="switchInspector('mixer')">🎚️ Mixer</button>
          <button class="inspector-tab" onclick="switchInspector('effects')">⚡ Effects</button>
        </div>
        
        <div class="inspector-content">
          <div id="mixer-panel">
            <div class="inspector-section">
              <div class="section-title">Master Volume</div>
              <div style="padding:10px 0;">
                <input type="range" min="-12" max="12" value="0" style="width:100%;" />
              </div>
            </div>
            <div class="inspector-section" id="channelsList"></div>
          </div>
          
          <div id="effects-panel" style="display:none;">
            <div class="inspector-section">
              <div class="section-title">EQ</div>
              <div style="font-size:12px;color:var(--text-dim);">3-Band EQ - Bass, Mid, High</div>
            </div>
            <div class="inspector-section">
              <div class="section-title">Compression</div>
              <div style="font-size:12px;color:var(--text-dim);">Dynamic Range Control</div>
            </div>
          </div>
        </div>
      </div>
    </div>
    
    <!-- BOTTOM NAVIGATION -->
    <div class="bottom-nav-bar">
      <div class="nav-item active" onclick="scrollToView('arrange')">
        <div class="nav-item-icon">📋</div>
        <div class="nav-item-label">Arrange</div>
      </div>
      <div class="nav-item" onclick="scrollToView('create')">
        <div class="nav-item-icon">✨</div>
        <div class="nav-item-label">Create</div>
      </div>
      <div class="nav-item" onclick="scrollToView('library')">
        <div class="nav-item-icon">📚</div>
        <div class="nav-item-label">Library</div>
      </div>
      <div class="nav-item" onclick="scrollToView('explore')">
        <div class="nav-item-icon">🔍</div>
        <div class="nav-item-label">Explore</div>
      </div>
    </div>
  </div>
  
  <script>
    let tracks = [];
    let library = JSON.parse(localStorage.getItem('p2j_library') || '[]');
    let currentAudio = null;
    let isPlaying = false;
    let selectedTrack = null;
    
    function init() {
      renderTracks();
      renderLibrary();
      document.getElementById('audio').addEventListener('timeupdate', updateTime);
    }
    
    function switchTab(tab) {
      document.querySelectorAll('.tab').forEach(t => t.classList.remove('active'));
      document.querySelectorAll('[data-tab="' + tab + '"]').forEach(t => {
        if (t.classList.contains('tab')) t.classList.add('active');
      });
      document.querySelectorAll('.tab-content').forEach(c => c.classList.remove('active'));
      document.querySelector('[data-tab="' + tab + '"].tab-content').classList.add('active');
    }
    
    function switchInspector(panel) {
      document.querySelectorAll('.inspector-tab').forEach(t => t.classList.remove('active'));
      event.target.classList.add('active');
      document.getElementById('mixer-panel').style.display = panel === 'mixer' ? 'block' : 'none';
      document.getElementById('effects-panel').style.display = panel === 'effects' ? 'block' : 'none';
    }
    
    function toggleLeftSidebar() {
      document.getElementById('leftSidebar').classList.toggle('collapsed');
    }
    
    function toggleRightSidebar() {
      document.getElementById('rightSidebar').classList.toggle('collapsed');
    }
    
    function updateValue(id) {
      document.getElementById(id + 'Value').textContent = document.getElementById(id).value;
    }
    
    async function generateMusic() {
      const prompt = document.getElementById('prompt').value.trim();
      if (!prompt) {
        showStatus('Enter a prompt', 'error');
        return;
      }
      
      const btn = document.getElementById('generateBtn');
      btn.disabled = true;
      btn.textContent = '⏳ Generating...';
      showStatus('Generating music... (30-60 seconds)', 'info');
      
      try {
        const res = await fetch('/api/generate', {
          method: 'POST',
          headers: {'Content-Type': 'application/json'},
          body: JSON.stringify({
            prompt,
            genre: document.getElementById('genre').value,
            mood: document.getElementById('mood').value,
            duration: parseInt(document.getElementById('duration').value),
            format: document.getElementById('format').value,
            lyrics: '[inst]'
          })
        });
        
        if (!res.ok) throw new Error('Generation failed');
        
        const blob = await res.blob();
        const url = URL.createObjectURL(blob);
        document.getElementById('audio').src = url;
        currentAudio = { url, blob, prompt };
        
        showStatus('✅ Generated! Ready to download or add to arrange', 'success');
      } catch (error) {
        showStatus(`❌ ${error.message}`, 'error');
      } finally {
        btn.disabled = false;
        btn.textContent = '🎵 Generate Music';
      }
    }
    
    function downloadAudio() {
      if (!currentAudio) {
        showStatus('Generate a track first', 'error');
        return;
      }
      const a = document.createElement('a');
      a.href = currentAudio.url;
      a.download = `p2j_${Date.now()}.${document.getElementById('format').value}`;
      a.click();
      showStatus('Downloaded!', 'success');
    }
    
    function addToArrange() {
      if (!currentAudio) {
        showStatus('Generate a track first', 'error');
        return;
      }
      addTrack();
      document.getElementById('timelineContent').innerHTML += `
        <div class="timeline-track">
          <div class="track-label">Generated - ${currentAudio.prompt.substring(0, 20)}...</div>
          <div class="timeline-clip" style="left:10%;width:40%;"><span>${currentAudio.prompt.substring(0, 25)}</span></div>
        </div>
      `;
      switchTab('arrange');
      showStatus('Added to arrange! Now ready to produce', 'success');
    }
    
    function saveToLibrary() {
      if (!currentAudio) return;
      library.unshift({
        id: Date.now().toString(),
        url: currentAudio.url,
        prompt: currentAudio.prompt,
        created: new Date().toLocaleDateString()
      });
      localStorage.setItem('p2j_library', JSON.stringify(library));
      renderLibrary();
    }
    
    function renderLibrary() {
      const list = document.getElementById('libraryList');
      if (!library.length) {
        list.innerHTML = '<p style="color:var(--text-muted);">No saved tracks yet</p>';
        return;
      }
      list.innerHTML = library.map(item => `
        <div style="background:var(--bg-hover);padding:10px;border-radius:6px;margin-bottom:8px;font-size:12px;">
          ${item.prompt.substring(0,40)}...
          <div style="margin-top:8px;display:flex;gap:6px;">
            <button class="btn btn-secondary" style="flex:1;padding:6px;" onclick="playFromLib('${item.id}')">▶</button>
            <button class="btn btn-secondary" style="flex:1;padding:6px;" onclick="deleteLib('${item.id}')">🗑</button>
          </div>
        </div>
      `).join('');
    }
    
    function playFromLib(id) {
      const item = library.find(i => i.id === id);
      if (item) {
        document.getElementById('audio').src = item.url;
        document.getElementById('audio').play();
      }
    }
    
    function deleteLib(id) {
      library = library.filter(i => i.id !== id);
      localStorage.setItem('p2j_library', JSON.stringify(library));
      renderLibrary();
    }
    
    function addTrack() {
      tracks.push({
        id: Date.now().toString(),
        name: `Track ${tracks.length + 1}`,
        muted: false,
        volume: 0.8
      });
      renderTracks();
    }
    
    function renderTracks() {
      const list = document.getElementById('trackList');
      list.innerHTML = tracks.map(t => `
        <div class="track-item" onclick="selectTrack('${t.id}')">
          <div class="track-icon">🎵</div>
          <div class="track-info">
            <div class="track-name">${t.name}</div>
            <div class="track-type">Audio</div>
          </div>
          <div class="track-controls">
            <button class="track-btn ${t.muted?'active':''}" onclick="event.stopPropagation();toggleMute('${t.id}')">M</button>
          </div>
        </div>
      `).join('');
    }
    
    function selectTrack(id) {
      selectedTrack = id;
      renderTracks();
    }
    
    function toggleMute(id) {
      const track = tracks.find(t => t.id === id);
      if (track) track.muted = !track.muted;
      renderTracks();
    }
    
    function togglePlay() {
      isPlaying = !isPlaying;
      document.getElementById('playBtn').textContent = isPlaying ? '⏸' : '▶';
      const audio = document.getElementById('audio');
      if (isPlaying) audio.play();
      else audio.pause();
    }
    
    function stop() {
      isPlaying = false;
      document.getElementById('playBtn').textContent = '▶';
      document.getElementById('audio').pause();
      document.getElementById('audio').currentTime = 0;
    }
    
    function seekStart() {
      document.getElementById('audio').currentTime = 0;
    }
    
    function updateTime() {
      const audio = document.getElementById('audio');
      const mm = Math.floor(audio.currentTime / 60);
      const ss = Math.floor(audio.currentTime % 60);
      document.getElementById('timeDisplay').textContent = 
        `${String(mm).padStart(2, '0')}:${String(ss).padStart(2, '0')}`;
    }
    
    function showStatus(msg, type) {
      const el = document.getElementById('statusMsg');
      el.textContent = msg;
      el.className = 'status-msg ' + (type === 'error' ? 'error' : type === 'success' ? 'success' : '');
      el.style.display = 'block';
      setTimeout(() => el.style.display = 'none', 5000);
    }
    
    function scrollToView(view) {
      document.querySelectorAll('.nav-item').forEach((n, i) => n.classList.remove('active'));
      event.target.closest('.nav-item').classList.add('active');
    }
    
    init();
  </script>
</body>
</html>
"""
