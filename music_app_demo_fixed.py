"""
Prompt 2 Jam - Music Generation PWA (Fixed Version)
A text-to-music generator using Facebook's MusicGen model
Optimized for cross-platform PWA deployment (iOS/Android)

Following Modal documentation best practices:
https://modal.com/docs/examples/text-to-audio
"""

import modal
from pathlib import Path
from uuid import uuid4
import json

# Create the Modal app
app = modal.App("prompt-2-jam")

# Define the ML inference image (no web deps)
# Following Modal's ACE-Step example architecture
ml_image = (
    modal.Image.debian_slim(python_version="3.11")
    .apt_install("ffmpeg", "libsndfile1")
    .uv_pip_install(
        "torch==2.4.0",
        "torchaudio==2.4.0",
        "transformers==4.41.0",
        "accelerate==0.30.0",
        "scipy==1.13.0",
    )
)

# Set up model caching - follows HuggingFace best practices
MODEL_CACHE_DIR = "/root/.cache/musicgen"
model_cache = modal.Volume.from_name("musicgen-model-cache", create_if_missing=True)

# Configure ML image with HF environment variables
ml_image = ml_image.env({
    "HF_HUB_CACHE": MODEL_CACHE_DIR,
    "HF_HUB_ENABLE_HF_TRANSFER": "1",
    "TRANSFORMERS_CACHE": MODEL_CACHE_DIR,
})


@app.cls(
    image=ml_image,
    gpu="t4",  # T4 GPU - cost-effective for inference
    volumes={MODEL_CACHE_DIR: model_cache},
    timeout=600,
)
class MusicGen:
    """Music generation class using MusicGen model - loads model once at startup"""
    
    @modal.enter()
    def load_model(self):
        """Load the MusicGen model on container startup (called once)"""
        from transformers import MusicgenForConditionalGeneration, AutoProcessor
        import torch
        
        print("🎵 Loading MusicGen model...")
        
        # Load processor and model from HuggingFace Hub
        # Will use cached volume on subsequent runs
        self.processor = AutoProcessor.from_pretrained(
            "facebook/musicgen-small",
            cache_dir=MODEL_CACHE_DIR,
        )
        self.model = MusicgenForConditionalGeneration.from_pretrained(
            "facebook/musicgen-small",
            cache_dir=MODEL_CACHE_DIR,
            torch_dtype=torch.float16,
        )
        
        # Move model to GPU for faster inference
        self.model = self.model.to("cuda")
        
        print("✅ Model loaded successfully!")

    @modal.method()
    def generate(self, prompt: str, duration: int = 10) -> bytes:
        """Generate music from a text prompt"""
        import scipy.io.wavfile as wavfile
        import torch
        import io
        
        # Validate inputs
        if not prompt or not prompt.strip():
            raise ValueError("Prompt cannot be empty")
        if duration < 5 or duration > 30:
            raise ValueError("Duration must be between 5-30 seconds")
        
        print(f"🎼 Generating {duration}s music for: '{prompt}'")
        
        try:
            # Process the prompt through the model
            inputs = self.processor(
                text=[prompt],
                padding=True,
                return_tensors="pt",
            ).to("cuda")
            
            # Calculate max_new_tokens based on duration (50 tokens per second)
            max_new_tokens = int(duration * 50)
            
            # Generate audio with optimal settings
            with torch.no_grad():
                audio_values = self.model.generate(
                    **inputs,
                    max_new_tokens=max_new_tokens,
                    do_sample=True,
                    guidance_scale=3.0,
                    top_k=250,
                    temperature=1.0,
                )
            
            # Extract audio data
            sampling_rate = self.model.config.audio_encoder.sampling_rate
            audio_data = audio_values[0, 0].cpu().numpy()
            
            # Create WAV file in memory
            buffer = io.BytesIO()
            wavfile.write(buffer, rate=sampling_rate, data=audio_data)
            buffer.seek(0)
            
            print("✅ Music generated successfully!")
            return buffer.read()
            
        except Exception as e:
            print(f"❌ Generation failed: {str(e)}")
            raise


# Web UI image - minimal with FastAPI + simple HTML/JS
web_image = (
    modal.Image.debian_slim(python_version="3.11")
    .uv_pip_install(
        "fastapi==0.128.0",
        "pydantic==2.10.1",
    )
)


