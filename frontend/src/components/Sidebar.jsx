import React from "react";
import { Plus, MessageSquare, Settings, Eye } from "lucide-react";

export default function Sidebar({ onNewChat }) {
  return (
    <div
      data-testid="app-sidebar"
      className="flex-none flex flex-col items-center py-4 gap-2"
      style={{ width: "52px", background: "#0D0D0D", borderRight: "1px solid #1C1C1C" }}
    >
      <div
        className="w-8 h-8 rounded-lg flex items-center justify-center mb-3 flex-shrink-0"
        style={{ background: "#C96A2A" }}
      >
        <Eye size={14} color="white" strokeWidth={2.5} />
      </div>

      <button
        data-testid="new-chat-button"
        onClick={onNewChat}
        title="New Chat"
        className="w-9 h-9 rounded-xl flex items-center justify-center transition-all flex-shrink-0"
        style={{ background: "#1A1A1A", border: "1px solid #222" }}
        onMouseEnter={e => {
          e.currentTarget.style.borderColor = "#C96A2A";
          e.currentTarget.style.background = "rgba(201,106,42,0.12)";
        }}
        onMouseLeave={e => {
          e.currentTarget.style.borderColor = "#222";
          e.currentTarget.style.background = "#1A1A1A";
        }}
      >
        <Plus size={15} style={{ color: "#888" }} />
      </button>

      <button
        title="History (coming soon)"
        className="w-9 h-9 rounded-xl flex items-center justify-center flex-shrink-0 cursor-not-allowed"
        style={{ opacity: 0.25 }}
      >
        <MessageSquare size={15} style={{ color: "#666" }} />
      </button>

      <div className="flex-1" />

      <button
        title="Settings (coming soon)"
        className="w-9 h-9 rounded-xl flex items-center justify-center flex-shrink-0 cursor-not-allowed"
        style={{ opacity: 0.25 }}
      >
        <Settings size={15} style={{ color: "#666" }} />
      </button>
    </div>
  );
}
