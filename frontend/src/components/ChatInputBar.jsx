import React, { useRef, useState, useEffect, useCallback } from "react";
import { Paperclip, Send, X, Film, ChevronDown, Loader2 } from "lucide-react";

export default function ChatInputBar({
  prompt,
  onPromptChange,
  onSend,
  onFileSelect,
  inputFile,
  onClearFile,
  isUploading,
  isAnalyzing,
  selectedModel,
  onModelSelect,
  models,
}) {
  const fileInputRef = useRef(null);
  const textareaRef = useRef(null);
  const dropdownRef = useRef(null);
  const [dropdownOpen, setDropdownOpen] = useState(false);

  const currentModel = models.find(m => m.id === selectedModel) || models[0];
  const canSend = !isAnalyzing && !isUploading && !!inputFile && !inputFile?.uploading;

  const resizeTextarea = useCallback(() => {
    const ta = textareaRef.current;
    if (!ta) return;
    ta.style.height = "auto";
    ta.style.height = Math.min(ta.scrollHeight, 180) + "px";
  }, []);

  useEffect(() => {
    resizeTextarea();
    if (!prompt && textareaRef.current) {
      textareaRef.current.style.height = "44px";
    }
  }, [prompt, resizeTextarea]);

  useEffect(() => {
    const handler = e => {
      if (dropdownRef.current && !dropdownRef.current.contains(e.target)) {
        setDropdownOpen(false);
      }
    };
    document.addEventListener("mousedown", handler);
    return () => document.removeEventListener("mousedown", handler);
  }, []);

  const handleKeyDown = e => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      if (canSend) onSend();
    }
  };

  return (
    <div className="flex-none px-4 pb-5 pt-2" style={{ background: "#111111" }}>
      <div style={{ maxWidth: "720px", margin: "0 auto" }}>
        <div
          className="rounded-2xl"
          style={{ background: "#181818", border: "1px solid #252525" }}
        >
          {inputFile && (
            <div className="px-3 pt-3 pb-1 flex items-center gap-2">
              {inputFile.file_type === "image" && inputFile.objectUrl ? (
                <div className="relative inline-flex flex-shrink-0">
                  <img
                    data-testid="input-file-preview"
                    src={inputFile.objectUrl}
                    alt="Attached"
                    className="w-14 h-14 rounded-lg object-cover"
                    style={{ border: "1px solid #333" }}
                  />
                  {(isUploading || inputFile.uploading) && (
                    <div className="absolute inset-0 flex items-center justify-center rounded-lg"
                      style={{ background: "rgba(0,0,0,0.55)" }}>
                      <Loader2 size={14} className="animate-spin" style={{ color: "#C96A2A" }} />
                    </div>
                  )}
                  <button
                    data-testid="clear-file-button"
                    onClick={onClearFile}
                    className="absolute -top-1.5 -right-1.5 w-4 h-4 rounded-full flex items-center justify-center"
                    style={{ background: "#444", border: "1px solid #555" }}
                  >
                    <X size={9} style={{ color: "#ddd" }} />
                  </button>
                </div>
              ) : (
                <div className="flex items-center gap-1.5 px-2.5 py-1.5 rounded-lg"
                  style={{ background: "#232323", border: "1px solid #2E2E2E" }}>
                  <Film size={12} style={{ color: "#C96A2A" }} />
                  <span className="text-xs" style={{
                    color: "#A1A1AA", maxWidth: "160px",
                    overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap"
                  }}>
                    {inputFile.filename}
                  </span>
                  {(isUploading || inputFile.uploading) && (
                    <Loader2 size={11} className="animate-spin flex-shrink-0" style={{ color: "#C96A2A" }} />
                  )}
                  <button data-testid="clear-file-button" onClick={onClearFile} className="ml-0.5">
                    <X size={10} style={{ color: "#666" }} />
                  </button>
                </div>
              )}
            </div>
          )}

          <textarea
            data-testid="chat-prompt-input"
            ref={textareaRef}
            value={prompt}
            onChange={e => { onPromptChange(e.target.value); resizeTextarea(); }}
            onKeyDown={handleKeyDown}
            placeholder="Ask about your image or video..."
            rows={1}
            className="w-full resize-none text-sm px-4 focus:outline-none"
            style={{
              background: "transparent",
              color: "#E4E4E7",
              lineHeight: "1.55",
              paddingTop: "14px",
              paddingBottom: "10px",
              minHeight: "44px",
              maxHeight: "180px",
            }}
          />

          <div className="px-3 pb-3 flex items-center gap-2">
            <button
              data-testid="file-attach-button"
              onClick={() => fileInputRef.current?.click()}
              title="Attach image or video"
              className="w-8 h-8 rounded-lg flex items-center justify-center transition-all flex-shrink-0"
              style={{ background: "#232323" }}
              onMouseEnter={e => e.currentTarget.style.background = "#2C2C2C"}
              onMouseLeave={e => e.currentTarget.style.background = "#232323"}
            >
              <Paperclip size={14} style={{ color: "#666" }} />
            </button>

            <div className="relative" ref={dropdownRef}>
              <button
                data-testid="model-selector-button"
                onClick={() => setDropdownOpen(v => !v)}
                className="flex items-center gap-1.5 px-2.5 py-1.5 rounded-lg text-xs transition-all"
                style={{
                  background: "#232323",
                  color: "#888",
                  border: `1px solid ${dropdownOpen ? "#C96A2A" : "#2E2E2E"}`,
                }}
              >
                <currentModel.icon size={11} style={{ color: selectedModel !== "gemini" ? "#C96A2A" : "#777" }} />
                <span>{currentModel.label}</span>
                <ChevronDown size={10} style={{
                  transition: "transform 0.15s",
                  transform: dropdownOpen ? "rotate(180deg)" : "rotate(0deg)"
                }} />
              </button>

              {dropdownOpen && (
                <div
                  data-testid="model-dropdown"
                  className="absolute bottom-full mb-2 left-0 w-60 rounded-xl overflow-hidden z-50"
                  style={{ background: "#181818", border: "1px solid #2A2A2A", boxShadow: "0 8px 32px rgba(0,0,0,0.5)" }}
                >
                  {models.map(m => {
                    const isActive = selectedModel === m.id;
                    return (
                      <button
                        key={m.id}
                        data-testid={`model-option-${m.id}`}
                        onClick={() => { onModelSelect(m.id); setDropdownOpen(false); }}
                        className="w-full text-left px-3.5 py-3 flex items-start gap-3 transition-colors"
                        style={{ background: isActive ? "rgba(201,106,42,0.07)" : "transparent" }}
                        onMouseEnter={e => { if (!isActive) e.currentTarget.style.background = "#202020"; }}
                        onMouseLeave={e => { e.currentTarget.style.background = isActive ? "rgba(201,106,42,0.07)" : "transparent"; }}
                      >
                        <m.icon size={13} style={{ color: isActive ? "#C96A2A" : "#555", marginTop: "2px", flexShrink: 0 }} />
                        <div className="flex-1">
                          <p className="text-xs font-medium" style={{ color: isActive ? "#C96A2A" : "#DDD" }}>{m.label}</p>
                          <p className="text-xs mt-0.5" style={{ color: "#484848" }}>{m.desc}</p>
                        </div>
                        {isActive && (
                          <div className="w-1.5 h-1.5 rounded-full flex-shrink-0 mt-1.5" style={{ background: "#C96A2A" }} />
                        )}
                      </button>
                    );
                  })}
                </div>
              )}
            </div>

            <div className="flex-1" />

            <button
              data-testid="analyze-send-button"
              onClick={() => canSend && onSend()}
              disabled={!canSend}
              title={!inputFile ? "Attach a file first" : "Analyze"}
              className="w-8 h-8 rounded-lg flex items-center justify-center transition-all flex-shrink-0"
              style={{
                background: canSend ? "#C96A2A" : "#232323",
                cursor: canSend ? "pointer" : "not-allowed",
              }}
              onMouseEnter={e => { if (canSend) e.currentTarget.style.background = "#E07A35"; }}
              onMouseLeave={e => { if (canSend) e.currentTarget.style.background = canSend ? "#C96A2A" : "#232323"; }}
            >
              {isAnalyzing ? (
                <Loader2 size={13} className="animate-spin" style={{ color: "#fff" }} />
              ) : (
                <Send size={13} style={{ color: canSend ? "#fff" : "#404040" }} />
              )}
            </button>
          </div>
        </div>

        <p className="text-center text-xs mt-2" style={{ color: "#2A2A2A" }}>
          Attach an image or video · JPEG · PNG · WEBP · MP4 · max 100 MB
        </p>
      </div>

      <input
        data-testid="file-input"
        ref={fileInputRef}
        type="file"
        accept="image/jpeg,image/png,image/webp,video/mp4,video/quicktime,video/x-msvideo,.jpg,.jpeg,.png,.webp,.mp4,.mov,.avi"
        onChange={e => { if (e.target.files[0]) { onFileSelect(e.target.files[0]); e.target.value = ""; } }}
        className="hidden"
      />
    </div>
  );
}
