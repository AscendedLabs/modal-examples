/**
 * Generator.tsx - Page 1: AI Song Generator
 * 
 * User enters prompt + settings → submits → polls job status → downloads stems
 */

import React, { useState, useEffect } from "react";
import axios from "axios";

interface GenerationRequest {
  prompt: string;
  genre: "pop" | "hip_hop" | "rock" | "electronic" | "jazz" | "classical" | "ambient" | "lofi";
  bpm: number;
  duration: number;
  key: string;
  style?: string;
}

interface Stem {
  stem_type: string;
  url: string;
  duration: number;
}

interface JobStatus {
  job_id: string;
  status: "queued" | "processing" | "completed" | "failed";
  request: GenerationRequest;
  stems?: Stem[];
  error?: string;
  progress: number;
  created_at: string;
  completed_at?: string;
}

const GENRES = ["pop", "hip_hop", "rock", "electronic", "jazz", "classical", "ambient", "lofi"];
const KEYS = ["C", "Dm", "Em", "F", "G", "Am", "Bb", "B"];

export const Generator: React.FC = () => {
  const [prompt, setPrompt] = useState("");
  const [genre, setGenre] = useState<GenerationRequest["genre"]>("pop");
  const [bpm, setBpm] = useState(120);
  const [duration, setDuration] = useState(30);
  const [key, setKey] = useState("C");
  const [style, setStyle] = useState("");

  const [jobId, setJobId] = useState<string | null>(null);
  const [jobStatus, setJobStatus] = useState<JobStatus | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const API_BASE = process.env.REACT_APP_API_BASE || "http://localhost:8000";

  // Poll job status every 2 seconds
  useEffect(() => {
    if (!jobId) return;

    const interval = setInterval(async () => {
      try {
        const response = await axios.get<JobStatus>(`${API_BASE}/api/jobs/${jobId}`);
        setJobStatus(response.data);

        if (response.data.status === "completed" || response.data.status === "failed") {
          setLoading(false);
        }
      } catch (err) {
        console.error("Error polling job:", err);
      }
    }, 2000);

    return () => clearInterval(interval);
  }, [jobId, API_BASE]);

  const handleGenerate = async (e: React.FormEvent) => {
    e.preventDefault();

    if (!prompt.trim()) {
      setError("Please enter a music prompt");
      return;
    }

    setError(null);
    setLoading(true);

    try {
      const response = await axios.post(`${API_BASE}/api/generate`, {
        prompt,
        genre,
        bpm,
        duration,
        key,
        style: style || undefined,
      } as GenerationRequest);

      setJobId(response.data.job_id);
      setJobStatus(null);
    } catch (err) {
      setError("Failed to generate stems. Please try again.");
      setLoading(false);
      console.error(err);
    }
  };

  const downloadStem = (stemUrl: string, stemType: string) => {
    const link = document.createElement("a");
    link.href = `${API_BASE}${stemUrl}`;
    link.download = `${stemType}.wav`;
    link.click();
  };

  const goToDAW = () => {
    if (jobId && jobStatus?.stems) {
      // Navigate to DAW with job_id in URL
      window.location.href = `/daw?job_id=${jobId}`;
    }
  };

  return (
    <div className="min-h-screen bg-gradient-to-br from-gray-900 via-purple-900 to-black text-white">
      {/* HEADER */}
      <div className="border-b border-purple-500/30 bg-black/50 backdrop-blur">
        <div className="max-w-4xl mx-auto px-6 py-6">
          <h1 className="text-3xl font-bold">🎵 AI Song Generator</h1>
          <p className="text-purple-300 mt-2">Describe your song, we'll generate the stems</p>
        </div>
      </div>

      {/* MAIN CONTENT */}
      <div className="max-w-4xl mx-auto px-6 py-12">
        {/* ERROR MESSAGE */}
        {error && (
          <div className="mb-6 p-4 bg-red-900/50 border border-red-500 rounded-lg text-red-200">
            {error}
          </div>
        )}

        {/* FORM OR RESULTS */}
        {!jobId ? (
          // FORM
          <form onSubmit={handleGenerate} className="space-y-6">
            {/* PROMPT INPUT */}
            <div>
              <label className="block text-sm font-semibold mb-3">Describe Your Song</label>
              <textarea
                value={prompt}
                onChange={(e) => setPrompt(e.target.value)}
                placeholder="e.g., A chill lo-fi hip-hop track with vinyl crackle, jazzy chords, and a steady boom-bap beat"
                className="w-full h-24 px-4 py-3 bg-gray-800 border border-purple-500/50 rounded-lg focus:border-purple-400 focus:outline-none resize-none"
              />
              <p className="text-xs text-gray-400 mt-2">Be specific about mood, instruments, and style</p>
            </div>

            {/* CONTROLS GRID */}
            <div className="grid grid-cols-2 gap-6 md:grid-cols-4">
              {/* GENRE */}
              <div>
                <label className="block text-sm font-semibold mb-2">Genre</label>
                <select
                  value={genre}
                  onChange={(e) => setGenre(e.target.value as GenerationRequest["genre"])}
                  className="w-full px-3 py-2 bg-gray-800 border border-purple-500/50 rounded-lg focus:border-purple-400 focus:outline-none"
                >
                  {GENRES.map((g) => (
                    <option key={g} value={g}>
                      {g.toUpperCase()}
                    </option>
                  ))}
                </select>
              </div>

              {/* BPM */}
              <div>
                <label className="block text-sm font-semibold mb-2">BPM</label>
                <input
                  type="number"
                  min={40}
                  max={200}
                  value={bpm}
                  onChange={(e) => setBpm(parseInt(e.target.value) || 120)}
                  className="w-full px-3 py-2 bg-gray-800 border border-purple-500/50 rounded-lg focus:border-purple-400 focus:outline-none"
                />
              </div>

              {/* KEY */}
              <div>
                <label className="block text-sm font-semibold mb-2">Key</label>
                <select
                  value={key}
                  onChange={(e) => setKey(e.target.value)}
                  className="w-full px-3 py-2 bg-gray-800 border border-purple-500/50 rounded-lg focus:border-purple-400 focus:outline-none"
                >
                  {KEYS.map((k) => (
                    <option key={k} value={k}>
                      {k}
                    </option>
                  ))}
                </select>
              </div>

              {/* DURATION */}
              <div>
                <label className="block text-sm font-semibold mb-2">Duration (sec)</label>
                <input
                  type="number"
                  min={10}
                  max={120}
                  value={duration}
                  onChange={(e) => setDuration(parseInt(e.target.value) || 30)}
                  className="w-full px-3 py-2 bg-gray-800 border border-purple-500/50 rounded-lg focus:border-purple-400 focus:outline-none"
                />
              </div>
            </div>

            {/* STYLE (OPTIONAL) */}
            <div>
              <label className="block text-sm font-semibold mb-2">Style (optional)</label>
              <input
                type="text"
                value={style}
                onChange={(e) => setStyle(e.target.value)}
                placeholder="e.g., inspired by Lo-Fi Girl, downtempo, 80s synthwave"
                className="w-full px-4 py-2 bg-gray-800 border border-purple-500/50 rounded-lg focus:border-purple-400 focus:outline-none"
              />
            </div>

            {/* SUBMIT BUTTON */}
            <button
              type="submit"
              disabled={loading}
              className="w-full py-3 bg-gradient-to-r from-purple-600 to-pink-600 hover:from-purple-700 hover:to-pink-700 disabled:opacity-50 font-semibold rounded-lg transition-all"
            >
              {loading ? "Generating..." : "✨ Generate Song"}
            </button>
          </form>
        ) : (
          // JOB STATUS & RESULTS
          <div className="space-y-6">
            {/* JOB ID */}
            <div className="p-4 bg-gray-800/50 border border-purple-500/30 rounded-lg">
              <p className="text-sm text-gray-400">Job ID: {jobId}</p>
            </div>

            {/* STATUS INDICATOR */}
            <div className="space-y-3">
              <h2 className="text-lg font-semibold">Generation Status</h2>

              {/* PROGRESS BAR */}
              <div className="relative h-2 bg-gray-700 rounded-full overflow-hidden">
                <div
                  className="h-full bg-gradient-to-r from-purple-500 to-pink-500 transition-all duration-500"
                  style={{ width: `${jobStatus?.progress || 0}%` }}
                />
              </div>

              {/* STATUS TEXT */}
              <div className="flex items-center gap-3">
                {jobStatus?.status === "processing" && (
                  <>
                    <div className="w-3 h-3 bg-yellow-400 rounded-full animate-pulse" />
                    <span className="text-yellow-400">Processing...</span>
                  </>
                )}
                {jobStatus?.status === "queued" && (
                  <>
                    <div className="w-3 h-3 bg-blue-400 rounded-full animate-pulse" />
                    <span className="text-blue-400">Queued</span>
                  </>
                )}
                {jobStatus?.status === "completed" && (
                  <>
                    <div className="w-3 h-3 bg-green-400 rounded-full" />
                    <span className="text-green-400">Complete!</span>
                  </>
                )}
                {jobStatus?.status === "failed" && (
                  <>
                    <div className="w-3 h-3 bg-red-400 rounded-full" />
                    <span className="text-red-400">Failed: {jobStatus.error}</span>
                  </>
                )}
              </div>

              {jobStatus?.progress && (
                <p className="text-sm text-gray-400">{jobStatus.progress}% complete</p>
              )}
            </div>

            {/* GENERATED STEMS */}
            {jobStatus?.stems && jobStatus.stems.length > 0 && (
              <div className="space-y-3">
                <h2 className="text-lg font-semibold">Generated Stems</h2>

                <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                  {jobStatus.stems.map((stem) => (
                    <div
                      key={stem.stem_type}
                      className="p-4 bg-gray-800/50 border border-purple-500/30 rounded-lg flex items-center justify-between"
                    >
                      <div>
                        <p className="font-semibold capitalize">{stem.stem_type}</p>
                        <p className="text-sm text-gray-400">{stem.duration}s</p>
                      </div>

                      <div className="flex gap-2">
                        {/* PREVIEW */}
                        <audio
                          controls
                          className="w-32 h-8"
                          src={`${API_BASE}${stem.url}`}
                        />

                        {/* DOWNLOAD */}
                        <button
                          onClick={() => downloadStem(stem.url, stem.stem_type)}
                          className="px-3 py-2 bg-purple-600 hover:bg-purple-700 rounded text-sm font-semibold"
                        >
                          ↓
                        </button>
                      </div>
                    </div>
                  ))}
                </div>

                {/* GO TO DAW BUTTON */}
                <button
                  onClick={goToDAW}
                  className="w-full py-3 bg-gradient-to-r from-green-600 to-blue-600 hover:from-green-700 hover:to-blue-700 font-semibold rounded-lg transition-all mt-6"
                >
                  🎛️ Open in DAW Studio
                </button>
              </div>
            )}

            {/* BACK BUTTON */}
            {(jobStatus?.status === "failed" || jobStatus?.status === "completed") && (
              <button
                onClick={() => {
                  setJobId(null);
                  setJobStatus(null);
                  setPrompt("");
                }}
                className="w-full py-2 bg-gray-700 hover:bg-gray-600 rounded-lg transition-all"
              >
                ← New Generation
              </button>
            )}
          </div>
        )}
      </div>
    </div>
  );
};

export default Generator;
