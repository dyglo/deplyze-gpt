import React from "react";

export default function ModelSelector({ models, selected, onSelect, disabledModelIds = [] }) {
  const disabledModelSet = React.useMemo(() => new Set(disabledModelIds), [disabledModelIds]);

  return (
    <div>
      <p
        className="text-xs font-medium uppercase tracking-wider mb-3"
        style={{ color: "#A1A1AA", fontFamily: "'JetBrains Mono', monospace" }}
      >
        Model
      </p>
      <div className="grid grid-cols-2 gap-2">
        {models.map(({ id, label, desc, icon: Icon }) => {
          const isActive = selected === id;
          const isDisabled = disabledModelSet.has(id);
          return (
            <button
              key={id}
              data-testid={`model-card-${id}`}
              onClick={() => {
                if (isDisabled) return;
                onSelect(id);
              }}
              disabled={isDisabled}
              className="text-left p-3 rounded-xl transition-all active:scale-[0.97]"
              style={{
                background: isActive ? "rgba(201,106,42,0.1)" : "#1A1A1A",
                border: `1px solid ${isActive ? "#C96A2A" : "#2A2A2A"}`,
                boxShadow: isActive ? "0 0 14px rgba(201,106,42,0.12)" : "none",
                cursor: isDisabled ? "not-allowed" : "pointer",
                opacity: isDisabled ? 0.45 : 1,
              }}
              onMouseEnter={(e) => {
                if (!isActive && !isDisabled) {
                  e.currentTarget.style.background = "#222";
                  e.currentTarget.style.borderColor = "#333";
                }
              }}
              onMouseLeave={(e) => {
                if (!isActive && !isDisabled) {
                  e.currentTarget.style.background = "#1A1A1A";
                  e.currentTarget.style.borderColor = "#2A2A2A";
                }
              }}
            >
              <div className="flex items-center gap-2 mb-1.5">
                <Icon
                  size={13}
                  style={{ color: isActive ? "#C96A2A" : "#666", flexShrink: 0 }}
                />
                <span
                  className="text-xs font-semibold truncate"
                  style={{
                    fontFamily: "'JetBrains Mono', monospace",
                    color: isActive ? "#C96A2A" : "#fff",
                  }}
                >
                  {label}
                </span>
              </div>
              <p className="text-xs leading-tight" style={{ color: "#555" }}>
                {desc}
              </p>
            </button>
          );
        })}
      </div>
    </div>
  );
}
