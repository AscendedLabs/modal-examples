"""
Music Generation App - Prompt 2 Jam
A simple text-to-music generator using Facebook's MusicGen model
"""

import modal
from pathlib import Path

# Create the Modal app
app = modal.App("music-app-demo")

# Define the container image with required dependencies
# Using Modal's micromamba image for faster builds with conda packages
image = (
    modal.Image.micromamba(python_version="3.11")
    .apt_install("ffmpeg")
    .micromamba_install(
        "pytorch",
        "torchaudio",
        channels=["pytorch", "nvidia", "conda-forge"],
    )
    .pip_install(
        "transformers",
        "accelerate",
        "scipy",
        "gradio",
    )
)

# Set up model caching to avoid re-downloading on every cold start
MODEL_DIR = "/cache/musicgen"
model_cache = modal.Volume.from_name("musicgen-cache", create_if_missing=True)


@app.cls(
    image=image,
    gpu="t4",  # Using T4 GPU for cost-effectiveness
    volumes={MODEL_DIR: model_cache},
    timeout=600,
)
class MusicGen:
    @modal.enter()
    def load_model(self):
        """Load the MusicGen model on container startup"""
        from transformers import MusicgenForConditionalGeneration, AutoProcessor
        import torch
        
        print("🎵 Loading MusicGen model...")
        
        # Load the model and processor
        self.processor = AutoProcessor.from_pretrained(
            "facebook/musicgen-small",
            cache_dir=MODEL_DIR
        )
        self.model = MusicgenForConditionalGeneration.from_pretrained(
            "facebook/musicgen-small",
            cache_dir=MODEL_DIR,
            torch_dtype=torch.float16,
        )
        
        # Move model to GPU
        self.model = self.model.to("cuda")
        
        print("✅ Model loaded successfully!")

    @modal.method()
    def generate(self, prompt: str, duration: int = 10) -> bytes:
        """Generate music from a text prompt"""
        import scipy.io.wavfile as wavfile
        import torch
        import io
        
        print(f"🎼 Generating music for: '{prompt}'")
        
        # Process the prompt
        inputs = self.processor(
            text=[prompt],
            padding=True,
            return_tensors="pt",
        ).to("cuda")
        
        # Calculate max_new_tokens based on duration (50 tokens per second)
        max_new_tokens = duration * 50
        
        # Generate audio
        with torch.no_grad():
            audio_values = self.model.generate(
                **inputs,
                max_new_tokens=max_new_tokens,
                do_sample=True,
                guidance_scale=3.0,
            )
        
        # Convert to numpy and create WAV file in memory
        sampling_rate = self.model.config.audio_encoder.sampling_rate
        audio_data = audio_values[0, 0].cpu().numpy()
        
        # Create WAV file in memory
        buffer = io.BytesIO()
        wavfile.write(buffer, rate=sampling_rate, data=audio_data)
        buffer.seek(0)
        
        print("✅ Music generated successfully!")
        return buffer.read()


# Web UI using Gradio
@app.function(
    image=image,
    max_containers=100,
)
@modal.asgi_app()
def web_ui():
    """Gradio web interface for music generation"""
    import gradio as gr
    from fastapi import FastAPI
    from gradio.routes import mount_gradio_app
    import io
    from uuid import uuid4
    
    api = FastAPI()
    
    # Get reference to the MusicGen class
    music_gen = MusicGen()
    
    def generate_music_ui(prompt: str, duration: int):
        """Generate music from the UI"""
        if not prompt.strip():
            return None
        
        # Call the remote generation method
        audio_bytes = music_gen.generate.remote(prompt, duration)
        
        # Save to temporary file for Gradio
        temp_path = f"/tmp/music_{uuid4()}.wav"
        with open(temp_path, "wb") as f:
            f.write(audio_bytes)
        
        return temp_path
    
    # Create Gradio interface
    with gr.Blocks(theme="soft", title="Prompt 2 Jam") as demo:
        gr.Markdown(
            """
            # 🎵 Prompt 2 Jam - Music Generator
            ### Your AI BandMate in your pocket!
            
            Generate original music from text descriptions. Describe the style, mood, instruments, and let AI create your track!
            """
        )
        
        with gr.Row():
            with gr.Column():
                prompt_input = gr.Textbox(
                    label="Music Prompt",
                    placeholder="e.g., upbeat electronic dance music with synthesizers and drums",
                    lines=3,
                    value="upbeat electronic dance music with synthesizers"
                )
                duration_slider = gr.Slider(
                    minimum=5,
                    maximum=300,
                    value=30,
                    step=5,
                    label="Duration (seconds) - Up to 5 minutes",
                )
                generate_btn = gr.Button("🎵 Generate Music", variant="primary", size="lg")
                
                gr.Markdown(
                    """
                    ### 💡 Example Prompts:
                    - "upbeat electronic dance music with synthesizers"
                    - "calm acoustic guitar melody"
                    - "energetic rock music with electric guitar"
                    - "relaxing piano jazz"
                    - "epic orchestral soundtrack"
                    """
                )
            
            with gr.Column():
                audio_output = gr.Audio(
                    label="Generated Music",
                    type="filepath",
                    autoplay=True
                )
        
        # Connect the button to the generation function
        generate_btn.click(
            fn=generate_music_ui,
            inputs=[prompt_input, duration_slider],
            outputs=audio_output,
        )
        
        # Add examples
        gr.Examples(
            examples=[
                ["upbeat electronic dance music with synthesizers", 30],
                ["calm acoustic guitar melody", 30],
                ["energetic rock music with electric guitar", 30],
                ["relaxing piano jazz", 30],
                ["epic orchestral soundtrack with drums", 60],
            ],
            inputs=[prompt_input, duration_slider],
        )
    
    return mount_gradio_app(app=api, blocks=demo, path="/")


# Command-line entrypoint
@app.local_entrypoint()
def main(prompt: str = "upbeat electronic dance music", duration: int = 10):
    """Generate music from command line"""
    print(f"🎵 Generating {duration}s of music from prompt: '{prompt}'")
    
    music_gen = MusicGen()
    audio_bytes = music_gen.generate.remote(prompt, duration)
    
    # Save to local file
    output_dir = Path("/tmp/music_output")
    output_dir.mkdir(exist_ok=True, parents=True)
    
    output_path = output_dir / f"music_{prompt[:30].replace(' ', '_')}.wav"
    output_path.write_bytes(audio_bytes)
    
    print(f"✅ Music saved to: {output_path}")
