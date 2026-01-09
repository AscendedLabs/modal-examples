# # Make music with ACE-Step

# In this example, we show you how you can run [ACE Studio](https://acestudio.ai/)'s
# [ACE-Step](https://github.com/ace-step/ACE-Step) music generation model
# on Modal.

# We'll set up both a serverless music generation service
# and a web user interface.

# ## Setting up dependencies

from pathlib import Path
from typing import Optional
from uuid import uuid4

import modal

# We start by defining the environment our generation runs in.
# This takes some explaining since, like most cutting-edge ML environments, it is a bit fiddly.

# This environment is captured by a
# [container image](https://modal.com/docs/guide/images),
# which we build step-by-step by calling methods to add dependencies,
# like `apt_install` to add system packages and `pip_install` to add
# Python packages.

# Note that we don't have to install anything with "CUDA"
# in the name -- the drivers come for free with the Modal environment
# and the rest gets installed `pip`. That makes our life a lot easier!
# If you want to see the details, check out [this guide](https://modal.com/docs/guide/gpu)
# in our docs.

image = (
    modal.Image.debian_slim(python_version="3.10")
    .apt_install("git", "ffmpeg")
    .uv_pip_install(
        "torch==2.8.0",
        "torchaudio==2.8.0",
        "transformers==4.50.0",
        "diffusers==0.33.0",  # Specific version that ACE-Step tested with
        "peft==0.14.0",  # Middle-ground version
        "git+https://github.com/ace-step/ACE-Step.git@6ae0852b1388de6dc0cca26b31a86d711f723cb3",
    )
)

# In addition to source code, we'll also need the model weights.

# ACE-Step integrates with the Hugging Face ecosystem, so setting up the models
# is straightforward. `ACEStepPipeline` internally uses the Hugging Face model hub
# to download the weights if not already present.


def load_model(and_return=False):
    from acestep.pipeline_ace_step import ACEStepPipeline

    model = ACEStepPipeline(dtype="bfloat16", cpu_offload=False, overlapped_decode=True)
    if and_return:
        return model


# But Modal Functions are serverless: instances spin down when they aren't being used.
# If we want to avoid downloading the weights every time we start a new instance,
# we need to store the weights somewhere besides our local filesystem.

# So we add a Modal [Volume](https://modal.com/docs/guide/volumes)
# to store the weights in the cloud. For more on storing model weights on Modal, see
# [this guide](https://modal.com/docs/guide/model-weights).

cache_dir = "/root/.cache/ace-step/checkpoints"
model_cache = modal.Volume.from_name("ACE-Step-model-cache", create_if_missing=True)

# We don't need to change any of the model loading code --
# we just need to make sure the model gets stored in the right directory.

# To do that, we set an environment variable that Hugging Face expects
# (and another one that speeds up downloads, for good measure)
# and then run the `load_model` Python function.

image = image.env(
    {"HF_HUB_CACHE": cache_dir, "HF_HUB_ENABLE_HF_TRANSER": "1"}
)
# Model will download on first request (ok for image build simplicity).run_function(load_model, volumes={cache_dir: model_cache})

# While we're at it, let's also define the environment for our UI.
# We'll stick with Python and so use FastAPI and Gradio.

web_image = (
    modal.Image.debian_slim(python_version="3.10")
    .uv_pip_install(
        "fastapi[standard]==0.115.4", 
        "gradio==4.44.1", 
        "pydantic==2.10.1"
    )
    .add_local_file(local_path="sw.js", remote_path="/root/sw.js")
    .add_local_file(local_path="pwa_manifest.json", remote_path="/root/pwa_manifest.json")
)

# This is a totally different environment from the one we run our model in.
# Say goodbye to Python dependency conflict hell!

# ## Running music generation on Modal

# Now, we write our music generation logic.

# - We make an [App](https://modal.com/docs/guide/apps) to organize our deployment.
# - We load the model at start, instead of during inference, with `modal.enter`,
# which requires that we use a Modal [`Cls`](https://modal.com/docs/guide/lifecycle-functions).
# - In the `app.cls` decorator, we specify the Image we built and attach the Volume.
# We also pick a GPU to run on -- here, an NVIDIA L40S.

