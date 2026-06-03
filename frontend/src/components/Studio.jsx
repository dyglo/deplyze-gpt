import React, { useState, useEffect, useRef, useCallback } from "react";
import axios from "axios";
import { Eye, Zap, Layers, Globe } from "lucide-react";
import UploadZone from "./UploadZone";
import ModelSelector from "./ModelSelector";
import OutputPanel from "./OutputPanel";
import ChatInput from "./ChatInput";

const BACKEND_URL = process.env.REACT_APP_BACKEND_URL;
const API = `${BACKEND_URL}/api`;
const LS_KEY = "deplyzegpt_job";

const MODELS = [
  { id: "gemini",     label: "gemini",     subtitle: "Gemini 3-flash",  desc: "Conversational vision analysis",  icon: Eye },
  { id: "yolo26",     label: "yolo26",     subtitle: "YOLO26",          desc: "Fast object detection",           icon: Zap },
  { id: "yolo26-seg", label: "yolo26-seg", subtitle: "YOLO26-Seg",      desc: "Instance segmentation",           icon: Layers },
  { id: "yolo26-sem", label: "yolo26-sem", subtitle: "YOLO26-Sem",      desc: "Semantic scene understanding",    icon: Globe },
];

export default function Studio() {
  const [selectedModel, setSelectedModel] = useState("gemini");
  const [uploadedFile, setUploadedFile]   = useState(null);
  const [isUploading, setIsUploading]     = useState(false);
  const [uploadProgress, setUploadProgress] = useState(0);
  const [uploadError, setUploadError]     = useState("");
  const [prompt, setPrompt]               = useState("");
  const [isAnalyzing, setIsAnalyzing]     = useState(false);
  const [result, setResult]               = useState(null);
  const [error, setError]                 = useState("");
  const [videoJob, setVideoJob]           = useState(null);
  const [storedJob, setStoredJob]         = useState(null);
  const [showJobBanner, setShowJobBanner] = useState(false);
  const pollRef = useRef(null);

  // Check localStorage for a persisted job on mount
  useEffect(() => {
    try {
      const saved = localStorage.getItem(LS_KEY);
      if (saved) {
        const job = JSON.parse(saved);
        const age = Date.now() - new Date(job.created_at).getTime();
        if (age < 24 * 3600 * 1000 && job.status !== "failed") {
          setStoredJob(job);
          setShowJobBanner(true);
        }
      }
    } catch (_) {}
  }, []);

  useEffect(() => () => { if (pollRef.current) clearInterval(pollRef.current); }, []);

  const startPolling = useCallback((jobId) => {
    if (pollRef.current) clearInterval(pollRef.current);

    pollRef.current = setInterval(async () => {
      try {
        const { data } = await axios.get(`${API}/analyze/video/status/${jobId}`);
        setVideoJob(data);

        // Keep localStorage in sync
        const stored = JSON.parse(localStorage.getItem(LS_KEY) || "{}");
        localStorage.setItem(LS_KEY, JSON.stringify({ ...stored, ...data }));

        if (data.status === "done") {
          clearInterval(pollRef.current);
          setIsAnalyzing(false);
          if (data.output_url) {
            setResult({
              type: "video",
              content: `${BACKEND_URL}${data.output_url}`,
              detections: [],
              suggestions: ["Analyze frames with Gemini", "Run segmentation on this", "Download result"],
            });
          }
        } else if (data.status === "failed") {
          clearInterval(pollRef.current);
          setIsAnalyzing(false);
          setError(data.error || "Video processing failed");
        }
      } catch (_) {
        clearInterval(pollRef.current);
        setIsAnalyzing(false);
      }
    }, 2000);
  }, []);

  const handleFileUpload = useCallback(async (file) => {
    setUploadError("");
    setError("");

    const validTypes = [
      "image/jpeg", "image/png", "image/webp",
      "video/mp4", "video/mov", "video/avi", "video/quicktime",
    ];
    const ext = file.name.split(".").pop().toLowerCase();
    const validExts = ["jpg", "jpeg", "png", "webp", "mp4", "mov", "avi"];

    if (!validTypes.includes(file.type) && !validExts.includes(ext)) {
      setUploadError("Unsupported file type. Accepted: JPEG, PNG, WEBP, MP4, MOV, AVI");
      return;
    }
    if (file.size > 100 * 1024 * 1024) {
      setUploadError("File exceeds 100MB limit");
      return;
    }

    setIsUploading(true);
    setUploadProgress(0);

    try {
      const fd = new FormData();
      fd.append("file", file);

      const { data } = await axios.post(`${API}/upload`, fd, {
        headers: { "Content-Type": "multipart/form-data" },
        onUploadProgress: (e) => setUploadProgress(Math.round((e.loaded / e.total) * 100)),
      });

      setUploadedFile({
        ...data,
        objectUrl: URL.createObjectURL(file),
      });
      setResult(null);
      setVideoJob(null);
    } catch (e) {
      setUploadError(e.response?.data?.detail || "Upload failed. Please try again.");
    } finally {
      setIsUploading(false);
      setUploadProgress(0);
    }
  }, []);

  const performAnalysis = useCallback(async (promptText) => {
    if (!uploadedFile) { setError("Please upload a file first"); return; }

    setError("");
    setIsAnalyzing(true);
    setResult(null);
    setVideoJob(null);

    const isVideo = uploadedFile.file_type === "video";
    const finalPrompt = promptText || `Analyze this ${isVideo ? "video" : "image"}`;

    try {
      if (isVideo) {
        if (selectedModel === "gemini") {
          const { data } = await axios.post(`${API}/analyze/video/gemini`, {
            file_url: uploadedFile.url,
            prompt: finalPrompt,
          });
          setResult(data);
          setIsAnalyzing(false);
        } else {
          const { data } = await axios.post(`${API}/analyze/video`, {
            file_url: uploadedFile.url,
            model: selectedModel,
            confidence: 0.25,
          });
          const jobData = {
            job_id: data.job_id,
            status: "queued",
            progress: 0,
            model: selectedModel,
            created_at: new Date().toISOString(),
          };
          setVideoJob(jobData);
          localStorage.setItem(LS_KEY, JSON.stringify(jobData));
          startPolling(data.job_id);
        }
      } else {
        const { data } = await axios.post(`${API}/analyze/image`, {
          file_url: uploadedFile.url,
          model: selectedModel,
          prompt: finalPrompt,
        });
        setResult(data);
        setIsAnalyzing(false);
      }
    } catch (e) {
      setError(e.response?.data?.detail || "Analysis failed. Please try again.");
      setIsAnalyzing(false);
    }
  }, [uploadedFile, selectedModel, startPolling]);

  const handleAnalyze = useCallback(() => {
    const p = prompt.trim() || (uploadedFile ? `Analyze this ${uploadedFile.file_type}` : "");
    performAnalysis(p);
  }, [prompt, uploadedFile, performAnalysis]);

  const handleSuggestionClick = useCallback((suggestion) => {
    setPrompt(suggestion);
    performAnalysis(suggestion);
  }, [performAnalysis]);

  const handleRestoreJob = useCallback(() => {
    if (!storedJob) return;
    setShowJobBanner(false);

    if (storedJob.status === "done" && storedJob.output_url) {
      setResult({
        type: "video",
        content: `${BACKEND_URL}${storedJob.output_url}`,
        detections: [],
        suggestions: ["Analyze with Gemini", "Run detection", "Download result"],
      });
    } else if (storedJob.status === "queued" || storedJob.status === "processing") {
      setIsAnalyzing(true);
      setVideoJob(storedJob);
      startPolling(storedJob.job_id);
    }
  }, [storedJob, startPolling]);

  const handleDownloadVideo = async (url) => {
    try {
      const res = await fetch(url, { redirect: "follow" });
      if (!res.ok) throw new Error("Download failed");
      const blob = await res.blob();
      const objUrl = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = objUrl;
      a.download = "deplyzegpt_output.mp4";
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
      URL.revokeObjectURL(objUrl);
    } catch (_) {
      setError("Download failed. Try right-clicking the video to save.");
    }
  };

  const handleClearUpload = useCallback(() => {
    setUploadedFile(null);
    setResult(null);
    setError("");
    setVideoJob(null);
    setUploadError("");
  }, []);

  return (
    <div
      data-testid="studio-container"
      style={{ background: "#111111", color: "#fff", fontFamily: "'Outfit', sans-serif" }}
      className="h-screen w-full flex flex-col overflow-hidden"
    >
      {/* Job Persistence Banner */}
      {showJobBanner && storedJob && (
        <div
          data-testid="job-persistence-banner"
          className="flex-none w-full px-6 py-2 flex items-center gap-2 text-sm"
          style={{ background: "rgba(201,106,42,0.08)", borderBottom: "1px solid rgba(201,106,42,0.2)" }}
        >
          <span className="w-2 h-2 rounded-full flex-shrink-0" style={{ background: "#C96A2A" }} />
          <span style={{ color: "#C96A2A" }}>Your previous video analysis is ready —</span>
          <button
            data-testid="restore-job-button"
            onClick={handleRestoreJob}
            className="underline font-medium transition-opacity hover:opacity-80"
            style={{ color: "#C96A2A" }}
          >
            View Output
          </button>
          <button
            onClick={() => setShowJobBanner(false)}
            className="ml-auto opacity-40 hover:opacity-80 transition-opacity text-base leading-none"
          >
            ×
          </button>
        </div>
      )}

      {/* Header */}
      <div
        data-testid="studio-header"
        className="flex-none px-6 py-4 flex items-center gap-3"
        style={{ borderBottom: "1px solid #2A2A2A" }}
      >
        <div
          className="w-9 h-9 rounded-xl flex items-center justify-center flex-shrink-0"
          style={{ background: "#C96A2A" }}
        >
          <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="white" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
            <path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z" />
            <circle cx="12" cy="12" r="3" />
          </svg>
        </div>
        <div>
          <h1 className="text-xl font-bold tracking-tight leading-none">DeplyzeGPT</h1>
          <p className="text-xs mt-0.5" style={{ color: "#A1A1AA" }}>Vision AI for everyone</p>
        </div>
        <div className="ml-auto flex items-center gap-2">
          <span
            className="px-2 py-0.5 rounded text-xs font-mono"
            style={{ background: "rgba(201,106,42,0.12)", color: "#C96A2A", border: "1px solid rgba(201,106,42,0.2)" }}
          >
            STUDIO
          </span>
        </div>
      </div>

      {/* Main two-column layout */}
      <div
        className="flex-1 overflow-hidden grid grid-cols-1"
        style={{ gridTemplateColumns: "clamp(320px, 420px, 440px) 1fr" }}
      >
        {/* Left Column */}
        <div
          data-testid="studio-left-column"
          className="flex flex-col overflow-hidden"
          style={{ borderRight: "1px solid #2A2A2A" }}
        >
          {/* Scrollable section */}
          <div className="flex-1 overflow-y-auto p-5 space-y-5">
            <UploadZone
              uploadedFile={uploadedFile}
              isUploading={isUploading}
              uploadProgress={uploadProgress}
              uploadError={uploadError}
              onFileSelect={handleFileUpload}
              onClear={handleClearUpload}
            />
            <ModelSelector
              models={MODELS}
              selected={selectedModel}
              onSelect={setSelectedModel}
            />
          </div>

          {/* Suggestion chips */}
          {result?.suggestions?.length > 0 && (
            <div
              data-testid="suggestion-chips-container"
              className="flex-none px-5 py-3 flex flex-wrap gap-2"
              style={{ borderTop: "1px solid #2A2A2A" }}
            >
              {result.suggestions.map((s, i) => (
                <button
                  key={i}
                  data-testid="suggestion-chip"
                  onClick={() => handleSuggestionClick(s)}
                  className="px-3 py-1.5 rounded-full text-xs transition-all"
                  style={{ background: "#1A1A1A", border: "1px solid #2A2A2A", color: "#A1A1AA" }}
                  onMouseEnter={(e) => { e.currentTarget.style.borderColor = "#C96A2A"; e.currentTarget.style.color = "#fff"; }}
                  onMouseLeave={(e) => { e.currentTarget.style.borderColor = "#2A2A2A"; e.currentTarget.style.color = "#A1A1AA"; }}
                >
                  {s}
                </button>
              ))}
            </div>
          )}

          {/* Chat Input – fixed at bottom */}
          <ChatInput
            prompt={prompt}
            onPromptChange={setPrompt}
            onAnalyze={handleAnalyze}
            isAnalyzing={isAnalyzing}
            hasFile={!!uploadedFile}
            error={error}
            onModelSelect={setSelectedModel}
          />
        </div>

        {/* Right Column */}
        <div
          data-testid="studio-right-column"
          className="flex flex-col overflow-hidden"
          style={{ background: "#151515" }}
        >
          <OutputPanel
            result={result}
            isLoading={isAnalyzing}
            videoJob={videoJob}
            onDownload={handleDownloadVideo}
          />
        </div>
      </div>
    </div>
  );
}
