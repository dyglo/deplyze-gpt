import React from "react";
import { Download, Eye } from "lucide-react";

// Simple inline markdown renderer
function MarkdownText({ content }) {
  const lines = (content || "").split("\n");
  return (
    <div className="space-y-0.5 text-sm" style={{ color: "#E4E4E7", lineHeight: "1.7" }}>
      {lines.map((line, i) => {
        if (!line.trim()) return <div key={i} className="h-3" />;
        if (line.startsWith("# "))
          return <h1 key={i} className="text-lg font-bold mt-4 mb-1">{line.slice(2)}</h1>;
        if (line.startsWith("## "))
          return <h2 key={i} className="text-base font-semibold mt-3 mb-0.5">{line.slice(3)}</h2>;
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
              <span style={{ color: "#C96A2A", flexShrink: 0, fontFamily: "'JetBrains Mono', monospace", fontSize: "11px" }}>{num}.</span>
              <span>{renderInline(line.replace(/^\d+[.)]\s/, ""))}</span>
            </div>
          );
        }
        if (line.startsWith("**") && line.endsWith("**"))
          return <p key={i} className="font-semibold">{line.slice(2, -2)}</p>;
        return <p key={i}>{renderInline(line)}</p>;
      })}
    </div>
  );
}

function renderInline(text) {
  // Bold: **text**
  const parts = text.split(/(\*\*[^*]+\*\*)/g);
  return parts.map((part, i) =>
    part.startsWith("**") && part.endsWith("**")
      ? <strong key={i}>{part.slice(2, -2)}</strong>
      : part
  );
}

function DetectionBadge({ detections }) {
  if (!detections || detections.length === 0) return null;
  const counts = detections.reduce((acc, d) => {
    acc[d.class] = (acc[d.class] || 0) + 1;
    return acc;
  }, {});
  const top = Object.entries(counts).slice(0, 4);

  return (
    <div
      className="flex-none px-4 py-2.5 flex items-center gap-3 text-xs overflow-x-auto"
      style={{ borderTop: "1px solid #2A2A2A", fontFamily: "'JetBrains Mono', monospace" }}
    >
      <span style={{ color: "#C96A2A", flexShrink: 0 }}>
        {detections.length} detection{detections.length !== 1 ? "s" : ""}
      </span>
      <span style={{ color: "#333", flexShrink: 0 }}>|</span>
      {top.map(([cls, cnt]) => (
        <span key={cls} style={{ color: "#666", flexShrink: 0 }}>
          {cls}: <span style={{ color: "#A1A1AA" }}>{cnt}</span>
        </span>
      ))}
    </div>
  );
}

export default function OutputPanel({ result, isLoading, videoJob, onDownload }) {
  // Skeleton while loading (non-video)
  if (isLoading && !videoJob) {
    return (
      <div className="flex-1 flex flex-col p-5 gap-4 overflow-hidden">
        <div
          data-testid="skeleton-loader"
          className="flex-1 rounded-xl animate-pulse"
          style={{ background: "#1A1A1A" }}
        />
        <div className="animate-pulse rounded-xl h-12" style={{ background: "#1A1A1A" }} />
        <div className="animate-pulse rounded-xl h-8" style={{ background: "#1A1A1A", width: "60%" }} />
      </div>
    );
  }

  // Video processing progress
  if (videoJob && (videoJob.status === "queued" || videoJob.status === "processing")) {
    return (
      <div className="flex-1 flex flex-col items-center justify-center p-8 gap-8">
        <div className="w-full max-w-sm space-y-4">
          <div className="text-center space-y-1">
            <p className="text-sm font-medium">Processing with {videoJob.model}…</p>
            <p className="text-xs" style={{ color: "#A1A1AA" }}>
              {videoJob.status === "queued"
                ? "Queued — starting soon"
                : `${videoJob.progress}% complete`}
            </p>
          </div>

          <div className="w-full h-2 rounded-full overflow-hidden" style={{ background: "#2A2A2A" }}>
            <div
              data-testid="processing-progress-bar"
              className="h-full rounded-full transition-all duration-500 ease-out"
              style={{ width: `${videoJob.progress}%`, background: "#C96A2A" }}
            />
          </div>

          <div className="flex justify-between text-xs" style={{ color: "#444" }}>
            <span>Annotating frames</span>
            <span style={{ color: "#666" }}>{videoJob.progress}%</span>
            <span>Encoding</span>
          </div>
        </div>

        <p className="text-xs text-center" style={{ color: "#333" }}>
          This may take a few minutes for longer videos
        </p>
      </div>
    );
  }

  // Annotated image result
  if (result?.type === "image") {
    return (
      <div data-testid="visual-output-panel" className="flex-1 flex flex-col overflow-hidden">
        <div
          className="flex-1 flex items-center justify-center p-4 overflow-auto"
          style={{ background: "#111111" }}
        >
          <img
            data-testid="output-annotated-image"
            src={result.content}
            alt="Analysis result"
            className="max-w-full max-h-full object-contain rounded-lg animate-fade-in"
            style={{ border: "1px solid #2A2A2A" }}
          />
        </div>
        <DetectionBadge detections={result.detections} />
      </div>
    );
  }

  // Processed video result
  if (result?.type === "video") {
    return (
      <div data-testid="visual-output-panel" className="flex-1 flex flex-col overflow-hidden">
        <div
          className="flex-1 flex items-center justify-center p-4 overflow-hidden"
          style={{ background: "#111111" }}
        >
          <video
            data-testid="output-video-player"
            src={result.content}
            controls
            playsInline
            className="max-w-full max-h-full rounded-lg animate-fade-in"
            style={{ border: "1px solid #2A2A2A" }}
          />
        </div>
        <div
          className="flex-none px-4 py-3 flex items-center justify-between"
          style={{ borderTop: "1px solid #2A2A2A" }}
        >
          <span className="text-xs" style={{ color: "#555" }}>
            Processed video — ready to download
          </span>
          <button
            data-testid="download-video-button"
            onClick={() => onDownload(result.content, result.job_id)}
            className="flex items-center gap-2 px-4 py-2 rounded-lg text-sm font-medium transition-all"
            style={{ background: "#C96A2A", color: "#fff" }}
            onMouseEnter={(e) => (e.currentTarget.style.background = "#E07A35")}
            onMouseLeave={(e) => (e.currentTarget.style.background = "#C96A2A")}
          >
            <Download size={14} />
            Download Video
          </button>
        </div>
      </div>
    );
  }

  // Text result (Gemini)
  if (result?.type === "text") {
    return (
      <div data-testid="visual-output-panel" className="flex-1 flex flex-col overflow-hidden">
        <div className="flex-1 p-6 overflow-y-auto animate-fade-in">
          <MarkdownText content={result.content} />
        </div>
      </div>
    );
  }

  // Empty state
  return (
    <div className="flex-1 flex flex-col items-center justify-center gap-5 p-8">
      <div
        className="w-20 h-20 rounded-2xl flex items-center justify-center"
        style={{ background: "#1A1A1A", border: "1px solid #2A2A2A" }}
      >
        <Eye size={34} style={{ color: "#2A2A2A" }} />
      </div>
      <div className="text-center space-y-1.5">
        <p className="text-sm font-medium" style={{ color: "#333" }}>No analysis yet</p>
        <p className="text-xs" style={{ color: "#2A2A2A" }}>
          Upload a file and describe what you want to analyze
        </p>
      </div>
    </div>
  );
}
