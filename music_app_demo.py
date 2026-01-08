"""
Prompt 2 Jam - Music Generation PWA
A text-to-music generator using Facebook's MusicGen model
Optimized for cross-platform PWA deployment (iOS/Android)
"""

import modal
from pathlib import Path
from uuid import uuid4
import os

# Create the Modal app
app = modal.App("prompt-2-jam")

# Define the container image with required dependencies
# Using debian_slim for smallest footprint + uv_pip for faster installation
image = (
    modal.Image.debian_slim(python_version="3.11")
    .apt_install("ffmpeg", "libsndfile1")
    .uv_pip_install(
        "torch==2.4.0",
        "torchaudio==2.4.0",
        "transformers==4.41.0",
        "accelerate==0.30.0",
        "scipy==1.13.0",
        "gradio==4.44.1",
        "pydantic==2.10.1",
    )
)

# Set up model caching to avoid re-downloading on every cold start
# Follows Hugging Face best practices per ACE-Step documentation
MODEL_CACHE_DIR = "/root/.cache/musicgen"
model_cache = modal.Volume.from_name("musicgen-model-cache", create_if_missing=True)

# Configure image with HF_HUB environment variables (best practices)
image = image.env({
    "HF_HUB_CACHE": MODEL_CACHE_DIR,
    "HF_HUB_ENABLE_HF_TRANSFER": "1",
    "TRANSFORMERS_CACHE": MODEL_CACHE_DIR,
})


@app.cls(
    image=image,
    gpu="t4",  # T4 GPU - cost-effective for inference
    volumes={MODEL_CACHE_DIR: model_cache},
    timeout=600,
)
class MusicGen:
    """Music generation class using MusicGen model"""
    
    @modal.enter()
    def load_model(self):
        """Load the MusicGen model on container startup"""
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
        if duration < 5 or duration > 300:
            raise ValueError("Duration must be between 5-300 seconds")
        
        print(f"🎼 Generating music for: '{prompt}' ({duration}s)")
        
        try:
            # Process the prompt through the model
            inputs = self.processor(
                text=[prompt],
                padding=True,
                return_tensors="pt",
            ).to("cuda")
            
            # Calculate max_new_tokens based on duration (50 tokens per second)
            max_new_tokens = int(duration * 50)
            
            # Generate audio with optimal settings for quality
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
            
            # Create WAV file in memory (streaming-friendly format)
            buffer = io.BytesIO()
            wavfile.write(buffer, rate=sampling_rate, data=audio_data)
            buffer.seek(0)
            
            print("✅ Music generated successfully!")
            return buffer.read()
            
        except Exception as e:
            print(f"❌ Generation failed: {str(e)}")
            raise


# Lightweight image for web UI (no ML dependencies needed)
web_image = (
    modal.Image.debian_slim(python_version="3.11")
    .uv_pip_install(
        "gradio==4.44.1",
        "pydantic==2.10.1",
    )
)


