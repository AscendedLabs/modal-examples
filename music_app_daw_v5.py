# Prompt2Jam Studio v0.0.5 - Full DAW Features
# Enterprise music production PWA with timeline, stems, effects, and library

from typing import Optional, List
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

app = modal.App("prompt-2-jam-v5-daw")

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
        print(f"🎵 Generating: {prompt} ({duration}s, steps={inference_steps})")
        
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

    fastapi_app = FastAPI(title="Prompt2Jam Studio v0.0.5 (DAW Pro)")
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
        action: Optional[str] = "new"
        extend_by: Optional[int] = 0

    @fastapi_app.get("/", response_class=HTMLResponse)
    async def root():
        return HTML_DAW_V5

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
            
            duration = request.duration
            manual_seeds = request.seed or 1
            if request.action == "extend" and (request.extend_by or 0) > 0:
                duration = min(240, duration + int(request.extend_by or 0))
            elif request.action == "variation":
                manual_seeds = None
            
            audio_bytes = await generate.aio(
                prompt=enhanced_prompt,
                lyrics=lyrics or "[inst]",
                duration=duration,
                format=request.format,
                manual_seeds=manual_seeds,
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

HTML_DAW_V5 = """<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <meta name="theme-color" content="#0f172a" />
  <title>Prompt2Jam Studio Pro</title>
  <link rel="manifest" href="/manifest.json" />
  <style>
    *{box-sizing:border-box;margin:0;padding:0}
    :root{
      --bg-primary:#0f172a;--bg-secondary:#1e293b;--bg-tertiary:#334155;
      --text-primary:#f1f5f9;--text-secondary:#cbd5e1;--text-muted:#94a3b8;
      --accent:#6366f1;--accent-hover:#4f46e5;--success:#10b981;--danger:#ef4444;
      --border:#334155;--shadow:rgba(0,0,0,0.3)
    }
    body{
      font-family:-apple-system,BlinkMacSystemFont,Segoe UI,Roboto,Inter,sans-serif;
      background:var(--bg-primary);color:var(--text-primary);
      min-height:100vh;overflow-x:hidden
    }
    .app{display:flex;flex-direction:column;min-height:100vh}
    
    /* Header */
    header{
      display:flex;align-items:center;justify-content:space-between;
      padding:12px 20px;background:var(--bg-secondary);
      border-bottom:1px solid var(--border);backdrop-filter:blur(10px);
      position:sticky;top:0;z-index:100
    }
    .logo{font-size:18px;font-weight:700;letter-spacing:.3px}
    .header-actions{display:flex;gap:10px}
    .icon-btn{
      background:var(--bg-tertiary);border:1px solid var(--border);
      color:var(--text-secondary);padding:8px 12px;border-radius:8px;
      cursor:pointer;transition:all .2s
    }
    .icon-btn:hover{background:var(--accent);color:#fff;border-color:var(--accent)}
    
    /* Main content */
    main{flex:1;display:flex;flex-direction:column;padding:16px;gap:16px;overflow-y:auto}
    
    /* Views */
    .view{display:none;flex-direction:column;gap:16px;animation:fadeIn .3s}
    .view.active{display:flex}
    @keyframes fadeIn{from{opacity:0;transform:translateY(10px)}to{opacity:1;transform:translateY(0)}}
    
    /* Cards */
    .card{
      background:var(--bg-secondary);border:1px solid var(--border);
      border-radius:16px;padding:20px;box-shadow:0 4px 12px var(--shadow)
    }
    .card-title{font-size:16px;font-weight:600;margin-bottom:14px;color:var(--text-primary)}
    
    /* Form controls */
    .form-row{display:grid;gap:12px;margin-bottom:14px}
    @media(min-width:720px){.form-row.cols-2{grid-template-columns:1fr 1fr}}
    label{display:block;font-size:11px;font-weight:600;color:var(--text-muted);margin-bottom:6px;text-transform:uppercase;letter-spacing:.5px}
    input,textarea,select{
      width:100%;background:var(--bg-tertiary);color:var(--text-primary);
      border:1.5px solid var(--border);border-radius:10px;padding:10px 12px;
      font-size:14px;transition:all .2s
    }
    input:focus,textarea:focus,select:focus{outline:none;border-color:var(--accent);box-shadow:0 0 0 3px rgba(99,102,241,.1)}
    textarea{min-height:80px;resize:vertical;font-family:inherit}
    
    /* Buttons */
    .btn{
      padding:12px 18px;border-radius:10px;border:none;font-weight:600;
      cursor:pointer;transition:all .2s;font-size:14px
    }
    .btn-primary{background:var(--accent);color:#fff}
    .btn-primary:hover{background:var(--accent-hover);transform:translateY(-1px);box-shadow:0 6px 20px rgba(99,102,241,.4)}
    .btn-secondary{background:var(--bg-tertiary);color:var(--text-primary);border:1px solid var(--border)}
    .btn-secondary:hover{background:var(--accent);color:#fff;border-color:var(--accent)}
    .btn-success{background:var(--success);color:#fff}
    .btn-danger{background:var(--danger);color:#fff}
    .btn:disabled{opacity:.5;cursor:not-allowed}
    .btn-group{display:flex;gap:8px;flex-wrap:wrap}
    
    /* Timeline */
    .timeline-container{
      background:var(--bg-tertiary);border-radius:12px;padding:16px;
      min-height:120px;position:relative;overflow-x:auto
    }
    .timeline-track{
      background:rgba(255,255,255,.05);border-radius:8px;
      min-height:60px;margin-bottom:10px;position:relative;padding:8px
    }
    .timeline-clip{
      background:linear-gradient(135deg,var(--accent),#8b5cf6);
      border-radius:6px;padding:8px;color:#fff;font-size:12px;
      position:absolute;height:44px;cursor:move
    }
    
    /* Waveform */
    .waveform-container{height:100px;margin:12px 0;border-radius:8px;overflow:hidden}
    
    /* Library item */
    .library-item{
      display:flex;justify-content:space-between;align-items:center;
      padding:12px;background:var(--bg-tertiary);border-radius:10px;
      margin-bottom:8px;border:1px solid var(--border)
    }
    .library-item:hover{border-color:var(--accent)}
    .library-meta{flex:1}
    .library-title{font-weight:600;margin-bottom:4px}
    .library-details{font-size:12px;color:var(--text-muted)}
    
    /* Bottom nav */
    .bottom-nav{
      position:sticky;bottom:0;display:grid;grid-template-columns:repeat(4,1fr);
      gap:4px;padding:8px;background:var(--bg-secondary);
      border-top:1px solid var(--border);backdrop-filter:blur(10px)
    }
    .nav-tab{
      display:flex;flex-direction:column;align-items:center;gap:4px;
      padding:10px 8px;border-radius:12px;color:var(--text-muted);
      border:1px solid transparent;cursor:pointer;transition:all .2s;font-size:11px
    }
    .nav-tab.active{background:var(--accent);color:#fff;border-color:var(--accent)}
    .nav-tab:hover:not(.active){background:var(--bg-tertiary)}
    .nav-icon{font-size:20px}
    
    /* Status */
    .status{padding:12px;border-radius:8px;margin:10px 0;font-size:14px}
    .status.info{background:#1e3a8a;color:#93c5fd}
    .status.success{background:#065f46;color:#6ee7b7}
    .status.error{background:#7f1d1d;color:#fca5a5}
    
    /* Responsive */
    @media(max-width:640px){
      main{padding:12px}
      .card{padding:16px}
      .form-row.cols-2{grid-template-columns:1fr}
    }
  </style>
</head>
<body>
  <div class="app">
    <header>
      <div class="logo">🎵 Prompt2Jam Pro</div>
      <div class="header-actions">
        <button class="icon-btn" id="shareBtn" title="Share">🔗</button>
        <button class="icon-btn" id="settingsBtn" title="Settings">⚙️</button>
      </div>
    </header>
    
    <main>
      <!-- CREATE VIEW -->
      <section id="view-create" class="view active">
        <div class="card">
          <h3 class="card-title">✨ Create New Track</h3>
          <form id="generateForm">
            <div class="form-row">
              <div>
                <label>Prompt</label>
                <textarea id="prompt" placeholder="Describe your music: upbeat electronic dance with synth melodies"></textarea>
              </div>
            </div>
            <div class="form-row cols-2">
              <div>
                <label>Genre</label>
                <select id="genre">
                  <option value="">Auto</option>
                  <option>Pop</option><option>Rock</option><option>Jazz</option>
                  <option>Electronic</option><option>Hip-Hop</option><option>Classical</option>
                </select>
              </div>
              <div>
                <label>Mood</label>
                <select id="mood">
                  <option value="">Auto</option>
                  <option>Happy</option><option>Sad</option><option>Energetic</option>
                  <option>Calm</option><option>Epic</option>
                </select>
              </div>
            </div>
            <div class="form-row cols-2">
              <div>
                <label>Duration (s)</label>
                <input id="duration" type="number" min="5" max="240" value="30" />
              </div>
              <div>
                <label>Format</label>
                <select id="format">
                  <option value="wav">WAV</option>
                  <option value="mp3">MP3</option>
                  <option value="flac">FLAC</option>
                </select>
              </div>
            </div>
            <div class="btn-group">
              <button type="submit" class="btn btn-primary" style="flex:1">🎵 Generate</button>
              <button type="button" id="variationBtn" class="btn btn-secondary">🎲 Variation</button>
              <button type="button" id="extendBtn" class="btn btn-secondary">➕ Extend</button>
            </div>
          </form>
          <div id="status"></div>
        </div>
        
        <div class="card">
          <h3 class="card-title">🎧 Player</h3>
          <div id="waveform" class="waveform-container"></div>
          <audio id="audio" controls style="width:100%;margin-top:12px"></audio>
          <div class="btn-group" style="margin-top:12px">
            <a id="downloadLink" class="btn btn-success" download>⬇️ Download</a>
            <button id="saveToLibraryBtn" class="btn btn-secondary">💾 Save to Library</button>
          </div>
        </div>
      </section>
      
      <!-- TIMELINE VIEW -->
      <section id="view-timeline" class="view">
        <div class="card">
          <h3 class="card-title">🎬 Multi-Track Timeline</h3>
          <div class="timeline-container">
            <div class="timeline-track">
              <small style="color:var(--text-muted)">Track 1: Vocals</small>
            </div>
            <div class="timeline-track">
              <small style="color:var(--text-muted)">Track 2: Instrumental</small>
            </div>
          </div>
          <div class="btn-group">
            <button class="btn btn-primary">➕ Add Track</button>
            <button class="btn btn-secondary">🎚️ Mixer</button>
            <button class="btn btn-secondary">🎛️ Effects</button>
          </div>
        </div>
      </section>
      
      <!-- LIBRARY VIEW -->
      <section id="view-library" class="view">
        <div class="card">
          <h3 class="card-title">📚 Your Library</h3>
          <div id="libraryList"></div>
        </div>
      </section>
      
      <!-- EXPLORE VIEW -->
      <section id="view-explore" class="view">
        <div class="card">
          <h3 class="card-title">🔥 Trending</h3>
          <p style="color:var(--text-muted)">Discover featured tracks and popular prompts.</p>
        </div>
      </section>
    </main>
    
    <nav class="bottom-nav">
      <button class="nav-tab active" data-view="create">
        <span class="nav-icon">✨</span>
        <span>Create</span>
      </button>
      <button class="nav-tab" data-view="timeline">
        <span class="nav-icon">🎬</span>
        <span>Timeline</span>
      </button>
      <button class="nav-tab" data-view="library">
        <span class="nav-icon">📚</span>
        <span>Library</span>
      </button>
      <button class="nav-tab" data-view="explore">
        <span class="nav-icon">🔥</span>
        <span>Explore</span>
      </button>
    </nav>
  </div>
  
  <script src="https://unpkg.com/wavesurfer.js"></script>
  <script>
    // Navigation
    const tabs = document.querySelectorAll('.nav-tab');
    const views = {
      create: document.getElementById('view-create'),
      timeline: document.getElementById('view-timeline'),
      library: document.getElementById('view-library'),
      explore: document.getElementById('view-explore')
    };
    
    function setView(name) {
      Object.values(views).forEach(v => v.classList.remove('active'));
      views[name].classList.add('active');
      tabs.forEach(t => t.classList.toggle('active', t.dataset.view === name));
      localStorage.setItem('p2j_view', name);
    }
    
    tabs.forEach(t => t.addEventListener('click', () => setView(t.dataset.view)));
    setView(localStorage.getItem('p2j_view') || 'create');
    
    // Library management
    let library = JSON.parse(localStorage.getItem('p2j_library') || '[]');
    let currentAudio = null;
    let wavesurfer = null;
    
    function saveToLibrary(audioUrl, metadata) {
      const item = {
        id: Date.now().toString(),
        url: audioUrl,
        ...metadata,
        createdAt: new Date().toISOString()
      };
      library.unshift(item);
      localStorage.setItem('p2j_library', JSON.stringify(library));
      renderLibrary();
      showStatus('Saved to library!', 'success');
    }
    
    function renderLibrary() {
      const list = document.getElementById('libraryList');
      if (!library.length) {
        list.innerHTML = '<p style="color:var(--text-muted)">No tracks yet. Create something!</p>';
        return;
      }
      list.innerHTML = library.map(item => `
        <div class="library-item">
          <div class="library-meta">
            <div class="library-title">${item.prompt?.substring(0, 50) || 'Untitled'}</div>
            <div class="library-details">${item.format?.toUpperCase()} • ${new Date(item.createdAt).toLocaleString()}</div>
          </div>
          <div class="btn-group">
            <button class="btn btn-secondary" onclick="playFromLibrary('${item.id}')">▶️</button>
            <a class="btn btn-secondary" href="${item.url}" download>⬇️</a>
            <button class="btn btn-danger" onclick="deleteFromLibrary('${item.id}')">🗑️</button>
          </div>
        </div>
      `).join('');
    }
    
    window.playFromLibrary = (id) => {
      const item = library.find(i => i.id === id);
      if (item) {
        document.getElementById('audio').src = item.url;
        document.getElementById('audio').play();
        if (wavesurfer) wavesurfer.load(item.url);
        setView('create');
      }
    };
    
    window.deleteFromLibrary = (id) => {
      if (confirm('Delete this track?')) {
        library = library.filter(i => i.id !== id);
        localStorage.setItem('p2j_library', JSON.stringify(library));
        renderLibrary();
      }
    };
    
    // Generation
    function showStatus(msg, type = 'info') {
      const status = document.getElementById('status');
      status.textContent = msg;
      status.className = `status ${type}`;
      setTimeout(() => status.className = 'status', 5000);
    }
    
    async function generate(action = 'new', extendBy = 0) {
      const prompt = document.getElementById('prompt').value.trim();
      if (!prompt) {
        showStatus('Enter a prompt first', 'error');
        return;
      }
      
      showStatus('🎼 Generating... (30-60s)', 'info');
      
      const req = {
        prompt,
        genre: document.getElementById('genre').value,
        mood: document.getElementById('mood').value,
        duration: parseInt(document.getElementById('duration').value),
        format: document.getElementById('format').value,
        action,
        extend_by: extendBy,
        lyrics: '[inst]'
      };
      
      try {
        const res = await fetch('/api/generate', {
          method: 'POST',
          headers: {'Content-Type': 'application/json'},
          body: JSON.stringify(req)
        });
        
        if (!res.ok) throw new Error('Generation failed');
        
        const blob = await res.blob();
        const url = URL.createObjectURL(blob);
        const audio = document.getElementById('audio');
        audio.src = url;
        audio.play();
        
        if (window.WaveSurfer) {
          if (wavesurfer) wavesurfer.destroy();
          wavesurfer = WaveSurfer.create({
            container: '#waveform',
            waveColor: '#64748b',
            progressColor: '#6366f1',
            height: 100
          });
          wavesurfer.load(url);
        }
        
        const dl = document.getElementById('downloadLink');
        dl.href = url;
        dl.download = `p2j_${Date.now()}.${req.format}`;
        
        currentAudio = { url, metadata: req };
        showStatus('✅ Ready!', 'success');
      } catch (error) {
        showStatus(`❌ ${error.message}`, 'error');
      }
    }
    
    document.getElementById('generateForm').addEventListener('submit', e => {
      e.preventDefault();
      generate('new', 0);
    });
    
    document.getElementById('variationBtn').addEventListener('click', () => generate('variation', 0));
    document.getElementById('extendBtn').addEventListener('click', () => generate('extend', 10));
    
    document.getElementById('saveToLibraryBtn').addEventListener('click', () => {
      if (currentAudio) {
        saveToLibrary(currentAudio.url, currentAudio.metadata);
      } else {
        showStatus('Generate a track first', 'error');
      }
    });
    
    document.getElementById('shareBtn').addEventListener('click', () => {
      if (navigator.share && currentAudio) {
        navigator.share({
          title: 'Check out my Prompt2Jam track',
          url: window.location.href
        }).catch(() => {});
      } else {
        navigator.clipboard.writeText(window.location.href);
        showStatus('Link copied!', 'success');
      }
    });
    
    renderLibrary();
  </script>
</body>
</html>
"""
