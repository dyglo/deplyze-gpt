import React, { useState, useEffect, useRef, useCallback, useMemo } from "react";
import axios from "axios";
import { doc, onSnapshot } from "firebase/firestore";
import { Crosshair, Eye, Zap, Layers, Globe } from "lucide-react";
import { db } from "../firebase";
import Sidebar from "./Sidebar";
import ChatMessages from "./ChatMessages";
import ChatInputBar from "./ChatInputBar";
import DatasetPage from "../pages/DatasetPage";
import { apiDownloadUrl, isApiUrl } from "../downloadUtils";
import { normalizeSuggestionText } from "../suggestionUtils";

const BACKEND_URL = process.env.REACT_APP_BACKEND_URL;
const API = `${BACKEND_URL}/api`;
const ENABLE_LOCATE_ANYTHING = process.env.REACT_APP_ENABLE_LOCATE_ANYTHING === "true";
const ENABLE_LOCATE_ANYTHING_VIDEO = process.env.REACT_APP_ENABLE_LOCATE_ANYTHING_VIDEO === "true";
const IMAGE_ONLY_MODELS = new Set(ENABLE_LOCATE_ANYTHING_VIDEO ? [] : ["locate-anything"]);

const BASE_MODELS = [
  { id: "gemini",     label: "Gemini",   desc: "Conversational vision analysis",  icon: Eye },
  { id: "yolo26",     label: "YOLO26",   desc: "Fast object detection",           icon: Zap },
  { id: "yolo26-seg", label: "YOLO-Seg", desc: "Instance segmentation",           icon: Layers },
  { id: "yolo26-sem", label: "YOLO-Sem", desc: "Semantic scene understanding",    icon: Globe },
];

const MODELS = ENABLE_LOCATE_ANYTHING
  ? [
      ...BASE_MODELS,
      { id: "locate-anything", label: "Locate", desc: "Open-vocabulary grounding", icon: Crosshair },
    ]
  : BASE_MODELS;

function fileTypeFromName(filename = "") {
  const ext = filename.split(".").pop()?.toLowerCase();
  return ["mp4", "mov", "avi"].includes(ext) ? "video" : "image";
}

function inputUrlFromMessage(message) {
  if (!message.job_id || !message.input_filename) return "";
  const ext = message.input_filename.includes(".")
    ? `.${message.input_filename.split(".").pop()}`
    : "";
  return `/api/files/uploads/${message.job_id}/input${ext}`;
}

function messageFromPersisted(message) {
  if (message.role === "user") {
    const filename = message.input_filename || "";
    return {
      id: message.message_id,
      type: "user",
      prompt: message.content,
      model: message.model,
      file: filename ? {
        filename,
        file_type: fileTypeFromName(filename),
        objectUrl: message.input_url,
        url: inputUrlFromMessage(message),
        session_id: message.session_id,
      } : null,
    };
  }

  if (message.output_type === "error") {
    return {
      id: message.message_id,
      type: "assistant",
      isLoading: false,
      model: message.model,
      result: null,
      error: message.content,
      videoJob: null,
    };
  }

  const resultType = message.output_type || "text";
  return {
    id: message.message_id,
    type: "assistant",
    isLoading: false,
    model: message.model,
    result: {
      type: resultType,
      content: resultType === "text" ? message.content : message.output_url,
      download_url: message.output_download_url,
      job_id: message.job_id,
      detections: message.detections || [],
      frames: message.frames || [],
      manifest_url: message.manifest_url,
      suggestions: message.suggestions || [],
    },
    error: null,
    videoJob: null,
  };
}

function downloadKeyFor(kind, jobId, source) {
  return `${kind}:${jobId || source || "output"}`;
}

function filenameForBlob(kind, blob) {
  if (kind === "video") return "deplyzegpt_output.mp4";
  const extensionByType = {
    "image/png": "png",
    "image/webp": "webp",
    "image/gif": "gif",
  };
  const extension = extensionByType[blob.type] || "jpg";
  return `deplyzegpt_output.${extension}`;
}

function triggerLocalBlobDownload(blob, filename) {
  const objectUrl = URL.createObjectURL(blob);
  const anchor = Object.assign(document.createElement("a"), {
    href: objectUrl,
    download: filename,
  });

  anchor.style.display = "none";
  document.body.appendChild(anchor);
  anchor.click();
  document.body.removeChild(anchor);
  URL.revokeObjectURL(objectUrl);
}

function greeting() {
  const h = new Date().getHours();
  if (h < 12) return "Good morning";
  if (h < 18) return "Good afternoon";
  return "Good evening";
}

