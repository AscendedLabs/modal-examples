# 🚀 V0.1.0 Quick Start — Local Development Guide

**Get the AI Song Generator running locally in 5 minutes.**

---

## ✅ Prerequisites

- **Node.js 18+** → `node --version`
- **Python 3.9+** → `python --version`
- **Git** → already in repo

---

## 📥 Installation (One-time)

### 1️⃣ Install Frontend Dependencies

```bash
cd /workspaces/modal-examples/frontend
npm install
```

**Expected output:**
```
added 123 packages in 24s
```

### 2️⃣ Setup Backend

```bash
cd /workspaces/modal-examples/backend

# Create virtual environment
python -m venv venv

# Activate it
source venv/bin/activate  # Linux/Mac
# or
venv\Scripts\activate  # Windows

# Install dependencies
pip install -r requirements.txt
```

**Expected output:**
```
Successfully installed fastapi uvicorn librosa torch ...
```

---

## 🎮 Running Locally

### Terminal 1: Backend API

```bash
cd /workspaces/modal-examples/backend
source venv/bin/activate
python -m uvicorn app.main:app --reload --port 8000
```

**Expected output:**
```
INFO:     Uvicorn running on http://127.0.0.1:8000
INFO:     Application startup complete
```

✅ **Backend is live at:** http://localhost:8000

---

### Terminal 2: Frontend Dev Server

```bash
cd /workspaces/modal-examples/frontend
npm run dev
```

**Expected output:**
```
  VITE v5.0.0  ready in 234 ms

  ➜  Local:   http://localhost:3000/
  ➜  press h to show help
```

✅ **Frontend is live at:** http://localhost:3000

---

## 🎵 Test the App

### Step 1: Open Generator Page
```
http://localhost:3000
```

You should see:
- Purple/dark theme
- "🎵 AI Song Generator" header
- Text input for song description
- Dropdowns for genre, BPM, key, duration

### Step 2: Generate a Song

1. Enter prompt: `"Chill lofi beat with jazzy chords"`
2. Select genre: `lofi`
3. Set BPM: `90`
4. Set duration: `30`
5. Click `✨ Generate Song`

### Step 3: Watch Job Status

You should see:
- Progress bar starting at 0%
- Status: "Processing..."
- After ~5 seconds: "Complete!"
- Generated stems display (Vocals, Bass, Drums, Melody, Other)

### Step 4: Try DAW

Click `🎛️ Open in DAW Studio` button

You should see:
- Left panel: Mixer with 5 tracks
- Right panel: Timeline with regions
- Transport controls (play/stop/pause)
- Volume/pan sliders

---

## 🧪 API Testing (Optional)

Test the API directly with curl:

```bash
# Generate
curl -X POST http://localhost:8000/api/generate \
  -H "Content-Type: application/json" \
  -d '{
    "prompt": "upbeat pop song",
    "genre": "pop",
    "bpm": 120,
    "duration": 30
  }'

# Response:
# {"job_id": "abc-123-def", "status": "queued"}

# Check status
curl http://localhost:8000/api/jobs/abc-123-def
```

---

## 🐛 Common Issues & Fixes

### ❌ `npm: command not found`
**Fix:** Install Node.js from https://nodejs.org

### ❌ `ModuleNotFoundError: No module named 'fastapi'`
**Fix:** Make sure venv is activated:
```bash
source venv/bin/activate
pip install -r requirements.txt
```

### ❌ `CORS error` in browser console
**Fix:** Make sure frontend proxy is correct in `vite.config.ts`:
```typescript
proxy: {
  '/api': {
    target: 'http://localhost:8000',  // ← Check this
    changeOrigin: true,
  }
}
```

### ❌ `Connection refused` when accessing http://localhost:3000
**Fix:** Make sure frontend dev server is running:
```bash
# Terminal 2
npm run dev
```

