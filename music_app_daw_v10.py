# Prompt2Jam Studio v0.0.10 - PROPER MULTI-PAGE DAW
# Combines ALL features from v0.0.5 + v0.0.6 + v0.0.7 + v0.0.8
# Page 1: Generate (like v0.0.5 - simple, clean)
# Page 2: Arrange (mixer + piano roll + timeline from v0.0.6/0.0.7)
# ACE-STUDIO inspired layout for mobile DAWs

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

app = modal.App("prompt-2-jam-v10-multipage")

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
        duration: float = 60.0,
        format: str = "wav",
        manual_seeds: Optional[int] = 1,
        inference_steps: int = 60,
        guidance_scale: float = 15.0,
    ) -> bytes:
        import tempfile
        import torch
        from transformers import AutoModelForCausalLM, AutoTokenizer

        if self.model is None:
            from ace_step.model import ACEStepModel
            self.model = ACEStepModel.from_pretrained(
                cache_dir=cache_dir,
                torch_dtype=torch.bfloat16
            ).to("cuda")

        with tempfile.NamedTemporaryFile(suffix=f".{format}", delete=False) as tmp:
            self.model.generate(
                prompt=prompt,
                lyrics=lyrics,
                duration=duration,
                output_path=tmp.name,
                manual_seeds=manual_seeds,
                inference_steps=inference_steps,
                guidance_scale=guidance_scale,
            )
            with open(tmp.name, "rb") as f:
                return f.read()

