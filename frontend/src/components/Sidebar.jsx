import React, { useState } from "react";
import {
  PanelLeft,
  Search,
  Plus,
  MessageCircle,
  Inbox,
  Share2,
  Briefcase,
  ChevronsUpDown,
} from "lucide-react";

/* Claude.ai sidebar nav. Each item maps to a route (page link) wired up later. */
const NAV_MAIN = [
  { id: "new",       label: "New chat",  icon: Plus,           route: "/" },
  { id: "chats",     label: "Chats",     icon: MessageCircle,  route: "/chats" },
  { id: "projects",  label: "Projects",  icon: Inbox,          route: "/projects" },
  { id: "artifacts", label: "Artifacts", icon: Share2,         route: "/artifacts" },
  { id: "customize", label: "Customize", icon: Briefcase,      route: "/customize" },
];

const ICON_SIZE = 18;
const ICON_STROKE = 1.75;

function NavItem({ item, expanded, active, onSelect }) {
  const Icon = item.icon;
  return (
    <button
      data-testid={`sidebar-nav-${item.id}`}
      onClick={() => onSelect(item)}
      title={expanded ? undefined : item.label}
      className="flex items-center rounded-lg transition-colors flex-shrink-0 overflow-hidden"
      style={{
        height: "34px",
        width: expanded ? "100%" : "34px",
        paddingLeft: expanded ? "8px" : "0",
        justifyContent: expanded ? "flex-start" : "center",
        gap: "11px",
        background: active ? "var(--bg-hover)" : "transparent",
      }}
      onMouseEnter={e => { if (!active) e.currentTarget.style.background = "var(--bg-hover)"; }}
      onMouseLeave={e => { if (!active) e.currentTarget.style.background = "transparent"; }}
    >
      <Icon
        size={ICON_SIZE}
        strokeWidth={ICON_STROKE}
        style={{ color: active ? "var(--text-primary)" : "var(--text-secondary)", flexShrink: 0 }}
      />
      {expanded && (
        <span
          className="text-[14px] whitespace-nowrap"
          style={{ color: active ? "var(--text-primary)" : "var(--text-secondary)" }}
        >
          {item.label}
        </span>
      )}
    </button>
  );
}

function IconBtn({ icon: Icon, title, onClick }) {
  return (
    <button
      onClick={onClick}
      title={title}
      className="w-8 h-8 rounded-lg flex items-center justify-center transition-colors flex-shrink-0"
      style={{ background: "transparent" }}
      onMouseEnter={e => e.currentTarget.style.background = "var(--bg-hover)"}
      onMouseLeave={e => e.currentTarget.style.background = "transparent"}
    >
      <Icon size={ICON_SIZE} strokeWidth={ICON_STROKE} style={{ color: "var(--text-secondary)" }} />
    </button>
  );
}

export default function Sidebar({ onNewChat }) {
  const [expanded, setExpanded] = useState(false);
  const [active, setActive] = useState("new");

  const handleSelect = item => {
    setActive(item.id);
    if (item.id === "new") onNewChat?.();
    // Routing hook-up later: navigate(item.route)
  };

  return (
    <div
      data-testid="app-sidebar"
      className="flex-none flex flex-col py-2.5 transition-all duration-200 ease-out"
      style={{
        width: expanded ? "248px" : "56px",
        background: "var(--bg-sidebar)",
        paddingLeft: expanded ? "8px" : "0",
        paddingRight: expanded ? "8px" : "0",
        alignItems: expanded ? "stretch" : "center",
      }}
    >
      {/* Header: brand + search + toggle (expanded) — just toggle (collapsed) */}
      {expanded ? (
        <div className="flex items-center justify-between mb-2 pl-2 pr-0.5" style={{ height: "36px" }}>
          <span className="font-serif-display text-[20px]" style={{ color: "var(--text-primary)" }}>
            Deplyze
          </span>
          <div className="flex items-center">
            <IconBtn icon={Search} title="Search" />
            <IconBtn icon={PanelLeft} title="Collapse sidebar" onClick={() => setExpanded(false)} />
          </div>
        </div>
      ) : (
        <button
          data-testid="sidebar-toggle"
          onClick={() => setExpanded(true)}
          title="Expand sidebar"
          className="w-8 h-8 rounded-lg flex items-center justify-center transition-colors flex-shrink-0 mb-2"
          style={{ background: "transparent" }}
          onMouseEnter={e => e.currentTarget.style.background = "var(--bg-hover)"}
          onMouseLeave={e => e.currentTarget.style.background = "transparent"}
        >
          <PanelLeft size={ICON_SIZE} strokeWidth={ICON_STROKE} style={{ color: "var(--text-secondary)" }} />
        </button>
      )}

      {/* Main nav */}
      <div className="flex flex-col gap-0.5">
        {NAV_MAIN.map(item => (
          <NavItem key={item.id} item={item} expanded={expanded} active={active === item.id} onSelect={handleSelect} />
        ))}
      </div>

      <div className="flex-1" />

      {/* User footer */}
      <button
        title="greetmeasap@gmail.com"
        className="flex items-center rounded-lg transition-colors flex-shrink-0 mt-1.5"
        style={{
          height: "48px",
          width: expanded ? "100%" : "40px",
          paddingLeft: expanded ? "6px" : "0",
          paddingRight: expanded ? "6px" : "0",
          justifyContent: expanded ? "flex-start" : "center",
          gap: "9px",
          background: "transparent",
        }}
        onMouseEnter={e => { if (expanded) e.currentTarget.style.background = "var(--bg-hover)"; }}
        onMouseLeave={e => e.currentTarget.style.background = "transparent"}
      >
        <div
          className="w-8 h-8 rounded-full flex items-center justify-center flex-shrink-0 text-xs font-semibold"
          style={{ background: "#5a5851", color: "var(--text-primary)" }}
        >
          T
        </div>
        {expanded && (
          <>
            <div className="flex flex-col items-start min-w-0 flex-1">
              <span className="text-[13px] font-medium whitespace-nowrap" style={{ color: "var(--text-primary)" }}>
                Tafar
              </span>
              <span className="text-[11px] whitespace-nowrap" style={{ color: "var(--text-muted)" }}>
                Free plan
              </span>
            </div>
            <ChevronsUpDown size={15} strokeWidth={ICON_STROKE} style={{ color: "var(--text-muted)", flexShrink: 0 }} />
          </>
        )}
      </button>
    </div>
  );
}
