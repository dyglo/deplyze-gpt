import React, { useEffect, useMemo, useRef, useState } from "react";
import {
  Check,
  ChevronsUpDown,
  Code2,
  LogOut,
  MessageCircle,
  MoreHorizontal,
  PanelLeft,
  Pencil,
  Pin,
  PinOff,
  Plus,
  Search,
  Settings,
  Share2,
  Trash2,
  Inbox,
  X,
} from "lucide-react";
import SettingsModal from "./SettingsModal";

const NAV_ITEMS = [
  { id: "dataset", label: "Dataset", icon: Inbox, view: "dataset" },
  { id: "artifacts", label: "Artifacts", icon: Share2, comingSoon: true },
  { id: "benchmark", label: "Benchmark", icon: Code2, comingSoon: true },
];

function initialsFromUser(user) {
  const name = user?.displayName || user?.email || "User";
  return name.trim().charAt(0).toUpperCase();
}

function sessionLabel(session) {
  return (session?.name || "New analysis").trim() || "New analysis";
}

function formatSessionDate(value) {
  if (!value) return "";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return "";
  return new Intl.DateTimeFormat(undefined, { month: "short", day: "numeric" }).format(date);
}

function SessionRow({
  session,
  active,
  collapsed,
  menuOpen,
  renaming,
  confirmingDelete,
  onSelect,
  onOpenMenu,
  onRenameStart,
  onRenameSave,
  onRenameCancel,
  onTogglePin,
  onDeleteStart,
  onDeleteCancel,
  onDeleteConfirm,
}) {
  const [draftName, setDraftName] = useState(sessionLabel(session));
  const title = sessionLabel(session);

  if (collapsed) {
    return (
      <button
        type="button"
        onClick={() => onSelect(session.session_id)}
        title={title}
        className="group flex h-10 w-10 items-center justify-center rounded-lg transition"
        style={{
          background: active ? "var(--bg-elevated)" : "transparent",
          color: active ? "var(--text-primary)" : "var(--text-muted)",
        }}
      >
        <MessageCircle size={18} />
      </button>
    );
  }

  if (renaming) {
    return (
      <div
        className="flex h-10 items-center gap-1 rounded-lg px-2"
        style={{ background: "var(--bg-elevated)", border: "1px solid var(--border-subtle)" }}
      >
        <input
          value={draftName}
          autoFocus
          onChange={(event) => setDraftName(event.target.value)}
          onKeyDown={(event) => {
            if (event.key === "Enter") onRenameSave(session.session_id, draftName);
            if (event.key === "Escape") onRenameCancel();
          }}
          className="min-w-0 flex-1 bg-transparent text-sm outline-none"
          style={{ color: "var(--text-primary)" }}
        />
        <button
          type="button"
          aria-label="Save session name"
          onClick={() => onRenameSave(session.session_id, draftName)}
          className="flex h-7 w-7 items-center justify-center rounded-md"
          style={{ color: "var(--text-muted)" }}
        >
          <Check size={15} />
        </button>
        <button
          type="button"
          aria-label="Cancel rename"
          onClick={onRenameCancel}
          className="flex h-7 w-7 items-center justify-center rounded-md"
          style={{ color: "var(--text-muted)" }}
        >
          <X size={15} />
        </button>
      </div>
    );
  }

  if (confirmingDelete) {
    return (
      <div
        className="flex h-10 items-center gap-2 rounded-lg px-2"
        style={{ background: "rgba(255, 85, 72, 0.10)", border: "1px solid rgba(255, 85, 72, 0.32)" }}
      >
        <span className="min-w-0 flex-1 truncate text-sm" style={{ color: "var(--text-primary)" }}>
          Delete?
        </span>
        <button
          type="button"
          aria-label="Confirm delete"
          onClick={() => onDeleteConfirm(session.session_id)}
          className="flex h-7 w-7 items-center justify-center rounded-md"
          style={{ color: "#FF6257" }}
        >
          <Check size={15} />
        </button>
        <button
          type="button"
          aria-label="Cancel delete"
          onClick={onDeleteCancel}
          className="flex h-7 w-7 items-center justify-center rounded-md"
          style={{ color: "var(--text-muted)" }}
        >
          <X size={15} />
        </button>
      </div>
    );
  }

  return (
    <div className="relative">
      <div
        className="group flex h-9 w-full items-center rounded-lg transition"
        style={{
          background: active ? "var(--bg-elevated)" : "transparent",
          border: active ? "1px solid var(--border-subtle)" : "1px solid transparent",
          color: "var(--text-primary)",
        }}
        onMouseEnter={(e) => { if (!active) e.currentTarget.style.background = "var(--bg-hover)"; }}
        onMouseLeave={(e) => { if (!active) e.currentTarget.style.background = "transparent"; }}
      >
        <button
          type="button"
          onClick={() => onSelect(session.session_id)}
          className="flex h-full min-w-0 flex-1 items-center gap-2 px-3 text-left"
        >
          {session.pinned && <Pin size={13} className="flex-none" style={{ color: "var(--accent)" }} />}
          <span className="min-w-0 flex-1 truncate text-sm">{title}</span>
          <span className="hidden flex-none text-[11px] group-hover:hidden xl:block" style={{ color: "var(--text-faint)" }}>
            {formatSessionDate(session.updated_at)}
          </span>
        </button>
        <button
          type="button"
          aria-label="Session menu"
          onClick={(event) => {
            event.stopPropagation();
            onOpenMenu(session.session_id);
          }}
          className="mr-1 hidden h-7 w-7 flex-none items-center justify-center rounded-md group-hover:flex"
          style={{ color: "var(--text-muted)" }}
        >
          <MoreHorizontal size={16} />
        </button>
      </div>

      {menuOpen && (
        <div
          className="absolute right-1 top-9 z-20 w-40 rounded-lg p-1 shadow-xl"
          style={{ background: "var(--bg-elevated)", border: "1px solid var(--border-subtle)" }}
        >
          <button
            type="button"
            onClick={() => onRenameStart(session.session_id, title)}
            className="flex h-8 w-full items-center gap-2 rounded-md px-2 text-left text-sm"
            style={{ color: "var(--text-primary)" }}
          >
            <Pencil size={14} /> Rename
          </button>
          <button
            type="button"
            onClick={() => onTogglePin(session)}
            className="flex h-8 w-full items-center gap-2 rounded-md px-2 text-left text-sm"
            style={{ color: "var(--text-primary)" }}
          >
            {session.pinned ? <PinOff size={14} /> : <Pin size={14} />}
            {session.pinned ? "Unpin" : "Pin"}
          </button>
          <button
            type="button"
            onClick={() => onDeleteStart(session.session_id)}
            className="flex h-8 w-full items-center gap-2 rounded-md px-2 text-left text-sm"
            style={{ color: "#FF6257" }}
          >
            <Trash2 size={14} /> Delete
          </button>
        </div>
      )}
    </div>
  );
}

