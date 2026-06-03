import React, { useRef, useEffect } from "react";
import { Download, Film, AlertCircle, Loader2 } from "lucide-react";

const MODEL_LABELS = {
  gemini: "Gemini 3-Flash",
  yolo26: "YOLO26 Detection",
  "yolo26-seg": "YOLO26 Segmentation",
  "yolo26-sem": "YOLO26 Semantic",
};

function MarkdownText({ content }) {
  const lines = (content || "").split("\n");
  return (
    <div className="space-y-0.5 text-sm" style={{ color: "#E4E4E7", lineHeight: "1.7" }}>
      {lines.map((line, i) => {
        if (!line.trim()) return <div key={i} className="h-2" />;
        if (line.startsWith("# "))
          return <h1 key={i} className="text-base font-bold mt-3 mb-1">{line.slice(2)}</h1>;
        if (line.startsWith("## "))
          return <h2 key={i} className="text-sm font-semibold mt-2 mb-0.5">{line.slice(3)}</h2>;
        if (line.startsWith("### "))
          return <h3 key={i} className="text-sm font-medium mt-2" style={{ color: "#C96A2A" }}>{line.slice(4)}</h3>;
        if (/^[-*]\s/.test(line))
          return (
            <div key={i} className="flex gap-2 ml-2">
              <span style={{ color: "#C96A2A", flexShrink: 0 }}>·</span>
              <span>{renderInline(line.slice(2))}</span>
            </div>
          );
        if (/^\d+[.)]\s/.test(line)) {
          const num = line.match(/^(\d+)[.)]/)[1];
          return (
            <div key={i} className="flex gap-2 ml-2">
              <span style={{ color: "#C96A2A", flexShrink: 0, fontFamily: "monospace", fontSize: "11px" }}>{num}.</span>
              <span>{renderInline(line.replace(/^\d+[.)]\s/, ""))}</span>
            </div>
          );
        }
        return <p key={i}>{renderInline(line)}</p>;
      })}
    </div>
  );
}

function renderInline(text) {
  return text.split(/(\*\*[^*]+\*\*)/g).map((part, i) =>
    part.startsWith("**") && part.endsWith("**")
      ? <strong key={i}>{part.slice(2, -2)}</strong>
      : part
  );
}

function SuggestionChips({ suggestions, onSuggestionClick }) {
  if (!suggestions?.length) return null;
  return (
    <div className="mt-3 flex flex-wrap gap-2">
      {suggestions.map((s, i) => (
        <button
          key={i}
          data-testid="suggestion-chip"
          onClick={() => onSuggestionClick(s)}
          className="text-xs px-3 py-1.5 rounded-full transition-all"
          style={{ background: "#1A1A1A", border: "1px solid #252525", color: "#777" }}
          onMouseEnter={e => { e.currentTarget.style.borderColor = "#C96A2A"; e.currentTarget.style.color = "#fff"; }}
          onMouseLeave={e => { e.currentTarget.style.borderColor = "#252525"; e.currentTarget.style.color = "#777"; }}
        >
          {s}
        </button>
      ))}
    </div>
  );
}

function Avatar() {
  return (
    <div
      className="w-7 h-7 rounded-full flex items-center justify-center flex-shrink-0 text-xs font-bold text-white"
      style={{ background: "#C96A2A" }}
    >
      D
    </div>
  );
}

