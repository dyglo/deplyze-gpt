import React, { useMemo, useRef, useState, useEffect } from "react";
import { ChevronDown, Search, Check } from "lucide-react";

const SORT_OPTIONS = [
  { id: "activity", label: "Recent activity" },
  { id: "edited", label: "Last edited" },
  { id: "created", label: "Date created" },
];

function EmptyIllustration() {
  return (
    <svg width="92" height="92" viewBox="0 0 92 92" fill="none" aria-hidden="true">
      <rect x="10" y="10" width="30" height="30" rx="4" stroke="var(--text-faint)" strokeWidth="2.2" />
      <rect x="10" y="48" width="30" height="30" rx="4" stroke="var(--text-faint)" strokeWidth="2.2" />
      <rect x="48" y="10" width="30" height="30" rx="4" stroke="var(--text-faint)" strokeWidth="2.2" />
      <path
        d="M52 52c0-2 1.6-3.6 3.6-3.6h2.8c2 0 3.6 1.6 3.6 3.6v9l8-3.4c1.8-.7 3.7.6 3.7 2.5v10c0 4.4-3.6 8-8 8h-9.2c-2.4 0-4.7-1.1-6.2-3l-6-7.6c-1.2-1.5-1-3.7.5-5 1.4-1.1 3.4-1 4.7.2L52 64V52Z"
        stroke="var(--text-faint)"
        strokeWidth="2.2"
        strokeLinejoin="round"
      />
    </svg>
  );
}

export default function DatasetPage({ onNewDataset }) {
  const [sort, setSort] = useState("activity");
  const [query, setQuery] = useState("");
  const [sortOpen, setSortOpen] = useState(false);
  const sortRef = useRef(null);

  const activeSort = useMemo(() => SORT_OPTIONS.find((o) => o.id === sort) || SORT_OPTIONS[0], [sort]);

  useEffect(() => {
    if (!sortOpen) return undefined;
    const onClick = (e) => { if (sortRef.current && !sortRef.current.contains(e.target)) setSortOpen(false); };
    document.addEventListener("mousedown", onClick);
    return () => document.removeEventListener("mousedown", onClick);
  }, [sortOpen]);

  return (
    <div className="flex-1 overflow-y-auto" style={{ background: "var(--bg-app)" }}>
      <div className="mx-auto w-full px-8 py-10" style={{ maxWidth: "960px" }}>
        {/* Coming soon banner */}
        <div
          className="mb-8 flex items-center gap-3 rounded-xl px-4 py-3"
          style={{
            background: "color-mix(in srgb, var(--accent) 9%, var(--bg-elevated))",
            border: "1px solid color-mix(in srgb, var(--accent) 30%, transparent)",
          }}
        >
          <span
            className="flex-none rounded-full px-2.5 py-0.5 text-[11px] font-semibold uppercase tracking-wide"
            style={{
              color: "var(--accent)",
              background: "color-mix(in srgb, var(--accent) 16%, transparent)",
            }}
          >
            Coming soon
          </span>
          <p className="min-w-0 text-sm leading-snug" style={{ color: "var(--text-muted)" }}>
            Datasets are actively being built. Explore the preview below — full functionality lands soon.
          </p>
        </div>

        {/* Header */}
        <div className="flex items-center justify-between gap-4">
          <h1 className="font-serif-display text-[34px] leading-none" style={{ color: "var(--text-primary)" }}>
            Dataset
          </h1>

          <div className="flex items-center gap-3">
            <span className="text-sm" style={{ color: "var(--text-muted)" }}>Sort by</span>
            <div ref={sortRef} className="relative">
              <button
                type="button"
                onClick={() => setSortOpen((v) => !v)}
                className="flex h-9 items-center gap-2 rounded-lg px-3 text-sm transition"
                style={{ background: "var(--bg-elevated)", border: "1px solid var(--border-subtle)", color: "var(--text-primary)" }}
              >
                {activeSort.label === "Recent activity" ? "Activity" : activeSort.label}
                <ChevronDown size={15} style={{ color: "var(--text-muted)" }} />
              </button>

              {sortOpen && (
                <div
                  className="absolute right-0 z-20 mt-1.5 w-48 rounded-xl p-1.5 shadow-xl"
                  style={{ background: "var(--bg-elevated)", border: "1px solid var(--border-subtle)" }}
                >
                  {SORT_OPTIONS.map((opt) => (
                    <button
                      key={opt.id}
                      type="button"
                      onClick={() => { setSort(opt.id); setSortOpen(false); }}
                      className="flex h-9 w-full items-center justify-between rounded-lg px-3 text-left text-sm transition"
                      style={{ color: "var(--text-primary)", background: "transparent" }}
                      onMouseEnter={(e) => (e.currentTarget.style.background = "var(--bg-hover)")}
                      onMouseLeave={(e) => (e.currentTarget.style.background = "transparent")}
                    >
                      {opt.label}
                      {sort === opt.id && <Check size={15} style={{ color: "var(--accent)" }} />}
                    </button>
                  ))}
                </div>
              )}
            </div>

            <button
              type="button"
              onClick={onNewDataset}
              className="h-9 rounded-lg px-4 text-sm font-medium transition"
              style={{ background: "var(--bg-elevated)", border: "1px solid var(--border-subtle)", color: "var(--text-primary)" }}
              onMouseEnter={(e) => (e.currentTarget.style.background = "var(--bg-hover)")}
              onMouseLeave={(e) => (e.currentTarget.style.background = "var(--bg-elevated)")}
            >
              New Dataset
            </button>
          </div>
        </div>

        {/* Search */}
        <div
          className="mt-6 flex h-12 items-center gap-3 rounded-xl px-4"
          style={{ background: "var(--bg-elevated)", border: "1px solid var(--border-subtle)" }}
        >
          <Search size={18} style={{ color: "var(--text-muted)" }} />
          <input
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="Search datasets..."
            className="w-full bg-transparent text-sm outline-none"
            style={{ color: "var(--text-primary)" }}
          />
        </div>

        {/* Empty state */}
        <div className="flex flex-col items-center justify-center py-24 text-center">
          <EmptyIllustration />
          <h2 className="mt-7 text-lg font-medium" style={{ color: "var(--text-primary)" }}>
            Looking to start a dataset?
          </h2>
          <p className="mt-2 max-w-sm text-sm leading-relaxed" style={{ color: "var(--text-muted)" }}>
            Upload materials, set custom instructions, and organize conversations in one space.
          </p>
          <button
            type="button"
            onClick={onNewDataset}
            className="mt-5 h-10 rounded-lg px-5 text-sm font-medium transition"
            style={{ background: "var(--accent)", color: "#fff" }}
            onMouseEnter={(e) => (e.currentTarget.style.background = "var(--accent-hover)")}
            onMouseLeave={(e) => (e.currentTarget.style.background = "var(--accent)")}
          >
            New Dataset
          </button>
        </div>
      </div>
    </div>
  );
}