# Web UI using FastAPI + vanilla HTML/JS (no Gradio dependency issues)
@app.function(
    image=web_image,
    max_containers=100,  # Handle multiple concurrent users
)
@modal.asgi_app()
def web_ui():
    """
    FastAPI web interface for music generation
    Mobile-responsive PWA-compatible interface (no Gradio dependency issues)
    """
    from fastapi import FastAPI
    from fastapi.responses import HTMLResponse, StreamingResponse
    from fastapi.staticfiles import StaticFiles
    import io
    
    app = FastAPI(title="Prompt 2 Jam")
    
    # Get reference to the MusicGen class
    music_gen = MusicGen()
    
    # PWA Manifest endpoint
    @app.get("/manifest.json")
    async def manifest():
        """Serve PWA manifest for installation support"""
        return {
            "name": "Prompt 2 Jam - AI Music Generator",
            "short_name": "Prompt 2 Jam",
            "description": "Your AI BandMate in your pocket! Generate original music from text.",
            "start_url": "/",
            "scope": "/",
            "display": "standalone",
            "orientation": "portrait-primary",
            "theme_color": "#1f2937",
            "background_color": "#ffffff",
            "icons": [
                {
                    "src": "data:image/svg+xml,<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 192 192'><rect fill='%231f2937' width='192' height='192'/><text x='96' y='120' font-size='100' fill='white' text-anchor='middle' font-weight='bold'>🎵</text></svg>",
                    "sizes": "192x192",
                    "type": "image/svg+xml"
                }
            ]
        }
    
    # Service Worker endpoint
    @app.get("/sw.js")
    async def service_worker():
        """Serve service worker with proper cache control headers"""
        from fastapi.responses import Response
        
        sw_code = """
const CACHE_NAME = 'prompt-2-jam-v1';
self.addEventListener('install', e => { self.skipWaiting(); });
self.addEventListener('activate', e => { self.clients.claim(); });
self.addEventListener('fetch', e => {
  if (e.request.method !== 'GET') return;
  // Network first for API calls
  if (e.request.url.includes('/api/')) {
    return e.respondWith(fetch(e.request).catch(() => 
      new Response(JSON.stringify({error: 'offline'}), {status: 503})
    ));
  }
  // Cache first for everything else
  e.respondWith(caches.match(e.request).then(r => r || fetch(e.request)));
});
"""
        return Response(
            content=sw_code,
            media_type="application/javascript",
            headers={
                "Cache-Control": "no-cache, no-store, must-revalidate",
                "Service-Worker-Allowed": "/"
            }
        )
    
    # API endpoint for music generation
    @app.post("/api/generate")
    async def generate_music(prompt: str, duration: int = 10):
        """Generate music from prompt"""
        try:
            if not prompt or not prompt.strip():
                return {"error": "Prompt cannot be empty"}, 400
            if duration < 5 or duration > 30:
                return {"error": "Duration must be 5-30 seconds"}, 400
            
            # Call the remote generation method
            audio_bytes = music_gen.generate.remote(prompt, duration)
            
            # Return as audio stream
            return StreamingResponse(
                iter([audio_bytes]),
                media_type="audio/wav",
                headers={"Content-Disposition": f"attachment; filename=music.wav"}
            )
        except Exception as e:
            return {"error": str(e)}, 500
    
    # Root endpoint - serve PWA HTML
    @app.get("/", response_class=HTMLResponse)
    async def root():
        """Serve the main HTML interface"""
        return """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0, viewport-fit=cover">
    <meta name="theme-color" content="#1f2937">
    <meta name="apple-mobile-web-app-capable" content="yes">
    <meta name="apple-mobile-web-app-status-bar-style" content="black-translucent">
    <link rel="manifest" href="/manifest.json">
    <title>Prompt 2 Jam - AI Music Generator</title>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Oxygen, Ubuntu, Cantarell, sans-serif;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            min-height: 100vh;
            display: flex;
            align-items: center;
            justify-content: center;
            padding: 20px;
        }
        .container {
            background: white;
            border-radius: 20px;
            box-shadow: 0 20px 60px rgba(0,0,0,0.3);
            max-width: 500px;
            width: 100%;
            padding: 40px 30px;
        }
        h1 {
            font-size: 28px;
            margin-bottom: 10px;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
            background-clip: text;
        }
        .subtitle {
            color: #666;
            margin-bottom: 30px;
            font-size: 14px;
        }
        .form-group {
            margin-bottom: 25px;
        }
        label {
            display: block;
            font-weight: 600;
            margin-bottom: 8px;
            color: #333;
        }
        textarea, input[type="range"] {
            width: 100%;
            padding: 12px;
            border: 2px solid #e0e0e0;
            border-radius: 10px;
            font-size: 14px;
            font-family: inherit;
        }
        textarea {
            resize: vertical;
            min-height: 100px;
        }
        textarea:focus, input[type="range"]:focus {
            outline: none;
            border-color: #667eea;
        }
        .slider-labels {
            display: flex;
            justify-content: space-between;
            font-size: 12px;
            color: #999;
            margin-top: 8px;
        }
        button {
            width: 100%;
            padding: 15px;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            border: none;
            border-radius: 10px;
            font-size: 16px;
            font-weight: 600;
            cursor: pointer;
            transition: transform 0.2s;
        }
        button:hover { transform: translateY(-2px); }
        button:active { transform: translateY(0); }
        button:disabled {
            opacity: 0.6;
            cursor: not-allowed;
        }
        #status {
            margin-top: 20px;
            padding: 15px;
            border-radius: 10px;
            text-align: center;
            display: none;
            font-size: 14px;
        }
        #status.info { background: #e3f2fd; color: #1976d2; }
        #status.success { background: #e8f5e9; color: #388e3c; }
        #status.error { background: #ffebee; color: #d32f2f; }
        audio {
            width: 100%;
            margin-top: 20px;
            border-radius: 10px;
        }
        .examples {
            margin-top: 30px;
            padding-top: 30px;
            border-top: 2px solid #e0e0e0;
        }
        .examples h3 {
            font-size: 14px;
            color: #666;
            margin-bottom: 10px;
        }
        .examples button {
            background: #f5f5f5;
            color: #333;
            margin-bottom: 8px;
            font-size: 13px;
            padding: 10px;
        }
        @media (max-width: 600px) {
            .container { padding: 25px 20px; }
            h1 { font-size: 24px; }
        }
    </style>
</head>
<body>
    <div class="container">
        <h1>🎵 Prompt 2 Jam</h1>
        <p class="subtitle">Your AI BandMate in your pocket!</p>
        
        <form id="form">
            <div class="form-group">
                <label for="prompt">Music Prompt</label>
                <textarea id="prompt" placeholder="e.g., upbeat electronic dance music with synthesizers" required>upbeat electronic dance music with synthesizers</textarea>
            </div>
            
            <div class="form-group">
                <label for="duration">Duration: <span id="durationValue">10</span>s</label>
                <input type="range" id="duration" min="5" max="30" value="10" step="5">
                <div class="slider-labels">
                    <span>5s</span>
                    <span>30s</span>
                </div>
            </div>
            
            <button type="submit" id="generateBtn">🎵 Generate Music</button>
        </form>
        
        <div id="status"></div>
        <audio id="audio" controls></audio>
        
        <div class="examples">
            <h3>💡 Quick Examples:</h3>
            <button class="example-btn" data-prompt="calm acoustic guitar melody">Acoustic Guitar</button>
            <button class="example-btn" data-prompt="energetic rock music with electric guitar">Rock Music</button>
            <button class="example-btn" data-prompt="relaxing piano jazz">Jazz Piano</button>
        </div>
    </div>
    
    <script>
        // Service Worker registration
        if ('serviceWorker' in navigator) {
            navigator.serviceWorker.register('/sw.js')
                .then(r => console.log('[PWA] Service worker registered'))
                .catch(e => console.log('[PWA] SW registration failed:', e));
        }
        
        const form = document.getElementById('form');
        const promptInput = document.getElementById('prompt');
        const durationInput = document.getElementById('duration');
        const durationValue = document.getElementById('durationValue');
        const generateBtn = document.getElementById('generateBtn');
        const status = document.getElementById('status');
        const audioPlayer = document.getElementById('audio');
        
        // Update duration display
        durationInput.addEventListener('input', e => {
            durationValue.textContent = e.target.value;
        });
        
        // Handle form submission
        form.addEventListener('submit', async e => {
            e.preventDefault();
            await generateMusic();
        });
        
        // Handle example buttons
        document.querySelectorAll('.example-btn').forEach(btn => {
            btn.addEventListener('click', e => {
                promptInput.value = e.target.dataset.prompt;
                generateMusic();
            });
        });
        
        async function generateMusic() {
            const prompt = promptInput.value.trim();
            const duration = parseInt(durationInput.value);
            
            if (!prompt) {
                showStatus('Please enter a prompt', 'error');
                return;
            }
            
            generateBtn.disabled = true;
            showStatus('🎼 Generating music...', 'info');
            
            try {
                const response = await fetch('/api/generate', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/x-www-form-urlencoded',
                    },
                    body: new URLSearchParams({
                        prompt: prompt,
                        duration: duration
                    })
                });
                
                if (!response.ok) {
                    const error = await response.json();
                    throw new Error(error.error || 'Generation failed');
                }
                
                const audioBlob = await response.blob();
                const audioUrl = URL.createObjectURL(audioBlob);
                audioPlayer.src = audioUrl;
                
                showStatus(`✅ Generated ${duration}s of music!`, 'success');
                audioPlayer.play();
            } catch (error) {
                showStatus(`❌ ${error.message}`, 'error');
            } finally {
                generateBtn.disabled = false;
            }
        }
        
        function showStatus(message, type) {
            status.textContent = message;
            status.className = type;
            status.style.display = 'block';
        }
    </script>
</body>
</html>
"""
    
    return app


# Command-line entrypoint for testing
@app.local_entrypoint()
def main(prompt: str = "upbeat electronic dance music", duration: int = 10):
    """Generate music from command line"""
    print(f"🎵 Generating {duration}s of music from prompt: '{prompt}'")
    
    music_gen = MusicGen()
    audio_bytes = music_gen.generate.remote(prompt, duration)
    
    # Save to local file
    output_dir = Path("/tmp/music_output")
    output_dir.mkdir(exist_ok=True, parents=True)
    
    output_path = output_dir / f"music_{prompt[:20].replace(' ', '_')}.wav"
    output_path.write_bytes(audio_bytes)
    
    print(f"✅ Music saved to: {output_path}")