function UserMessage({ message }) {
  const { prompt, file } = message;
  return (
    <div data-testid="user-message" className="flex justify-end mb-5">
      <div style={{ maxWidth: "min(640px, 80%)" }}>
        {file && (
          <div className="mb-2 flex justify-end">
            {file.file_type === "image" && file.objectUrl ? (
              <img
                data-testid="user-message-image"
                src={file.objectUrl}
                alt={file.filename}
                className="rounded-xl max-h-48 max-w-xs object-cover"
                style={{ border: "1px solid #2A2A2A" }}
              />
            ) : (
              <div
                className="flex items-center gap-2 px-3 py-2 rounded-xl text-xs"
                style={{ background: "#1A1A1A", border: "1px solid #2A2A2A", color: "#A1A1AA" }}
              >
                <Film size={13} style={{ color: "#C96A2A" }} />
                <span style={{ maxWidth: "180px", overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>{file.filename}</span>
              </div>
            )}
          </div>
        )}
        {prompt && (
          <div
            data-testid="user-message-text"
            className="px-4 py-3 rounded-2xl text-sm"
            style={{ background: "#1E1E1E", color: "#E4E4E7", border: "1px solid #252525" }}
          >
            {prompt}
          </div>
        )}
      </div>
    </div>
  );
}

function AssistantMessage({ message, onSuggestionClick, onDownload }) {
  const { isLoading, result, error, model, videoJob } = message;

  if (isLoading && !videoJob) {
    return (
      <div data-testid="assistant-loading" className="flex gap-3 mb-5">
        <Avatar />
        <div className="flex-1">
          <p className="text-xs mb-1.5" style={{ color: "#444" }}>{MODEL_LABELS[model] || model}</p>
          <div className="flex items-center gap-2 text-sm" style={{ color: "#555" }}>
            <Loader2 size={13} className="animate-spin" style={{ color: "#C96A2A" }} />
            <span>Analyzing...</span>
          </div>
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div data-testid="assistant-error" className="flex gap-3 mb-5">
        <Avatar />
        <div className="flex-1">
          <p className="text-xs mb-1.5" style={{ color: "#444" }}>{MODEL_LABELS[model] || model}</p>
          <div className="flex items-start gap-2 text-sm" style={{ color: "#EF4444" }}>
            <AlertCircle size={14} className="flex-shrink-0 mt-0.5" />
            <span>{error}</span>
          </div>
        </div>
      </div>
    );
  }

  if (videoJob && (videoJob.status === "queued" || videoJob.status === "processing")) {
    return (
      <div data-testid="assistant-video-progress" className="flex gap-3 mb-5">
        <Avatar />
        <div className="flex-1">
          <p className="text-xs mb-1.5" style={{ color: "#444" }}>{MODEL_LABELS[model] || model}</p>
          <div className="space-y-2" style={{ maxWidth: "300px" }}>
            <p className="text-sm" style={{ color: "#A1A1AA" }}>
              {videoJob.status === "queued" ? "Video queued for processing..." : `Processing — ${videoJob.progress}%`}
            </p>
            <div data-testid="processing-progress-bar" className="w-full h-1 rounded-full overflow-hidden" style={{ background: "#252525" }}>
              <div
                className="h-full rounded-full transition-all duration-500"
                style={{ width: `${Math.max(videoJob.progress || 3, 3)}%`, background: "#C96A2A" }}
              />
            </div>
          </div>
        </div>
      </div>
    );
  }

  if (result?.type === "image") {
    const counts = (result.detections || []).reduce((a, d) => { a[d.class] = (a[d.class] || 0) + 1; return a; }, {});
    return (
      <div data-testid="assistant-image-result" className="flex gap-3 mb-5">
        <Avatar />
        <div style={{ maxWidth: "min(640px, 90%)" }}>
          <p className="text-xs mb-1.5" style={{ color: "#444" }}>{MODEL_LABELS[model] || model}</p>
          <img
            data-testid="output-annotated-image"
            src={result.content}
            alt="Analysis result"
            className="rounded-xl"
            style={{ maxWidth: "100%", maxHeight: "480px", objectFit: "contain", border: "1px solid #252525", display: "block" }}
          />
          {result.detections?.length > 0 && (
            <div className="mt-2 flex flex-wrap items-center gap-1.5">
              <span className="text-xs font-medium" style={{ color: "#C96A2A" }}>{result.detections.length} detected:</span>
              {Object.entries(counts).slice(0, 6).map(([cls, cnt]) => (
                <span key={cls} className="text-xs px-2 py-0.5 rounded-full"
                  style={{ background: "#1A1A1A", color: "#888", border: "1px solid #252525" }}>
                  {cls}{cnt > 1 ? ` x${cnt}` : ""}
                </span>
              ))}
            </div>
          )}
          <SuggestionChips suggestions={result.suggestions} onSuggestionClick={onSuggestionClick} />
        </div>
      </div>
    );
  }

  if (result?.type === "text") {
    return (
      <div data-testid="assistant-text-result" className="flex gap-3 mb-5">
        <Avatar />
        <div style={{ maxWidth: "min(640px, 90%)" }}>
          <p className="text-xs mb-1.5" style={{ color: "#444" }}>{MODEL_LABELS[model] || model}</p>
          <MarkdownText content={result.content} />
          <SuggestionChips suggestions={result.suggestions} onSuggestionClick={onSuggestionClick} />
        </div>
      </div>
    );
  }

  if (result?.type === "video") {
    return (
      <div data-testid="assistant-video-result" className="flex gap-3 mb-5">
        <Avatar />
        <div style={{ maxWidth: "min(640px, 90%)" }}>
          <p className="text-xs mb-1.5" style={{ color: "#444" }}>{MODEL_LABELS[model] || model}</p>
          <video
            data-testid="output-video-player"
            src={result.content}
            controls
            playsInline
            className="rounded-xl"
            style={{ maxWidth: "100%", maxHeight: "400px", border: "1px solid #252525", display: "block" }}
          />
          <div className="mt-2">
            <button
              data-testid="download-video-button"
              onClick={() => onDownload(result.content)}
              className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-medium transition-all"
              style={{ background: "#C96A2A", color: "#fff" }}
              onMouseEnter={e => e.currentTarget.style.background = "#E07A35"}
              onMouseLeave={e => e.currentTarget.style.background = "#C96A2A"}
            >
              <Download size={12} /> Download
            </button>
          </div>
          <SuggestionChips suggestions={result.suggestions} onSuggestionClick={onSuggestionClick} />
        </div>
      </div>
    );
  }

  return null;
}

function EmptyState({ onSuggestionClick }) {
  const prompts = ["Detect all objects", "Segment the scene", "Describe this image in detail", "Count people visible"];
  return (
    <div data-testid="chat-empty-state" className="flex-1 flex flex-col items-center justify-center px-6">
      <div className="text-center" style={{ maxWidth: "480px" }}>
        <div
          className="w-12 h-12 rounded-2xl flex items-center justify-center mx-auto mb-5"
          style={{ background: "rgba(201,106,42,0.08)", border: "1px solid rgba(201,106,42,0.18)" }}
        >
          <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="#C96A2A" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
            <path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z" /><circle cx="12" cy="12" r="3" />
          </svg>
        </div>
        <h2 className="text-2xl font-semibold mb-2" style={{ color: "#E4E4E7", letterSpacing: "-0.3px" }}>
          What would you like to analyze today?
        </h2>
        <p className="text-sm mb-6" style={{ color: "#484848" }}>
          Attach an image or video and ask me anything about it
        </p>
        <div className="flex flex-wrap gap-2 justify-center">
          {prompts.map(s => (
            <button
              key={s}
              data-testid="empty-state-suggestion"
              onClick={() => onSuggestionClick(s)}
              className="text-xs px-3 py-2 rounded-full transition-all"
              style={{ background: "#1A1A1A", border: "1px solid #222", color: "#666" }}
              onMouseEnter={e => { e.currentTarget.style.borderColor = "#C96A2A"; e.currentTarget.style.color = "#ddd"; }}
              onMouseLeave={e => { e.currentTarget.style.borderColor = "#222"; e.currentTarget.style.color = "#666"; }}
            >
              {s}
            </button>
          ))}
        </div>
      </div>
    </div>
  );
}

export default function ChatMessages({ messages, onSuggestionClick, onDownload }) {
  const endRef = useRef(null);

  useEffect(() => {
    endRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  if (messages.length === 0) {
    return <EmptyState onSuggestionClick={onSuggestionClick} />;
  }

  return (
    <div data-testid="chat-messages-container" className="flex-1 overflow-y-auto px-5 pt-6 pb-2">
      <div style={{ maxWidth: "720px", margin: "0 auto" }}>
        {messages.map(msg =>
          msg.type === "user"
            ? <UserMessage key={msg.id} message={msg} />
            : <AssistantMessage key={msg.id} message={msg} onSuggestionClick={onSuggestionClick} onDownload={onDownload} />
        )}
        <div ref={endRef} />
      </div>
    </div>
  );
}