app = modal.App("example-generate-music")


@app.cls(gpu="l40s", image=image, volumes={cache_dir: model_cache})
class MusicGenerator:
    def __init__(self):
        self.model = None
    
    @modal.enter()
    def init(self):
        """Lazy load model on first use to avoid import issues during init"""
        pass

    @modal.method()
    def run(
        self,
        prompt: str,
        lyrics: str,
        duration: float = 60.0,
        format: str = "wav",  # or mp3
        manual_seeds: Optional[int] = 1,
    ) -> bytes:
        import uuid
        
        # Load model on first request
        if self.model is None:
            from acestep.pipeline_ace_step import ACEStepPipeline
            self.model = ACEStepPipeline(dtype="bfloat16", cpu_offload=False, overlapped_decode=True)

        output_path = f"/dev/shm/output_{uuid.uuid4().hex}.{format}"
        print("Generating music...")
        self.model(
            audio_duration=duration,
            prompt=prompt,
            lyrics=lyrics,
            format=format,
            save_path=output_path,
            manual_seeds=manual_seeds,
            # for samples, see https://github.com/ace-step/ACE-Step/tree/6ae0852b1388de6dc0cca26b31a86d711f723cb3/examples/
            # note that the parameters below are fixed in all of the samples in the default folder
            infer_step=60,
            guidance_scale=15,
            scheduler_type="euler",
            cfg_type="apg",
            omega_scale=10,
            guidance_interval=0.5,
            guidance_interval_decay=0,
            min_guidance_scale=3,
            use_erg_tag=True,
            use_erg_lyric=True,
            use_erg_diffusion=True,
        )
        return Path(output_path).read_bytes()


# We can then generate music from anywhere by running code like what we have in the `local_entrypoint` below.


@app.local_entrypoint()
def main(
    prompt: Optional[str] = None,
    lyrics: Optional[str] = None,
    duration: Optional[float] = None,
    format: str = "wav",  # or mp3
    manual_seeds: Optional[int] = 1,
):
    if lyrics is None:
        lyrics = "[inst]"
    if prompt is None:
        prompt = "Korean pop music, bright energetic electronic music, catchy melody, female vocals"
        lyrics = """[intro][intro]
            [chorus]
            We're goin' up, up, up, it's our moment
            You know together we're glowing
            Gonna be, gonna be golden
            Oh, up, up, up with our voices
            영원히 깨질 수 없는
            Gonna be, gonna be golden"""
    if duration is None:
        duration = 30.0  # seconds
    print(
        f"🎼 generating {duration} seconds of music from prompt '{prompt[:32] + ('...' if len(prompt) > 32 else '')}'"
        f" and lyrics '{lyrics[:32] + ('...' if len(lyrics) > 32 else '')}'"
    )

    music_generator = MusicGenerator()  # outside of this file, use modal.Cls.from_name
    clip = music_generator.run.remote(
        prompt, lyrics, duration=duration, format=format, manual_seeds=manual_seeds
    )

    dir = Path("/tmp/generate-music")
    dir.mkdir(exist_ok=True, parents=True)

    output_path = dir / f"{slugify(prompt)[:64]}.{format}"
    print(f"🎼 Saving to {output_path}")
    output_path.write_bytes(clip)


def slugify(string):
    return (
        string.lower()
        .replace(" ", "-")
        .replace("/", "-")
        .replace("\\", "-")
        .replace(":", "-")
    )


# You can execute it with a command like:

# ``` shell
# modal run generate_music.py
# ```

# Pass in `--help` to see options and how to use them.

# ## Hosting a web UI for the music generator

# With the Gradio library, we can create a simple web UI in Python
# that calls out to our music generator,
# then host it on Modal for anyone to try out.

# To deploy both the music generator and the UI, run

# ``` shell
# modal deploy generate_music.py
# ```


