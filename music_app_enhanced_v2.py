# Prompt2Jam Studio - Enhanced Music Generation v0.0.2
# Enhanced UI with comprehensive controls for ACE-Step
# Built on the proven v0.0.1 architecture with better UX

from pathlib import Path
from typing import Optional
from uuid import uuid4
import modal

# Keep same image and cache as v0.0.1
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
    "Gradio==4.44.1",
    "Pydantic==2.10.5",
)

app = modal.App("prompt-2-jam-enhanced")

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
            audio_bytes = f.read()
        
        return audio_bytes

@app.function(image=web_image, allow_concurrent_inputs=100, timeout=1800)
@modal.asgi_app()
def web_ui():
    from fastapi import FastAPI
    from fastapi.responses import StreamingResponse, HTMLResponse, JSONResponse
    from pydantic import BaseModel
    
    fastapi_app = FastAPI(title="Prompt2Jam Studio v0.0.2")
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
        language: str = "english"
        inference_steps: int = 60
        guidance_scale: float = 15.0
        seed: Optional[int] = None
    
    @fastapi_app.get("/", response_class=HTMLResponse)
    async def root():
        return HTML_ENHANCED_UI
    
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
            
            print(f"🎵 Enhanced: {enhanced_prompt} | {request.duration}s | Steps: {request.inference_steps}")
            
            audio_bytes = await generate.aio(
                prompt=enhanced_prompt,
                lyrics=lyrics or "[inst]",
                duration=request.duration,
                format="wav",
                manual_seeds=request.seed or 1,
                inference_steps=request.inference_steps,
                guidance_scale=request.guidance_scale,
            )
            
            return StreamingResponse(
                iter([audio_bytes]),
                media_type="audio/wav",
                headers={"Content-Disposition": f"attachment; filename=music_{uuid4().hex[:8]}.wav"}
            )
        except Exception as e:
            import traceback
            print(f"❌ {traceback.format_exc()}")
            return JSONResponse({"error": str(e)}, status_code=500)
    
    return fastapi_app

