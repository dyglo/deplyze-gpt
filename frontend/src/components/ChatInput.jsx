import React, { useState } from "react";
import { Send } from "lucide-react";

const SLASH_COMMANDS = [
  { cmd: "/detect", label: "Switch to YOLO26 Detection",       model: "yolo26" },
  { cmd: "/seg",    label: "Switch to YOLO26-Seg Segmentation", model: "yolo26-seg" },
];

export default function ChatInput({
  prompt,
  onPromptChange,
  onAnalyze,
  isAnalyzing,
  hasFile,
  error,
  onModelSelect,
}) {
  const [showSlash, setShowSlash] = useState(false);

  const handleChange = (e) => {
    const val = e.target.value;
    onPromptChange(val);
    setShowSlash(val === "/");
  };

  const handleKeyDown = (e) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      if (!isAnalyzing && hasFile) onAnalyze();
    }
    if (e.key === "Escape") setShowSlash(false);
  };

  const handleSlashSelect = (cmd) => {
    onModelSelect(cmd.model);
    onPromptChange("");
    setShowSlash(false);
  };

  const canSend = !isAnalyzing && hasFile;

  return (
    <div
      className="flex-none pb-5 pt-3 px-5"
      style={{ borderTop: "1px solid #2A2A2A", background: "#111111" }}
    >
      {/* Slash command menu */}
      {showSlash && (
        <div
          data-testid="slash-command-menu"
          className="mb-2 rounded-xl overflow-hidden"
          style={{ border: "1px solid #2A2A2A", background: "#1A1A1A" }}
        >
          {SLASH_COMMANDS.map((cmd) => (
            <button
              key={cmd.cmd}
              onClick={() => handleSlashSelect(cmd)}
              className="w-full text-left px-4 py-3 text-sm flex items-center gap-3 transition-colors"
              onMouseEnter={(e) => (e.currentTarget.style.background = "#222")}
              onMouseLeave={(e) => (e.currentTarget.style.background = "transparent")}
            >
              <span
                className="text-xs"
                style={{ color: "#C96A2A", fontFamily: "'JetBrains Mono', monospace" }}
              >
                {cmd.cmd}
              </span>
              <span style={{ color: "#A1A1AA" }}>{cmd.label}</span>
            </button>
          ))}
        </div>
      )}

      {/* Inline error */}
      {error && (
        <p
          data-testid="inline-error-message"
          className="mb-2 text-xs flex items-start gap-1"
          style={{ color: "#EF4444" }}
        >
          <span className="mt-px">⚠</span>
          <span>{error}</span>
        </p>
      )}

      {/* Input row */}
      <div className="flex gap-2">
        <input
          data-testid="chat-prompt-input"
          type="text"
          value={prompt}
          onChange={handleChange}
          onKeyDown={handleKeyDown}
          placeholder="Describe what to analyze... (type / for commands)"
          className="flex-1 text-sm rounded-xl px-4 py-3 transition-all focus:outline-none"
          style={{
            background: "#1A1A1A",
            border: "1px solid #2A2A2A",
            color: "#fff",
          }}
          onFocus={(e) => (e.target.style.borderColor = "#C96A2A")}
          onBlur={(e) => (e.target.style.borderColor = "#2A2A2A")}
        />
        <button
          data-testid="analyze-send-button"
          onClick={onAnalyze}
          disabled={!canSend}
          className="flex-shrink-0 w-11 h-11 rounded-xl flex items-center justify-center transition-all"
          style={{
            background: canSend ? "#C96A2A" : "#1A1A1A",
            border: `1px solid ${canSend ? "#C96A2A" : "#2A2A2A"}`,
            cursor: canSend ? "pointer" : "not-allowed",
            color: canSend ? "#fff" : "#444",
          }}
          onMouseEnter={(e) => { if (canSend) e.currentTarget.style.background = "#E07A35"; }}
          onMouseLeave={(e) => { if (canSend) e.currentTarget.style.background = "#C96A2A"; }}
          aria-label="Analyze"
        >
          {isAnalyzing ? (
            <div
              className="w-4 h-4 rounded-full border-2 border-t-transparent animate-spin"
              style={{ borderColor: "#C96A2A", borderTopColor: "transparent" }}
            />
          ) : (
            <Send size={15} />
          )}
        </button>
      </div>
    </div>
  );
}
