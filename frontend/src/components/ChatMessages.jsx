import React, { useRef, useEffect } from "react";
import { Download, Film, AlertCircle, Loader2 } from "lucide-react";

const MODEL_LABELS = {
  gemini: "Gemini 2.5 Flash-Lite",
  yolo26: "YOLO26 Detection",
  "yolo26-seg": "YOLO26 Segmentation",
  "yolo26-sem": "YOLO26 Semantic",
};

function MarkdownText({ content }) {
  const lines = (content || "").split("\n");
  return (
    <div className="space-y-0.5 text-[15px]" style={{ color: "var(--text-primary)", lineHeight: "1.7" }}>
      {lines.map((line, i) => {
        if (!line.trim()) return <div key={i} className="h-2" />;
        if (line.startsWith("# "))
          return <h1 key={i} className="text-lg font-semibold mt-3 mb-1">{line.slice(2)}</h1>;
        if (line.startsWith("## "))
          return <h2 key={i} className="text-base font-semibold mt-2 mb-0.5">{line.slice(3)}</h2>;
        if (line.startsWith("### "))
          return <h3 key={i} className="text-[15px] font-medium mt-2" style={{ color: "var(--accent)" }}>{line.slice(4)}</h3>;
        if (/^[-*]\s/.test(line))
          return (
            <div key={i} className="flex gap-2 ml-2">
              <span style={{ color: "var(--accent)", flexShrink: 0 }}>·</span>
              <span>{renderInline(line.slice(2))}</span>
            </div>
          );
        if (/^\d+[.)]\s/.test(line)) {
          const num = line.match(/^(\d+)[.)]/)[1];
          return (
            <div key={i} className="flex gap-2 ml-2">
              <span style={{ color: "var(--accent)", flexShrink: 0, fontFamily: "monospace", fontSize: "12px" }}>{num}.</span>
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
          className="text-[13px] px-3 py-1.5 rounded-full transition-colors"
          style={{ background: "var(--bg-elevated)", border: "1px solid var(--border-subtle)", color: "var(--text-secondary)" }}
          onMouseEnter={e => { e.currentTarget.style.background = "var(--bg-hover)"; e.currentTarget.style.color = "var(--text-primary)"; }}
          onMouseLeave={e => { e.currentTarget.style.background = "var(--bg-elevated)"; e.currentTarget.style.color = "var(--text-secondary)"; }}
        >
          {s}
        </button>
      ))}
    </div>
  );
}

function downloadKeyFor(kind, jobId, source) {
  return `${kind}:${jobId || source || "output"}`;
}

function Avatar() {
  return (
    <div className="w-7 h-7 flex items-center justify-center flex-shrink-0 mt-0.5">
      <svg width="20" height="20" viewBox="0 0 24 24" fill="none">
        <path
          d="M12 2.2c.35 2.5.9 3.6 2 4.6m0 0c1.1 1 2.2 1.5 4.6 1.85M14 6.8 18.6 8.65M12 2.2c-.35 2.5-.9 3.6-2 4.6m0 0c-1.1 1-2.2 1.5-4.6 1.85M10 6.8 5.4 8.65M12 21.8c.35-2.5.9-3.6 2-4.6m0 0c1.1-1 2.2-1.5 4.6-1.85M14 17.2l4.6-1.85M12 21.8c-.35-2.5-.9-3.6-2-4.6m0 0c-1.1-1-2.2-1.5-4.6-1.85M10 17.2 5.4 15.35M2.2 12c2.5.35 3.6.9 4.6 2m0 0c1 1.1 1.5 2.2 1.85 4.6M6.8 14l1.85 4.6M2.2 12c2.5-.35 3.6-.9 4.6-2m0 0c1-1.1 1.5-2.2 1.85-4.6M6.8 10 8.65 5.4M21.8 12c-2.5.35-3.6.9-4.6 2m0 0c-1 1.1-1.5 2.2-1.85 4.6M17.2 14l-1.85 4.6M21.8 12c-2.5-.35-3.6-.9-4.6-2m0 0c-1-1.1-1.5-2.2-1.85-4.6M17.2 10l-1.85-4.6"
          stroke="var(--accent)"
          strokeWidth="1.6"
          strokeLinecap="round"
          strokeLinejoin="round"
        />
      </svg>
    </div>
  );
}