@app.function(image=web_image, keep_warm=1)
@modal.asgi_app()
def web_ui():
    from fastapi import FastAPI, Request
    from fastapi.responses import Response, HTMLResponse, JSONResponse
    from pydantic import BaseModel
    import asyncio

    web_app = FastAPI()

    class GenerateRequest(BaseModel):
        prompt: str
        genre: str = ""
        mood: str = ""
        lyrics: str = "[inst]"
        duration: float = 60.0
        format: str = "wav"
        inference_steps: int = 60
        guidance_scale: float = 15.0

    @web_app.post("/api/generate")
    async def generate_music(request: GenerateRequest):
        try:
            full_prompt = request.prompt
            if request.genre and request.genre.lower() != "auto":
                full_prompt = f"{request.genre.lower()} {full_prompt}"
            if request.mood and request.mood.lower() != "auto":
                full_prompt = f"{request.mood.lower()} {full_prompt}"

            generator = MusicGenerator()
            audio_bytes = generator.run.remote(
                prompt=full_prompt,
                lyrics=request.lyrics or "[inst]",
                duration=request.duration,
                format=request.format,
                inference_steps=request.inference_steps,
                guidance_scale=request.guidance_scale,
            )

            return Response(
                content=audio_bytes,
                media_type=f"audio/{request.format}",
                headers={
                    "Content-Disposition": f'attachment; filename="prompt2jam_{uuid4().hex[:8]}.{request.format}"'
                },
            )
        except Exception as e:
            return JSONResponse({"error": str(e)}, status_code=500)

    HTML_MULTIPAGE_DAW = f'''<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1,maximum-scale=1,user-scalable=no">
<title>Prompt2Jam Studio v0.0.10 - Multi-Page DAW</title>
<style>
*{{margin:0;padding:0;box-sizing:border-box}}
:root{{
  --bg:#0f172a;--bg-secondary:#1e293b;--bg-tertiary:#334155;
  --text:#f1f5f9;--text-secondary:#cbd5e1;--text-muted:#64748b;
  --accent:#6366f1;--accent-hover:#4f46e5;--border:#334155;
  --success:#10b981;--danger:#ef4444;--shadow:rgba(0,0,0,.3)
}}
body{{
  font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,sans-serif;
  background:var(--bg);color:var(--text);min-height:100vh;
  display:flex;flex-direction:column;overflow:hidden
}}

/* Header */
header{{
  padding:12px 16px;background:var(--bg-secondary);
  border-bottom:1px solid var(--border);display:flex;
  justify-content:space-between;align-items:center;flex-shrink:0
}}
.logo{{font-size:18px;font-weight:700;color:var(--accent)}}
.header-nav{{display:flex;gap:8px}}
.header-btn{{
  background:var(--bg-tertiary);border:1px solid var(--border);
  color:var(--text-secondary);padding:6px 14px;border-radius:8px;
  cursor:pointer;transition:all .2s;font-size:13px
}}
.header-btn:hover{{background:var(--accent);color:#fff;border-color:var(--accent)}}
.header-btn.active{{background:var(--accent);color:#fff;border-color:var(--accent)}}

/* Main container */
main{{flex:1;overflow:hidden;position:relative}}

/* Pages */
.page{{
  display:none;width:100%;height:100%;
  position:absolute;top:0;left:0;
  overflow-y:auto;animation:fadeIn .3s
}}
.page.active{{display:block}}
@keyframes fadeIn{{from{{opacity:0;transform:translateY(10px)}}to{{opacity:1;transform:translateY(0)}}}}

/* ===== PAGE 1: GENERATE (v0.0.5 style) ===== */
#page-generate{{padding:16px}}
.generate-container{{max-width:800px;margin:0 auto;display:flex;flex-direction:column;gap:16px}}
.card{{
  background:var(--bg-secondary);border:1px solid var(--border);
  border-radius:16px;padding:20px;box-shadow:0 4px 12px var(--shadow)
}}
.card-title{{font-size:16px;font-weight:600;margin-bottom:14px;color:var(--text)}}
.form-row{{display:grid;gap:12px;margin-bottom:14px}}
@media(min-width:720px){{.form-row.cols-2{{grid-template-columns:1fr 1fr}}}}
label{{
  display:block;font-size:11px;font-weight:600;
  color:var(--text-muted);margin-bottom:6px;
  text-transform:uppercase;letter-spacing:.5px
}}
input,textarea,select{{
  width:100%;background:var(--bg-tertiary);color:var(--text);
  border:1.5px solid var(--border);border-radius:10px;
  padding:10px 12px;font-size:14px;transition:all .2s
}}
input:focus,textarea:focus,select:focus{{
  outline:none;border-color:var(--accent);
  box-shadow:0 0 0 3px rgba(99,102,241,.1)
}}
textarea{{min-height:80px;resize:vertical;font-family:inherit}}
.btn{{
  padding:12px 18px;border-radius:10px;border:none;
  font-weight:600;cursor:pointer;transition:all .2s;font-size:14px
}}
.btn-primary{{background:var(--accent);color:#fff}}
.btn-primary:hover{{
  background:var(--accent-hover);transform:translateY(-1px);
  box-shadow:0 6px 20px rgba(99,102,241,.4)
}}
.btn-secondary{{
  background:var(--bg-tertiary);color:var(--text);
  border:1px solid var(--border)
}}
.btn-secondary:hover{{background:var(--accent);color:#fff;border-color:var(--accent)}}
.btn:disabled{{opacity:.5;cursor:not-allowed}}
.btn-group{{display:flex;gap:8px;flex-wrap:wrap}}
.status{{padding:12px;border-radius:8px;margin:10px 0;font-size:14px}}
.status.info{{background:#1e3a8a;color:#93c5fd}}
.status.success{{background:#065f46;color:#6ee7b7}}
.status.error{{background:#7f1d1d;color:#fca5a5}}
audio{{width:100%;margin:12px 0}}

/* ===== PAGE 2: ARRANGE (v0.0.6/0.0.7 style) ===== */
#page-arrange{{display:flex;flex-direction:column;height:100%}}

/* Toolbar */
.arrange-toolbar{{
  padding:10px 16px;background:var(--bg-secondary);
  border-bottom:1px solid var(--border);display:flex;
  gap:10px;align-items:center;flex-wrap:wrap
}}
.tool-btn{{
  background:var(--bg-tertiary);border:1px solid var(--border);
  color:var(--text-secondary);padding:8px 14px;border-radius:8px;
  cursor:pointer;transition:all .2s;font-size:13px;
  display:flex;align-items:center;gap:6px
}}
.tool-btn:hover{{background:var(--accent);color:#fff;border-color:var(--accent)}}
.tool-btn.active{{background:var(--accent);color:#fff;border-color:var(--accent)}}

/* Main arrange area - 3 columns */
.arrange-content{{flex:1;display:flex;overflow:hidden}}

/* Left panel - Track list */
.track-panel{{
  width:200px;background:var(--bg-secondary);
  border-right:1px solid var(--border);
  display:flex;flex-direction:column;flex-shrink:0
}}
.track-panel-header{{
  padding:12px 16px;border-bottom:1px solid var(--border);
  font-weight:600;font-size:13px
}}
.track-list{{flex:1;overflow-y:auto;padding:8px}}
.track-item{{
  background:var(--bg-tertiary);border:1px solid var(--border);
  border-radius:8px;padding:10px;margin-bottom:8px;
  cursor:pointer;transition:all .2s
}}
.track-item:hover{{border-color:var(--accent)}}
.track-item.active{{border-color:var(--accent);background:rgba(99,102,241,.1)}}
.track-name{{font-size:13px;font-weight:600;margin-bottom:4px}}
.track-type{{font-size:11px;color:var(--text-muted)}}
.add-track-btn{{
  margin:10px;padding:10px;background:var(--accent);
  color:#fff;border:none;border-radius:8px;
  cursor:pointer;font-weight:600;font-size:13px
}}
.add-track-btn:hover{{background:var(--accent-hover)}}

/* Center panel - Timeline/Mixer/Piano Roll */
.workspace-panel{{flex:1;display:flex;flex-direction:column;overflow:hidden}}
.workspace-panel.split{{gap:8px}}
.workspace-panel.split #timelineView{{display:block;flex:1}}
.workspace-panel.split #mixerView{{display:flex;flex:1}}

/* Timeline view */
.timeline-view{{flex:1;overflow:auto;background:var(--bg)}}
.timeline-ruler{{
  height:30px;background:var(--bg-secondary);
  border-bottom:1px solid var(--border);
  display:flex;padding:0 200px 0 0
}}
.timeline-marker{{
  flex:1;padding:6px 8px;font-size:11px;
  color:var(--text-muted);border-right:1px solid var(--border)
}}
.timeline-tracks{{padding:8px 0}}
.timeline-track{{
  height:60px;background:rgba(255,255,255,.02);
  border-bottom:1px solid var(--border);
  position:relative;padding:8px;display:flex;align-items:center
}}
.timeline-clip{{
  background:linear-gradient(135deg,var(--accent),#8b5cf6);
  border-radius:6px;padding:8px;color:#fff;
  font-size:12px;position:absolute;height:44px;
  cursor:move;left:10%;width:40%
}}
.clip-name{{font-weight:600;margin-bottom:2px}}
.clip-waveform{{
  height:20px;background:rgba(255,255,255,.2);
  border-radius:3px;margin-top:4px
}}

/* Mixer view */
.mixer-view{{
  display:none;flex:1;padding:20px;
  overflow-x:auto;overflow-y:auto
}}
.mixer-view.active{{display:flex}}
.mixer-channels{{display:flex;gap:16px;align-items:flex-end}}
.mixer-channel{{
  background:var(--bg-secondary);border:1px solid var(--border);
  border-radius:12px;padding:16px;width:90px;
  display:flex;flex-direction:column;align-items:center;gap:8px
}}
.channel-label{{font-size:11px;font-weight:600;text-align:center}}
.channel-fader{{
  width:40px;height:200px;background:var(--bg-tertiary);
  border-radius:20px;position:relative;border:1px solid var(--border)
}}
.fader-thumb{{
  width:100%;height:20px;background:var(--accent);
  border-radius:10px;position:absolute;cursor:ns-resize;
  transition:background .2s
}}
.fader-thumb:hover{{background:var(--accent-hover)}}
.channel-meter{{
  width:40px;height:60px;background:var(--bg-tertiary);
  border-radius:6px;border:1px solid var(--border);
  position:relative;overflow:hidden
}}
.meter-bar{{
  width:100%;background:linear-gradient(to top,var(--success),#fbbf24,var(--danger));
  position:absolute;bottom:0;height:0%;transition:height .1s
}}
.channel-value{{font-size:10px;color:var(--text-muted)}}
.mixer-channel.master{{background:rgba(99,102,241,.15);border-color:var(--accent)}}

/* Piano Roll view */
.piano-roll{{
  display:none;flex:1;overflow:auto;
  background:var(--bg)
}}
.piano-roll.active{{display:block}}
.piano-roll-grid{{
  display:flex;height:100%;min-height:420px
}}
.piano-keys{{
  width:60px;background:var(--bg-secondary);
  border-right:1px solid var(--border);flex-shrink:0
}}
.piano-key{{
  height:20px;border-bottom:1px solid var(--border);
  padding:4px 8px;font-size:10px;color:var(--text-muted);
  display:flex;align-items:center;justify-content:center
}}
.piano-key.black{{background:var(--bg-tertiary)}}
.piano-grid{{
  flex:1;position:relative;
  background-image:
    repeating-linear-gradient(0deg,var(--border) 0,var(--border) 1px,transparent 1px,transparent 20px),
    repeating-linear-gradient(90deg,var(--border) 0,var(--border) 1px,transparent 1px,transparent 60px);
  background-size:100% 20px,60px 100%
}}
.piano-note{{
  position:absolute;background:var(--accent);
  border-radius:4px;height:16px;top:1px;
  cursor:pointer;transition:background .2s;
  max-width:140px
}}
.piano-note:hover{{background:var(--accent-hover)}}

/* Right panel - Inspector */
.inspector-panel{{
  width:280px;background:var(--bg-secondary);
  border-left:1px solid var(--border);
  display:flex;flex-direction:column;flex-shrink:0
}}
.inspector-header{{
  padding:12px 16px;border-bottom:1px solid var(--border);
  font-weight:600;font-size:13px
}}
.inspector-content{{flex:1;overflow-y:auto;padding:16px}}
.inspector-section{{margin-bottom:20px}}
.section-title{{
  font-size:12px;font-weight:600;
  color:var(--text-muted);margin-bottom:10px;
  text-transform:uppercase;letter-spacing:.5px
}}
.param-group{{margin-bottom:14px}}
.param-label{{
  display:block;font-size:11px;font-weight:600;
  color:var(--text-muted);margin-bottom:6px
}}
.param-input{{
  width:100%;background:var(--bg-tertiary);
  border:1px solid var(--border);border-radius:6px;
  padding:8px 10px;color:var(--text);font-size:13px
}}
.param-slider{{width:100%;margin:8px 0}}

/* Transport controls */
.transport-bar{{
  height:60px;background:var(--bg-secondary);
  border-top:1px solid var(--border);
  display:flex;align-items:center;justify-content:center;
  gap:12px;flex-shrink:0
}}
.transport-btn{{
  width:44px;height:44px;background:var(--accent);
  color:#fff;border:none;border-radius:50%;
  font-size:18px;cursor:pointer;
  transition:all .2s;display:flex;
  align-items:center;justify-content:center
}}
.transport-btn:hover{{
  background:var(--accent-hover);
  transform:scale(1.1)
}}
.time-display{{
  font-family:monospace;font-size:20px;
  min-width:120px;text-align:center;
  color:var(--accent)
}}

/* Responsive */
@media(max-width:1024px){{
  .track-panel{{width:160px}}
  .inspector-panel{{width:240px}}
}}
@media(max-width:768px){{
  .arrange-content{{flex-direction:column}}
  .track-panel,.inspector-panel{{
    width:100%;max-height:200px;
    border:none;border-bottom:1px solid var(--border)
  }}
  .mixer-channels{{flex-direction:row;overflow-x:auto}}
}}

/* Library view */
.library-container{{padding:16px;max-width:1200px;margin:0 auto}}
.library-grid{{
  display:grid;grid-template-columns:repeat(auto-fill,minmax(280px,1fr));
  gap:16px;margin-top:16px
}}
.library-item{{
  background:var(--bg-secondary);border:1px solid var(--border);
  border-radius:12px;padding:16px;transition:all .2s
}}
.library-item:hover{{border-color:var(--accent);transform:translateY(-2px)}}
.library-title{{font-weight:600;margin-bottom:6px}}
.library-meta{{font-size:12px;color:var(--text-muted);margin-bottom:12px}}
.library-actions{{display:flex;gap:8px}}
.library-actions button{{
  flex:1;padding:8px;border-radius:6px;
  border:1px solid var(--border);background:var(--bg-tertiary);
  color:var(--text);cursor:pointer;font-size:12px
}}
.library-actions button:hover{{background:var(--accent);color:#fff;border-color:var(--accent)}}
</style>
</head>
<body>
<header>
  <div class="logo">🎵 Prompt2Jam Studio</div>
  <div class="header-nav">
    <button class="header-btn active" onclick="switchPage('generate')">🎨 Generate</button>
    <button class="header-btn" onclick="switchPage('arrange')">🎹 Arrange</button>
    <button class="header-btn" onclick="switchPage('library')">📚 Library</button>
  </div>
</header>

<main>
  <!-- PAGE 1: GENERATE (Beautiful clean page from v9_fixed) -->
  <div id="page-generate" class="page active">
    <div class="generate-container">
      <div class="card">
        <h3 class="card-title">✨ Create Music</h3>
        <form id="generateForm" onsubmit="generateMusic(event)">
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
            <button type="submit" class="btn btn-primary" id="generateBtn" style="flex: 1;">🎵 Generate Music</button>
            <button type="button" class="btn btn-secondary" onclick="randomVariation()">🎲 Variation</button>
          </div>
          
          <div id="status"></div>
        </form>
      </div>
      
      <div class="card">
        <h3 class="card-title">🎧 Playback</h3>
        <audio id="audioPlayer" controls></audio>
        <div class="btn-group" style="margin-top: 12px;">
          <button class="btn btn-success" onclick="downloadTrack()" style="flex: 1;">⬇️ Download</button>
          <button class="btn btn-primary" onclick="addToArrange()" style="flex: 1;">➕ Add to Arrange</button>
          <button class="btn btn-secondary" onclick="saveToLibrary()">💾 Save</button>
        </div>
      </div>
    </div>
  </div>

  <!-- PAGE 2: ARRANGE -->
  <div id="page-arrange" class="page">
    <div class="arrange-toolbar">
      <button class="tool-btn active" onclick="showArrangeView('timeline')">📊 Timeline</button>
      <button class="tool-btn" onclick="showArrangeView('mixer')">🎚️ Mixer</button>
      <button class="tool-btn" onclick="showArrangeView('piano')">🎹 Piano Roll</button>
      <button class="tool-btn" onclick="showArrangeView('split')">↕ Split</button>
    </div>
    
    <div class="arrange-content">
      <!-- Left: Track list -->
      <div class="track-panel">
        <div class="track-panel-header">Tracks</div>
        <div class="track-list" id="trackList">
          <div class="track-item active">
            <div class="track-name">Track 1</div>
            <div class="track-type">Audio</div>
          </div>
          <div class="track-item">
            <div class="track-name">Track 2</div>
            <div class="track-type">Audio</div>
          </div>
        </div>
        <button class="add-track-btn" onclick="addTrack()">+ Add Track</button>
      </div>
      
      <!-- Center: Timeline/Mixer/Piano Roll -->
      <div class="workspace-panel" id="workspacePanel">
        <!-- Timeline view -->
        <div class="timeline-view active" id="timelineView">
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
              <div class="timeline-clip">
                <div class="clip-name">Vocals.wav</div>
                <div class="clip-waveform"></div>
              </div>
            </div>
            <div class="timeline-track">
              <div class="timeline-clip" style="left:20%;width:35%">
                <div class="clip-name">Piano.wav</div>
                <div class="clip-waveform"></div>
              </div>
            </div>
          </div>
        </div>
        
        <!-- Mixer view -->
        <div class="mixer-view" id="mixerView">
          <div class="mixer-channels">
            <div class="mixer-channel">
              <div class="channel-label">Track 1</div>
              <div class="channel-fader">
                <div class="fader-thumb" style="bottom:60%"></div>
              </div>
              <div class="channel-meter">
                <div class="meter-bar" style="height:50%"></div>
              </div>
              <div class="channel-value">-12 dB</div>
            </div>
            <div class="mixer-channel">
              <div class="channel-label">Track 2</div>
              <div class="channel-fader">
                <div class="fader-thumb" style="bottom:70%"></div>
              </div>
              <div class="channel-meter">
                <div class="meter-bar" style="height:60%"></div>
              </div>
              <div class="channel-value">-6 dB</div>
            </div>
            <div class="mixer-channel master">
              <div class="channel-label">Master</div>
              <div class="channel-fader">
                <div class="fader-thumb" style="bottom:80%"></div>
              </div>
              <div class="channel-meter">
                <div class="meter-bar" style="height:75%"></div>
              </div>
              <div class="channel-value">0 dB</div>
            </div>
          </div>
        </div>
        
        <!-- Piano Roll view -->
        <div class="piano-roll" id="pianoRollView">
          <div class="piano-roll-grid">
            <div class="piano-keys" id="pianoKeys"></div>
            <div class="piano-grid" id="pianoGrid">
              <div class="piano-note" style="left:120px;width:90px;top:90px"></div>
              <div class="piano-note" style="left:240px;width:70px;top:130px"></div>
              <div class="piano-note" style="left:330px;width:110px;top:170px"></div>
            </div>
          </div>
        </div>
        
        <!-- Transport controls -->
        <div class="transport-bar">
          <button class="transport-btn" onclick="playArrange()">▶</button>
          <button class="transport-btn" onclick="pauseArrange()">⏸</button>
          <button class="transport-btn" onclick="stopArrange()">⏹</button>
          <div class="time-display" id="timeDisplay">00:00.000</div>
        </div>
      </div>
      
      <!-- Right: Inspector -->
      <div class="inspector-panel">
        <div class="inspector-header">Track Inspector</div>
        <div class="inspector-content">
          <div class="inspector-section">
            <div class="section-title">Track Settings</div>
            <div class="param-group">
              <label class="param-label">Track Name</label>
              <input type="text" class="param-input" value="Track 1">
            </div>
            <div class="param-group">
              <label class="param-label">Volume</label>
              <input type="range" class="param-slider" min="0" max="100" value="80">
            </div>
            <div class="param-group">
              <label class="param-label">Pan</label>
              <input type="range" class="param-slider" min="-100" max="100" value="0">
            </div>
          </div>
          
          <div class="inspector-section">
            <div class="section-title">Effects</div>
            <div class="param-group">
              <label class="param-label">Reverb</label>
              <input type="range" class="param-slider" min="0" max="100" value="20">
            </div>
            <div class="param-group">
              <label class="param-label">Delay</label>
              <input type="range" class="param-slider" min="0" max="100" value="0">
            </div>
            <div class="param-group">
              <label class="param-label">Chorus</label>
              <input type="range" class="param-slider" min="0" max="100" value="0">
            </div>
          </div>
        </div>
      </div>
    </div>
  </div>

  <!-- PAGE 3: LIBRARY -->
  <div id="page-library" class="page">
    <div class="library-container">
      <div class="card">
        <h3 class="card-title">📚 Your Library</h3>
        <div class="library-grid" id="libraryGrid">
          <!-- Library items loaded from localStorage -->
        </div>
      </div>
    </div>
  </div>
</main>

<script>
// State
let currentPage = 'generate';
let currentArrangeView = 'timeline';
let currentAudio = null;
let library = JSON.parse(localStorage.getItem('p2j_library') || '[]');
let arrangeTrackCounter = 2;

// Page switching
function switchPage(page) {{
  currentPage = page;
  document.querySelectorAll('.page').forEach(p => p.classList.remove('active'));
  document.getElementById(`page-${{page}}`).classList.add('active');
  document.querySelectorAll('.header-btn').forEach((btn,idx) => {{
    btn.classList.toggle('active',['generate','arrange','library'][idx]===page);
  }});
  
  if(page === 'library') renderLibrary();
}}

// Arrange view switching
function showArrangeView(view) {{
  currentArrangeView = view;
  const workspace = document.getElementById('workspacePanel');
  const views = ['timeline','mixer','piano','split'];
  document.querySelectorAll('.tool-btn').forEach((btn,idx) => {{
    btn.classList.toggle('active',views[idx]===view);
  }});
  
  if(view === 'split') {{
    workspace.classList.add('split');
    document.getElementById('timelineView').classList.add('active');
    document.getElementById('mixerView').classList.add('active');
    document.getElementById('pianoRollView').classList.remove('active');
  }} else {{
    workspace.classList.remove('split');
    document.getElementById('timelineView').classList.toggle('active',view==='timeline');
    document.getElementById('mixerView').classList.toggle('active',view==='mixer');
    document.getElementById('pianoRollView').classList.toggle('active',view==='piano');
  }}
  
  if(view === 'piano' || view === 'split') initPianoRoll();
}}

// Generate music
async function generateMusic(e) {{
  e.preventDefault();
  const form = e.target;
  const btn = document.getElementById('generateBtn');
  const statusDiv = document.getElementById('status');
  const player = document.getElementById('player');
  
  btn.disabled = true;
  btn.textContent = '🎵 Generating...';
  statusDiv.innerHTML = '<div class="status info">⏳ Generating music (30-60 seconds)...</div>';
  player.classList.remove('active');
  
  try {{
    const response = await fetch('/api/generate', {{
      method: 'POST',
      headers: {{'Content-Type': 'application/json'}},
      body: JSON.stringify({{
        prompt: form.prompt.value,
        genre: form.genre.value,
        mood: form.mood.value,
        lyrics: form.lyrics.value || '[inst]',
        duration: parseFloat(form.duration.value),
        format: form.format.value
      }})
    }});
    
    if(!response.ok) throw new Error('Generation failed');
    
    const blob = await response.blob();
    const url = URL.createObjectURL(blob);
    
    currentAudio = {{
      url,
      prompt: form.prompt.value,
      genre: form.genre.value,
      mood: form.mood.value,
      lyrics: form.lyrics.value,
      duration: form.duration.value,
      format: form.format.value,
      created: new Date().toISOString()
    }};
    
    document.getElementById('audioPlayer').src = url;
    player.classList.add('active');
    statusDiv.innerHTML = '<div class="status success">✅ Music generated successfully!</div>';
  }} catch(err) {{
    statusDiv.innerHTML = `<div class="status error">❌ Error: ${{err.message}}</div>`;
  }} finally {{
    btn.disabled = false;
    btn.textContent = '🎵 Generate Music';
  }}
}}

// Random variation
function randomVariation() {{
  const prompts = [
    'Upbeat electronic dance with synth melodies',
    'Chill lofi hip hop with piano and rain sounds',
    'Epic orchestral cinematic with strings',
    'Funky bassline with groovy drums',
    'Ambient atmospheric pad with soft vocals'
  ];
  document.getElementById('prompt').value = prompts[Math.floor(Math.random()*prompts.length)];
}}

// Download track
function downloadTrack() {{
  if(!currentAudio) return;
  const a = document.createElement('a');
  a.href = currentAudio.url;
  a.download = `prompt2jam_${{Date.now()}}.${{currentAudio.format}}`;
  a.click();
}}

// Add to arrange
function addToArrange() {{
  if(!currentAudio) return;
  
  // Add new track to track list
  arrangeTrackCounter++;
  const trackItem = document.createElement('div');
  trackItem.className = 'track-item';
  trackItem.innerHTML = `
    <div class="track-name">Track ${{arrangeTrackCounter}}</div>
    <div class="track-type">Audio</div>
  `;
  trackItem.onclick = () => showArrangeView('piano');
  document.getElementById('trackList').appendChild(trackItem);
  
  // Add clip to timeline
  const timelineTrack = document.createElement('div');
  timelineTrack.className = 'timeline-track';
  timelineTrack.innerHTML = `
    <div class="timeline-clip" style="left:${{Math.random()*50}}%;width:${{20+Math.random()*30}}%">
      <div class="clip-name">${{currentAudio.prompt.substring(0,20)}}...</div>
      <div class="clip-waveform"></div>
    </div>
  `;
  timelineTrack.onclick = () => showArrangeView('piano');
  document.getElementById('timelineTracks').appendChild(timelineTrack);
  
  // Add mixer channel
  const mixerChannel = document.createElement('div');
  mixerChannel.className = 'mixer-channel';
  mixerChannel.innerHTML = `
    <div class="channel-label">Track ${{arrangeTrackCounter}}</div>
    <div class="channel-fader">
      <div class="fader-thumb" style="bottom:70%"></div>
    </div>
    <div class="channel-meter">
      <div class="meter-bar" style="height:0%"></div>
    </div>
    <div class="channel-value">-6 dB</div>
  `;
  document.querySelector('.mixer-channels').insertBefore(mixerChannel,document.querySelector('.mixer-channel.master'));
  
  // Switch to arrange page
  switchPage('arrange');
  alert('✅ Track added to arrangement!');
}}

// Save to library
function saveToLibrary() {{
  if(!currentAudio) return;
  library.push({{
    id: Date.now(),
    ...currentAudio
  }});
  localStorage.setItem('p2j_library', JSON.stringify(library));
  alert('✅ Saved to library!');
}}

// Render library
function renderLibrary() {{
  const grid = document.getElementById('libraryGrid');
  if(library.length === 0) {{
    grid.innerHTML = '<div style="grid-column:1/-1;text-align:center;padding:40px;color:var(--text-muted)">No tracks saved yet. Generate music and save it to your library!</div>';
    return;
  }}
  
  grid.innerHTML = library.map(item => `
    <div class="library-item">
      <div class="library-title">${{item.prompt.substring(0,40)}}...</div>
      <div class="library-meta">
        ${{item.genre||'Auto'}} • ${{item.mood||'Auto'}} • ${{item.duration}}s • ${{new Date(item.created).toLocaleDateString()}}
      </div>
      <audio controls src="${{item.url}}" style="width:100%;margin:8px 0"></audio>
      <div class="library-actions">
        <button onclick="addLibraryToArrange(${{item.id}})">➕ Add</button>
        <button onclick="deleteLibraryItem(${{item.id}})">🗑️ Delete</button>
      </div>
    </div>
  `).join('');
}}

// Add library item to arrange
function addLibraryToArrange(id) {{
  const item = library.find(i => i.id === id);
  if(!item) return;
  currentAudio = item;
  addToArrange();
}}

// Delete library item
function deleteLibraryItem(id) {{
  if(!confirm('Delete this track?')) return;
  library = library.filter(i => i.id !== id);
  localStorage.setItem('p2j_library', JSON.stringify(library));
  renderLibrary();
}}

// Add track
function addTrack() {{
  arrangeTrackCounter++;
  const trackItem = document.createElement('div');
  trackItem.className = 'track-item';
  trackItem.innerHTML = `
    <div class="track-name">Track ${{arrangeTrackCounter}}</div>
    <div class="track-type">Audio</div>
  `;
  document.getElementById('trackList').appendChild(trackItem);
  
  const timelineTrack = document.createElement('div');
  timelineTrack.className = 'timeline-track';
  document.getElementById('timelineTracks').appendChild(timelineTrack);
  timelineTrack.onclick = () => showArrangeView('piano');
  
  alert(`✅ Track ${{arrangeTrackCounter}} added!`);
}}

// Bind clicks to existing tracks and timeline
function bindTrackClicks() {{
  document.querySelectorAll('#trackList .track-item').forEach(item => {{
    item.onclick = () => showArrangeView('piano');
  }});
  document.querySelectorAll('#timelineTracks .timeline-track').forEach(track => {{
    track.onclick = () => showArrangeView('piano');
  }});
}}

// Transport controls
function playArrange() {{
  alert('Play transport - Web Audio API integration coming in v0.1.0');
}}
function pauseArrange() {{
  alert('Pause transport');
}}
function stopArrange() {{
  alert('Stop transport');
}}

// Initialize piano roll
function initPianoRoll() {{
  const keysDiv = document.getElementById('pianoKeys');
  if(keysDiv.children.length > 0) return; // Already initialized
  
  const notes = ['C','C#','D','D#','E','F','F#','G','G#','A','A#','B'];
  for(let octave = 7; octave >= 2; octave--) {{
    for(let i = notes.length-1; i >= 0; i--) {{
      const key = document.createElement('div');
      key.className = `piano-key${{notes[i].includes('#') ? ' black' : ''}}`;
      key.textContent = `${{notes[i]}}${{octave}}`;
      keysDiv.appendChild(key);
    }}
  }}
}}

// Initialize interactions
bindTrackClicks();
</script>
</body>
</html>
'''

    @web_app.get("/", response_class=HTMLResponse)
    async def root():
        return HTML_MULTIPAGE_DAW

    return web_app
