# Prompt2Jam Studio v0.0.11 - PROPER LAYOUT FIX
# Landing: Generate/Create page (v0.0.9 style)
# Arrange: Full DAW with Timeline + Mixer at BOTTOM (full width, toggleable)
# Bottom Nav: Create | Arrange | Library

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

app = modal.App("prompt-2-jam-v11-fixed-layout")

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

@app.function(image=web_image, min_containers=1)
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

    HTML_DAW = f'''<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1,maximum-scale=1,user-scalable=no">
<title>Prompt2Jam Studio v0.0.11</title>
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
  background:var(--bg);color:var(--text);height:100vh;
  display:flex;flex-direction:column;overflow:hidden
}}

/* Main container */
main{{flex:1;overflow:hidden;position:relative}}

/* Pages */
.page{{
  display:none;width:100%;height:100%;
  position:absolute;top:0;left:0
}}
.page.active{{display:flex;flex-direction:column}}

/* ===== CREATE PAGE (v0.0.9 style - LANDING) ===== */
#page-create{{padding:16px;overflow-y:auto}}
.create-container{{max-width:800px;margin:0 auto;display:flex;flex-direction:column;gap:16px}}
.card{{
  background:var(--bg-secondary);border:1px solid var(--border);
  border-radius:8px;padding:16px;box-shadow:0 2px 8px rgba(0,0,0,.2)
}}
.card-title{{font-size:16px;font-weight:600;margin-bottom:16px;color:var(--text)}}
.form-row{{display:flex;gap:12px;margin-bottom:12px;flex-wrap:wrap}}
.form-row.cols-2{{display:grid;grid-template-columns:1fr 1fr;gap:12px}}
.form-row>div{{flex:1;min-width:150px}}
label{{
  display:block;font-size:12px;font-weight:600;
  margin-bottom:6px;color:var(--text-secondary);
  text-transform:uppercase;letter-spacing:.3px
}}
input,select,textarea{{
  width:100%;padding:10px 12px;background:var(--bg-primary);
  border:1px solid var(--border);border-radius:6px;
  color:var(--text);font-family:inherit;font-size:14px
}}
input:focus,select:focus,textarea:focus{{
  outline:none;border-color:var(--accent);
  box-shadow:0 0 0 3px rgba(99,102,241,.1)
}}
textarea{{resize:vertical;min-height:80px}}
.btn{{
  padding:10px 16px;border:none;border-radius:6px;
  font-weight:600;font-size:13px;cursor:pointer;
  transition:all .2s;white-space:nowrap
}}
.btn-primary{{background:var(--accent);color:#fff}}
.btn-primary:hover:not(:disabled){{background:var(--accent-hover);transform:translateY(-1px)}}
.btn-primary:disabled{{opacity:.6;cursor:not-allowed}}
.btn-secondary{{background:var(--bg-tertiary);color:var(--text);border:1px solid var(--border)}}
.btn-secondary:hover{{background:var(--border)}}
.btn-success{{background:var(--success);color:#fff}}
.btn-success:hover{{background:#059669}}
.btn-group{{display:flex;gap:8px;flex-wrap:wrap}}
audio{{width:100%;margin:12px 0}}
.status{{padding:12px;border-radius:8px;margin:10px 0;font-size:14px}}
.status.info{{background:#1e3a8a;color:#93c5fd}}
.status.success{{background:#065f46;color:#6ee7b7}}
.status.error{{background:#7f1d1d;color:#fca5a5}}

/* ===== ARRANGE PAGE ===== */
#page-arrange{{display:flex;flex-direction:column}}

/* Arrange content area - 3 columns */
.arrange-main{{
  flex:1;display:flex;overflow:hidden;
  position:relative
}}

/* Left: Track list */
.track-panel{{
  width:200px;background:var(--bg-secondary);
  border-right:1px solid var(--border);
  display:flex;flex-direction:column;flex-shrink:0;
  overflow-y:auto
}}
.track-panel-header{{
  padding:12px 16px;border-bottom:1px solid var(--border);
  font-weight:600;font-size:13px;position:sticky;top:0;
  background:var(--bg-secondary);z-index:10
}}
.track-list{{flex:1;padding:8px}}
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

/* Center: Timeline + Transport */
.timeline-panel{{
  flex:1;display:flex;flex-direction:column;
  overflow:hidden;position:relative
}}
.timeline-toolbar{{
  padding:10px 16px;background:var(--bg-secondary);
  border-bottom:1px solid var(--border);
  display:flex;gap:10px;align-items:center;flex-wrap:wrap
}}
.tool-btn{{
  background:var(--bg-tertiary);border:1px solid var(--border);
  color:var(--text-secondary);padding:8px 14px;border-radius:8px;
  cursor:pointer;transition:all .2s;font-size:13px
}}
.tool-btn:hover{{background:var(--accent);color:#fff;border-color:var(--accent)}}
.tool-btn.active{{background:var(--accent);color:#fff;border-color:var(--accent)}}

/* Timeline view */
.timeline-view{{flex:1;overflow:auto;background:var(--bg)}}
.timeline-ruler{{
  height:30px;background:var(--bg-secondary);
  border-bottom:1px solid var(--border);display:flex
}}
.timeline-marker{{
  flex:1;padding:6px 8px;font-size:11px;
  color:var(--text-muted);border-right:1px solid var(--border)
}}
.timeline-tracks{{padding:8px 0}}
.timeline-track{{
  height:60px;background:rgba(255,255,255,.02);
  border-bottom:1px solid var(--border);
  position:relative;padding:8px;cursor:pointer
}}
.timeline-track:hover{{background:rgba(255,255,255,.05)}}
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

/* Piano Roll view */
.piano-roll-view{{
  display:none;flex:1;overflow:auto;background:var(--bg)
}}
.piano-roll-view.active{{display:block}}
.piano-roll-grid{{display:flex;height:100%;min-height:400px}}
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
  cursor:pointer;transition:background .2s;max-width:120px
}}
.piano-note:hover{{background:var(--accent-hover)}}

/* Transport bar */
.transport-bar{{
  height:60px;background:var(--bg-secondary);
  border-top:1px solid var(--border);
  display:flex;align-items:center;justify-content:center;
  gap:12px;flex-shrink:0
}}
.transport-btn{{
  width:44px;height:44px;background:var(--accent);
  color:#fff;border:none;border-radius:50%;
  font-size:18px;cursor:pointer;transition:all .2s;
  display:flex;align-items:center;justify-content:center
}}
.transport-btn:hover{{background:var(--accent-hover);transform:scale(1.1)}}
.time-display{{
  font-family:monospace;font-size:20px;
  min-width:120px;text-align:center;color:var(--accent)
}}

/* Right: Inspector */
.inspector-panel{{
  width:280px;background:var(--bg-secondary);
  border-left:1px solid var(--border);
  display:flex;flex-direction:column;flex-shrink:0;
  overflow-y:auto
}}
.inspector-header{{
  padding:12px 16px;border-bottom:1px solid var(--border);
  font-weight:600;font-size:13px;position:sticky;top:0;
  background:var(--bg-secondary);z-index:10
}}
.inspector-content{{flex:1;padding:16px}}
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

/* MIXER - FULL WIDTH AT BOTTOM */
.mixer-panel{{
  position:absolute;bottom:0;left:0;right:0;
  background:var(--bg-secondary);
  border-top:2px solid var(--border);
  display:none;z-index:50;
  max-height:300px;overflow-y:auto
}}
.mixer-panel.active{{display:block}}
.mixer-header{{
  padding:10px 16px;background:var(--bg-tertiary);
  border-bottom:1px solid var(--border);
  display:flex;justify-content:space-between;align-items:center;
  position:sticky;top:0;z-index:10
}}
.mixer-title{{font-weight:600;font-size:14px}}
.mixer-close{{
  background:none;border:none;color:var(--text-muted);
  cursor:pointer;font-size:18px;padding:4px 8px
}}
.mixer-close:hover{{color:var(--text)}}
.mixer-channels{{
  display:flex;gap:12px;padding:16px;
  overflow-x:auto;align-items:flex-end
}}
.mixer-channel{{
  background:var(--bg);border:1px solid var(--border);
  border-radius:8px;padding:12px;min-width:80px;
  display:flex;flex-direction:column;align-items:center;gap:8px
}}
.channel-label{{font-size:11px;font-weight:600;text-align:center}}
.channel-fader{{
  width:36px;height:150px;background:var(--bg-tertiary);
  border-radius:18px;position:relative;border:1px solid var(--border)
}}
.fader-thumb{{
  width:100%;height:18px;background:var(--accent);
  border-radius:9px;position:absolute;cursor:ns-resize
}}
.fader-thumb:hover{{background:var(--accent-hover)}}
.channel-meter{{
  width:36px;height:50px;background:var(--bg-tertiary);
  border-radius:6px;border:1px solid var(--border);
  position:relative;overflow:hidden
}}
.meter-bar{{
  width:100%;background:linear-gradient(to top,var(--success),#fbbf24,var(--danger));
  position:absolute;bottom:0;height:0%;transition:height .1s
}}
.channel-value{{font-size:10px;color:var(--text-muted)}}
.mixer-channel.master{{background:rgba(99,102,241,.1);border-color:var(--accent)}}

/* Bottom nav */
nav.bottom-nav{{
  display:flex;height:56px;background:var(--bg-secondary);
  border-top:1px solid var(--border);flex-shrink:0
}}
.nav-tab{{
  flex:1;display:flex;flex-direction:column;
  align-items:center;justify-content:center;gap:4px;
  border:none;background:transparent;color:var(--text-muted);
  cursor:pointer;font-size:10px;font-weight:600;transition:all .2s
}}
.nav-tab:hover{{color:var(--text-secondary);background:rgba(255,255,255,.05)}}
.nav-tab.active{{color:var(--accent);background:rgba(99,102,241,.1)}}
.nav-icon{{font-size:20px}}

/* Library popover */
.library-popover{{
  display:none;position:fixed;bottom:56px;left:0;right:0;
  height:60vh;background:var(--bg-secondary);
  border-top:2px solid var(--border);z-index:100;
  overflow-y:auto
}}
.library-popover.active{{display:block}}
.library-header{{
  padding:16px;border-bottom:1px solid var(--border);
  display:flex;justify-content:space-between;align-items:center;
  position:sticky;top:0;background:var(--bg-secondary);z-index:10
}}
.library-title{{font-weight:600;font-size:16px}}
.library-close{{
  background:none;border:none;color:var(--text-muted);
  cursor:pointer;font-size:20px;padding:4px 8px
}}
.library-close:hover{{color:var(--text)}}
.library-grid{{
  display:grid;grid-template-columns:repeat(auto-fill,minmax(250px,1fr));
  gap:12px;padding:16px
}}
.library-item{{
  background:var(--bg);border:1px solid var(--border);
  border-radius:8px;padding:12px;transition:all .2s
}}
.library-item:hover{{border-color:var(--accent);transform:translateY(-2px)}}
.library-item-title{{font-weight:600;margin-bottom:6px;font-size:13px}}
.library-item-meta{{font-size:11px;color:var(--text-muted);margin-bottom:10px}}
.library-item-actions{{display:flex;gap:6px}}
.library-item-actions button{{
  flex:1;padding:6px;border-radius:6px;
  border:1px solid var(--border);background:var(--bg-tertiary);
  color:var(--text);cursor:pointer;font-size:11px
}}
.library-item-actions button:hover{{background:var(--accent);color:#fff;border-color:var(--accent)}}

/* Responsive */
@media(max-width:768px){{
  .track-panel{{width:150px}}
  .inspector-panel{{width:220px}}
  .form-row.cols-2{{grid-template-columns:1fr}}
}}
@media(max-width:480px){{
  .track-panel,.inspector-panel{{
    position:absolute;top:0;bottom:0;
    transform:translateX(-100%);transition:transform .3s;
    z-index:20;width:80%
  }}
  .track-panel.active,.inspector-panel.active{{transform:translateX(0)}}
}}
</style>
</head>
<body>
<main>
  <!-- CREATE PAGE (LANDING) -->
  <div id="page-create" class="page active">
    <div class="create-container">
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
            <button type="submit" class="btn btn-primary" id="generateBtn" style="flex:1">🎵 Generate Music</button>
            <button type="button" class="btn btn-secondary" onclick="randomVariation()">🎲 Variation</button>
          </div>
          
          <div id="status"></div>
        </form>
      </div>
      
      <div class="card">
        <h3 class="card-title">🎧 Playback</h3>
        <audio id="audioPlayer" controls></audio>
        <div class="btn-group" style="margin-top:12px">
          <button class="btn btn-success" onclick="downloadTrack()" style="flex:1">⬇️ Download</button>
          <button class="btn btn-primary" onclick="addToArrangeAndSwitch()" style="flex:1">➕ Add to Arrange</button>
          <button class="btn btn-secondary" onclick="saveToLibrary()">💾 Save</button>
        </div>
      </div>
    </div>
  </div>

  <!-- ARRANGE PAGE -->
  <div id="page-arrange" class="page">
    <div class="arrange-main">
      <!-- Left: Tracks -->
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
      
      <!-- Center: Timeline/Piano Roll + Transport -->
      <div class="timeline-panel">
        <div class="timeline-toolbar">
          <button class="tool-btn active" onclick="showTimelineView()">📊 Timeline</button>
          <button class="tool-btn" onclick="showPianoRoll()">🎹 Piano Roll</button>
          <button class="tool-btn" onclick="toggleMixer()">🎚️ Mixer</button>
        </div>
        
        <!-- Timeline -->
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
            <div class="timeline-track" onclick="openTrackInPianoRoll(1)">
              <div class="timeline-clip">
                <div class="clip-name">Vocals.wav</div>
                <div class="clip-waveform"></div>
              </div>
            </div>
            <div class="timeline-track" onclick="openTrackInPianoRoll(2)">
              <div class="timeline-clip" style="left:20%;width:35%">
                <div class="clip-name">Piano.wav</div>
                <div class="clip-waveform"></div>
              </div>
            </div>
          </div>
        </div>
        
        <!-- Piano Roll -->
        <div class="piano-roll-view" id="pianoRollView">
          <div class="piano-roll-grid">
            <div class="piano-keys" id="pianoKeys"></div>
            <div class="piano-grid" id="pianoGrid">
              <div class="piano-note" style="left:120px;width:90px;top:100px"></div>
              <div class="piano-note" style="left:240px;width:70px;top:140px"></div>
            </div>
          </div>
        </div>
        
        <!-- Transport -->
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
          </div>
        </div>
      </div>
      
      <!-- Mixer - FULL WIDTH BOTTOM -->
      <div class="mixer-panel" id="mixerPanel">
        <div class="mixer-header">
          <div class="mixer-title">🎚️ Mixer</div>
          <button class="mixer-close" onclick="toggleMixer()">✕</button>
        </div>
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
    </div>
  </div>

  <!-- Library Popover -->
  <div class="library-popover" id="libraryPopover">
    <div class="library-header">
      <div class="library-title">📚 Your Library</div>
      <button class="library-close" onclick="closeLibrary()">✕</button>
    </div>
    <div class="library-grid" id="libraryGrid"></div>
  </div>
</main>

<!-- Bottom Nav -->
<nav class="bottom-nav">
  <button class="nav-tab active" onclick="switchToPage('create')">
    <div class="nav-icon">✨</div>
    <div>Create</div>
  </button>
  <button class="nav-tab" onclick="switchToPage('arrange')">
    <div class="nav-icon">🎹</div>
    <div>Arrange</div>
  </button>
  <button class="nav-tab" onclick="openLibrary()">
    <div class="nav-icon">📚</div>
    <div>Library</div>
  </button>
</nav>

<script>
let currentPage = 'create';
let currentAudio = null;
let library = JSON.parse(localStorage.getItem('p2j_library') || '[]');
let arrangeTrackCounter = 2;

// Switch pages
function switchToPage(page) {{
  currentPage = page;
  document.querySelectorAll('.page').forEach(p => p.classList.remove('active'));
  document.getElementById(`page-${{page}}`).classList.add('active');
  document.querySelectorAll('.nav-tab').forEach((tab,idx) => {{
    tab.classList.toggle('active',['create','arrange','library'][idx]===page);
  }});
}}

// Generate music
async function generateMusic(e) {{
  e.preventDefault();
  const form = e.target;
  const btn = document.getElementById('generateBtn');
  const statusDiv = document.getElementById('status');
  
  btn.disabled = true;
  btn.textContent = '🎵 Generating...';
  statusDiv.innerHTML = '<div class="status info">⏳ Generating music (30-60 seconds)...</div>';
  
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
    statusDiv.innerHTML = '<div class="status success">✅ Music generated successfully!</div>';
  }} catch(err) {{
    statusDiv.innerHTML = `<div class="status error">❌ Error: ${{err.message}}</div>`;
  }} finally {{
    btn.disabled = false;
    btn.textContent = '🎵 Generate Music';
  }}
}}

function randomVariation() {{
  const prompts = [
    'Upbeat electronic dance with synth melodies',
    'Chill lofi hip hop with piano and rain sounds',
    'Epic orchestral cinematic with strings'
  ];
  document.getElementById('prompt').value = prompts[Math.floor(Math.random()*prompts.length)];
}}

function downloadTrack() {{
  if(!currentAudio) return;
  const a = document.createElement('a');
  a.href = currentAudio.url;
  a.download = `prompt2jam_${{Date.now()}}.${{currentAudio.format}}`;
  a.click();
}}

function addToArrangeAndSwitch() {{
  if(!currentAudio) return;
  
  // Add to timeline
  arrangeTrackCounter++;
  const trackItem = document.createElement('div');
  trackItem.className = 'track-item';
  trackItem.innerHTML = `<div class="track-name">Track ${{arrangeTrackCounter}}</div><div class="track-type">Audio</div>`;
  trackItem.onclick = () => showPianoRoll();
  document.getElementById('trackList').appendChild(trackItem);
  
  const timelineTrack = document.createElement('div');
  timelineTrack.className = 'timeline-track';
  timelineTrack.innerHTML = `
    <div class="timeline-clip" style="left:${{Math.random()*50}}%;width:${{20+Math.random()*30}}%">
      <div class="clip-name">${{currentAudio.prompt.substring(0,20)}}...</div>
      <div class="clip-waveform"></div>
    </div>
  `;
  timelineTrack.onclick = () => showPianoRoll();
  document.getElementById('timelineTracks').appendChild(timelineTrack);
  
  // Add mixer channel
  const mixerChannel = document.createElement('div');
  mixerChannel.className = 'mixer-channel';
  mixerChannel.innerHTML = `
    <div class="channel-label">Track ${{arrangeTrackCounter}}</div>
    <div class="channel-fader"><div class="fader-thumb" style="bottom:70%"></div></div>
    <div class="channel-meter"><div class="meter-bar" style="height:0%"></div></div>
    <div class="channel-value">-6 dB</div>
  `;
  document.querySelector('.mixer-channels').insertBefore(mixerChannel,document.querySelector('.mixer-channel.master'));
  
  // Switch to arrange
  switchToPage('arrange');
}}

function saveToLibrary() {{
  if(!currentAudio) return;
  library.push({{id:Date.now(),...currentAudio}});
  localStorage.setItem('p2j_library', JSON.stringify(library));
  alert('✅ Saved to library!');
}}

// Arrange views
function showTimelineView() {{
  document.getElementById('timelineView').classList.add('active');
  document.getElementById('pianoRollView').classList.remove('active');
}}

function showPianoRoll() {{
  document.getElementById('timelineView').classList.remove('active');
  document.getElementById('pianoRollView').classList.add('active');
  initPianoRoll();
}}

function openTrackInPianoRoll(trackId) {{
  showPianoRoll();
}}

function toggleMixer() {{
  document.getElementById('mixerPanel').classList.toggle('active');
}}

function addTrack() {{
  arrangeTrackCounter++;
  const trackItem = document.createElement('div');
  trackItem.className = 'track-item';
  trackItem.innerHTML = `<div class="track-name">Track ${{arrangeTrackCounter}}</div><div class="track-type">Audio</div>`;
  trackItem.onclick = () => showPianoRoll();
  document.getElementById('trackList').appendChild(trackItem);
  
  const timelineTrack = document.createElement('div');
  timelineTrack.className = 'timeline-track';
  timelineTrack.onclick = () => showPianoRoll();
  document.getElementById('timelineTracks').appendChild(timelineTrack);
  
  alert(`✅ Track ${{arrangeTrackCounter}} added!`);
}}

// Transport
function playArrange() {{alert('Play - Web Audio API coming v0.1.0')}}
function pauseArrange() {{alert('Pause')}}
function stopArrange() {{alert('Stop')}}

// Piano roll init
function initPianoRoll() {{
  const keysDiv = document.getElementById('pianoKeys');
  if(keysDiv.children.length > 0) return;
  const notes = ['C','C#','D','D#','E','F','F#','G','G#','A','A#','B'];
  for(let octave = 6; octave >= 2; octave--) {{
    for(let i = notes.length-1; i >= 0; i--) {{
      const key = document.createElement('div');
      key.className = `piano-key${{notes[i].includes('#') ? ' black' : ''}}`;
      key.textContent = `${{notes[i]}}${{octave}}`;
      keysDiv.appendChild(key);
    }}
  }}
}}

// Library
function openLibrary() {{
  document.getElementById('libraryPopover').classList.add('active');
  renderLibrary();
}}

function closeLibrary() {{
  document.getElementById('libraryPopover').classList.remove('active');
}}

function renderLibrary() {{
  const grid = document.getElementById('libraryGrid');
  if(library.length === 0) {{
    grid.innerHTML = '<div style="grid-column:1/-1;text-align:center;padding:40px;color:var(--text-muted)">No tracks saved yet</div>';
    return;
  }}
  grid.innerHTML = library.map(item => `
    <div class="library-item">
      <div class="library-item-title">${{item.prompt.substring(0,30)}}...</div>
      <div class="library-item-meta">${{item.genre||'Auto'}} • ${{item.duration}}s</div>
      <audio controls src="${{item.url}}" style="width:100%;margin:8px 0"></audio>
      <div class="library-item-actions">
        <button onclick="deleteLibraryItem(${{item.id}})">🗑️</button>
      </div>
    </div>
  `).join('');
}}

function deleteLibraryItem(id) {{
  if(!confirm('Delete?')) return;
  library = library.filter(i => i.id !== id);
  localStorage.setItem('p2j_library', JSON.stringify(library));
  renderLibrary();
}}

// Bind existing track clicks
document.querySelectorAll('#trackList .track-item').forEach(item => {{
  item.onclick = () => showPianoRoll();
}});
document.querySelectorAll('#timelineTracks .timeline-track').forEach(track => {{
  track.onclick = () => showPianoRoll();
}});
</script>
</body>
</html>
'''

    @web_app.get("/", response_class=HTMLResponse)
    async def root():
        return HTML_DAW

    return web_app
