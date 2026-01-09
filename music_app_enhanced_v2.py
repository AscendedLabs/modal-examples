# Enhanced Music Generation App - v0.0.2
# Adds comprehensive controls: genre presets, mood, tempo, lyrics, advanced settings

from pathlib import Path
from typing import Optional
from uuid import uuid4

import modal

# Keep same image configuration as v0.0.1
image = (
    modal.Image.debian_slim(python_version="3.10")
    .apt_install("git", "ffmpeg")
    .uv_pip_install(
        "torch==2.8.0",
        "torchaudio==2.8.0",
        "transformers==4.50.0",
        "diffusers==0.33.0",
        "peft==0.14.0",  # Key to resolving dependency conflicts
        "git+https://github.com/ace-step/ACE-Step.git@6ae0852b1388de6dc0cca26b31a86d711f723cb3",
    )
)

# Same cache setup
cache_dir = "/root/.cache/ace-step/checkpoints"
model_cache = modal.Volume.from_name("ACE-Step-model-cache", create_if_missing=True)

# Web dependencies
web_image = image.pip_install(
    "FastAPI[standard]==0.115.4",
    "Gradio==4.44.1",
    "Pydantic==2.10.5",
)

app = modal.App("prompt-2-jam-v2")

# Same MusicGenerator class - no changes needed
@app.cls(
    gpu="l40s",
    image=image,
    volumes={cache_dir: model_cache},
    timeout=1800,
)
class MusicGenerator:
    model: Optional[object] = None

    def init(self):
        """Lazy load model on first use"""
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
        cfg_type: str = "apg",
        scheduler_type: str = "euler",
    ) -> bytes:
        import uuid
        
        # Load model on first request
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
            scheduler_type=scheduler_type,
            cfg_type=cfg_type,
            omega_scale=10,
            guidance_interval=0.5,
            guidance_interval_decay=0,
            min_guidance_scale=3,
            use_erg_tag=True,
            use_erg_lyric=True,
        )

        with open(output_path, "rb") as f:
            audio_bytes = f.read()
        
        return audio_bytes

# Bundle service worker and manifest into the image
web_image_with_assets = (
    web_image
    .add_local_file("sw.js", "/root/sw.js")
    .add_local_file("pwa_manifest.json", "/root/pwa_manifest.json")
)

# Enhanced Web UI with comprehensive controls
@app.function(
    image=web_image_with_assets,
    allow_concurrent_inputs=100,
    timeout=1800,
)
@modal.asgi_app()
def web_ui_enhanced():
    from fastapi import FastAPI, Response
    from fastapi.responses import StreamingResponse, FileResponse, HTMLResponse, JSONResponse
    from pydantic import BaseModel
    
    fastapi_app = FastAPI(title="Prompt2Jam Studio v2")
    
    # Create generator instance
    music_generator = MusicGenerator()
    
    class GenerateRequest(BaseModel):
        prompt: str
        lyrics: str = ""
        duration: float = 30.0
        tempo: Optional[int] = None
        key: Optional[str] = None
        genre: Optional[str] = None
        mood: Optional[str] = None
        vocal_type: str = "vocal"  # vocal or instrumental
        language: str = "english"
        inference_steps: int = 60
        guidance_scale: float = 15.0
        seed: Optional[int] = None
    
    @fastapi_app.get("/", response_class=HTMLResponse)
    async def root():
        return HTML_ENHANCED
    
    @fastapi_app.post("/api/generate")
    async def generate_music_api(request: GenerateRequest):
        try:
            if not request.prompt or not request.prompt.strip():
                return JSONResponse({"error": "Prompt cannot be empty"}, status_code=400)
            if request.duration < 5 or request.duration > 240:
                return JSONResponse({"error": "Duration must be 5-240 seconds"}, status_code=400)
            
            # Build enhanced prompt with metadata
            enhanced_prompt = request.prompt
            if request.genre:
                enhanced_prompt = f"{request.genre}, {enhanced_prompt}"
            if request.mood:
                enhanced_prompt = f"{request.mood}, {enhanced_prompt}"
            if request.tempo:
                enhanced_prompt = f"{request.tempo} BPM, {enhanced_prompt}"
            
            # Handle lyrics
            lyrics = request.lyrics.strip() if request.lyrics else ""
            if request.vocal_type == "instrumental" and not lyrics:
                lyrics = "[inst]"
            
            print(f"🎵 Enhanced Generation: {enhanced_prompt} ({request.duration}s)")
            print(f"   Lyrics: {lyrics[:50]}...")
            print(f"   Steps: {request.inference_steps}, Guidance: {request.guidance_scale}")
            
            # Call MusicGenerator via remote
            audio_bytes = await music_generator.run.remote.aio(
                prompt=enhanced_prompt,
                lyrics=lyrics or "[inst]",
                duration=request.duration,
                format="wav",
                manual_seeds=request.seed or 1,
                inference_steps=request.inference_steps,
                guidance_scale=request.guidance_scale,
            )
            
            print(f"✅ Generated {len(audio_bytes)} bytes")
            
            return StreamingResponse(
                iter([audio_bytes]),
                media_type="audio/wav",
                headers={"Content-Disposition": f"attachment; filename=music_{uuid4().hex[:8]}.wav"}
            )
        except Exception as e:
            import traceback
            print(f"❌ Error: {traceback.format_exc()}")
            return JSONResponse({"error": str(e)}, status_code=500)
    
    @fastapi_app.get("/sw.js")
    async def service_worker():
        return FileResponse("/root/sw.js", media_type="application/javascript")

    @fastapi_app.get("/pwa_manifest.json")
    async def pwa_manifest():
        return FileResponse("/root/pwa_manifest.json", media_type="application/manifest+json")

    @fastapi_app.get("/favicon.ico")
    async def favicon():
        return Response(status_code=204)
    
    return fastapi_app