@app.function(
    image=web_image,
    # Gradio requires sticky sessions
    # so we limit the number of concurrent containers to 1
    # and allow it to scale to 1000 concurrent inputs
    max_containers=1,
)
@modal.concurrent(max_inputs=100)
@modal.asgi_app()
def ui():
    import gradio as gr
    from fastapi import FastAPI
    from gradio.routes import mount_gradio_app

    api = FastAPI()

    # Since this Gradio app is running from its own container,
    # we make a `.remote` call to the music generator
    music_generator = MusicGenerator()
    generate = music_generator.run.remote

    temp_dir = Path("/dev/shm")

    async def generate_music(
        prompt: str, lyrics: str, duration: float = 30.0, format: str = "wav"
    ):
        audio_bytes = await generate.aio(
            prompt, lyrics, duration=duration, format=format
        )

        audio_path = temp_dir / f"{uuid4()}.{format}"
        audio_path.write_bytes(audio_bytes)

        return audio_path

    with gr.Blocks(theme="soft") as demo:
        gr.Markdown("# Generate Music")
        with gr.Row():
            with gr.Column():
                prompt = gr.Textbox(label="Prompt")
                lyrics = gr.Textbox(label="Lyrics")
                duration = gr.Number(
                    label="Duration (seconds)", value=10.0, minimum=1.0, maximum=300.0
                )
                format = gr.Radio(["wav", "mp3"], label="Format", value="wav")
                btn = gr.Button("Generate")
            with gr.Column():
                clip_output = gr.Audio(label="Generated Music", autoplay=True)

        btn.click(
            generate_music,
            inputs=[prompt, lyrics, duration, format],
            outputs=[clip_output],
        )

    return mount_gradio_app(app=api, blocks=demo, path="/")