HTML_ENHANCED_UI = """<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Prompt2Jam Studio - AI Music Production</title>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        
        body {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            min-height: 100vh;
            padding: 20px;
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
            border-bottom: 2px solid #e5e7eb;
            padding-bottom: 20px;
        }
        
        h1 {
            font-size: 2.5em;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
            margin-bottom: 10px;
        }
        
        .subtitle { color: #6b7280; font-size: 1.1em; }
        
        .main-grid {
            display: grid;
            grid-template-columns: 1fr 1fr;
            gap: 30px;
        }
        
        @media (max-width: 968px) { .main-grid { grid-template-columns: 1fr; } }
        
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
        }
        
        .form-group {
            margin-bottom: 20px;
        }
        
        label {
            display: block;
            font-weight: 600;
            margin-bottom: 8px;
            color: #374151;
        }
        
        input, textarea, select {
            width: 100%;
            padding: 12px 16px;
            border: 2px solid #e5e7eb;
            border-radius: 12px;
            font-size: 1em;
            font-family: inherit;
            transition: all 0.3s;
        }
        
        input:focus, textarea:focus, select:focus {
            outline: none;
            border-color: #667eea;
            box-shadow: 0 0 0 3px rgba(102, 126, 234, 0.1);
        }
        
        textarea { min-height: 100px; resize: vertical; }
        
        .slider-group {
            margin-bottom: 20px;
        }
        
        .slider-header {
            display: flex;
            justify-content: space-between;
            margin-bottom: 8px;
            font-weight: 600;
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
        }
        
        .preset-grid {
            display: grid;
            grid-template-columns: repeat(auto-fill, minmax(110px, 1fr));
            gap: 10px;
            margin-bottom: 15px;
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
        }
        
        .preset-btn.active {
            background: #667eea;
            color: white;
            border-color: #667eea;
        }
        
        .radio-group {
            display: flex;
            gap: 20px;
        }
        
        .radio-label {
            display: flex;
            align-items: center;
            gap: 6px;
            cursor: pointer;
        }
        
        .collapsible {
            background: white;
            border: 2px solid #e5e7eb;
            border-radius: 12px;
            margin-top: 20px;
            overflow: hidden;
        }
        
        .collapsible-header {
            padding: 16px;
            cursor: pointer;
            font-weight: 600;
            display: flex;
            justify-content: space-between;
            transition: background 0.3s;
        }
        
        .collapsible-header:hover { background: #f9fafb; }
        
        .collapsible-content {
            max-height: 0;
            overflow: hidden;
            transition: all 0.3s;
        }
        
        .collapsible-content.open {
            max-height: 1000px;
            padding: 20px;
        }
        
        .generate-btn {
            width: 100%;
            padding: 18px;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            border: none;
            border-radius: 16px;
            font-size: 1.2em;
            font-weight: 600;
            cursor: pointer;
            transition: all 0.3s;
            box-shadow: 0 10px 30px rgba(102, 126, 234, 0.4);
            margin-top: 20px;
        }
        
        .generate-btn:hover {
            transform: translateY(-2px);
            box-shadow: 0 15px 40px rgba(102, 126, 234, 0.5);
        }
        
        .generate-btn:disabled {
            opacity: 0.6;
            cursor: not-allowed;
        }
        
        .status {
            padding: 16px;
            border-radius: 12px;
            margin: 20px 0;
            display: none;
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
        
        .small { font-size: 0.85em; color: #6b7280; display: block; margin-top: 6px; }
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
                <div>
                    <div class="section">
                        <h2 class="section-title">🎨 Creative Prompt</h2>
                        <div class="form-group">
                            <label>Describe Your Music</label>
                            <textarea id="prompt" placeholder="E.g., upbeat electronic dance music with synth melodies"></textarea>
                        </div>
                        
                        <div class="form-group">
                            <label>🎭 Genre</label>
                            <div class="preset-grid" id="genrePresets"></div>
                        </div>
                        
                        <div class="form-group">
                            <label>😊 Mood</label>
                            <select id="mood">
                                <option value="">-- Select --</option>
                                <option value="happy">😊 Happy</option>
                                <option value="sad">😢 Sad</option>
                                <option value="energetic">⚡ Energetic</option>
                                <option value="calm">😌 Calm</option>
                                <option value="dramatic">🎭 Dramatic</option>
                                <option value="romantic">💕 Romantic</option>
                                <option value="epic">🏔️ Epic</option>
                            </select>
                        </div>
                    </div>
                    
                    <div class="section" style="margin-top: 20px;">
                        <h2 class="section-title">🎤 Lyrics</h2>
                        <div class="form-group">
                            <label>Add Lyrics with Tags</label>
                            <textarea id="lyrics" placeholder="[verse] Your lyrics here&#10;[chorus] Chorus here"></textarea>
                            <span class="small">Use: [verse], [chorus], [bridge], [intro], [outro]</span>
                        </div>
                        
                        <div class="form-group">
                            <label>Type</label>
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
                
                <div>
                    <div class="section">
                        <h2 class="section-title">⚙️ Settings</h2>
                        
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
                                <option value="G Major">G Major</option>
                                <option value="D Major">D Major</option>
                                <option value="A Major">A Major</option>
                                <option value="E Major">E Major</option>
                                <option value="A Minor">A Minor</option>
                                <option value="E Minor">E Minor</option>
                                <option value="D Minor">D Minor</option>
                            </select>
                        </div>
                        
                        <div class="collapsible">
                            <div class="collapsible-header" onclick="toggleAdvanced()">
                                <span>🔬 Advanced</span>
                                <span id="toggle">▼</span>
                            </div>
                            <div class="collapsible-content" id="advContent">
                                <div class="slider-group">
                                    <div class="slider-header">
                                        <label>Quality (Steps)</label>
                                        <span id="stepsValue">60</span>
                                    </div>
                                    <input type="range" id="steps" min="27" max="100" value="60" step="1">
                                    <span class="small">Higher = better quality, slower</span>
                                </div>
                                
                                <div class="slider-group">
                                    <div class="slider-header">
                                        <label>Prompt Strength</label>
                                        <span id="guidanceValue">15</span>
                                    </div>
                                    <input type="range" id="guidance" min="7" max="25" value="15" step="0.5">
                                </div>
                                
                                <div class="form-group">
                                    <label>Seed (Optional)</label>
                                    <input type="number" id="seed" placeholder="Random">
                                    <span class="small">Same seed = reproducible</span>
                                </div>
                            </div>
                        </div>
                        
                        <button type="submit" class="generate-btn" id="generateBtn">
                            🎵 Generate Music
                        </button>
                        
                        <div id="status" class="status"></div>
                    </div>
                </div>
            </div>
        </form>
        
        <div class="player-section">
            <h3 style="margin-bottom: 16px;">🎧 Your Creation</h3>
            <audio id="audio" controls></audio>
        </div>
    </div>
    
    <script>
        const GENRES = ['Pop', 'Rock', 'Jazz', 'Classical', 'Electronic', 'Hip-Hop', 'Country', 'Blues', 'R&B', 'Metal', 'Folk', 'Reggae', 'Latin', 'Dance', 'Ambient', 'Indie', 'Soul', 'Funk'];
        
        let selectedGenre = '';
        const genreContainer = document.getElementById('genrePresets');
        
        GENRES.forEach(genre => {
            const btn = document.createElement('button');
            btn.type = 'button';
            btn.className = 'preset-btn';
            btn.textContent = genre;
            btn.onclick = e => {
                e.preventDefault();
                document.querySelectorAll('.preset-btn').forEach(b => b.classList.remove('active'));
                if (selectedGenre === genre) {
                    selectedGenre = '';
                } else {
                    selectedGenre = genre;
                    btn.classList.add('active');
                }
            };
            genreContainer.appendChild(btn);
        });
        
        ['duration', 'tempo', 'steps', 'guidance'].forEach(id => {
            document.getElementById(id).addEventListener('input', e => {
                document.getElementById(id + 'Value').textContent = e.target.value;
            });
        });
        
        function toggleAdvanced() {
            const content = document.getElementById('advContent');
            content.classList.toggle('open');
            document.getElementById('toggle').textContent = content.classList.contains('open') ? '▲' : '▼';
        }
        
        document.getElementById('form').addEventListener('submit', async e => {
            e.preventDefault();
            const prompt = document.getElementById('prompt').value.trim();
            if (!prompt) {
                showStatus('Please describe your music', 'error');
                return;
            }
            
            const btn = document.getElementById('generateBtn');
            btn.disabled = true;
            showStatus('🎼 Generating... (may take ~30-60 seconds)', 'info');
            
            try {
                const response = await fetch('/api/generate', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({
                        prompt,
                        lyrics: document.getElementById('lyrics').value.trim(),
                        duration: parseInt(document.getElementById('duration').value),
                        tempo: parseInt(document.getElementById('tempo').value),
                        genre: selectedGenre,
                        mood: document.getElementById('mood').value,
                        vocal_type: document.querySelector('input[name="vocalType"]:checked').value,
                        inference_steps: parseInt(document.getElementById('steps').value),
                        guidance_scale: parseFloat(document.getElementById('guidance').value),
                        seed: document.getElementById('seed').value ? parseInt(document.getElementById('seed').value) : null
                    })
                });
                
                if (!response.ok) throw new Error('Generation failed');
                
                const blob = await response.blob();
                document.getElementById('audio').src = URL.createObjectURL(blob);
                showStatus('✅ Ready to play!', 'success');
                document.getElementById('audio').play();
            } catch (error) {
                showStatus(`❌ ${error.message}`, 'error');
            } finally {
                btn.disabled = false;
            }
        });
        
        function showStatus(msg, type) {
            const status = document.getElementById('status');
            status.textContent = msg;
            status.className = `status ${type}`;
        }
    </script>
</body>
</html>
"""
