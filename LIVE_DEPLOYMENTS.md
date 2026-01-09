# 🎵 Prompt2Jam Studio - Live Deployments

## ✅ Current Live Apps

### 🎉 ENHANCED v0.0.2 (NEW - RECOMMENDED)
**URL:** https://ascendedlabs--prompt-2-jam-v2-enhanced-web-ui.modal.run

**Features:**
- ✨ 18 Genre Presets (Pop, Rock, Jazz, Electronic, Hip-Hop, Country, Blues, R&B, Metal, Folk, Reggae, Latin, Dance, Ambient, Indie, Soul, Funk)
- 😊 Mood Controls (Happy, Sad, Energetic, Calm, Dramatic, Romantic, Epic)
- 🎚️ Tempo/BPM Slider (60-200 BPM)
- ⏱️ Duration Control (10-240 seconds)
- 🎤 Lyrics Editor with Structure Tags ([verse], [chorus], [bridge], [intro], [outro])
- 🎹 Vocal/Instrumental Toggle
- ⚙️ Advanced Settings (Collapsible):
  - Quality Control (Inference Steps: 27-100)
  - Prompt Strength (Guidance Scale: 7-25)
  - Seed for Reproducibility
- 🎨 Modern Gradient UI Design
- 🎧 Professional Audio Player
- 📊 Real-time Status Updates

**Status:** ✅ LIVE & TESTED
**Deploy Time:** ~20 seconds
**Response Time:** ~30-60 seconds per generation

---

### 📦 ORIGINAL v0.0.1 (REFERENCE/BACKUP)
**URL:** https://ascendedlabs--prompt-2-jam-web-ui.modal.run

**Features:**
- Simple Text-to-Music Generation
- Basic Prompt Input
- Duration Control (10-30 seconds)
- Direct Audio Download
- Minimal UI (Quick MVP)

**Status:** ✅ Still Working (Reference Implementation)
**File:** `music_app_modal_official_v0.0.1_backup.py`

---

## 📁 File Structure

```
Music-App-v0.0.2 Branch
├── music_app_enhanced_v2.py                    ← ACTIVE (v0.0.2)
├── music_app_modal_official_v0.0.1_backup.py   ← BACKUP/REFERENCE
├── ACE_STUDIO_CLONE_ROADMAP.md                 ← Development Plan
├── DEPLOYMENT_SUCCESS.md                       ← Architecture Docs
├── PRODUCTION_STATUS.md                        ← Status Tracking
├── sw.js                                       ← Service Worker
└── pwa_manifest.json                           ← PWA Config
```

---

## 🚀 Quick Start

### Using v0.0.2 (Enhanced)
1. Open: https://ascendedlabs--prompt-2-jam-v2-enhanced-web-ui.modal.run
2. Describe your music (or pick genre + mood)
3. Set tempo, duration, vocal type
4. Click "Generate Music"
5. Wait 30-60 seconds
6. Play and download WAV file

### Using v0.0.1 (Simple)
1. Open: https://ascendedlabs--prompt-2-jam-web-ui.modal.run
2. Enter text prompt
3. Click "Generate"
4. Download audio

---

## 🎯 Deployment Details

### Infrastructure
- **Platform:** Modal.com (Serverless)
- **GPU:** NVIDIA L40S (40GB VRAM)
- **Model:** ACE-Step v0.2.0
- **Audio Format:** WAV, 48kHz, Stereo

### Performance
- **Cold Start:** ~20 seconds (deployment)
- **Warm Start:** ~5 seconds (existing container)
- **Generation Time:** ~1-2 seconds per 10 seconds of audio
- **Concurrent Users:** 100+ (with auto-scaling)

### Python Stack
- **Python:** 3.10
- **Framework:** FastAPI 0.115.4
- **UI:** HTML5 + Vanilla JavaScript
- **Audio Engine:** Web Audio API + HTML5 Audio

### Dependencies
```
torch==2.8.0
torchaudio==2.8.0
transformers==4.50.0        (ACE-Step requirement)
diffusers==0.33.0           (Music generation)
peft==0.14.0                (Key to dependency resolution)
ACE-Step (GitHub commit)
```

---

## 🔄 How to Update

### Update v0.0.2 (Enhanced)
```bash
# Make changes to music_app_enhanced_v2.py
modal deploy --name prompt-2-jam-v2-enhanced music_app_enhanced_v2.py
```

### Deploy v0.0.1 (Backup)
```bash
# Use original v0.0.1
modal deploy --name prompt-2-jam music_app_modal_official_v0.0.1_backup.py
```

---

## 📊 Testing Checklist

- [x] v0.0.2 Deploys Successfully
- [x] Web UI Loads (HTTP 200)
- [x] Genre Presets Work
- [x] Mood Selector Works
- [x] Tempo Slider Works
- [x] Duration Control Works
- [x] Audio Generation Works
- [x] Download Works
- [ ] Waveform Visualization (TODO)
- [ ] Multi-format Export (TODO)
- [ ] Generation History (TODO)

---

## 🎵 Next Phase (v0.0.3)

**Timeline:** Week 3-4

**Features to Add:**
1. Waveform visualization (WaveSurfer.js)
2. Download in multiple formats (MP3, FLAC)
3. Generation history (localStorage)
4. Variations generation (different seed)
5. Extend track (add to beginning/end)
6. Share & copy links
7. Effects preview (EQ, reverb settings)

---

## 🛠️ Troubleshooting

### v0.0.2 Not Loading
- Clear browser cache (Cmd+Shift+Delete)
- Check internet connection
- Try incognito mode
- Verify URL: https://ascendedlabs--prompt-2-jam-v2-enhanced-web-ui.modal.run

### Generation Timeout
- Try shorter duration (30s instead of 240s)
- Lower quality (fewer steps: 27 vs 60)
- Check Modal dashboard for errors

### Audio Quality Issues
- Increase inference steps (60 vs 27)
- Increase guidance scale (15 vs 7)
- Try different seed
- Check prompt clarity

---

## 📈 Roadmap Preview

| Phase | Version | Status | Timeline |
|-------|---------|--------|----------|
| Enhanced UI | v0.0.2 | ✅ LIVE | Week 1-2 |
| Advanced Controls | v0.0.3 | 📝 Planned | Week 3-4 |
| Multi-Track DAW | v0.0.4 | 📋 Planned | Month 2 |
| Vocal Editor | v0.0.5 | 📋 Planned | Month 2 |
| Effects & Mixing | v0.0.6 | 📋 Planned | Month 2 |
| Piano Roll MIDI | v0.0.7 | 📋 Planned | Month 3 |
| AI Assistant | v0.0.8 | 📋 Planned | Month 3 |
| Collaboration | v0.1.0 | 📋 Planned | Month 4 |
| Production Ready | v1.0.0 | 🚀 Goal | Month 4 |

---

## 📞 Support

### GitHub Repository
- **Branch:** Music-App-v0.0.2
- **URL:** https://github.com/AscendedLabs/modal-examples
- **Docs:** See ACE_STUDIO_CLONE_ROADMAP.md

### Monitoring
- **Modal Dashboard:** https://modal.com/apps/ascendedlabs/main/deployed/
- **Logs:** `modal app logs prompt-2-jam-v2-enhanced`

### Issues?
Check the following:
1. ACE_STUDIO_CLONE_ROADMAP.md (development plan)
2. DEPLOYMENT_SUCCESS.md (architecture docs)
3. Modal dashboard for error logs

---

**🎵 Building the future of AI music production!** 🚀
