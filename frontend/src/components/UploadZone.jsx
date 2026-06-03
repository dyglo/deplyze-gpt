import React, { useRef, useState } from "react";
import { Upload, X, Film, Image } from "lucide-react";

function formatSize(bytes) {
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(0)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

export default function UploadZone({
  uploadedFile,
  isUploading,
  uploadProgress,
  uploadError,
  onFileSelect,
  onClear,
}) {
  const [isDragging, setIsDragging] = useState(false);
  const inputRef = useRef(null);

  const handleDrop = (e) => {
    e.preventDefault();
    setIsDragging(false);
    const f = e.dataTransfer.files[0];
    if (f) onFileSelect(f);
  };

  // Uploaded file preview
  if (uploadedFile) {
    const isImage = uploadedFile.file_type === "image";
    return (
      <div>
        <p
          className="text-xs font-medium uppercase tracking-wider mb-3"
          style={{ color: "#A1A1AA", fontFamily: "'JetBrains Mono', monospace" }}
        >
          File
        </p>
        <div
          className="relative rounded-xl overflow-hidden"
          style={{ background: "#1A1A1A", border: "1px solid #2A2A2A" }}
        >
          {isImage ? (
            <img
              data-testid="upload-image-preview"
              src={uploadedFile.objectUrl}
              alt="Preview"
              className="w-full h-36 object-cover"
            />
          ) : (
            <div
              data-testid="upload-video-preview"
              className="h-28 flex flex-col items-center justify-center gap-2"
            >
              <Film size={28} style={{ color: "#C96A2A" }} />
              <p className="text-sm font-medium truncate max-w-[85%]">{uploadedFile.filename}</p>
              <p className="text-xs" style={{ color: "#A1A1AA" }}>
                {formatSize(uploadedFile.size)} · Video
              </p>
            </div>
          )}

          {/* Clear button */}
          <button
            data-testid="clear-upload-button"
            onClick={onClear}
            className="absolute top-2 right-2 w-6 h-6 rounded-full flex items-center justify-center transition-all"
            style={{ background: "rgba(17,17,17,0.85)", border: "1px solid #333" }}
            onMouseEnter={(e) => (e.currentTarget.style.borderColor = "#EF4444")}
            onMouseLeave={(e) => (e.currentTarget.style.borderColor = "#333")}
            aria-label="Remove file"
          >
            <X size={12} />
          </button>

          <div className="px-3 py-2" style={{ borderTop: "1px solid #2A2A2A" }}>
            <div className="flex items-center justify-between">
              <p className="text-xs truncate" style={{ color: "#A1A1AA" }}>{uploadedFile.filename}</p>
              <span
                className="ml-2 flex-shrink-0 text-xs px-1.5 py-0.5 rounded"
                style={{
                  background: uploadedFile.file_type === "image" ? "rgba(16,185,129,0.1)" : "rgba(201,106,42,0.1)",
                  color: uploadedFile.file_type === "image" ? "#10B981" : "#C96A2A",
                  fontFamily: "'JetBrains Mono', monospace",
                  fontSize: "10px",
                }}
              >
                {uploadedFile.file_type.toUpperCase()}
              </span>
            </div>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div>
      <p
        className="text-xs font-medium uppercase tracking-wider mb-3"
        style={{ color: "#A1A1AA", fontFamily: "'JetBrains Mono', monospace" }}
      >
        Upload
      </p>

      <div
        data-testid="media-upload-zone"
        className="rounded-xl p-8 flex flex-col items-center justify-center gap-3 cursor-pointer transition-all select-none"
        style={{
          border: `2px dashed ${isDragging ? "#C96A2A" : "#2A2A2A"}`,
          background: isDragging ? "rgba(201,106,42,0.05)" : "#1A1A1A",
          minHeight: "140px",
        }}
        onDragOver={(e) => { e.preventDefault(); setIsDragging(true); }}
        onDragLeave={() => setIsDragging(false)}
        onDrop={handleDrop}
        onClick={() => !isUploading && inputRef.current?.click()}
      >
        {isUploading ? (
          <div className="w-full space-y-3 text-center">
            <div
              data-testid="upload-progress-bar"
              className="w-full h-1.5 rounded-full overflow-hidden"
              style={{ background: "#2A2A2A" }}
            >
              <div
                className="h-full rounded-full transition-all duration-300"
                style={{ width: `${uploadProgress}%`, background: "#C96A2A" }}
              />
            </div>
            <p className="text-sm" style={{ color: "#A1A1AA" }}>
              Uploading... {uploadProgress}%
            </p>
          </div>
        ) : (
          <>
            <div
              className="w-11 h-11 rounded-full flex items-center justify-center"
              style={{ background: "#222" }}
            >
              <Upload size={20} style={{ color: isDragging ? "#C96A2A" : "#555" }} />
            </div>
            <div className="text-center">
              <p className="text-sm font-medium">
                Drop file here or{" "}
                <span style={{ color: "#C96A2A" }}>browse</span>
              </p>
              <p className="text-xs mt-1" style={{ color: "#555" }}>
                JPEG · PNG · WEBP · MP4 · MOV · AVI · max 100MB
              </p>
            </div>
          </>
        )}
      </div>

      {uploadError && (
        <p
          data-testid="upload-error-message"
          className="mt-2 text-xs flex items-start gap-1"
          style={{ color: "#EF4444" }}
        >
          <span className="mt-px">⚠</span>
          <span>{uploadError}</span>
        </p>
      )}

      <input
        data-testid="file-input"
        ref={inputRef}
        type="file"
        accept="image/jpeg,image/png,image/webp,video/mp4,video/quicktime,video/x-msvideo,.jpg,.jpeg,.png,.webp,.mp4,.mov,.avi"
        onChange={(e) => e.target.files[0] && onFileSelect(e.target.files[0])}
        className="hidden"
      />
    </div>
  );
}