# Web UI using Gradio - responsive PWA-friendly interface
@app.function(
    image=web_image,
    max_containers=100,  # Handle multiple concurrent users
)
@modal.asgi_app()
def web_ui():
    """
    Gradio web interface for music generation
    Mobile-responsive PWA-compatible interface
    """
    import gradio as gr
    from fastapi import FastAPI, Response
    from fastapi.staticfiles import StaticFiles
    from gradio.routes import mount_gradio_app
    
    api = FastAPI()
    
    # Serve PWA manifest and service worker
    @api.get("/manifest.json")
    async def manifest():
        """Serve PWA manifest"""
        return {
            "name": "Prompt 2 Jam - AI Music Generator",
            "short_name": "Prompt 2 Jam",
            "description": "Your AI BandMate in your pocket! Generate original music from text descriptions.",
            "start_url": "/",
            "scope": "/",
            "display": "standalone",
            "orientation": "portrait-primary",
            "theme_color": "#1f2937",
            "background_color": "#ffffff",
            "icons": [
                {
                    "src": "data:image/svg+xml,<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 192 192'><rect fill='%231f2937' width='192' height='192'/><text x='96' y='120' font-size='100' fill='white' text-anchor='middle' font-family='Arial' font-weight='bold'>🎵</text></svg>",
                    "sizes": "192x192",
                    "type": "image/svg+xml"
                },
                {
                    "src": "data:image/svg+xml,<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 512 512'><rect fill='%231f2937' width='512' height='512'/><text x='256' y='340' font-size='280' fill='white' text-anchor='middle' font-family='Arial' font-weight='bold'>🎵</text></svg>",
                    "sizes": "512x512",
                    "type": "image/svg+xml"
                }
            ]
        }
    
    @api.get("/sw.js")
    async def service_worker():
        """Serve service worker with proper headers"""
        return Response(
            content="""
// Service Worker for Prompt 2 Jam PWA
const CACHE_VERSION = 'v1';
const CACHE_NAME = `prompt-2-jam-${CACHE_VERSION}`;

self.addEventListener('install', (event) => {
  console.log('[SW] Service worker installed');
  self.skipWaiting();
});

self.addEventListener('activate', (event) => {
  console.log('[SW] Service worker activated');
  self.clients.claim();
});

self.addEventListener('fetch', (event) => {
  const url = new URL(event.request.url);
  if (event.request.method !== 'GET') return;
  
  // Network first for API calls
  if (url.pathname.includes('/api/')) {
    return event.respondWith(
      fetch(event.request).catch(() => {
        return new Response(JSON.stringify({error: 'offline'}), {
          status: 503,
          headers: {'Content-Type': 'application/json'}
        });
      })
    );
  }
  
  // Cache first for everything else
  event.respondWith(
    caches.match(event.request).then(r => r || fetch(event.request))
  );
});
""",
            media_type="application/javascript",
            headers={
                "Cache-Control": "no-cache, no-store, must-revalidate",
                "Service-Worker-Allowed": "/"
            }
        )
    
    # Get reference to the MusicGen class
    music_gen = MusicGen()
    
    def generate_music_ui(prompt: str, duration: int):
        """Generate music from the UI"""
        if not prompt or not prompt.strip():
            return None, "❌ Please enter a prompt"
        
        try:
            # Call the remote generation method
            audio_bytes = music_gen.generate.remote(prompt, duration)
            
            # Save to temporary file for Gradio
            temp_path = f"/tmp/music_{uuid4().hex}.wav"
            with open(temp_path, "wb") as f:
                f.write(audio_bytes)
            
            return temp_path, f"✅ Generated {duration}s of music!"
            
        except ValueError as e:
            return None, f"❌ Error: {str(e)}"
        except Exception as e:
            return None, f"❌ Generation failed. Please try again."
    
    # Create mobile-responsive Gradio interface with PWA headers
    with gr.Blocks(theme="soft", title="Prompt 2 Jam", css="""
        .container { max-width: 100%; padding: 0 10px; }
        body { margin: 0; padding: 0; }
        @media (max-width: 600px) {
            .row { flex-direction: column; }
            .gr-textbox { font-size: 16px; }
        }
        .gr-button-primary {
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        }
    """, head="<meta name='viewport' content='width=device-width, initial-scale=1, viewport-fit=cover'><link rel='manifest' href='/manifest.json'><meta name='theme-color' content='#1f2937'><meta name='apple-mobile-web-app-capable' content='yes'><meta name='apple-mobile-web-app-status-bar-style' content='black-translucent'><script>if ('serviceWorker' in navigator) { navigator.serviceWorker.register('/sw.js').then(r => console.log('[PWA] SW registered')).catch(e => console.log('[PWA] SW failed:', e)); }</script>") as demo:
        gr.Markdown(
            """
            # 🎵 Prompt 2 Jam
            ### Your AI BandMate in your pocket!
            
            Generate original music from text descriptions. Describe the style, mood, and instruments, and let AI create your track!
            """
        )
        
        with gr.Row():
            with gr.Column(scale=1):
                prompt_input = gr.Textbox(
                    label="Music Prompt",
                    placeholder="e.g., upbeat electronic dance music with synthesizers and drums",
                    lines=4,
                    value="upbeat electronic dance music with synthesizers",
                    interactive=True,
                )
                duration_slider = gr.Slider(
                    minimum=5,
                    maximum=30,  # Reduced from 300 for faster generation/testing
                    value=10,
                    step=5,
                    label="Duration (seconds)",
                    interactive=True,
                )
                generate_btn = gr.Button("🎵 Generate Music", variant="primary", size="lg")
                
                status_output = gr.Textbox(
                    label="Status",
                    interactive=False,
                    value="Ready to generate!",
                )
                
                gr.Markdown(
                    """
                    ### 💡 Example Prompts:
                    - "upbeat electronic dance music"
                    - "calm acoustic guitar"
                    - "energetic rock music"
                    - "relaxing piano jazz"
                    - "epic orchestral soundtrack"
                    """
                )
            
            with gr.Column(scale=1):
                audio_output = gr.Audio(
                    label="Generated Music",
                    type="filepath",
                    interactive=False,
                )
        
        # Connect the button to the generation function
        generate_btn.click(
            fn=generate_music_ui,
            inputs=[prompt_input, duration_slider],
            outputs=[audio_output, status_output],
        )
        
        # Add quick-start examples
        gr.Examples(
            examples=[
                ["upbeat electronic dance music with synthesizers", 10],
                ["calm acoustic guitar melody", 10],
                ["energetic rock music with electric guitar", 15],
            ],
            inputs=[prompt_input, duration_slider],
            label="Quick Start Examples",
        )
    
    return mount_gradio_app(app=api, blocks=demo, path="/")


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