function UserMessage({ message }) {
  const { prompt, file } = message;
  return (
    <div data-testid="user-message" className="flex justify-end mb-6">
      <div style={{ maxWidth: "min(640px, 80%)" }}>
        {file && (
          <div className="mb-2 flex justify-end">
            {file.file_type === "image" && file.objectUrl ? (
              <img
                data-testid="user-message-image"
                src={file.objectUrl}
                alt={file.filename}
                className="rounded-2xl max-h-48 max-w-xs object-cover"
                style={{ border: "1px solid var(--border-subtle)" }}
              />
            ) : (
              <div
                className="flex items-center gap-2 px-3 py-2 rounded-xl text-xs"
                style={{ background: "var(--bg-elevated)", border: "1px solid var(--border-subtle)", color: "var(--text-secondary)" }}
              >
                <Film size={13} style={{ color: "var(--accent)" }} />
                <span style={{ maxWidth: "180px", overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>{file.filename}</span>
              </div>
            )}
          </div>
        )}
        {prompt && (
          <div
            data-testid="user-message-text"
            className="px-4 py-2.5 rounded-2xl text-[15px]"
            style={{ background: "var(--bg-elevated)", color: "var(--text-primary)" }}
          >
            {prompt}
          </div>
        )}
      </div>
    </div>
  );
}

function AssistantMessage({ message, onSuggestionClick, onDownload, onDownloadImage, downloadStatus }) {
  const { isLoading, result, error, model, videoJob } = message;

  if (isLoading && !videoJob) {
    return (
      <div data-testid="assistant-loading" className="flex gap-3 mb-6">
        <Avatar />
        <div className="flex-1">
          <p className="text-xs mb-1.5" style={{ color: "var(--text-faint)" }}>{MODEL_LABELS[model] || model}</p>
          <div className="flex items-center gap-2 text-[15px]" style={{ color: "var(--text-muted)" }}>
            <Loader2 size={14} className="animate-spin" style={{ color: "var(--accent)" }} />
            <span>Analyzing...</span>
          </div>
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div data-testid="assistant-error" className="flex gap-3 mb-6">
        <Avatar />
        <div className="flex-1">
          <p className="text-xs mb-1.5" style={{ color: "var(--text-faint)" }}>{MODEL_LABELS[model] || model}</p>
          <div className="flex items-start gap-2 text-[15px]" style={{ color: "#e06a5a" }}>
            <AlertCircle size={15} className="flex-shrink-0 mt-0.5" />
            <span>{error}</span>
          </div>
        </div>
      </div>
    );
  }

  if (videoJob && (videoJob.status === "queued" || videoJob.status === "processing")) {
    return (
      <div data-testid="assistant-video-progress" className="flex gap-3 mb-6">
        <Avatar />
        <div className="flex-1">
          <p className="text-xs mb-1.5" style={{ color: "var(--text-faint)" }}>{MODEL_LABELS[model] || model}</p>
          <div className="space-y-2" style={{ maxWidth: "300px" }}>
            <p className="text-[15px]" style={{ color: "var(--text-secondary)" }}>
              {videoJob.status === "queued" ? "Video queued for processing..." : `Processing — ${videoJob.progress}%`}
            </p>
            <div data-testid="processing-progress-bar" className="w-full h-1.5 rounded-full overflow-hidden" style={{ background: "#3a3937" }}>
              <div
                className="h-full rounded-full transition-all duration-500 progress-shimmer"
                style={{
                  width: `${Math.max(videoJob.progress || 3, 3)}%`,
                  background: "linear-gradient(90deg, #d97757 0%, #e89070 50%, #d97757 100%)",
                  backgroundSize: "200% 100%",
                }}
              />
            </div>
          </div>
        </div>
      </div>
    );
  }

  if (result?.type === "image") {
    const counts = (result.detections || []).reduce((a, d) => { a[d.class] = (a[d.class] || 0) + 1; return a; }, {});
    const downloadKey = downloadKeyFor("image", result.job_id, result.content);
    const downloadState = downloadStatus?.[downloadKey] || {};
    return (
      <div data-testid="assistant-image-result" className="flex gap-3 mb-6">
        <Avatar />
        <div style={{ maxWidth: "min(640px, 90%)" }}>
          <p className="text-xs mb-1.5" style={{ color: "var(--text-faint)" }}>{MODEL_LABELS[model] || model}</p>
          <img
            data-testid="output-annotated-image"
            src={result.content}
            alt="Analysis result"
            className="rounded-2xl"
            style={{ maxWidth: "100%", maxHeight: "480px", objectFit: "contain", border: "1px solid var(--border-subtle)", display: "block" }}
          />
          <div className="mt-2">
            <button
              data-testid="download-image-button"
              type="button"
              onClick={() => onDownloadImage(result.content, result.job_id, downloadKey, result.download_url)}
              disabled={downloadState.isLoading}
              aria-busy={downloadState.isLoading ? "true" : "false"}
              className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-[13px] font-medium transition-colors"
              style={{
                background: downloadState.isLoading ? "var(--accent-hover)" : "var(--accent)",
                color: "#fff",
                cursor: downloadState.isLoading ? "progress" : "pointer",
                opacity: downloadState.isLoading ? 0.85 : 1,
              }}
              onMouseEnter={e => { if (!downloadState.isLoading) e.currentTarget.style.background = "var(--accent-hover)"; }}
              onMouseLeave={e => { if (!downloadState.isLoading) e.currentTarget.style.background = "var(--accent)"; }}
            >
              {downloadState.isLoading ? <Loader2 size={13} className="animate-spin" /> : <Download size={13} />}
              {downloadState.isLoading ? "Downloading..." : "Download"}
            </button>
            {downloadState.error && (
              <p data-testid="download-image-error" className="mt-1.5 text-[13px]" style={{ color: "#e06a5a" }}>
                {downloadState.error}
              </p>
            )}
          </div>
          {result.detections?.length > 0 && (
            <div className="mt-2 flex flex-wrap items-center gap-1.5">
              <span className="text-[13px] font-medium" style={{ color: "var(--accent)" }}>{result.detections.length} detected:</span>
              {Object.entries(counts).slice(0, 6).map(([cls, cnt]) => (
                <span key={cls} className="text-xs px-2 py-0.5 rounded-full"
                  style={{ background: "var(--bg-elevated)", color: "var(--text-secondary)", border: "1px solid var(--border-subtle)" }}>
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
      <div data-testid="assistant-text-result" className="flex gap-3 mb-6">
        <Avatar />
        <div style={{ maxWidth: "min(640px, 90%)" }}>
          <p className="text-xs mb-1.5" style={{ color: "var(--text-faint)" }}>{MODEL_LABELS[model] || model}</p>
          <MarkdownText content={result.content} />
          <SuggestionChips suggestions={result.suggestions} onSuggestionClick={onSuggestionClick} />
        </div>
      </div>
    );
  }

  if (result?.type === "video") {
    const downloadKey = downloadKeyFor("video", result.job_id, result.content);
    const downloadState = downloadStatus?.[downloadKey] || {};
    return (
      <div data-testid="assistant-video-result" className="flex gap-3 mb-6">
        <Avatar />
        <div style={{ maxWidth: "min(640px, 90%)" }}>
          <p className="text-xs mb-1.5" style={{ color: "var(--text-faint)" }}>{MODEL_LABELS[model] || model}</p>
          <video
            data-testid="output-video-player"
            src={result.content}
            controls
            playsInline
            className="rounded-2xl"
            style={{ maxWidth: "100%", maxHeight: "400px", border: "1px solid var(--border-subtle)", display: "block" }}
          />
          <div className="mt-2">
            <button
              data-testid="download-video-button"
              type="button"
              onClick={() => onDownload(result.content, result.job_id, downloadKey, result.download_url)}
              disabled={downloadState.isLoading}
              aria-busy={downloadState.isLoading ? "true" : "false"}
              className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-[13px] font-medium transition-colors"
              style={{
                background: downloadState.isLoading ? "var(--accent-hover)" : "var(--accent)",
                color: "#fff",
                cursor: downloadState.isLoading ? "progress" : "pointer",
                opacity: downloadState.isLoading ? 0.85 : 1,
              }}
              onMouseEnter={e => { if (!downloadState.isLoading) e.currentTarget.style.background = "var(--accent-hover)"; }}
              onMouseLeave={e => { if (!downloadState.isLoading) e.currentTarget.style.background = "var(--accent)"; }}
            >
              {downloadState.isLoading ? <Loader2 size={13} className="animate-spin" /> : <Download size={13} />}
              {downloadState.isLoading ? "Downloading..." : "Download"}
            </button>
            {downloadState.error && (
              <p data-testid="download-video-error" className="mt-1.5 text-[13px]" style={{ color: "#e06a5a" }}>
                {downloadState.error}
              </p>
            )}
          </div>
          <SuggestionChips suggestions={result.suggestions} onSuggestionClick={onSuggestionClick} />
        </div>
      </div>
    );
  }

  return null;
}

export default function ChatMessages({ messages, onSuggestionClick, onDownload, onDownloadImage, downloadStatus }) {
  const endRef = useRef(null);

  useEffect(() => {
    endRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  if (messages.length === 0) return null;

  return (
    <div data-testid="chat-messages-container" className="flex-1 overflow-y-auto px-5 pt-6 pb-2">
      <div style={{ maxWidth: "768px", margin: "0 auto" }}>
        {messages.map(msg =>
          msg.type === "user"
            ? <UserMessage key={msg.id} message={msg} />
            : (
              <AssistantMessage
                key={msg.id}
                message={msg}
                onSuggestionClick={onSuggestionClick}
                onDownload={onDownload}
                onDownloadImage={onDownloadImage}
                downloadStatus={downloadStatus}
              />
            )
        )}
        <div ref={endRef} />
      </div>
    </div>
  );
}