export default function Sidebar({
  onNewChat,
  user,
  onSignOut,
  sessions = [],
  activeSessionId,
  isLoadingSessions,
  onSelectSession,
  onRenameSession,
  onTogglePinSession,
  onDeleteSession,
  activeView = "chat",
  onSelectView,
}) {
  const [collapsed, setCollapsed] = useState(false);
  const [settingsOpen, setSettingsOpen] = useState(false);
  const [accountMenuOpen, setAccountMenuOpen] = useState(false);
  const [menuSessionId, setMenuSessionId] = useState(null);
  const [renamingSessionId, setRenamingSessionId] = useState(null);
  const [confirmDeleteSessionId, setConfirmDeleteSessionId] = useState(null);
  const accountRef = useRef(null);
  const displayName = user?.displayName || user?.email || "Tafar";
  const displayEmail = user?.email || "Signed in";

  useEffect(() => {
    if (!accountMenuOpen) return undefined;
    const onClick = (e) => { if (accountRef.current && !accountRef.current.contains(e.target)) setAccountMenuOpen(false); };
    document.addEventListener("mousedown", onClick);
    return () => document.removeEventListener("mousedown", onClick);
  }, [accountMenuOpen]);

  const pinnedCount = useMemo(() => sessions.filter((session) => session.pinned).length, [sessions]);

  const renameStart = (sessionId) => {
    setMenuSessionId(null);
    setConfirmDeleteSessionId(null);
    setRenamingSessionId(sessionId);
  };

  const renameSave = async (sessionId, name) => {
    await onRenameSession?.(sessionId, name);
    setRenamingSessionId(null);
  };

  const deleteStart = (sessionId) => {
    setMenuSessionId(null);
    setRenamingSessionId(null);
    setConfirmDeleteSessionId(sessionId);
  };

  const deleteConfirm = async (sessionId) => {
    await onDeleteSession?.(sessionId);
    setConfirmDeleteSessionId(null);
  };

  return (
    <>
      <aside
        className="flex h-screen flex-none flex-col border-r transition-[width] duration-200"
        style={{
          width: collapsed ? 56 : 288,
          background: "var(--bg-sidebar)",
          borderColor: "var(--border-subtle)",
        }}
      >
        <div className={`flex h-14 flex-none items-center gap-2 ${collapsed ? "justify-center px-0" : "px-3"}`}>
          {!collapsed && (
            <div className="min-w-0 flex-1 truncate font-serif-display text-xl" style={{ color: "var(--text-primary)" }}>
              Deplyze
            </div>
          )}
          {!collapsed && (
            <button
              type="button"
              aria-label="Search"
              className="flex h-8 w-8 items-center justify-center rounded-lg"
              style={{ color: "var(--text-muted)" }}
            >
              <Search size={17} />
            </button>
          )}
          <button
            type="button"
            aria-label="Toggle sidebar"
            onClick={() => setCollapsed((value) => !value)}
            className="flex h-8 w-8 items-center justify-center rounded-lg"
            style={{ color: "var(--text-muted)" }}
          >
            <PanelLeft size={17} />
          </button>
        </div>

        <div className={`flex flex-none flex-col gap-1 ${collapsed ? "px-0 items-center" : "px-2"}`}>
          <button
            type="button"
            onClick={() => { onSelectView?.("chat"); onNewChat?.(); }}
            className={`flex h-9 items-center gap-3 rounded-lg text-sm transition ${collapsed ? "w-9 justify-center px-0" : "px-3"}`}
            style={{ color: "var(--text-primary)", background: "transparent" }}
            onMouseEnter={(e) => (e.currentTarget.style.background = "var(--bg-hover)")}
            onMouseLeave={(e) => (e.currentTarget.style.background = "transparent")}
            title="New chat"
          >
            <span
              className="flex h-6 w-6 flex-none items-center justify-center rounded-full"
              style={{ border: "1px solid var(--border-subtle)", color: "var(--text-primary)" }}
            >
              <Plus size={14} />
            </span>
            {!collapsed && <span className="min-w-0 truncate">New chat</span>}
          </button>

          <nav className={`mt-2 flex flex-col gap-1 ${collapsed ? "items-center" : ""}`}>
            {NAV_ITEMS.map(({ id, label, icon: Icon, view, comingSoon }) => {
              const isActive = view ? activeView === view : false;
              return (
                <button
                  key={id}
                  type="button"
                  onClick={() => { if (comingSoon) return; if (view) onSelectView?.(view); }}
                  aria-disabled={comingSoon || undefined}
                  className={`flex h-9 items-center gap-3 rounded-lg text-sm transition ${collapsed ? "w-9 justify-center px-0" : "px-3"} ${comingSoon ? "cursor-default" : ""}`}
                  style={{
                    background: isActive ? "var(--bg-elevated)" : "transparent",
                    color: comingSoon ? "var(--text-muted)" : "var(--text-primary)",
                  }}
                  onMouseEnter={(e) => { if (!isActive && !comingSoon) e.currentTarget.style.background = "var(--bg-hover)"; }}
                  onMouseLeave={(e) => { if (!isActive) e.currentTarget.style.background = "transparent"; }}
                  title={comingSoon ? `${label} — Coming soon` : label}
                >
                  <Icon size={17} className="flex-none" />
                  {!collapsed && <span className="min-w-0 truncate">{label}</span>}
                  {!collapsed && comingSoon && (
                    <span
                      className="ml-auto flex-none rounded-full px-2 py-0.5 text-[10px] font-medium uppercase tracking-wide"
                      style={{
                        color: "var(--accent)",
                        background: "color-mix(in srgb, var(--accent) 14%, transparent)",
                        border: "1px solid color-mix(in srgb, var(--accent) 32%, transparent)",
                      }}
                    >
                      Soon
                    </span>
                  )}
                </button>
              );
            })}
          </nav>
        </div>

        {collapsed ? (
          <div className="min-h-0 flex-1" />
        ) : (
          <div className="mt-4 min-h-0 flex-1 overflow-y-auto px-2 pb-3" onClick={() => setMenuSessionId(null)}>
            <div className="mb-2 flex items-center justify-between px-3">
              <span className="text-[11px] font-medium uppercase tracking-wide" style={{ color: "var(--text-muted)" }}>
                Recents
              </span>
              {pinnedCount > 0 && (
                <span className="text-[11px]" style={{ color: "var(--text-muted)" }}>
                  {pinnedCount} pinned
                </span>
              )}
            </div>

            <div className="flex flex-col gap-0.5">
              {isLoadingSessions && sessions.length === 0 ? (
                <div className="px-3 py-2 text-sm" style={{ color: "var(--text-muted)" }}>
                  Loading sessions
                </div>
              ) : sessions.length === 0 ? (
                <div className="px-3 py-2 text-sm leading-snug" style={{ color: "var(--text-muted)" }}>
                  No sessions yet
                </div>
              ) : (
                sessions.map((session) => (
                  <SessionRow
                    key={session.session_id}
                    session={session}
                    active={session.session_id === activeSessionId}
                    collapsed={collapsed}
                    menuOpen={menuSessionId === session.session_id}
                    renaming={renamingSessionId === session.session_id}
                    confirmingDelete={confirmDeleteSessionId === session.session_id}
                    onSelect={onSelectSession}
                    onOpenMenu={(sessionId) => setMenuSessionId((current) => current === sessionId ? null : sessionId)}
                    onRenameStart={renameStart}
                    onRenameSave={renameSave}
                    onRenameCancel={() => setRenamingSessionId(null)}
                    onTogglePin={async (item) => {
                      setMenuSessionId(null);
                      await onTogglePinSession?.(item);
                    }}
                    onDeleteStart={deleteStart}
                    onDeleteCancel={() => setConfirmDeleteSessionId(null)}
                    onDeleteConfirm={deleteConfirm}
                  />
                ))
              )}
            </div>
          </div>
        )}

        <div ref={accountRef} className={`relative flex-none border-t p-2 ${collapsed ? "flex justify-center" : ""}`} style={{ borderColor: "var(--border-subtle)" }}>
          {accountMenuOpen && (
            <div
              className="absolute bottom-[calc(100%+6px)] left-2 z-30 overflow-hidden rounded-xl p-1.5 shadow-xl"
              style={{
                background: "var(--bg-elevated)",
                border: "1px solid var(--border-subtle)",
                right: collapsed ? "auto" : "0.5rem",
                width: collapsed ? "188px" : "auto",
              }}
            >
              <button
                type="button"
                onClick={() => { setAccountMenuOpen(false); setSettingsOpen(true); }}
                className="flex h-9 w-full items-center gap-2.5 rounded-lg px-2.5 text-left text-sm transition"
                style={{ color: "var(--text-primary)", background: "transparent" }}
                onMouseEnter={(e) => (e.currentTarget.style.background = "var(--bg-hover)")}
                onMouseLeave={(e) => (e.currentTarget.style.background = "transparent")}
              >
                <Settings size={16} style={{ color: "var(--text-muted)" }} /> Settings
              </button>
              <button
                type="button"
                onClick={() => { setAccountMenuOpen(false); onSignOut?.(); }}
                className="flex h-9 w-full items-center gap-2.5 rounded-lg px-2.5 text-left text-sm transition"
                style={{ color: "var(--text-primary)", background: "transparent" }}
                onMouseEnter={(e) => (e.currentTarget.style.background = "var(--bg-hover)")}
                onMouseLeave={(e) => (e.currentTarget.style.background = "transparent")}
              >
                <LogOut size={16} style={{ color: "var(--text-muted)" }} /> Sign out
              </button>
            </div>
          )}

          <button
            type="button"
            onClick={() => setAccountMenuOpen((v) => !v)}
            className={`flex h-12 items-center gap-3 rounded-lg text-left transition ${collapsed ? "w-9 justify-center px-0" : "w-full px-2"}`}
            style={{ color: "var(--text-primary)", background: accountMenuOpen ? "var(--bg-hover)" : "transparent" }}
            onMouseEnter={(e) => { if (!accountMenuOpen) e.currentTarget.style.background = "var(--bg-hover)"; }}
            onMouseLeave={(e) => { if (!accountMenuOpen) e.currentTarget.style.background = "transparent"; }}
            title={displayName}
          >
            <span
              className="flex h-9 w-9 flex-none items-center justify-center rounded-full text-sm font-semibold"
              style={{ background: "var(--bg-elevated)", color: "var(--text-primary)" }}
            >
              {initialsFromUser(user)}
            </span>
            {!collapsed && (
              <>
                <span className="min-w-0 flex-1">
                  <span className="block truncate text-sm font-medium">{displayName}</span>
                  <span className="block truncate text-xs" style={{ color: "var(--text-faint)" }}>{displayEmail}</span>
                </span>
                <ChevronsUpDown size={15} style={{ color: "var(--text-muted)" }} />
              </>
            )}
          </button>
        </div>
      </aside>

      <SettingsModal
        open={settingsOpen}
        onClose={() => setSettingsOpen(false)}
        user={user}
        onSignOut={onSignOut}
      />
    </>
  );
}