### ❌ Backend won't start
**Fix:** Kill any existing process on port 8000:
```bash
# Find process
lsof -i :8000

# Kill it
kill -9 <PID>

# Try again
python -m uvicorn app.main:app --reload --port 8000
```

---

## 📁 Project Structure Quick Reference

```
modal-examples/
├── frontend/              ← React/TypeScript
│   ├── src/
│   │   ├── pages/        ← Generator.tsx, DAW.tsx
│   │   ├── App.tsx       ← Router
│   │   └── index.tsx     ← Entry
│   ├── vite.config.ts    ← Build config (has API proxy)
│   └── package.json      ← Dependencies
│
├── backend/              ← Python/FastAPI
│   ├── app/
│   │   └── main.py       ← All API routes
│   └── requirements.txt  ← Dependencies
│
├── src/
│   ├── frontend/         ← Actual source files
│   └── backend/          ← Actual source files
│
└── public/
    └── index.html        ← HTML entry
```

---

## 🔄 Typical Workflow

```
┌─────────────────────────────────────────┐
│ 1. Both servers running                 │
│    Terminal 1: uvicorn                  │
│    Terminal 2: npm run dev              │
│                                         │
│ 2. Make frontend changes                │
│    → Vite auto-refreshes browser        │
│                                         │
│ 3. Make backend changes                 │
│    → Uvicorn auto-reloads app           │
│                                         │
│ 4. Test in browser                      │
│    http://localhost:3000                │
│                                         │
│ 5. Check Console / Terminal logs        │
│    → Errors appear immediately          │
│                                         │
│ 6. Commit when working                  │
│    git add . && git commit -m "..."     │
└─────────────────────────────────────────┘
```

---

## 📊 Development Commands

### Frontend

```bash
# Start dev server
npm run dev

# Build for production
npm run build

# Preview production build
npm run preview
```

### Backend

```bash
# Start API server
python -m uvicorn app.main:app --reload

# Run tests (when you add them)
pytest

# Format code
black src/backend/

# Check types
mypy src/backend/
```

---

## 🎯 Next: What to Build

Once local setup is working, next priority:

1. **Replace placeholder music generation** with real AI model
   - File: `src/backend/main.py` (search for `# Simulate music generation`)
   - Use: MusicLM / AudioCraft / Replicate

2. **Add real stem separation**
   - Use: Demucs / OpenUnmix

3. **Wire up audio playback in DAW**
   - File: `src/frontend/pages/DAW.tsx`
   - Use: Web Audio API + Tone.js

See [V0.1.0_PHASE1_COMPLETION.md](./V0.1.0_PHASE1_COMPLETION.md) for detailed next steps.

---

## 📖 Documentation Index

- **Setup & Architecture:** [V0.1.0_PROJECT_README.md](./V0.1.0_PROJECT_README.md)
- **Full Roadmap:** [V0.1.0_IMPLEMENTATION_ROADMAP.md](./V0.1.0_IMPLEMENTATION_ROADMAP.md)
- **Completion & Next Steps:** [V0.1.0_PHASE1_COMPLETION.md](./V0.1.0_PHASE1_COMPLETION.md)
- **Open Source Tools & Research:** [DAW OPEN-SOURCE-TOOLS.md](./DAW%20OPEN-SOURCE-TOOLS..md)

---

## 💡 Tips

- **Restart servers rarely** — Vite and Uvicorn auto-reload
- **Keep console open** — Errors show up immediately
- **Use DevTools** — Chrome F12 for frontend debugging
- **Test API first** — Curl before adding UI
- **Commit frequently** — Small, meaningful commits

---

## 🎉 You're Ready!

```bash
# Start both servers and open http://localhost:3000

Terminal 1:
cd backend && source venv/bin/activate && python -m uvicorn app.main:app --reload

Terminal 2:
cd frontend && npm run dev

Browser:
http://localhost:3000
```

**Happy coding! 🚀**

---

**Last Updated:** January 12, 2026  
**Branch:** Music-App-v0.1.0
