import modal

# Import the FastAPI app we've already built
from src.backend.main import app as fastapi_app_main

# Define Modal stub and minimal image for ASGI app
stub = modal.Stub("ai-song-generator-fastapi")
image = modal.Image.debian_slim().pip_install(
    "fastapi",
    "pydantic",
    "modal-client",
    "requests",
)

@stub.asgi_app(image=image)
def fastapi_app():
    """Expose the FastAPI app via Modal's ASGI wrapper."""
    return fastapi_app_main
