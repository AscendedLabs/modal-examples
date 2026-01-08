"""Simple test to verify Modal is working"""
import modal

app = modal.App("test-modal-setup")

@app.function()
def hello():
    print("✅ Modal is working!")
    return "Success!"

@app.local_entrypoint()
def main():
    result = hello.remote()
    print(f"Result: {result}")
