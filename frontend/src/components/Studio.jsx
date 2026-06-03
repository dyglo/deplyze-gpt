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

function greeting() {
  const h = new Date().getHours();
  if (h < 12) return "Good morning";
  if (h < 18) return "Good afternoon";
  return "Good evening";
}

function Greeting() {
  return (
    <div className="flex items-center justify-center gap-3 mb-7">
      <svg width="30" height="30" viewBox="0 0 24 24" fill="none">
        <path
          d="M12 2.2c.35 2.5.9 3.6 2 4.6m0 0c1.1 1 2.2 1.5 4.6 1.85M14 6.8 18.6 8.65M12 2.2c-.35 2.5-.9 3.6-2 4.6m0 0c-1.1 1-2.2 1.5-4.6 1.85M10 6.8 5.4 8.65M12 21.8c.35-2.5.9-3.6 2-4.6m0 0c1.1-1 2.2-1.5 4.6-1.85M14 17.2l4.6-1.85M12 21.8c-.35-2.5-.9-3.6-2-4.6m0 0c-1.1-1-2.2-1.5-4.6-1.85M10 17.2 5.4 15.35M2.2 12c2.5.35 3.6.9 4.6 2m0 0c1 1.1 1.5 2.2 1.85 4.6M6.8 14l1.85 4.6M2.2 12c2.5-.35 3.6-.9 4.6-2m0 0c1-1.1 1.5-2.2 1.85-4.6M6.8 10 8.65 5.4M21.8 12c-2.5.35-3.6.9-4.6 2m0 0c-1 1.1-1.5 2.2-1.85 4.6M17.2 14l-1.85 4.6M21.8 12c-2.5-.35-3.6-.9-4.6-2m0 0c-1-1.1-1.5-2.2-1.85-4.6M17.2 10l-1.85-4.6"
          stroke="var(--accent)"
          strokeWidth="1.5"
          strokeLinecap="round"
          strokeLinejoin="round"
        />
      </svg>
      <h1 className="font-serif-display text-[40px] leading-none" style={{ color: "var(--text-primary)" }}>
        {greeting()}, Tafar
      </h1>
    </div>
  );
}

export default function Studio() {
  const [messages, setMessages]         = useState([]);
  const [selectedModel, setSelectedModel] = useState("gemini");
  const [inputPrompt, setInputPrompt]   = useState("");
  const [inputFile, setInputFile]       = useState(null);
  const [isUploading, setIsUploading]   = useState(false);
  const [isAnalyzing, setIsAnalyzing]   = useState(false);
  const pollRef = useRef(null);
  const isEmpty = messages.length === 0;

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
      } catch (e) {
        clearInterval(pollRef.current);
        setIsAnalyzing(false);
        updateMessage(assistId, {
          isLoading: false,
          error: e.response?.data?.detail || "Video status check failed. Please try again.",
        });
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
    let objectUrl = null;
    try {
      const response = await fetch(url);
      if (!response.ok) throw new Error("Video download failed");
      const blob = await response.blob();
      objectUrl = URL.createObjectURL(blob);
      const filename = url.split("/").pop() || "deplyzegpt_output.mp4";
      const a = Object.assign(document.createElement("a"), {
        href: objectUrl,
        download: filename,
      });
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
    } catch (_) {
      const a = Object.assign(document.createElement("a"), {
        href: url,
        download: url.split("/").pop() || "deplyzegpt_output.mp4",
      });
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
    } finally {
      if (objectUrl) {
        setTimeout(() => URL.revokeObjectURL(objectUrl), 1000);
      }
    }
  };

  const handleDownloadImage = async (content) => {
    let objectUrl = null;
    try {
      const response = await fetch(content);
      const blob = await response.blob();
      objectUrl = URL.createObjectURL(blob);
      const extension = blob.type.includes("png") ? "png" : "jpg";
      const a = Object.assign(document.createElement("a"), {
        href: objectUrl,
        download: `deplyzegpt_output.${extension}`,
      });
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
    } finally {
      if (objectUrl) {
        setTimeout(() => URL.revokeObjectURL(objectUrl), 1000);
      }
    }
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
      style={{ background: "var(--bg-app)", color: "var(--text-primary)", fontFamily: "'Inter', sans-serif" }}
      className="h-screen w-full flex overflow-hidden"
    >
      <Sidebar onNewChat={handleNewChat} />

      <div className="flex-1 flex flex-col overflow-hidden">
        {/* Header */}
        <header
          data-testid="studio-header"
          className="flex-none px-4 py-2.5 flex items-center justify-end"
        >
          <span
            className="text-xs px-2.5 py-1 rounded-md font-medium"
            style={{ background: "var(--bg-elevated)", color: "var(--text-muted)" }}
          >
            Free
          </span>
        </header>

        {isEmpty ? (
          /* Empty state — greeting + input centered together (Claude home) */
          <div className="flex-1 flex flex-col items-center justify-center overflow-y-auto px-4">
            <div className="w-full" style={{ maxWidth: "768px" }}>
              <Greeting />
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
                showSuggestions
                onSuggestionClick={handleSuggestionClick}
                centered
              />
            </div>
          </div>
        ) : (
          /* Conversation — messages scroll, input pinned to bottom */
          <>
            <ChatMessages
              messages={messages}
              onSuggestionClick={handleSuggestionClick}
              onDownload={handleDownloadVideo}
              onDownloadImage={handleDownloadImage}
            />
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
              showSuggestions={false}
              onSuggestionClick={handleSuggestionClick}
            />
          </>
        )}
      </div>
    </div>
  );
}