function Greeting({ name }) {
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
        {greeting()}, {name}
      </h1>
    </div>
  );
}

export default function Studio({ user, onSignOut, onProfileUpdate, profileVersion = 0 }) {
  const [messages, setMessages]         = useState([]);
  const [selectedModel, setSelectedModel] = useState("gemini");
  const [inputPrompt, setInputPrompt]   = useState("");
  const [inputFile, setInputFile]       = useState(null);
  const [isUploading, setIsUploading]   = useState(false);
  const [uploadProgress, setUploadProgress] = useState(0);
  const [uploadError, setUploadError] = useState("");
  const [isAnalyzing, setIsAnalyzing]   = useState(false);
  const [contextFile, setContextFile] = useState(null);
  const [sessions, setSessions] = useState([]);
  const [activeSessionId, setActiveSessionId] = useState(null);
  const [isLoadingSession, setIsLoadingSession] = useState(false);
  const [view, setView] = useState("chat");
  const [downloadStatus, setDownloadStatus] = useState({});
  const jobUnsubscribeRef = useRef(null);
  const isEmpty = messages.length === 0;
  // profileVersion is included so the greeting refreshes after a profile edit
  // (updateProfile mutates the same user object in place).
  // eslint-disable-next-line react-hooks/exhaustive-deps
  const displayName = useMemo(() => user?.displayName || user?.email || "User", [user, profileVersion]);
  const firstName = useMemo(() => displayName.split("@")[0].split(" ")[0] || "there", [displayName]);
  const storageKey = useMemo(() => `deplyzegpt.activeSession.${user.uid}`, [user.uid]);
  const activeFileForControls = inputFile?.url ? inputFile : contextFile;
  const disabledModelIds = useMemo(
    () => activeFileForControls?.file_type === "video" ? ["locate-anything"] : [],
    [activeFileForControls],
  );

  useEffect(() => () => {
    if (jobUnsubscribeRef.current) jobUnsubscribeRef.current();
  }, []);

  useEffect(() => {
    if (activeFileForControls?.file_type === "video" && IMAGE_ONLY_MODELS.has(selectedModel)) {
      setSelectedModel("gemini");
    }
  }, [activeFileForControls, selectedModel]);

  const authHeaders = useCallback(async (extra = {}) => ({
    ...extra,
    Authorization: `Bearer ${await user.getIdToken()}`,
  }), [user]);

  const loadSessions = useCallback(async () => {
    const { data } = await axios.get(`${API}/sessions`, { headers: await authHeaders() });
    setSessions(data.sessions || []);
    return data.sessions || [];
  }, [authHeaders]);

  const loadSessionMessages = useCallback(async (sessionId) => {
    setIsLoadingSession(true);
    try {
      const { data } = await axios.get(`${API}/sessions/${sessionId}/messages`, {
        headers: await authHeaders(),
      });
      const restored = (data.messages || []).map(messageFromPersisted);
      setMessages(restored);
      const lastInput = [...(data.messages || [])].reverse().find(message => message.input_r2_path && message.job_id);
      if (lastInput) {
        const filename = lastInput.input_filename || "";
        setContextFile({
          filename,
          file_type: fileTypeFromName(filename),
          objectUrl: lastInput.input_url,
          url: inputUrlFromMessage(lastInput),
          session_id: sessionId,
        });
      } else {
        setContextFile(null);
      }
      setActiveSessionId(sessionId);
      localStorage.setItem(storageKey, sessionId);
    } finally {
      setIsLoadingSession(false);
    }
  }, [authHeaders, storageKey]);

  useEffect(() => {
    let cancelled = false;
    loadSessions()
      .then((items) => {
        if (cancelled) return;
        const saved = localStorage.getItem(storageKey);
        if (saved && items.some(session => session.session_id === saved)) {
          loadSessionMessages(saved).catch(() => localStorage.removeItem(storageKey));
        }
      })
      .catch(() => {});
    return () => {
      cancelled = true;
    };
  }, [loadSessions, loadSessionMessages, storageKey]);

  const updateMessage = useCallback((id, updates) => {
    setMessages(prev => prev.map(m => m.id === id ? { ...m, ...updates } : m));
  }, []);

  const stopJobListener = useCallback(() => {
    if (jobUnsubscribeRef.current) {
      jobUnsubscribeRef.current();
      jobUnsubscribeRef.current = null;
    }
  }, []);

  const startJobListener = useCallback((jobId, assistId) => {
    stopJobListener();
    const jobDocument = doc(db, "jobs", user.uid, "items", jobId);
    jobUnsubscribeRef.current = onSnapshot(
      jobDocument,
      async (snapshot) => {
        if (!snapshot.exists()) return;
        const data = snapshot.data();
        updateMessage(assistId, { videoJob: data });

        if (data.status === "done" && (data.output_url || data.output_key || data.output_r2_path)) {
          let videoUrl = data.output_url;
          if (!videoUrl) {
            const response = await axios.get(`${API}/files/presign/${jobId}`, {
              headers: await authHeaders(),
            });
            videoUrl = response.data.url;
          }
          stopJobListener();
          setIsAnalyzing(false);
          updateMessage(assistId, {
            isLoading: false,
            videoJob: data,
            result: videoUrl ? {
              type: "video",
              content: videoUrl,
              download_url: `${API}/files/download/${jobId}`,
              job_id: jobId,
              detections: [],
              suggestions: data.model === "locate-anything"
                ? ["Refine the target prompt", "Describe this video with Gemini", "Download result"]
                : ["Analyze frames with Gemini", "Run segmentation", "Download result"],
            } : null,
          });
          loadSessions().catch(() => {});
        } else if (data.status === "failed") {
          stopJobListener();
          setIsAnalyzing(false);
          updateMessage(assistId, { isLoading: false, error: data.error || "Video processing failed", videoJob: data });
        }
      },
      (error) => {
        stopJobListener();
        setIsAnalyzing(false);
        updateMessage(assistId, {
          isLoading: false,
          error: error?.message || "Video status listener failed. Please try again.",
        });
      },
    );
  }, [authHeaders, loadSessions, stopJobListener, updateMessage, user.uid]);

  const handleFileSelect = useCallback(async (file) => {
    const ext = file.name.split(".").pop().toLowerCase();
    const validExts = ["jpg", "jpeg", "png", "webp", "mp4", "mov", "avi"];
    if (!validExts.includes(ext) || file.size > 100 * 1024 * 1024) return;

    const objectUrl = URL.createObjectURL(file);
    const isImg = file.type.startsWith("image/") || ["jpg","jpeg","png","webp"].includes(ext);
    if (!isImg && IMAGE_ONLY_MODELS.has(selectedModel)) {
      setSelectedModel("gemini");
    }
    setInputFile({ uploading: true, filename: file.name, size: file.size, objectUrl, file_type: isImg ? "image" : "video" });
    setUploadProgress(0);
    setUploadError("");
    setIsUploading(true);

    try {
      const fd = new FormData();
      fd.append("file", file);
      if (activeSessionId) fd.append("session_id", activeSessionId);
      const { data } = await axios.post(`${API}/upload`, fd, {
        headers: await authHeaders(),
        onUploadProgress: (event) => {
          if (!event.total) return;
          setUploadProgress(Math.round((event.loaded * 100) / event.total));
        },
      });
      setActiveSessionId(data.session_id);
      localStorage.setItem(storageKey, data.session_id);
      setInputFile(prev => ({ ...data, session_id: data.session_id, objectUrl: prev?.objectUrl || objectUrl }));
      loadSessions().catch(() => {});
    } catch (error) {
      setUploadError(error.response?.data?.detail || "Upload failed. Please try again.");
      setInputFile(prev => prev ? { ...prev, uploading: false } : null);
    } finally {
      setIsUploading(false);
      setUploadProgress(0);
    }
  }, [activeSessionId, authHeaders, loadSessions, selectedModel, storageKey]);

  const handleSend = useCallback(async () => {
    const promptText = inputPrompt.trim();
    const activeFile = inputFile?.url ? inputFile : contextFile;
    if (isAnalyzing || isUploading || inputFile?.uploading || !activeFile) return;
    if (!inputFile?.url && !promptText) return;

    const file    = activeFile;
    const prompt  = promptText || `Analyze this ${file.file_type}`;
    const model   = selectedModel;
    const isVideo = file.file_type === "video";
    const sessionId = activeSessionId || file.session_id || null;

    if (isVideo && IMAGE_ONLY_MODELS.has(model)) {
      setUploadError("LocateAnything video analysis is not enabled in this environment.");
      return;
    }

    setInputPrompt("");
    setInputFile(null);
    setContextFile(file);
    setUploadProgress(0);
    setUploadError("");
    setIsAnalyzing(true);

    const userId  = `user-${Date.now()}`;
    const assistId = `asst-${Date.now() + 1}`;

    setMessages(prev => [
      ...prev,
      { id: userId,  type: "user",      prompt, file, model },
      { id: assistId, type: "assistant", isLoading: true, model, result: null, error: null, videoJob: null },
    ]);

    try {
      const headers = await authHeaders();
      if (isVideo) {
        if (model === "gemini") {
          const { data } = await axios.post(`${API}/analyze/video/gemini`, { file_url: file.url, prompt, session_id: sessionId }, { headers });
          if (data.session_id) {
            setActiveSessionId(data.session_id);
            localStorage.setItem(storageKey, data.session_id);
          }
          updateMessage(assistId, { isLoading: false, result: data });
          setIsAnalyzing(false);
          loadSessions().catch(() => {});
        } else {
          const { data } = await axios.post(`${API}/analyze/video`, { file_url: file.url, model, confidence: 0.25, prompt, session_id: sessionId }, { headers });
          if (data.session_id) {
            setActiveSessionId(data.session_id);
            localStorage.setItem(storageKey, data.session_id);
          }
          updateMessage(assistId, { videoJob: { job_id: data.job_id, status: "queued", progress: 0, model } });
          startJobListener(data.job_id, assistId);
          loadSessions().catch(() => {});
        }
      } else {
        const { data } = await axios.post(`${API}/analyze/image`, { file_url: file.url, model, prompt, session_id: sessionId }, { headers });
        if (data.session_id) {
          setActiveSessionId(data.session_id);
          localStorage.setItem(storageKey, data.session_id);
        }
        updateMessage(assistId, { isLoading: false, result: data });
        setIsAnalyzing(false);
        loadSessions().catch(() => {});
      }
    } catch (e) {
      updateMessage(assistId, { isLoading: false, error: e.response?.data?.detail || "Analysis failed. Please try again." });
      setIsAnalyzing(false);
    }
  }, [activeSessionId, inputFile, contextFile, inputPrompt, selectedModel, isAnalyzing, isUploading, updateMessage, startJobListener, authHeaders, loadSessions, storageKey]);

  const handleSuggestionClick = useCallback((s) => {
    setInputPrompt(normalizeSuggestionText(s));
    if (contextFile) {
      setSelectedModel("gemini");
    }
  }, [contextFile]);

  const handleClearFile = useCallback(() => {
    setInputFile(null);
    setUploadProgress(0);
    setUploadError("");
  }, []);

  const downloadRequest = useCallback(async (jobId, fallbackUrl, downloadUrl) => {
    const url = apiDownloadUrl({
      apiBase: API,
      jobId,
      downloadUrl,
      source: fallbackUrl,
    });

    // Only ever fetch the same-origin authenticated API. apiDownloadUrl returns
    // an empty string when it cannot build one, which we treat as a hard error
    // so the browser never issues a direct (CORS-blocked) R2 request.
    if (!isApiUrl(url, API)) {
      throw new Error("Download is not available for this result.");
    }

    return {
      url,
      headers: await authHeaders(),
    };
  }, [authHeaders]);

  const handleBlobDownload = useCallback(async (kind, source, jobId, providedKey, downloadUrl) => {
    const key = providedKey || downloadKeyFor(kind, jobId, source);
    setDownloadStatus(prev => ({ ...prev, [key]: { isLoading: true, error: "" } }));

    try {
      const { url, headers } = await downloadRequest(jobId, source, downloadUrl);
      const response = await fetch(url, { headers, redirect: "follow" });
      if (!response.ok) {
        throw new Error(`Download failed with status ${response.status}`);
      }
      const blob = await response.blob();
      triggerLocalBlobDownload(blob, filenameForBlob(kind, blob));
      setDownloadStatus(prev => {
        const next = { ...prev };
        delete next[key];
        return next;
      });
    } catch {
      setDownloadStatus(prev => ({
        ...prev,
        [key]: {
          isLoading: false,
          error: "Download failed. Please try again.",
        },
      }));
    }
  }, [downloadRequest]);

  const handleDownloadVideo = useCallback((url, jobId, key, downloadUrl) => {
    handleBlobDownload("video", url, jobId, key, downloadUrl);
  }, [handleBlobDownload]);

  const handleDownloadImage = useCallback((content, jobId, key, downloadUrl) => {
    handleBlobDownload("image", content, jobId, key, downloadUrl);
  }, [handleBlobDownload]);

  const handleNewChat = useCallback(() => {
    setView("chat");
    stopJobListener();
    setMessages([]);
    setInputPrompt("");
    setInputFile(null);
    setContextFile(null);
    setActiveSessionId(null);
    localStorage.removeItem(storageKey);
    setIsAnalyzing(false);
    setIsUploading(false);
    setUploadProgress(0);
    setUploadError("");
  }, [stopJobListener, storageKey]);

  const handleSelectSession = useCallback((sessionId) => {
    setView("chat");
    if (!sessionId || sessionId === activeSessionId) return;
    stopJobListener();
    setInputPrompt("");
    setInputFile(null);
    setUploadError("");
    loadSessionMessages(sessionId).catch(() => {});
  }, [activeSessionId, loadSessionMessages, stopJobListener]);

  const handleRenameSession = useCallback(async (sessionId, name) => {
    const cleanName = name.trim();
    if (!sessionId || !cleanName) return;
    // Optimistic update so the UI reflects the new name immediately.
    setSessions((current) =>
      current.map((s) => (s.session_id === sessionId ? { ...s, name: cleanName } : s))
    );
    try {
      await axios.patch(`${API}/sessions/${sessionId}`, { name: cleanName }, {
        headers: await authHeaders(),
      });
    } catch (err) {
      // Roll back to the server's truth if the save failed.
      await loadSessions().catch(() => {});
    }
  }, [authHeaders, loadSessions]);

  const handleTogglePinSession = useCallback(async (session) => {
    if (!session?.session_id) return;
    const nextPinned = !session.pinned;
    setSessions((current) =>
      current.map((s) => (s.session_id === session.session_id ? { ...s, pinned: nextPinned } : s))
    );
    try {
      await axios.patch(`${API}/sessions/${session.session_id}`, { pinned: nextPinned }, {
        headers: await authHeaders(),
      });
      await loadSessions();
    } catch (err) {
      await loadSessions().catch(() => {});
    }
  }, [authHeaders, loadSessions]);

  const handleDeleteSession = useCallback(async (sessionId) => {
    if (!sessionId) return;
    await axios.delete(`${API}/sessions/${sessionId}`, {
      headers: await authHeaders(),
    });
    if (sessionId === activeSessionId) {
      handleNewChat();
    }
    await loadSessions();
  }, [activeSessionId, authHeaders, handleNewChat, loadSessions]);

  return (
    <div
      data-testid="studio-container"
      style={{ background: "var(--bg-app)", color: "var(--text-primary)", fontFamily: "'Inter', sans-serif" }}
      className="h-screen w-full flex overflow-hidden"
    >
      <Sidebar
        onNewChat={handleNewChat}
        user={user}
        onSignOut={onSignOut}
        onProfileUpdate={onProfileUpdate}
        profileVersion={profileVersion}
        sessions={sessions}
        activeSessionId={activeSessionId}
        isLoadingSessions={isLoadingSession}
        onSelectSession={handleSelectSession}
        onRenameSession={handleRenameSession}
        onTogglePinSession={handleTogglePinSession}
        onDeleteSession={handleDeleteSession}
        activeView={view}
        onSelectView={setView}
      />

      <div className="flex-1 flex flex-col overflow-hidden">
        {view === "dataset" ? (
          <DatasetPage onNewDataset={() => {}} />
        ) : isEmpty ? (
          <div className="flex-1 flex flex-col items-center justify-center overflow-y-auto px-4">
            <div className="w-full" style={{ maxWidth: "768px" }}>
              <Greeting name={firstName} />
              <ChatInputBar
                prompt={inputPrompt}
                onPromptChange={setInputPrompt}
                onSend={handleSend}
                onFileSelect={handleFileSelect}
                inputFile={inputFile}
                onClearFile={handleClearFile}
                isUploading={isUploading}
                uploadProgress={uploadProgress}
                uploadError={uploadError}
                isAnalyzing={isAnalyzing}
                hasContextFile={Boolean(contextFile)}
                selectedModel={selectedModel}
                onModelSelect={setSelectedModel}
                models={MODELS}
                disabledModelIds={disabledModelIds}
                showSuggestions
                onSuggestionClick={handleSuggestionClick}
                centered
              />
            </div>
          </div>
        ) : (
          <>
            <ChatMessages
              messages={messages}
              onSuggestionClick={handleSuggestionClick}
              onDownload={handleDownloadVideo}
              onDownloadImage={handleDownloadImage}
              downloadStatus={downloadStatus}
            />
            <ChatInputBar
              prompt={inputPrompt}
              onPromptChange={setInputPrompt}
              onSend={handleSend}
              onFileSelect={handleFileSelect}
              inputFile={inputFile}
              onClearFile={handleClearFile}
              isUploading={isUploading}
              uploadProgress={uploadProgress}
              uploadError={uploadError}
              isAnalyzing={isAnalyzing}
              hasContextFile={Boolean(contextFile)}
              selectedModel={selectedModel}
              onModelSelect={setSelectedModel}
              models={MODELS}
              disabledModelIds={disabledModelIds}
              showSuggestions={false}
              onSuggestionClick={handleSuggestionClick}
            />
          </>
        )}
      </div>
    </div>
  );
}
