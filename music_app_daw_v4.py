# Prompt2Jam Studio - DAW UI v0.0.4
# Bottom-nav PWA with Explore / Create / Library views

from typing import Optional
from uuid import uuid4
import modal

image = (
    modal.Image.debian_slim(python_version="3.10")
    .apt_install("git", "ffmpeg")
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

app = modal.App("prompt-2-jam-v4-daw")

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

    fastapi_app = FastAPI(title="Prompt2Jam Studio v0.0.4 (DAW)")
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
        return HTML_DAW_UI

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
            return StreamingResponse(
                iter([audio_bytes]),
                media_type=media_types.get(fmt, "audio/wav"),
                headers={"Content-Disposition": f"attachment; filename=music_{uuid4().hex[:8]}.{fmt}"}
            )
        except Exception as e:
            return JSONResponse({"error": str(e)}, status_code=500)

    return fastapi_app

HTML_DAW_UI = """<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <title>Prompt2Jam Studio – DAW</title>
  <style>
    *{box-sizing:border-box}
    body{margin:0;font-family:Inter,ui-sans-serif,system-ui,Segoe UI,Roboto;background:#0f172a;color:#e5e7eb}
    .app{display:flex;flex-direction:column;min-height:100vh}
    header{padding:16px 20px;border-bottom:1px solid rgba(255,255,255,.08);backdrop-filter:blur(8px);position:sticky;top:0;background:rgba(15,23,42,.7)}
    .title{font-size:18px;font-weight:700;letter-spacing:.2px}
    .content{flex:1;padding:16px}
    .bottom-nav{position:sticky;bottom:0;display:grid;grid-template-columns:1fr 1fr 1fr;gap:8px;padding:10px;border-top:1px solid rgba(255,255,255,.08);background:rgba(15,23,42,.9);backdrop-filter:blur(8px)}
    .tab{display:flex;flex-direction:column;align-items:center;gap:6px;padding:10px 12px;border-radius:12px;color:#cbd5e1;border:1px solid transparent}
    .tab.active{background:#1f2937;color:#fff;border-color:rgba(255,255,255,.08)}
    .btn{padding:12px 14px;border-radius:12px;background:#4f46e5;color:#fff;border:none;font-weight:600;cursor:pointer}
    .card{background:#111827;border:1px solid rgba(255,255,255,.06);border-radius:16px;padding:16px}
    input,textarea,select{width:100%;background:#0b1220;color:#e5e7eb;border:1.5px solid #334155;border-radius:12px;padding:12px 14px}
    label{font-size:12px;color:#94a3b8;margin-bottom:6px;display:block}
    .row{display:grid;gap:12px}
    @media(min-width:720px){.row{grid-template-columns:1fr 1fr}}
  </style>
</head>
<body>
  <div class="app">
    <header><div class="title">🎵 Prompt2Jam Studio</div></header>
    <main class="content">
      <section id="view-explore" class="view" style="display:none;">
        <div class="card">
          <h3>🔎 Explore</h3>
          <p style="color:#94a3b8">Featured prompts and community creations (coming soon).</p>
        </div>
      </section>
      <section id="view-create" class="view">
        <div class="card">
          <h3 style="margin:0 0 10px 0;">🎨 Create</h3>
          <div class="row">
            <div>
              <label>Prompt</label>
              <textarea id="prompt" placeholder="Upbeat electronic dance music with synth leads."></textarea>
            </div>
            <div>
              <label>Lyrics</label>
              <textarea id="lyrics" placeholder="[inst]"></textarea>
            </div>
          </div>
          <div class="row" style="margin-top:12px;">
            <div>
              <label>Duration (s)</label>
              <input id="duration" type="number" min="5" max="240" value="30" />
            </div>
            <div>
              <label>Format</label>
              <select id="format"><option>wav</option><option>mp3</option><option>flac</option></select>
            </div>
          </div>
          <div class="row" style="margin-top:12px;">
            <div>
              <label>Steps</label>
              <input id="steps" type="number" min="27" max="100" value="60" />
            </div>
            <div>
              <label>Guidance</label>
              <input id="guidance" type="number" min="7" max="25" step="0.5" value="15" />
            </div>
          </div>
          <button id="generateBtn" class="btn" style="margin-top:14px;">Generate</button>
          <div id="status" style="margin-top:10px;color:#cbd5e1;"></div>
        </div>
        <div class="card" style="margin-top:14px;">
          <div id="waveform" style="height:96px;margin-bottom:12px;"></div>
          <audio id="audio" controls style="width:100%"></audio>
          <div style="display:flex;gap:8px;margin-top:12px;">
            <a id="downloadLink" class="btn" style="background:#334155">Download</a>
            <button id="variationBtn" class="btn" style="background:#4338ca">Variation</button>
            <button id="extendBtn" class="btn" style="background:#2563eb">Extend +10s</button>
          </div>
        </div>
      </section>
      <section id="view-library" class="view" style="display:none;">
        <div class="card">
          <h3>📚 Library</h3>
          <div id="historyList" style="margin-top:8px;"></div>
        </div>
      </section>
    </main>
    <nav class="bottom-nav">
      <button class="tab active" data-view="create">🎚️ Create</button>
      <button class="tab" data-view="explore">🔎 Explore</button>
      <button class="tab" data-view="library">📚 Library</button>
    </nav>
  </div>
  <script src="https://unpkg.com/wavesurfer.js"></script>
  <script>
    const tabs = document.querySelectorAll('.tab');
    const views = {
      explore: document.getElementById('view-explore'),
      create: document.getElementById('view-create'),
      library: document.getElementById('view-library'),
    };
    function setView(name){
      Object.values(views).forEach(v=>v.style.display='none');
      views[name].style.display='block';
      tabs.forEach(t=>t.classList.toggle('active', t.dataset.view===name));
      localStorage.setItem('p2j_view', name);
    }
    tabs.forEach(t=>t.addEventListener('click', ()=>setView(t.dataset.view)));
    setView(localStorage.getItem('p2j_view')||'create');

    let wavesurfer=null; const history=[];
    function showStatus(msg){ document.getElementById('status').textContent=msg; }
    async function generate(action='new', extendBy=0){
      const prompt = document.getElementById('prompt').value.trim();
      if(!prompt){ showStatus('Enter a prompt.'); return; }
      showStatus('Generating...');
      const fmt = document.getElementById('format').value;
      const req = {
        prompt,
        lyrics: document.getElementById('lyrics').value.trim()||'[inst]',
        duration: parseInt(document.getElementById('duration').value)||30,
        format: fmt,
        inference_steps: parseInt(document.getElementById('steps').value)||60,
        guidance_scale: parseFloat(document.getElementById('guidance').value)||15,
        action,
        extend_by: extendBy
      };
      const res = await fetch('/api/generate', {method:'POST', headers:{'Content-Type':'application/json'}, body: JSON.stringify(req)});
      if(!res.ok){ showStatus('Failed to generate.'); return; }
      const blob = await res.blob(); const url = URL.createObjectURL(blob);
      const audio = document.getElementById('audio'); audio.src=url; audio.play();
      if(window.WaveSurfer){ if(wavesurfer) wavesurfer.destroy(); wavesurfer = WaveSurfer.create({container:'#waveform',waveColor:'#64748b',progressColor:'#4f46e5',height:96}); wavesurfer.load(url); }
      const dl = document.getElementById('downloadLink'); dl.href=url; dl.download=`music_${Date.now()}.${fmt}`;
      history.unshift({time:new Date().toLocaleString(), url, fmt}); renderHistory(); showStatus('Ready!');
    }
    function renderHistory(){
      const list=document.getElementById('historyList'); list.innerHTML='';
      history.slice(0,10).forEach((h,i)=>{ const item=document.createElement('div'); item.style.display='flex'; item.style.justifyContent='space-between'; item.style.padding='8px 0';
        const left=document.createElement('div'); left.textContent=`${h.time} • ${h.fmt}`;
        const right=document.createElement('div'); const play=document.createElement('button'); play.textContent='Play'; play.className='btn'; play.style.background='#334155'; play.onclick=()=>{document.getElementById('audio').src=h.url; document.getElementById('audio').play(); if(wavesurfer) wavesurfer.load(h.url);};
        const dl=document.createElement('a'); dl.textContent='Download'; dl.className='btn'; dl.style.background='#475569'; dl.href=h.url; dl.download=`music_${i}.${h.fmt}`; right.style.display='flex'; right.style.gap='8px'; right.append(play, dl);
        item.append(left, right); list.append(item);
      });
    }
    document.getElementById('generateBtn').addEventListener('click',()=>generate('new',0));
    document.getElementById('variationBtn').addEventListener('click',()=>generate('variation',0));
    document.getElementById('extendBtn').addEventListener('click',()=>generate('extend',10));
  </script>
</body>
</html>
"""