# Custom PWA Web UI with FastAPI
@app.function(image=web_image, timeout=1800)
@modal.asgi_app()
def web_ui():
    """Custom PWA UI with download support"""
    from fastapi import FastAPI, Response
    from fastapi.responses import StreamingResponse, HTMLResponse, JSONResponse, FileResponse
    from pydantic import BaseModel
    
    fastapi_app = FastAPI(title="Prompt 2 Jam")
    
    # Follow Modal's pattern
    music_generator = MusicGenerator()
    generate = music_generator.run.remote
    
    class GenerateRequest(BaseModel):
        prompt: str
        duration: float = 10.0
    
    @fastapi_app.get("/", response_class=HTMLResponse)
    async def root():
        return """<!DOCTYPE html>
<html>
<head>
    <title>Prompt 2 Jam</title>
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <link rel="manifest" href="/pwa_manifest.json">
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
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
            max-width: 600px;
            width: 100%;
            padding: 40px;
        }
        h1 { color: #333; margin-bottom: 10px; text-align: center; }
        .subtitle { color: #666; text-align: center; margin-bottom: 30px; font-size: 14px; }
        form { display: flex; flex-direction: column; gap: 20px; }
        label { font-weight: 600; color: #333; margin-bottom: 8px; display: block; }
        input[type="text"], input[type="range"] {
            padding: 12px;
            border: 2px solid #ddd;
            border-radius: 10px;
            font-size: 16px;
        }
        input[type="text"]:focus { outline: none; border-color: #667eea; }
        .duration-control { display: flex; gap: 20px; align-items: center; }
        input[type="range"] { flex: 1; padding: 0; height: 6px; }
        .duration-display { min-width: 40px; text-align: right; font-weight: 600; color: #667eea; }
        button {
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
        button:disabled { opacity: 0.6; cursor: not-allowed; }
        #status {
            padding: 15px;
            border-radius: 10px;
            text-align: center;
            display: none;
            font-size: 14px;
        }
        #status.info { background: #e3f2fd; color: #1976d2; }
        #status.success { background: #e8f5e9; color: #388e3c; }
        #status.error { background: #ffebee; color: #d32f2f; }
        audio { width: 100%; margin-top: 20px; border-radius: 10px; }
        .examples { margin-top: 30px; padding-top: 30px; border-top: 2px solid #eee; }
        .examples h3 { color: #333; margin-bottom: 15px; font-size: 14px; }
        .example-btn {
            background: #f5f5f5 !important;
            color: #667eea !important;
            border: 2px solid #ddd !important;
            padding: 10px 15px !important;
            margin-right: 10px;
            margin-bottom: 10px;
            font-size: 13px !important;
        }
        .example-btn:hover { background: #efefef !important; transform: none !important; }
    </style>
</head>
<body>
    <div class="container">
        <h1>🎵 Prompt 2 Jam</h1>
        <p class="subtitle">AI Music Generation</p>
        
        <form id="form">
            <div>
                <label for="prompt">🎼 Describe your music:</label>
                <input type="text" id="prompt" placeholder="e.g., upbeat electronic dance music" required>
            </div>
            
            <div>
                <label>⏱️ Duration (seconds)</label>
                <div class="duration-control">
                    <input type="range" id="duration" min="5" max="30" value="10">
                    <span class="duration-display"><span id="durationValue">10</span>s</span>
                </div>
            </div>
            
            <button type="submit" id="generateBtn">Generate Music 🎵</button>
        </form>
        
        <div id="status"></div>
        <audio id="audio" controls></audio>
        
        <div class="examples">
            <h3>💡 Quick Examples:</h3>
            <button class="example-btn" data-prompt="calm acoustic guitar melody">Acoustic</button>
            <button class="example-btn" data-prompt="energetic rock music">Rock</button>
            <button class="example-btn" data-prompt="relaxing piano jazz">Jazz</button>
        </div>
    </div>

    <script>
        const form = document.getElementById('form');
        const promptInput = document.getElementById('prompt');
        const durationInput = document.getElementById('duration');
        const durationValue = document.getElementById('durationValue');
        const generateBtn = document.getElementById('generateBtn');
        const status = document.getElementById('status');
        const audioPlayer = document.getElementById('audio');
        
        durationInput.addEventListener('input', e => {
            durationValue.textContent = e.target.value;
        });
        
        form.addEventListener('submit', async e => {
            e.preventDefault();
            await generateMusic();
        });
        
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
            showStatus('🎼 Generating music... (first time takes ~60s)', 'info');
            
            try {
                const response = await fetch('/api/generate', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ prompt, duration })
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
        
        if ('serviceWorker' in navigator) {
            window.addEventListener('load', () => {
                navigator.serviceWorker.register('/sw.js').catch(() => {});
            });
        }
    </script>
</body>
</html>"""

    @fastapi_app.get("/sw.js")
    async def service_worker():
        return FileResponse("/root/sw.js", media_type="application/javascript")

    @fastapi_app.get("/pwa_manifest.json")
    async def pwa_manifest():
        return FileResponse("/root/pwa_manifest.json", media_type="application/manifest+json")

    @fastapi_app.get("/favicon.ico")
    async def favicon():
        return Response(status_code=204)
    
    @fastapi_app.post("/api/generate")
    async def generate_music_api(request: GenerateRequest):
        try:
            if not request.prompt or not request.prompt.strip():
                return JSONResponse({"error": "Prompt cannot be empty"}, status_code=400)
            if request.duration < 5 or request.duration > 30:
                return JSONResponse({"error": "Duration must be 5-30 seconds"}, status_code=400)
            
            print(f"🎵 Generating: {request.prompt} ({request.duration}s)")
            
            # Use Modal's .aio() pattern
            audio_bytes = await generate.aio(
                prompt=request.prompt,
                lyrics="[inst]",
                duration=request.duration,
                format="wav",
            )
            
            print(f"✅ Generated {len(audio_bytes)} bytes")
            
            return StreamingResponse(
                iter([audio_bytes]),
                media_type="audio/wav",
                headers={"Content-Disposition": "attachment; filename=music.wav"}
            )
        except Exception as e:
            import traceback
            print(f"❌ Error: {traceback.format_exc()}")
            return JSONResponse({"error": str(e)}, status_code=500)
    
    return fastapi_app
