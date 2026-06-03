import React, { useRef, useState, useEffect, useCallback } from "react";
import { Plus, ArrowUp, X, Film, ChevronDown, Loader2, Mic, AudioLines, Sparkles, Layers, FileText, Users } from "lucide-react";

const STARTER_CHIPS = [
  { label: "Detect all objects", icon: Sparkles },
  { label: "Segment the scene", icon: Layers },
  { label: "Describe this image in detail", icon: FileText },
  { label: "Count people visible", icon: Users },
];

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
  showSuggestions,
  onSuggestionClick,
  centered,
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
      textareaRef.current.style.height = "24px";
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
    <div
      className={centered ? "px-4" : "flex-none px-4 pb-4 pt-2"}
      style={{ background: "var(--bg-app)" }}
    >
      <div style={{ maxWidth: "768px", margin: "0 auto" }}>
        <div
          className="rounded-[1.75rem]"
          style={{
            background: "var(--bg-input)",
            border: "1px solid var(--border-subtle)",
            boxShadow: "0 2px 8px rgba(0,0,0,0.18)",
          }}
        >
          {inputFile && (
            <div className="px-4 pt-3.5 pb-1 flex items-center gap-2">
              {inputFile.file_type === "image" && inputFile.objectUrl ? (
                <div className="relative inline-flex flex-shrink-0">
                  <img
                    data-testid="input-file-preview"
                    src={inputFile.objectUrl}
                    alt="Attached"
                    className="w-14 h-14 rounded-xl object-cover"
                    style={{ border: "1px solid var(--border-subtle)" }}
                  />
                  {(isUploading || inputFile.uploading) && (
                    <div className="absolute inset-0 flex items-center justify-center rounded-xl"
                      style={{ background: "rgba(0,0,0,0.5)" }}>
                      <Loader2 size={14} className="animate-spin" style={{ color: "var(--accent)" }} />
                    </div>
                  )}
                  <button
                    data-testid="clear-file-button"
                    onClick={onClearFile}
                    className="absolute -top-1.5 -right-1.5 w-5 h-5 rounded-full flex items-center justify-center"
                    style={{ background: "#54524c", border: "1px solid #6a675f" }}
                  >
                    <X size={10} style={{ color: "var(--text-primary)" }} />
                  </button>
                </div>
              ) : (
                <div className="flex items-center gap-1.5 px-3 py-2 rounded-xl"
                  style={{ background: "var(--bg-hover)", border: "1px solid var(--border-subtle)" }}>
                  <Film size={13} style={{ color: "var(--accent)" }} />
                  <span className="text-xs" style={{
                    color: "var(--text-secondary)", maxWidth: "160px",
                    overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap"
                  }}>
                    {inputFile.filename}
                  </span>
                  {(isUploading || inputFile.uploading) && (
                    <Loader2 size={11} className="animate-spin flex-shrink-0" style={{ color: "var(--accent)" }} />
                  )}
                  <button data-testid="clear-file-button" onClick={onClearFile} className="ml-0.5">
                    <X size={11} style={{ color: "var(--text-muted)" }} />
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
            placeholder="How can I help you today?"
            rows={1}
            className="w-full resize-none text-[15px] px-5 focus:outline-none"
            style={{
              boxSizing: "content-box",
              background: "transparent",
              color: "var(--text-primary)",
              lineHeight: "24px",
              paddingTop: "16px",
              paddingBottom: "12px",
              minHeight: "24px",
              maxHeight: "180px",
            }}
          />

          <div className="px-3 pb-3 pt-1 flex items-center gap-2">
            <button
              data-testid="file-attach-button"
              onClick={() => fileInputRef.current?.click()}
              title="Attach image or video"
              className="w-8 h-8 rounded-full flex items-center justify-center transition-colors flex-shrink-0"
              style={{ background: "transparent", border: "1px solid var(--border-subtle)" }}
              onMouseEnter={e => e.currentTarget.style.background = "var(--bg-hover)"}
              onMouseLeave={e => e.currentTarget.style.background = "transparent"}
            >
              <Plus size={17} style={{ color: "var(--text-secondary)" }} />
            </button>

            <div className="flex-1" />

            {/* Model selector — names/logic unchanged */}
            <div className="relative" ref={dropdownRef}>
              <button
                data-testid="model-selector-button"
                onClick={() => setDropdownOpen(v => !v)}
                className="flex items-center gap-1.5 px-2.5 py-1.5 rounded-lg text-[13px] transition-colors"
                style={{ background: "transparent", color: "var(--text-secondary)" }}
                onMouseEnter={e => e.currentTarget.style.background = "var(--bg-hover)"}
                onMouseLeave={e => e.currentTarget.style.background = "transparent"}
              >
                <currentModel.icon size={13} style={{ color: selectedModel !== "gemini" ? "var(--accent)" : "var(--text-secondary)" }} />
                <span className="font-medium">{currentModel.label}</span>
                <ChevronDown size={13} style={{
                  transition: "transform 0.15s",
                  transform: dropdownOpen ? "rotate(180deg)" : "rotate(0deg)",
                  color: "var(--text-muted)",
                }} />
              </button>

              {dropdownOpen && (
                <div
                  data-testid="model-dropdown"
                  className="absolute bottom-full mb-2 right-0 w-64 rounded-2xl overflow-hidden z-50 py-1.5"
                  style={{ background: "var(--bg-elevated)", border: "1px solid var(--border-subtle)", boxShadow: "0 12px 40px rgba(0,0,0,0.5)" }}
                >
                  {models.map(m => {
                    const isActive = selectedModel === m.id;
                    return (
                      <button
                        key={m.id}
                        data-testid={`model-option-${m.id}`}
                        onClick={() => { onModelSelect(m.id); setDropdownOpen(false); }}
                        className="w-full text-left px-3 py-2 flex items-start gap-3 transition-colors mx-0"
                        style={{ background: "transparent" }}
                        onMouseEnter={e => { e.currentTarget.style.background = "var(--bg-hover)"; }}
                        onMouseLeave={e => { e.currentTarget.style.background = "transparent"; }}
                      >
                        <m.icon size={15} style={{ color: isActive ? "var(--accent)" : "var(--text-muted)", marginTop: "2px", flexShrink: 0 }} />
                        <div className="flex-1 min-w-0">
                          <p className="text-[13px] font-medium" style={{ color: "var(--text-primary)" }}>{m.label}</p>
                          <p className="text-xs mt-0.5" style={{ color: "var(--text-muted)" }}>{m.desc}</p>
                        </div>
                        {isActive && (
                          <svg className="flex-shrink-0 mt-1" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="var(--accent)" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
                            <path d="M20 6 9 17l-5-5" />
                          </svg>
                        )}
                      </button>
                    );
                  })}
                </div>
              )}
            </div>

            {canSend ? (
              <button
                data-testid="analyze-send-button"
                onClick={onSend}
                title="Analyze"
                className="w-8 h-8 rounded-full flex items-center justify-center transition-colors flex-shrink-0"
                style={{ background: "var(--accent)" }}
                onMouseEnter={e => e.currentTarget.style.background = "var(--accent-hover)"}
                onMouseLeave={e => e.currentTarget.style.background = "var(--accent)"}
              >
                {isAnalyzing ? (
                  <Loader2 size={15} className="animate-spin" style={{ color: "#fff" }} />
                ) : (
                  <ArrowUp size={17} strokeWidth={2.25} style={{ color: "#fff" }} />
                )}
              </button>
            ) : isAnalyzing ? (
              <div
                data-testid="analyze-send-button"
                className="w-8 h-8 rounded-full flex items-center justify-center flex-shrink-0"
                style={{ background: "var(--accent)" }}
              >
                <Loader2 size={15} className="animate-spin" style={{ color: "#fff" }} />
              </div>
            ) : (
              <>
                <button
                  title="Dictate"
                  className="w-8 h-8 rounded-full flex items-center justify-center transition-colors flex-shrink-0"
                  style={{ background: "transparent" }}
                  onMouseEnter={e => e.currentTarget.style.background = "var(--bg-hover)"}
                  onMouseLeave={e => e.currentTarget.style.background = "transparent"}
                >
                  <Mic size={16} style={{ color: "var(--text-secondary)" }} />
                </button>
                <button
                  data-testid="analyze-send-button"
                  onClick={() => canSend && onSend()}
                  disabled
                  title="Attach a file first"
                  className="w-8 h-8 rounded-full flex items-center justify-center flex-shrink-0"
                  style={{ background: "transparent", cursor: "not-allowed" }}
                >
                  <AudioLines size={16} style={{ color: "var(--text-secondary)" }} />
                </button>
              </>
            )}
          </div>
        </div>

        {showSuggestions ? (
          <div className="flex flex-wrap gap-2 justify-center mt-4">
            {STARTER_CHIPS.map(({ label, icon: Icon }) => (
              <button
                key={label}
                data-testid="empty-state-suggestion"
                onClick={() => onSuggestionClick?.(label)}
                className="flex items-center gap-2 text-[13px] px-3.5 py-2 rounded-xl transition-colors"
                style={{ background: "var(--bg-elevated)", border: "1px solid var(--border-subtle)", color: "var(--text-secondary)" }}
                onMouseEnter={e => { e.currentTarget.style.background = "var(--bg-hover)"; e.currentTarget.style.color = "var(--text-primary)"; }}
                onMouseLeave={e => { e.currentTarget.style.background = "var(--bg-elevated)"; e.currentTarget.style.color = "var(--text-secondary)"; }}
              >
                <Icon size={15} style={{ color: "var(--accent)" }} />
                {label}
              </button>
            ))}
          </div>
        ) : (
          <p className="text-center text-xs mt-2.5" style={{ color: "var(--text-faint)" }}>
            Attach an image or video · JPEG · PNG · WEBP · MP4 · max 100 MB
          </p>
        )}
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