# HTML with enhanced controls
HTML_ENHANCED = """<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Prompt2Jam Studio - AI Music Production</title>
    <link rel="manifest" href="/pwa_manifest.json">
    <meta name="theme-color" content="#6366f1">
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        
        body {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            min-height: 100vh;
            padding: 20px;
            color: #333;
        }
        
        .container {
            max-width: 1200px;
            margin: 0 auto;
            background: rgba(255, 255, 255, 0.98);
            border-radius: 24px;
            padding: 40px;
            box-shadow: 0 20px 60px rgba(0, 0, 0, 0.3);
        }
        
        header {
            text-align: center;
            margin-bottom: 40px;
            padding-bottom: 20px;
            border-bottom: 2px solid #e5e7eb;
        }
        
        h1 {
            font-size: 2.5em;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
            margin-bottom: 10px;
        }
        
        .subtitle {
            color: #6b7280;
            font-size: 1.1em;
        }
        
        .main-grid {
            display: grid;
            grid-template-columns: 1fr 1fr;
            gap: 30px;
            margin-bottom: 30px;
        }
        
        @media (max-width: 968px) {
            .main-grid { grid-template-columns: 1fr; }
        }
        
        .section {
            background: #f9fafb;
            border-radius: 16px;
            padding: 24px;
            border: 1px solid #e5e7eb;
        }
        
        .section-title {
            font-size: 1.3em;
            font-weight: 600;
            margin-bottom: 20px;
            color: #111827;
            display: flex;
            align-items: center;
            gap: 8px;
        }
        
        .form-group {
            margin-bottom: 20px;
        }
        
        label {
            display: block;
            font-weight: 600;
            margin-bottom: 8px;
            color: #374151;
            font-size: 0.95em;
        }
        
        input[type="text"],
        textarea,
        select {
            width: 100%;
            padding: 12px 16px;
            border: 2px solid #e5e7eb;
            border-radius: 12px;
            font-size: 1em;
            transition: all 0.3s;
            font-family: inherit;
        }
        
        input:focus,
        textarea:focus,
        select:focus {
            outline: none;
            border-color: #667eea;
            box-shadow: 0 0 0 3px rgba(102, 126, 234, 0.1);
        }
        
        textarea {
            resize: vertical;
            min-height: 100px;
        }
        
        .slider-group {
            margin-bottom: 20px;
        }
        
        .slider-header {
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 8px;
        }
        
        input[type="range"] {
            width: 100%;
            height: 6px;
            border-radius: 3px;
            background: #e5e7eb;
            outline: none;
            -webkit-appearance: none;
        }
        
        input[type="range"]::-webkit-slider-thumb {
            -webkit-appearance: none;
            width: 20px;
            height: 20px;
            border-radius: 50%;
            background: #667eea;
            cursor: pointer;
            transition: all 0.3s;
        }
        
        input[type="range"]::-webkit-slider-thumb:hover {
            background: #5558d9;
            transform: scale(1.2);
        }
        
        .preset-grid {
            display: grid;
            grid-template-columns: repeat(auto-fill, minmax(120px, 1fr));
            gap: 10px;
            margin-bottom: 20px;
        }
        
        .preset-btn {
            padding: 12px;
            background: white;
            border: 2px solid #e5e7eb;
            border-radius: 12px;
            cursor: pointer;
            font-weight: 500;
            transition: all 0.3s;
            font-size: 0.9em;
        }
        
        .preset-btn:hover {
            border-color: #667eea;
            background: #f0f4ff;
            transform: translateY(-2px);
        }
        
        .preset-btn.active {
            background: #667eea;
            color: white;
            border-color: #667eea;
        }
        
        .radio-group {
            display: flex;
            gap: 15px;
            margin-top: 8px;
        }
        
        .radio-label {
            display: flex;
            align-items: center;
            gap: 6px;
            cursor: pointer;
            font-weight: normal;
        }
        
        .collapsible {
            background: white;
            border: 2px solid #e5e7eb;
            border-radius: 12px;
            margin-top: 20px;
            overflow: hidden;
        }
        
        .collapsible-header {
            padding: 16px 20px;
            cursor: pointer;
            display: flex;
            justify-content: space-between;
            align-items: center;
            font-weight: 600;
            transition: background 0.3s;
        }
        
        .collapsible-header:hover {
            background: #f9fafb;
        }
        
        .collapsible-content {
            padding: 0 20px;
            max-height: 0;
            overflow: hidden;
            transition: all 0.3s;
        }
        
        .collapsible-content.open {
            padding: 20px;
            max-height: 1000px;
        }
        
        .generate-btn {
            width: 100%;
            padding: 18px 32px;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            border: none;
            border-radius: 16px;
            font-size: 1.2em;
            font-weight: 600;
            cursor: pointer;
            transition: all 0.3s;
            box-shadow: 0 10px 30px rgba(102, 126, 234, 0.4);
        }
        
        .generate-btn:hover {
            transform: translateY(-2px);
            box-shadow: 0 15px 40px rgba(102, 126, 234, 0.5);
        }
        
        .generate-btn:disabled {
            opacity: 0.6;
            cursor: not-allowed;
            transform: none;
        }
        
        .status {
            padding: 16px;
            border-radius: 12px;
            margin: 20px 0;
            display: none;
            font-weight: 500;
        }
        
        .status.info {
            background: #dbeafe;
            color: #1e40af;
            display: block;
        }
        
        .status.success {
            background: #d1fae5;
            color: #065f46;
            display: block;
        }
        
        .status.error {
            background: #fee2e2;
            color: #991b1b;
            display: block;
        }
        
        .player-section {
            background: #111827;
            border-radius: 16px;
            padding: 24px;
            margin-top: 30px;
            color: white;
        }
        
        audio {
            width: 100%;
            border-radius: 8px;
            margin-top: 16px;
        }
        
        .history {
            max-height: 300px;
            overflow-y: auto;
            margin-top: 20px;
        }
        
        .history-item {
            background: white;
            padding: 12px 16px;
            border-radius: 8px;
            margin-bottom: 10px;
            display: flex;
            justify-content: space-between;
            align-items: center;
            border: 1px solid #e5e7eb;
        }
        
        .history-item:hover {
            border-color: #667eea;
        }
        
        .download-btn {
            padding: 8px 16px;
            background: #667eea;
            color: white;
            border: none;
            border-radius: 8px;
            cursor: pointer;
            font-size: 0.9em;
        }
    </style>
</head>
<body>
    <div class="container">
        <header>
            <h1>🎵 Prompt2Jam Studio</h1>
            <p class="subtitle">Professional AI Music Production powered by ACE-Step</p>
        </header>
        
        <form id="form">
            <div class="main-grid">
                <!-- Left Column: Main Controls -->
                <div>
                    <div class="section">
                        <h2 class="section-title">🎨 Creative Prompt</h2>
                        
                        <div class="form-group">
                            <label>Describe Your Music</label>
                            <textarea id="prompt" placeholder="E.g., upbeat electronic dance music with synth melodies"></textarea>
                        </div>
                        
                        <div class="form-group">
                            <label>🎭 Genre Presets</label>
                            <div class="preset-grid" id="genrePresets"></div>
                        </div>
                        
                        <div class="form-group">
                            <label>😊 Mood</label>
                            <select id="mood">
                                <option value="">-- Select Mood --</option>
                                <option value="happy">😊 Happy</option>
                                <option value="sad">😢 Sad</option>
                                <option value="energetic">⚡ Energetic</option>
                                <option value="calm">😌 Calm</option>
                                <option value="dramatic">🎭 Dramatic</option>
                                <option value="romantic">💕 Romantic</option>
                                <option value="mysterious">🔮 Mysterious</option>
                                <option value="epic">🏔️ Epic</option>
                            </select>
                        </div>
                    </div>
                    
                    <div class="section" style="margin-top: 20px;">
                        <h2 class="section-title">🎤 Lyrics (Optional)</h2>
                        <div class="form-group">
                            <label>Add Lyrics with Structure Tags</label>
                            <textarea id="lyrics" placeholder="[verse] Walking down the road&#10;[chorus] Feeling so free&#10;[bridge] Taking it slow"></textarea>
                            <small style="color: #6b7280; display: block; margin-top: 8px;">
                                Use [verse], [chorus], [bridge], [intro], [outro] tags
                            </small>
                        </div>
                        
                        <div class="form-group">
                            <label>Vocal Type</label>
                            <div class="radio-group">
                                <label class="radio-label">
                                    <input type="radio" name="vocalType" value="vocal" checked> 🎤 Vocal
                                </label>
                                <label class="radio-label">
                                    <input type="radio" name="vocalType" value="instrumental"> 🎹 Instrumental
                                </label>
                            </div>
                        </div>
                    </div>
                </div>
                
                <!-- Right Column: Settings -->
                <div>
                    <div class="section">
                        <h2 class="section-title">⚙️ Generation Settings</h2>
                        
                        <div class="slider-group">
                            <div class="slider-header">
                                <label>Duration</label>
                                <span id="durationValue">30</span>s
                            </div>
                            <input type="range" id="duration" min="10" max="240" value="30" step="5">
                        </div>
                        
                        <div class="slider-group">
                            <div class="slider-header">
                                <label>Tempo (BPM)</label>
                                <span id="tempoValue">120</span>
                            </div>
                            <input type="range" id="tempo" min="60" max="200" value="120" step="5">
                        </div>
                        
                        <div class="form-group">
                            <label>Key</label>
                            <select id="key">
                                <option value="">-- Auto --</option>
                                <option value="C Major">C Major</option>
                                <option value="C Minor">C Minor</option>
                                <option value="D Major">D Major</option>
                                <option value="D Minor">D Minor</option>
                                <option value="E Major">E Major</option>
                                <option value="E Minor">E Minor</option>
                                <option value="F Major">F Major</option>
                                <option value="F Minor">F Minor</option>
                                <option value="G Major">G Major</option>
                                <option value="G Minor">G Minor</option>
                                <option value="A Major">A Major</option>
                                <option value="A Minor">A Minor</option>
                                <option value="B Major">B Major</option>
                                <option value="B Minor">B Minor</option>
                            </select>
                        </div>
                        
                        <div class="form-group">
                            <label>Language</label>
                            <select id="language">
                                <option value="english">🇺🇸 English</option>
                                <option value="chinese">🇨🇳 Chinese</option>
                                <option value="spanish">🇪🇸 Spanish</option>
                                <option value="japanese">🇯🇵 Japanese</option>
                                <option value="korean">🇰🇷 Korean</option>
                                <option value="french">🇫🇷 French</option>
                                <option value="german">🇩🇪 German</option>
                                <option value="russian">🇷🇺 Russian</option>
                            </select>
                        </div>
                        
                        <div class="collapsible">
                            <div class="collapsible-header" onclick="toggleAdvanced()">
                                <span>🔬 Advanced Settings</span>
                                <span id="advancedToggle">▼</span>
                            </div>
                            <div class="collapsible-content" id="advancedContent">
                                <div class="slider-group">
                                    <div class="slider-header">
                                        <label>Inference Steps</label>
                                        <span id="stepsValue">60</span>
                                    </div>
                                    <input type="range" id="steps" min="27" max="100" value="60" step="1">
                                    <small style="color: #6b7280;">Higher = better quality, slower generation</small>
                                </div>
                                
                                <div class="slider-group">
                                    <div class="slider-header">
                                        <label>Guidance Scale</label>
                                        <span id="guidanceValue">15</span>
                                    </div>
                                    <input type="range" id="guidance" min="7" max="25" value="15" step="0.5">
                                    <small style="color: #6b7280;">Higher = stricter prompt adherence</small>
                                </div>
                                
                                <div class="form-group">
                                    <label>Seed (Optional)</label>
                                    <input type="number" id="seed" placeholder="Random" min="1">
                                    <small style="color: #6b7280;">Same seed = reproducible results</small>
                                </div>
                            </div>
                        </div>
                    </div>
                    
                    <button type="submit" class="generate-btn" id="generateBtn">
                        🎵 Generate Music
                    </button>
                    
                    <div id="status" class="status"></div>
                </div>
            </div>
        </form>
        
        <div class="player-section">
            <h3 style="margin-bottom: 16px;">🎧 Generated Music</h3>
            <audio id="audio" controls></audio>
        </div>
    </div>
    
    <script>
        const GENRES = [
            'Pop', 'Rock', 'Jazz', 'Classical', 'Electronic', 'Hip-Hop',
            'Country', 'Blues', 'R&B', 'Metal', 'Folk', 'Reggae',
            'Latin', 'Dance', 'Ambient', 'Indie', 'Soul', 'Funk'
        ];
        
        // Initialize genre presets
        const genreContainer = document.getElementById('genrePresets');
        GENRES.forEach(genre => {
            const btn = document.createElement('button');
            btn.type = 'button';
            btn.className = 'preset-btn';
            btn.textContent = genre;
            btn.onclick = () => selectGenre(genre, btn);
            genreContainer.appendChild(btn);
        });
        
        let selectedGenre = '';
        
        function selectGenre(genre, btn) {
            document.querySelectorAll('.preset-btn').forEach(b => b.classList.remove('active'));
            if (selectedGenre === genre) {
                selectedGenre = '';
            } else {
                selectedGenre = genre;
                btn.classList.add('active');
            }
        }
        
        // Slider value updates
        ['duration', 'tempo', 'steps', 'guidance'].forEach(id => {
            const slider = document.getElementById(id);
            const display = document.getElementById(id + 'Value');
            slider.addEventListener('input', e => {
                display.textContent = e.target.value;
            });
        });
        
        function toggleAdvanced() {
            const content = document.getElementById('advancedContent');
            const toggle = document.getElementById('advancedToggle');
            content.classList.toggle('open');
            toggle.textContent = content.classList.contains('open') ? '▲' : '▼';
        }
        
        document.getElementById('form').addEventListener('submit', async e => {
            e.preventDefault();
            await generateMusic();
        });
        
        async function generateMusic() {
            const prompt = document.getElementById('prompt').value.trim();
            const lyrics = document.getElementById('lyrics').value.trim();
            const duration = parseInt(document.getElementById('duration').value);
            const tempo = parseInt(document.getElementById('tempo').value);
            const key = document.getElementById('key').value;
            const mood = document.getElementById('mood').value;
            const language = document.getElementById('language').value;
            const vocalType = document.querySelector('input[name="vocalType"]:checked').value;
            const steps = parseInt(document.getElementById('steps').value);
            const guidance = parseFloat(document.getElementById('guidance').value);
            const seed = document.getElementById('seed').value ? parseInt(document.getElementById('seed').value) : null;
            
            if (!prompt) {
                showStatus('Please describe your music', 'error');
                return;
            }
            
            const generateBtn = document.getElementById('generateBtn');
            generateBtn.disabled = true;
            showStatus(`🎼 Generating ${duration}s of ${selectedGenre || 'music'}... (may take ~${Math.ceil(duration/4)}s)`, 'info');
            
            try {
                const response = await fetch('/api/generate', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({
                        prompt,
                        lyrics,
                        duration,
                        tempo,
                        key,
                        genre: selectedGenre,
                        mood,
                        vocal_type: vocalType,
                        language,
                        inference_steps: steps,
                        guidance_scale: guidance,
                        seed
                    })
                });
                
                if (!response.ok) {
                    const error = await response.json();
                    throw new Error(error.error || 'Generation failed');
                }
                
                const audioBlob = await response.blob();
                const audioUrl = URL.createObjectURL(audioBlob);
                document.getElementById('audio').src = audioUrl;
                
                showStatus(`✅ Generated ${duration}s of ${selectedGenre || 'music'}!`, 'success');
                document.getElementById('audio').play();
            } catch (error) {
                showStatus(`❌ ${error.message}`, 'error');
            } finally {
                generateBtn.disabled = false;
            }
        }
        
        function showStatus(message, type) {
            const status = document.getElementById('status');
            status.textContent = message;
            status.className = `status ${type}`;
        }
        
        if ('serviceWorker' in navigator) {
            navigator.serviceWorker.register('/sw.js').catch(() => {});
        }
    </script>
</body>
</html>
"""
