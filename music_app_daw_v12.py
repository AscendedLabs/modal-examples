# ---
# cmd: ["modal", "serve", "music_app_daw_v12.py"]
# ---

import io
import math
import struct
from typing import Optional

import modal
from fastapi import FastAPI, Header, Request
from fastapi.responses import HTMLResponse, Response
from pydantic import BaseModel

image = modal.Image.debian_slim().uv_pip_install("fastapi[standard]", "pydantic")
app = modal.App("music-app-v12", image=image)
web_app = FastAPI()


class GenerateRequest(BaseModel):
    prompt: Optional[str] = ""
    lyrics: Optional[str] = ""
    genre: Optional[str] = ""
    mood: Optional[str] = ""
    duration_sec: Optional[int] = 4


@web_app.get("/", response_class=HTMLResponse)
async def handle_root(user_agent: Optional[str] = Header(None)):
    html = '''
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <title>ACE Studio – Music App v0.0.12</title>
  <style>
    :root {
      --bg: #0e0f13;
      --panel: #14161d;
      --panel-2: #1a1d26;
      --text: #e7eaf3;
      --muted: #a8afc0;
      --accent: #7aa2ff;
      --accent-2: #6ee7b7;
      --danger: #ff6b6b;
      --yellow: #ffd166;
      --blue: #5b8bff;
      --border: #262a36;
    }
    * { box-sizing: border-box; }
    html, body { height: 100%; }
    body { margin: 0; background: var(--bg); color: var(--text); font-family: ui-sans-serif, system-ui, -apple-system, Segoe UI, Roboto, Arial, "Noto Sans", "Helvetica Neue", sans-serif; }
    button { cursor: pointer; }
    .hidden { display: none !important; }

    /* Top bar with hamburger + page title + actions */
    .topbar { position: fixed; top: 0; left: 0; right: 0; height: 54px; display: flex; align-items: center; gap: 8px; padding: 0 12px; background: var(--panel-2); border-bottom: 1px solid var(--border); z-index: 50; }
    .hamburger { width: 36px; height: 36px; display: grid; place-items: center; background: var(--panel); border: 1px solid var(--border); border-radius: 8px; }
    .page-title { font-weight: 600; margin-left: 6px; }
    .top-actions { margin-left: auto; display: flex; gap: 8px; }
    .top-actions .action { height: 36px; padding: 0 12px; border-radius: 8px; background: var(--panel); border: 1px solid var(--border); color: var(--text); }

    /* Left app drawer (not track list) */
    .app-drawer { position: fixed; top: 54px; left: 0; bottom: 54px; width: 280px; background: var(--panel-2); border-right: 1px solid var(--border); transform: translateX(-100%); transition: transform 0.18s ease; z-index: 60; display: flex; flex-direction: column; }
    .app-drawer.active { transform: translateX(0); }
    .drawer-header { padding: 12px; border-bottom: 1px solid var(--border); font-weight: 600; }
    .drawer-item { padding: 10px 12px; border-bottom: 1px solid var(--border); color: var(--text); }

    /* Right inspector drawer */
    .inspector { position: fixed; top: 54px; right: 0; bottom: 54px; width: 320px; background: var(--panel-2); border-left: 1px solid var(--border); transform: translateX(100%); transition: transform 0.18s ease; z-index: 60; display: flex; flex-direction: column; }
    .inspector.active { transform: translateX(0); }
    .inspector-header { padding: 12px; border-bottom: 1px solid var(--border); font-weight: 600; }
    .inspector-body { padding: 12px; overflow-y: auto; }

    /* Main content area */
    .content { position: fixed; top: 54px; left: 0; right: 0; bottom: 54px; display: grid; grid-template-columns: 1fr; }

    /* Pages */
    .page { overflow: hidden; }

    /* Create (Generate) page */
    .create-page { padding: 12px; display: grid; gap: 12px; grid-template-columns: 1fr; }
    .card { background: var(--panel); border: 1px solid var(--border); border-radius: 12px; padding: 12px; }
    .field { display: grid; gap: 6px; }
    .row { display: flex; gap: 6px; }
    .btn { height: 38px; padding: 0 14px; border-radius: 8px; border: 1px solid var(--border); background: var(--accent); color: #0b1020; font-weight: 600; }
    .btn.secondary { background: var(--panel-2); color: var(--text); }

    /* Arrange page */
    .arrange-page { display: grid; grid-template-rows: auto 1fr auto; }
    .transport { height: 42px; display: flex; align-items: center; gap: 8px; padding: 6px 12px; border-bottom: 1px solid var(--border); background: var(--panel-2); }
    .transport .ctl { height: 30px; padding: 0 10px; border-radius: 8px; background: var(--panel); border: 1px solid var(--border); color: var(--text); }

    /* Timeline with inline track headers */
    .timeline { position: relative; overflow: auto; background: var(--panel); border-top: 1px solid var(--border); border-bottom: 1px solid var(--border); }
    .timeline-inner { min-width: 800px; padding: 8px; display: grid; gap: 10px; }
    .timeline-row { display: grid; grid-template-columns: 220px 1fr; align-items: stretch; min-height: 64px; }
    .track-header { background: var(--panel-2); border: 1px solid var(--border); border-radius: 10px; padding: 8px; display: grid; gap: 6px; }
    .th-top { display: flex; justify-content: space-between; align-items: center; }
    .th-name { font-weight: 600; }
    .th-ctls { display: flex; gap: 6px; }
    .th-ctls .ctl { height: 26px; padding: 0 8px; border-radius: 6px; background: var(--panel); border: 1px solid var(--border); color: var(--text); font-size: 12px; }
    .track-lane { position: relative; border: 1px dashed var(--border); border-radius: 10px; background: #12141a; }
    .timeline-clip { position: absolute; top: 8px; left: 20px; height: calc(100% - 16px); min-width: 160px; background: #1e2432; border: 1px solid var(--border); border-radius: 8px; display: grid; place-items: center; color: var(--muted); }

    /* Piano roll */
    .piano { display: grid; grid-template-rows: auto 1fr; border-top: 1px solid var(--border); }
    .piano-toolbar { height: 40px; display: flex; align-items: center; gap: 8px; padding: 6px 12px; background: var(--panel-2); border-bottom: 1px solid var(--border); }
    .piano-toolbar .tool { height: 28px; padding: 0 10px; border-radius: 6px; background: var(--panel); border: 1px solid var(--border); color: var(--text); font-size: 12px; }
    .piano-body { display: grid; grid-template-columns: 80px 1fr; }
    .piano-keys { background: var(--panel-2); border-right: 1px solid var(--border); }
    .key { height: 20px; border-bottom: 1px solid var(--border); display: grid; place-items: center; color: var(--muted); font-size: 11px; }
    .grid { position: relative; background: #0f1218; }
    .grid-row { height: 20px; border-bottom: 1px solid #151822; }
    .note { position: absolute; height: 18px; background: var(--accent); border-radius: 4px; top: 10px; left: 40px; width: 120px; }

    /* Mixer (full-width bottom, compact channels) */
    .mixer { height: 170px; background: var(--panel-2); border-top: 1px solid var(--border); display: grid; grid-template-rows: auto 1fr; }
    .mixer-top { height: 36px; display: flex; align-items: center; gap: 8px; padding: 6px 12px; border-bottom: 1px solid var(--border); }
    .mixer-top .toggle { height: 28px; padding: 0 10px; border-radius: 6px; background: var(--panel); border: 1px solid var(--border); color: var(--text); font-size: 12px; }
    .mixer-channels { overflow-x: auto; display: flex; gap: 10px; padding: 8px 12px; }
    .channel { min-width: 120px; background: var(--panel); border: 1px solid var(--border); border-radius: 10px; padding: 8px; display: grid; grid-template-rows: auto auto 1fr; gap: 6px; }
    .ch-name { font-size: 12px; font-weight: 600; }
    .ch-ctls { display: flex; gap: 6px; }
    .ch-ctls .ctl { height: 24px; padding: 0 8px; border-radius: 6px; background: var(--panel-2); border: 1px solid var(--border); color: var(--text); font-size: 12px; }
    .fader-block { display: grid; grid-template-columns: 1fr 6px; align-items: end; gap: 6px; }
    .fader { width: 100%; height: 96px; background: #0f1218; border: 1px solid var(--border); border-radius: 6px; position: relative; }
    .fader .thumb { position: absolute; left: 0; right: 0; bottom: 40%; height: 10px; background: var(--accent); border-radius: 4px; }
    .vu { width: 6px; height: 96px; background: #0f1218; border: 1px solid var(--border); border-radius: 6px; position: relative; }
    .vu .fill { position: absolute; left: 0; right: 0; bottom: 0; height: 30%; background: var(--accent-2); border-radius: 6px; }

    /* Bottom nav */
    .bottom-nav { position: fixed; left: 0; right: 0; bottom: 0; height: 54px; background: var(--panel-2); border-top: 1px solid var(--border); display: grid; grid-template-columns: repeat(4, 1fr); z-index: 50; }
    .nav-item { display: grid; place-items: center; color: var(--muted); font-weight: 600; }
    .nav-item.active { color: var(--text); }

    @media (min-width: 900px) {
      .create-page { grid-template-columns: 1fr 1fr; }
    }
  </style>
</head>
<body>
  <div class="topbar">
    <div id="hamburger" class="hamburger" title="Menu">
      <svg width="18" height="18" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg"><path d="M4 6H20M4 12H20M4 18H20" stroke="#e7eaf3" stroke-width="2" stroke-linecap="round"/></svg>
    </div>
    <div class="page-title" id="pageTitle">Create</div>
    <div class="top-actions">
      <button class="action" id="btnShare">Share</button>
      <button class="action" id="btnExport">Export</button>
      <button class="action" id="btnSettings">Settings</button>
      <button class="action" id="btnInspector">Inspector</button>
    </div>
  </div>

  <div id="appDrawer" class="app-drawer">
    <div class="drawer-header">App Menu</div>
    <div class="drawer-item">Files</div>
    <div class="drawer-item">Edit</div>
    <div class="drawer-item">Settings</div>
    <div class="drawer-item">Help</div>
  </div>

  <div id="inspector" class="inspector">
    <div class="inspector-header">Inspector</div>
    <div class="inspector-body">Select a clip or track to edit properties.</div>
  </div>

  <div class="content">
    <!-- Create Page -->
    <div id="pageCreate" class="page create-page">
      <div class="card">
        <h3>Create A Track</h3>
        <div class="field">
          <label>Prompt</label>
          <textarea id="prompt" rows="3" placeholder="Describe your music..."></textarea>
        </div>
        <div class="row">
          <div class="field" style="flex:1">
            <label>Genre</label>
            <input id="genre" placeholder="e.g., hip hop" />
          </div>
          <div class="field" style="flex:1">
            <label>Mood</label>
            <input id="mood" placeholder="e.g., moody, dark" />
          </div>
        </div>
        <div class="field">
          <label>Lyrics</label>
          <textarea id="lyrics" rows="3" placeholder="Optional lyrics..."></textarea>
        </div>
        <div class="row">
          <button id="btnGenerate" class="btn">Generate</button>
          <button id="btnAddToArrange" class="btn secondary">Add to Arrange</button>
        </div>
      </div>
      <div class="card">
        <h3>Recent Library</h3>
        <div id="libraryList">No items yet.</div>
      </div>
    </div>

    <!-- Arrange Page -->
    <div id="pageArrange" class="page arrange-page hidden">
      <div class="transport">
        <button class="ctl" id="play">Play</button>
        <button class="ctl" id="stop">Stop</button>
        <button class="ctl" id="rec">Rec</button>
        <span style="margin-left:auto;color:var(--muted)">1:1:00</span>
      </div>
      <div class="timeline">
        <div id="timelineInner" class="timeline-inner"></div>
      </div>
      <div class="piano">
        <div class="piano-toolbar">
          <button class="tool">Select</button>
          <button class="tool">Draw</button>
          <button class="tool">Erase</button>
          <button class="tool">Quantize</button>
          <button class="tool">Scale</button>
        </div>
        <div class="piano-body">
          <div class="piano-keys" id="pianoKeys"></div>
          <div class="grid" id="pianoGrid">
            <div class="note"></div>
          </div>
        </div>
      </div>
      <div class="mixer">
        <div class="mixer-top">
          <div style="font-weight:600">Mixer</div>
          <button id="toggleMixer" class="toggle">Toggle</button>
        </div>
        <div id="mixerChannels" class="mixer-channels"></div>
      </div>
    </div>

    <!-- Library Page (popover-like) -->
    <div id="pageLibrary" class="page hidden" style="padding:12px">
      <div class="card">
        <h3>Library</h3>
        <div id="libraryPageList">No items yet.</div>
      </div>
    </div>

    <!-- Explore Page -->
    <div id="pageExplore" class="page hidden" style="padding:12px">
      <div class="card">
        <h3>Explore</h3>
        <div>Discover templates, styles, and featured creations.</div>
      </div>
    </div>
  </div>

  <div class="bottom-nav">
    <div id="navCreate" class="nav-item active">Create</div>
    <div id="navArrange" class="nav-item">Timeline</div>
    <div id="navLibrary" class="nav-item">Library</div>
    <div id="navExplore" class="nav-item">Explore</div>
  </div>

  <script>
    const pageTitle = document.getElementById('pageTitle');
    const pageCreate = document.getElementById('pageCreate');
    const pageArrange = document.getElementById('pageArrange');
    const pageLibrary = document.getElementById('pageLibrary');
    const pageExplore = document.getElementById('pageExplore');

    const navCreate = document.getElementById('navCreate');
    const navArrange = document.getElementById('navArrange');
    const navLibrary = document.getElementById('navLibrary');
    const navExplore = document.getElementById('navExplore');

    const appDrawer = document.getElementById('appDrawer');
    const inspector = document.getElementById('inspector');

    const hamburger = document.getElementById('hamburger');
    const btnInspector = document.getElementById('btnInspector');

    const promptEl = document.getElementById('prompt');
    const genreEl = document.getElementById('genre');
    const moodEl = document.getElementById('mood');
    const lyricsEl = document.getElementById('lyrics');

    const btnGenerate = document.getElementById('btnGenerate');
    const btnAddToArrange = document.getElementById('btnAddToArrange');

    const libraryList = document.getElementById('libraryList');
    const libraryPageList = document.getElementById('libraryPageList');

    const timelineInner = document.getElementById('timelineInner');
    const mixerChannels = document.getElementById('mixerChannels');

    function setActiveNav(tab) {
      [navCreate, navArrange, navLibrary, navExplore].forEach(n => n.classList.remove('active'));
      tab.classList.add('active');
    }
    function setPage(name) {
      pageTitle.textContent = name;
      [pageCreate, pageArrange, pageLibrary, pageExplore].forEach(p => p.classList.add('hidden'));
      if (name === 'Create') pageCreate.classList.remove('hidden');
      if (name === 'Timeline') pageArrange.classList.remove('hidden');
      if (name === 'Library') pageLibrary.classList.remove('hidden');
      if (name === 'Explore') pageExplore.classList.remove('hidden');
    }

    navCreate.addEventListener('click', () => { setActiveNav(navCreate); setPage('Create'); });
    navArrange.addEventListener('click', () => { setActiveNav(navArrange); setPage('Timeline'); });
    navLibrary.addEventListener('click', () => { setActiveNav(navLibrary); setPage('Library'); });
    navExplore.addEventListener('click', () => { setActiveNav(navExplore); setPage('Explore'); });

    hamburger.addEventListener('click', () => { appDrawer.classList.toggle('active'); });
    btnInspector.addEventListener('click', () => { inspector.classList.toggle('active'); });

    // Populate piano keys
    const pianoKeys = document.getElementById('pianoKeys');
    for (let i = 0; i < 24; i++) {
      const k = document.createElement('div');
      k.className = 'key';
      k.textContent = i % 12 === 0 ? 'C' : '';
      pianoKeys.appendChild(k);
    }
    // Populate piano grid rows
    const pianoGrid = document.getElementById('pianoGrid');
    for (let i = 0; i < 24; i++) {
      const r = document.createElement('div');
      r.className = 'grid-row';
      pianoGrid.appendChild(r);
    }

    // Timeline + mixer helpers
    let trackCount = 0;
    function addTrack(name) {
      trackCount += 1;
      const row = document.createElement('div');
      row.className = 'timeline-row';

      const header = document.createElement('div');
      header.className = 'track-header';
      const top = document.createElement('div'); top.className = 'th-top';
      const nm = document.createElement('div'); nm.className = 'th-name'; nm.textContent = name;
      const ctls = document.createElement('div'); ctls.className = 'th-ctls';
      ['M','S','R'].forEach(label => { const b = document.createElement('button'); b.className = 'ctl'; b.textContent = label; ctls.appendChild(b); });
      top.appendChild(nm); top.appendChild(ctls);
      header.appendChild(top);

      const lane = document.createElement('div');
      lane.className = 'track-lane';
      const clip = document.createElement('div'); clip.className = 'timeline-clip'; clip.textContent = 'Clip';
      lane.appendChild(clip);

      row.appendChild(header);
      row.appendChild(lane);
      timelineInner.appendChild(row);

      addMixerChannel(name);
    }

    function addMixerChannel(name) {
      const ch = document.createElement('div'); ch.className = 'channel';
      const title = document.createElement('div'); title.className = 'ch-name'; title.textContent = name;
      const ctls = document.createElement('div'); ctls.className = 'ch-ctls';
      ['M','S','R','Pan'].forEach(label => { const b = document.createElement('button'); b.className = 'ctl'; b.textContent = label; ctls.appendChild(b); });
      const fblock = document.createElement('div'); fblock.className = 'fader-block';
      const fader = document.createElement('div'); fader.className = 'fader'; const thumb = document.createElement('div'); thumb.className = 'thumb'; fader.appendChild(thumb);
      const vu = document.createElement('div'); vu.className = 'vu'; const fill = document.createElement('div'); fill.className = 'fill'; vu.appendChild(fill);
      fblock.appendChild(fader); fblock.appendChild(vu);
      ch.appendChild(title); ch.appendChild(ctls); ch.appendChild(fblock);
      mixerChannels.appendChild(ch);
    }

    // Generate handler (stub to backend)
    async function generate() {
      const req = {
        prompt: promptEl.value || '',
        lyrics: lyricsEl.value || '',
        genre: genreEl.value || '',
        mood: moodEl.value || '',
        duration_sec: 2
      };
      try {
        const resp = await fetch('/api/generate', {
          method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(req)
        });
        if (!resp.ok) throw new Error('Failed to generate');
        const blob = await resp.blob();
        const url = URL.createObjectURL(blob);
        const audio = new Audio(url);
        audio.play();
        const item = document.createElement('div'); item.textContent = 'Generated clip';
        libraryList.textContent = ''; libraryList.appendChild(item);
        libraryPageList.textContent = ''; libraryPageList.appendChild(item.cloneNode(true));
      } catch (e) {
        console.error(e);
        alert('Generate failed');
      }
    }

    btnGenerate.addEventListener('click', generate);
    btnAddToArrange.addEventListener('click', () => {
      addTrack('Track ' + (trackCount + 1));
      setActiveNav(navArrange); setPage('Timeline');
    });

    // Toggle mixer height (compact)
    const toggleMixer = document.getElementById('toggleMixer');
    const mixerEl = document.querySelector('.mixer');
    toggleMixer.addEventListener('click', () => {
      if (mixerEl.style.height === '36px') {
        mixerEl.style.height = '170px';
      } else {
        mixerEl.style.height = '36px';
      }
    });

    // Start on Create page
    setActiveNav(navCreate); setPage('Create');
  </script>
</body>
</html>
'''
    return HTMLResponse(content=html)


@web_app.post("/api/generate")
async def api_generate(req: GenerateRequest):
    # Return a short sine wave WAV so the endpoint is testable.
    sample_rate = 44100
    duration = max(1, int(req.duration_sec or 1))
    freq = 440.0
    nframes = sample_rate * duration
    buf = io.BytesIO()

    import wave
    with wave.open(buf, 'wb') as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)  # 16-bit
        wf.setframerate(sample_rate)
        for i in range(nframes):
            t = i / sample_rate
            val = int(32767.0 * 0.2 * math.sin(2.0 * math.pi * freq * t))
            wf.writeframes(struct.pack('<h', val))

    data = buf.getvalue()
    return Response(content=data, media_type="audio/wav")


@app.function()
@modal.asgi_app()
def music_app_v12():
    return web_app


if __name__ == "__main__":
    app.deploy("music-app-v12-web")
