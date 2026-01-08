#!/bin/bash
# Script to run the music generation app in development mode

echo "🎵 Starting Modal music generation app..."
echo ""

# Run in development mode with live reload
modal serve 06_gpu_and_ml/text-to-audio/generate_music.py

echo ""
echo "✅ App is running! Check the output above for the URL."
echo "The URL will look like: https://your-workspace--example-generate-music-ui-dev.modal.run"
