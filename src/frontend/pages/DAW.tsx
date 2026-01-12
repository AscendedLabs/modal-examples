/**
 * DAW.tsx - Page 2: DAW Studio
 * 
 * Multi-track editor with:
 * - Timeline / Arrangement
 * - Mixer (faders, pan, mute/solo)
 * - Transport (play, stop, tempo)
 * - AI Enhancement Tools
 */

import React, { useState, useEffect, useRef } from "react";
import axios from "axios";
import * as Tone from "tone";

interface Track {
  id: string;
  name: string;
  stems: AudioRegion[];
  volume: number;
  pan: number;
  mute: boolean;
  solo: boolean;
  color: string;
}

interface AudioRegion {
  id: string;
  stemType: string;
  url: string;
  startTime: number;
  duration: number;
  offset: number;
}

interface TransportState {
  isPlaying: boolean;
  bpm: number;
  timeSignature: string;
  currentTime: number;
}

const DAW: React.FC = () => {
  // STATE
  const [tracks, setTracks] = useState<Track[]>([]);
  const [transport, setTransport] = useState<TransportState>({
    isPlaying: false,
    bpm: 120,
    timeSignature: "4/4",
    currentTime: 0,
  });
  const [selectedTrackId, setSelectedTrackId] = useState<string | null>(null);
  const [jobId, setJobId] = useState<string | null>(null);

  // REFS
  const synth = useRef<Tone.Synth | null>(null);
  const now = useRef<number>(Tone.now());

  const API_BASE = process.env.REACT_APP_API_BASE || "http://localhost:8000";

  // Initialize Tone.js on mount
  useEffect(() => {
    synth.current = new Tone.Synth({
      oscillator: { type: "triangle" },
      envelope: { attack: 0.005, decay: 0.1, sustain: 0.3, release: 1 },
    }).toDestination();

    return () => {
      synth.current?.dispose();
    };
  }, []);

  // Load generated stems from job_id (from URL)
  useEffect(() => {
    const params = new URLSearchParams(window.location.search);
    const jobIdParam = params.get("job_id");

    if (jobIdParam) {
      setJobId(jobIdParam);
      loadStemsFromJob(jobIdParam);
    }
  }, []);

  const loadStemsFromJob = async (jobId: string) => {
    try {
      const response = await axios.get(`${API_BASE}/api/jobs/${jobId}`);
      const job = response.data;

      if (job.stems) {
        // Create tracks from stems
        const newTracks: Track[] = job.stems.map((stem: any, index: number) => ({
          id: `track-${index}`,
          name: stem.stem_type,
          stems: [
            {
              id: `region-${index}`,
              stemType: stem.stem_type,
              url: stem.url,
              startTime: 0,
              duration: stem.duration,
              offset: 0,
            },
          ],
          volume: -6,
          pan: 0,
          mute: false,
          solo: false,
          color: TRACK_COLORS[index % TRACK_COLORS.length],
        }));

        setTracks(newTracks);
        setTransport((prev) => ({
          ...prev,
          bpm: job.request.bpm,
        }));
      }
    } catch (err) {
      console.error("Error loading stems:", err);
    }
  };

  // Transport controls
  const togglePlayback = async () => {
    await Tone.start();

    if (transport.isPlaying) {
      Tone.Transport.stop();
    } else {
      Tone.Transport.bpm.value = transport.bpm;
      Tone.Transport.start();
    }

    setTransport((prev) => ({
      ...prev,
      isPlaying: !prev.isPlaying,
    }));
  };

  const stopTransport = () => {
    Tone.Transport.stop();
    Tone.Transport.position = 0;
    setTransport((prev) => ({
      ...prev,
      isPlaying: false,
      currentTime: 0,
    }));
  };

  const updateBPM = (newBpm: number) => {
    Tone.Transport.bpm.value = newBpm;
    setTransport((prev) => ({
      ...prev,
      bpm: newBpm,
    }));
  };

  // Track controls
  const updateTrackVolume = (trackId: string, volume: number) => {
    setTracks((prev) =>
      prev.map((t) => (t.id === trackId ? { ...t, volume } : t))
    );
  };

  const updateTrackPan = (trackId: string, pan: number) => {
    setTracks((prev) =>
      prev.map((t) => (t.id === trackId ? { ...t, pan } : t))
    );
  };

  const toggleTrackMute = (trackId: string) => {
    setTracks((prev) =>
      prev.map((t) => (t.id === trackId ? { ...t, mute: !t.mute } : t))
    );
  };

  const toggleTrackSolo = (trackId: string) => {
    const hasSolo = tracks.some((t) => t.solo);

    setTracks((prev) =>
      prev.map((t) => {
        if (t.id === trackId) {
          return { ...t, solo: !t.solo };
        }
        if (hasSolo) {
          return { ...t, solo: false };
        }
        return t;
      })
    );
  };

  return (
    <div className="min-h-screen bg-gradient-to-br from-gray-900 via-slate-900 to-black text-white font-mono">
      {/* HEADER + TRANSPORT */}
      <div className="border-b border-gray-700/50 bg-black/80 backdrop-blur p-4">
        <div className="max-w-full mx-auto">
          <div className="flex items-center justify-between mb-4">
            <div>
              <h1 className="text-2xl font-bold">🎛️ DAW Studio</h1>
              {jobId && <p className="text-xs text-gray-400 mt-1">Job: {jobId}</p>}
            </div>
            <button
              onClick={() => window.location.href = "/"}
              className="px-3 py-2 bg-gray-700 hover:bg-gray-600 rounded text-sm"
            >
              ← Back to Generator
            </button>
          </div>

          {/* TRANSPORT CONTROLS */}
          <div className="flex items-center gap-4 bg-gray-900/50 border border-gray-700/50 rounded-lg p-3">
            {/* PLAY/STOP */}
            <div className="flex gap-2">
              <button
                onClick={togglePlayback}
                className={`px-4 py-2 rounded font-semibold ${
                  transport.isPlaying
                    ? "bg-red-600 hover:bg-red-700"
                    : "bg-green-600 hover:bg-green-700"
                }`}
              >
                {transport.isPlaying ? "⏸ Pause" : "▶ Play"}
              </button>
              <button
                onClick={stopTransport}
                className="px-4 py-2 bg-gray-600 hover:bg-gray-700 rounded font-semibold"
              >
                ⏹ Stop
              </button>
            </div>

            {/* SEPARATOR */}
            <div className="w-px h-6 bg-gray-600" />

            {/* BPM CONTROL */}
            <div className="flex items-center gap-2">
              <label className="text-sm font-semibold">BPM:</label>
              <input
                type="number"
                min={40}
                max={200}
                value={transport.bpm}
                onChange={(e) => updateBPM(parseInt(e.target.value) || 120)}
                className="w-16 px-2 py-1 bg-gray-800 border border-gray-600 rounded text-sm"
              />
            </div>

            {/* TIME SIGNATURE */}
            <div className="flex items-center gap-2">
              <label className="text-sm font-semibold">Signature:</label>
              <select className="px-2 py-1 bg-gray-800 border border-gray-600 rounded text-sm">
                <option>4/4</option>
                <option>3/4</option>
                <option>6/8</option>
              </select>
            </div>

            {/* SPACER */}
            <div className="flex-1" />

            {/* CURRENT TIME */}
            <div className="text-sm font-semibold text-blue-400">
              {formatTime(transport.currentTime)}
            </div>
          </div>
        </div>
      </div>

      {/* MAIN LAYOUT: MIXER (left) + TIMELINE (right) */}
      <div className="flex h-[calc(100vh-120px)] overflow-hidden">
        {/* MIXER PANEL (LEFT) */}
        <div className="w-64 bg-gray-900/50 border-r border-gray-700/50 overflow-y-auto">
          <div className="p-3 space-y-2">
            <h2 className="text-sm font-bold text-purple-400 mb-4">MIXER</h2>

            {tracks.length === 0 ? (
              <div className="p-4 text-center text-gray-400">
                <p className="text-sm mb-2">No tracks loaded</p>
                <button
                  onClick={() => window.location.href = "/"}
                  className="px-3 py-1 bg-purple-600 hover:bg-purple-700 rounded text-xs"
                >
                  Generate Song
                </button>
              </div>
            ) : (
              tracks.map((track) => (
                <div
                  key={track.id}
                  onClick={() => setSelectedTrackId(track.id)}
                  className={`p-3 border rounded cursor-pointer transition-all ${
                    selectedTrackId === track.id
                      ? "bg-purple-900/50 border-purple-500"
                      : "bg-gray-800/50 border-gray-700/50 hover:border-gray-600"
                  }`}
                >
                  {/* TRACK NAME */}
                  <div className="flex items-center gap-2 mb-2">
                    <div
                      className="w-3 h-3 rounded-full"
                      style={{ backgroundColor: track.color }}
                    />
                    <p className="text-xs font-semibold truncate capitalize">{track.name}</p>
                  </div>

                  {/* MUTE / SOLO */}
                  <div className="flex gap-1 mb-2">
                    <button
                      onClick={(e) => {
                        e.stopPropagation();
                        toggleTrackMute(track.id);
                      }}
                      className={`flex-1 px-2 py-1 rounded text-xs font-semibold ${
                        track.mute
                          ? "bg-red-600/50 text-red-200"
                          : "bg-gray-700 text-gray-300"
                      }`}
                    >
                      M
                    </button>
                    <button
                      onClick={(e) => {
                        e.stopPropagation();
                        toggleTrackSolo(track.id);
                      }}
                      className={`flex-1 px-2 py-1 rounded text-xs font-semibold ${
                        track.solo
                          ? "bg-yellow-600/50 text-yellow-200"
                          : "bg-gray-700 text-gray-300"
                      }`}
                    >
                      S
                    </button>
                  </div>

                  {/* VOLUME */}
                  <div>
                    <input
                      type="range"
                      min={-60}
                      max={6}
                      value={track.volume}
                      onChange={(e) =>
                        updateTrackVolume(track.id, parseInt(e.target.value))
                      }
                      onClick={(e) => e.stopPropagation()}
                      className="w-full h-6 accent-purple-500"
                    />
                    <p className="text-xs text-gray-400 text-center">{track.volume}dB</p>
                  </div>

                  {/* PAN */}
                  <div className="mt-2">
                    <input
                      type="range"
                      min={-100}
                      max={100}
                      value={track.pan}
                      onChange={(e) => updateTrackPan(track.id, parseInt(e.target.value))}
                      onClick={(e) => e.stopPropagation()}
                      className="w-full h-4 accent-blue-500"
                    />
                  </div>
                </div>
              ))
            )}
          </div>
        </div>

        {/* TIMELINE / ARRANGEMENT (RIGHT) */}
        <div className="flex-1 bg-gray-950 overflow-auto relative">
          {tracks.length === 0 ? (
            <div className="flex items-center justify-center h-full">
              <p className="text-gray-400">Load or generate a song to begin editing</p>
            </div>
          ) : (
            <div className="min-w-full">
              {/* TIMELINE HEADER (measures) */}
              <div className="sticky top-0 h-8 bg-gray-900/80 border-b border-gray-700/50 flex items-center px-4 gap-8">
                {Array.from({ length: 16 }).map((_, i) => (
                  <div
                    key={i}
                    className="flex-1 text-xs font-semibold text-gray-500 border-l border-gray-700/30"
                  >
                    {i + 1}
                  </div>
                ))}
              </div>

              {/* TRACK LANES */}
              {tracks.map((track, idx) => (
                <div
                  key={track.id}
                  className={`h-20 border-b border-gray-700/50 flex items-center px-4 gap-8 bg-gray-950 hover:bg-gray-900/50 ${
                    selectedTrackId === track.id ? "bg-purple-900/20" : ""
                  }`}
                >
                  {track.stems.map((region) => (
                    <div
                      key={region.id}
                      className="flex-1 h-12 rounded-sm bg-gradient-to-b from-purple-600 to-purple-800 cursor-move hover:from-purple-500 hover:to-purple-700 flex items-center px-2"
                    >
                      <p className="text-xs font-semibold text-white truncate">
                        {region.stemType}
                      </p>
                    </div>
                  ))}
                </div>
              ))}
            </div>
          )}
        </div>
      </div>
    </div>
  );
};

const TRACK_COLORS = [
  "#ef4444", // red
  "#f97316", // orange
  "#eab308", // yellow
  "#22c55e", // green
  "#06b6d4", // cyan
  "#3b82f6", // blue
  "#8b5cf6", // purple
  "#ec4899", // pink
];

function formatTime(seconds: number): string {
  const mins = Math.floor(seconds / 60);
  const secs = Math.floor(seconds % 60);
  return `${mins}:${secs.toString().padStart(2, "0")}`;
}

export default DAW;
