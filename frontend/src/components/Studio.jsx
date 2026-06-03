import React, { useState, useEffect, useRef, useCallback } from "react";
import axios from "axios";
import { Eye, Zap, Layers, Globe } from "lucide-react";
import Sidebar from "./Sidebar";
import ChatMessages from "./ChatMessages";
import ChatInputBar from "./ChatInputBar";

const BACKEND_URL = process.env.REACT_APP_BACKEND_URL;
const API = `${BACKEND_URL}/api`;

const MODELS = [
  { id: "gemini",     label: "Gemini",   desc: "Conversational vision analysis",  icon: Eye },
  { id: "yolo26",     label: "YOLO26",   desc: "Fast object detection",           icon: Zap },
  { id: "yolo26-seg", label: "YOLO-Seg", desc: "Instance segmentation",           icon: Layers },
  { id: "yolo26-sem", label: "YOLO-Sem", desc: "Semantic scene understanding",    icon: Globe },
];

export default function Studio() {
  const [messages, setMessages]         = useState([]);
  const [selectedModel, setSelectedModel] = useState("gemini");
  const [inputPrompt, setInputPrompt]   = useState("");
  const [inputFile, setInputFile]       = useState(null);
  const [isUploading, setIsUploading]   = useState(false);
  const [isAnalyzing, setIsAnalyzing]   = useState(false);
  const pollRef = useRef(null);

  useEffect(() => () => { if (pollRef.current) clearInterval(pollRef.current); }, []);

  const updateMessage = useCallback((id, updates) => {
    setMessages(prev => prev.map(m => m.id === id ? { ...m, ...updates } : m));
  }, []);

  const startPolling = useCallback((jobId, assistId) => {
    if (pollRef.current) clearInterval(pollRef.current);
    pollRef.current = setInterval(async () => {
      try {
        const { data } = await axios.get(`${API}/analyze/video/status/${jobId}`);
        updateMessage(assistId, { videoJob: data });
        if (data.status === "done") {
          clearInterval(pollRef.current);
          setIsAnalyzing(false);
          updateMessage(assistId, {
            isLoading: false,
            videoJob: data,
            result: data.output_url ? {
              type: "video",
              content: `${BACKEND_URL}${data.output_url}`,
              detections: [],
              suggestions: ["Analyze frames with Gemini", "Run segmentation", "Download result"],
            } : null,
          });
        } else if (data.status === "failed") {
          clearInterval(pollRef.current);
          setIsAnalyzing(false);
          updateMessage(assistId, { isLoading: false, error: data.error || "Video processing failed", videoJob: data });
        }
      } catch (_) {
        clearInterval(pollRef.current);
        setIsAnalyzing(false);
      }
    }, 2000);
  }, [updateMessage]);

  const handleFileSelect = useCallback(async (file) => {
    const ext = file.name.split(".").pop().toLowerCase();
    const validExts = ["jpg", "jpeg", "png", "webp", "mp4", "mov", "avi"];
    if (!validExts.includes(ext) || file.size > 100 * 1024 * 1024) return;

    const objectUrl = URL.createObjectURL(file);
    const isImg = file.type.startsWith("image/") || ["jpg","jpeg","png","webp"].includes(ext);
    // Show file instantly in the input (instant UX)
    setInputFile({ uploading: true, filename: file.name, size: file.size, objectUrl, file_type: isImg ? "image" : "video" });
    setIsUploading(true);

    try {
      const fd = new FormData();
      fd.append("file", file);
      const { data } = await axios.post(`${API}/upload`, fd, {
        headers: { "Content-Type": "multipart/form-data" },
      });
      setInputFile(prev => ({ ...data, objectUrl: prev?.objectUrl || objectUrl }));
    } catch (_) {
      setInputFile(null);
    } finally {
      setIsUploading(false);
    }
  }, []);

  const handleSend = useCallback(async () => {
    if (isAnalyzing || isUploading || !inputFile || inputFile?.uploading) return;

    const file    = inputFile;
    const prompt  = inputPrompt.trim() || `Analyze this ${inputFile.file_type}`;
    const model   = selectedModel;
    const isVideo = file.file_type === "video";

    setInputPrompt("");
    setInputFile(null);
    setIsAnalyzing(true);

    const userId  = `user-${Date.now()}`;
    const assistId = `asst-${Date.now() + 1}`;

    setMessages(prev => [
      ...prev,
      { id: userId,  type: "user",      prompt, file, model },
      { id: assistId, type: "assistant", isLoading: true, model, result: null, error: null, videoJob: null },
    ]);

    try {
      if (isVideo) {
        if (model === "gemini") {
          const { data } = await axios.post(`${API}/analyze/video/gemini`, { file_url: file.url, prompt });
          updateMessage(assistId, { isLoading: false, result: data });
          setIsAnalyzing(false);
        } else {
          const { data } = await axios.post(`${API}/analyze/video`, { file_url: file.url, model, confidence: 0.25 });
          updateMessage(assistId, { videoJob: { job_id: data.job_id, status: "queued", progress: 0, model } });
          startPolling(data.job_id, assistId);
        }
      } else {
        const { data } = await axios.post(`${API}/analyze/image`, { file_url: file.url, model, prompt });
        updateMessage(assistId, { isLoading: false, result: data });
        setIsAnalyzing(false);
      }
    } catch (e) {
      updateMessage(assistId, { isLoading: false, error: e.response?.data?.detail || "Analysis failed. Please try again." });
      setIsAnalyzing(false);
    }
  }, [inputFile, inputPrompt, selectedModel, isAnalyzing, isUploading, updateMessage, startPolling]);

  const handleSuggestionClick = useCallback((s) => {
    setInputPrompt(s);
  }, []);

  const handleDownloadVideo = async (url) => {
    try {
      const blob = await fetch(url).then(r => r.blob());
      const a = Object.assign(document.createElement("a"), {
        href: URL.createObjectURL(blob),
        download: "deplyzegpt_output.mp4",
      });
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
    } catch (_) {}
  };

  const handleNewChat = useCallback(() => {
    if (pollRef.current) clearInterval(pollRef.current);
    setMessages([]);
    setInputPrompt("");
    setInputFile(null);
    setIsAnalyzing(false);
    setIsUploading(false);
  }, []);

  return (
    <div
      data-testid="studio-container"
      style={{ background: "#111111", color: "#fff", fontFamily: "'Outfit', sans-serif" }}
      className="h-screen w-full flex overflow-hidden"
    >
      <Sidebar onNewChat={handleNewChat} />

      <div className="flex-1 flex flex-col overflow-hidden">
        {/* Header */}
        <header
          data-testid="studio-header"
          className="flex-none px-5 py-3 flex items-center justify-between"
          style={{ borderBottom: "1px solid #1C1C1C" }}
        >
          <div className="flex items-center gap-2.5">
            <div
              className="w-7 h-7 rounded-lg flex items-center justify-center flex-shrink-0"
              style={{ background: "#C96A2A" }}
            >
              <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="white" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
                <path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z"/>
                <circle cx="12" cy="12" r="3"/>
              </svg>
            </div>
            <span className="font-semibold text-sm tracking-tight">DeplyzeGPT</span>
          </div>
          <span
            className="text-xs px-2 py-0.5 rounded"
            style={{ background: "#1A1A1A", color: "#555", border: "1px solid #222" }}
          >
            Free
          </span>
        </header>

        {/* Chat messages area */}
        <ChatMessages
          messages={messages}
          onSuggestionClick={handleSuggestionClick}
          onDownload={handleDownloadVideo}
        />

        {/* Input bar */}
        <ChatInputBar
          prompt={inputPrompt}
          onPromptChange={setInputPrompt}
          onSend={handleSend}
          onFileSelect={handleFileSelect}
          inputFile={inputFile}
          onClearFile={() => setInputFile(null)}
          isUploading={isUploading}
          isAnalyzing={isAnalyzing}
          selectedModel={selectedModel}
          onModelSelect={setSelectedModel}
          models={MODELS}
        />
      </div>
    </div>
  );
}
