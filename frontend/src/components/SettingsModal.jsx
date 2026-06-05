import React, { useEffect, useMemo, useRef, useState } from "react";
import {
  Settings as SettingsIcon,
  UserRound,
  Search,
  X,
  ChevronDown,
  Sun,
  Moon,
  Monitor,
  MoreVertical,
  Camera,
  Loader2,
  Check,
} from "lucide-react";
import { updateProfile } from "firebase/auth";
import { doc, setDoc, serverTimestamp } from "firebase/firestore";
import { ref as storageRef, uploadBytes, getDownloadURL } from "firebase/storage";
import { auth, db, storage } from "../firebase";
import { useTheme } from "../theme";

/*
 * Settings modal styled after Claude.ai. Supports a dark theme (matching the
 * app's warm-dark surface) and a light theme (Claude's Pampas/cream palette).
 * The Appearance toggle switches the live theme of the modal.
 */

const NAV = [
  { id: "general", label: "General", icon: SettingsIcon },
  { id: "account", label: "Account", icon: UserRound },
];

const THEMES = {
  light: {
    modalBg: "#FFFFFF",
    navBg: "#FBFAF7",
    text: "#2C2B28",
    textMuted: "#6B6862",
    textFaint: "#8F8B82",
    placeholder: "#A8A49B",
    border: "#E7E4DD",
    borderInput: "#DAD6CD",
    hover: "#F4F3EE",
    active: "#EDEAE2",
    fieldBg: "#FFFFFF",
    toggleTrack: "#F4F3EE",
    toggleActive: "#FFFFFF",
    accent: "#C15F3C",
  },
  dark: {
    modalBg: "#262624",
    navBg: "#1F1E1D",
    text: "#F5F4EF",
    textMuted: "#C2C0B6",
    textFaint: "#8A877E",
    placeholder: "#6B6862",
    border: "#3A3937",
    borderInput: "#45433F",
    hover: "#353432",
    active: "#30302E",
    fieldBg: "#30302E",
    toggleTrack: "#1F1E1D",
    toggleActive: "#45433F",
    accent: "#D97757",
  },
};

function Field({ c, label, children, hint, multiline, first }) {
  return (
    <div
      className={multiline ? "py-5" : "flex items-start justify-between gap-6 py-5"}
      style={first ? undefined : { borderTop: `1px solid ${c.border}` }}
    >
      <div className={multiline ? undefined : "pt-1.5"}>
        <p className="text-sm font-medium" style={{ color: c.text }}>{label}</p>
        {hint && <p className="mt-1 text-[13px] leading-snug" style={{ color: c.textMuted }}>{hint}</p>}
      </div>
      {multiline ? children : <div className="flex-shrink-0">{children}</div>}
    </div>
  );
}

function TextInput({ c, value, onChange, placeholder, width = 280 }) {
  return (
    <input
      value={value}
      onChange={onChange}
      placeholder={placeholder}
      className="h-10 rounded-lg px-3.5 text-sm outline-none transition"
      style={{ width, background: c.fieldBg, border: `1px solid ${c.borderInput}`, color: c.text }}
      onFocus={(e) => (e.currentTarget.style.borderColor = c.accent)}
      onBlur={(e) => (e.currentTarget.style.borderColor = c.borderInput)}
    />
  );
}

function GeneralPanel({ c, user, themePref, onThemeChange, onProfileUpdate }) {
  const fallbackName = user?.displayName || user?.email?.split("@")[0] || "";
  const initial = (fallbackName.trim()[0] || "U").toUpperCase();
  const [fullName, setFullName] = useState(fallbackName);
  const [callName, setCallName] = useState(fallbackName);
  const [photoURL, setPhotoURL] = useState(user?.photoURL || "");
  const [uploading, setUploading] = useState(false);
  const [savingName, setSavingName] = useState(false);
  const [nameSaved, setNameSaved] = useState(false);
  const [error, setError] = useState("");
  const fileInputRef = useRef(null);
  const saveTimer = useRef(null);
  const savedTimer = useRef(null);

  // Keep local fields in sync if the underlying user changes.
  useEffect(() => {
    setFullName(user?.displayName || user?.email?.split("@")[0] || "");
    setPhotoURL(user?.photoURL || "");
  }, [user]);

  useEffect(() => () => {
    if (saveTimer.current) clearTimeout(saveTimer.current);
    if (savedTimer.current) clearTimeout(savedTimer.current);
  }, []);

  // Debounced auto-save of the display name to Firebase Auth + Firestore.
  const handleNameChange = (value) => {
    setFullName(value);
    setError("");
    setNameSaved(false);
    if (saveTimer.current) clearTimeout(saveTimer.current);
    saveTimer.current = setTimeout(() => {
      const clean = value.trim();
      if (!clean || !auth.currentUser || clean === (user?.displayName || "")) return;
      setSavingName(true);
      Promise.all([
        updateProfile(auth.currentUser, { displayName: clean }),
        setDoc(
          doc(db, "users", auth.currentUser.uid),
          { displayName: clean, email: auth.currentUser.email || null, updatedAt: serverTimestamp() },
          { merge: true }
        ),
      ])
        .then(() => {
          onProfileUpdate?.();
          setNameSaved(true);
          if (savedTimer.current) clearTimeout(savedTimer.current);
          savedTimer.current = setTimeout(() => setNameSaved(false), 1800);
        })
        .catch(() => setError("Couldn't save your name. Try again."))
        .finally(() => setSavingName(false));
    }, 600);
  };

  // Upload avatar to Firebase Storage and save its URL to the profile.
  const handleAvatarSelect = async (event) => {
    const file = event.target.files?.[0];
    event.target.value = "";
    if (!file || !auth.currentUser) return;
    if (!file.type.startsWith("image/")) {
      setError("Please choose an image file.");
      return;
    }
    if (file.size > 5 * 1024 * 1024) {
      setError("Image must be under 5 MB.");
      return;
    }
    setError("");
    setUploading(true);
    try {
      const uid = auth.currentUser.uid;
      const ext = (file.name.split(".").pop() || "jpg").toLowerCase();
      const ref = storageRef(storage, `users/${uid}/avatar/profile.${ext}`);
      await uploadBytes(ref, file, { contentType: file.type });
      const url = await getDownloadURL(ref);
      await Promise.all([
        updateProfile(auth.currentUser, { photoURL: url }),
        setDoc(
          doc(db, "users", uid),
          { photoURL: url, email: auth.currentUser.email || null, updatedAt: serverTimestamp() },
          { merge: true }
        ),
      ]);
      setPhotoURL(url);
      onProfileUpdate?.();
    } catch (err) {
      setError("Avatar upload failed. Try again.");
    } finally {
      setUploading(false);
    }
  };

  const themeOptions = [
    { id: "system", icon: Monitor, label: "System" },
    { id: "light", icon: Sun, label: "Light" },
    { id: "dark", icon: Moon, label: "Dark" },
  ];

  return (
    <div className="px-8 py-7">
      <h3 className="text-[15px] font-semibold" style={{ color: c.text }}>Profile</h3>

      <div className="mt-3">
        <Field c={c} label="Avatar" first>
          <input
            ref={fileInputRef}
            type="file"
            accept="image/*"
            className="hidden"
            onChange={handleAvatarSelect}
          />
          <button
            type="button"
            onClick={() => fileInputRef.current?.click()}
            disabled={uploading}
            aria-label="Change avatar"
            className="group relative flex h-11 w-11 items-center justify-center overflow-hidden rounded-full text-sm font-semibold transition"
            style={{ background: c.active, color: c.textMuted, border: `1px solid ${c.border}` }}
            title="Upload a new avatar"
          >
            {photoURL ? (
              <img src={photoURL} alt="Avatar" className="h-full w-full object-cover" />
            ) : (
              initial
            )}
            <span
              className="absolute inset-0 flex items-center justify-center opacity-0 transition group-hover:opacity-100"
              style={{ background: "rgba(0,0,0,0.45)", color: "#fff" }}
            >
              {uploading ? <Loader2 size={16} className="animate-spin" /> : <Camera size={16} />}
            </span>
          </button>
        </Field>

        <Field c={c} label="Full name">
          <div className="flex items-center gap-2">
            {savingName && <Loader2 size={15} className="animate-spin" style={{ color: c.textFaint }} />}
            {nameSaved && !savingName && <Check size={15} style={{ color: c.accent }} />}
            <TextInput c={c} value={fullName} onChange={(e) => handleNameChange(e.target.value)} placeholder="Your name" />
          </div>
        </Field>

        {error && (
          <p className="-mt-2 mb-1 text-[13px]" style={{ color: "#E5484D" }}>{error}</p>
        )}

        <Field c={c} label="What should Claude call you?">
          <TextInput c={c} value={callName} onChange={(e) => setCallName(e.target.value)} placeholder="Nickname" />
        </Field>

        <Field c={c} label="What best describes your work?">
          <button
            type="button"
            className="flex h-10 w-[220px] items-center justify-between rounded-lg px-3.5 text-sm transition"
            style={{ background: c.fieldBg, border: `1px solid ${c.borderInput}`, color: c.textMuted }}
          >
            Select
            <ChevronDown size={16} style={{ color: c.textFaint }} />
          </button>
        </Field>
      </div>

      <h3 className="mt-6 text-[15px] font-semibold" style={{ color: c.text }}>Preferences</h3>
      <div className="mt-3">
        <Field c={c} label="Appearance" first>
          <div className="flex items-center gap-1 rounded-lg p-1" style={{ background: c.toggleTrack, border: `1px solid ${c.border}` }}>
            {themeOptions.map(({ id, icon: Icon, label }) => {
              const isActive = themePref === id;
              return (
                <button
                  key={id}
                  type="button"
                  title={label}
                  onClick={() => onThemeChange?.(id)}
                  className="flex h-8 w-10 items-center justify-center rounded-md transition"
                  style={{
                    background: isActive ? c.toggleActive : "transparent",
                    boxShadow: isActive ? "0 1px 2px rgba(0,0,0,0.12)" : "none",
                    color: isActive ? c.text : c.textFaint,
                  }}
                >
                  <Icon size={16} />
                </button>
              );
            })}
          </div>
        </Field>
      </div>
    </div>
  );
}

function ActionRow({ c, label, hint, children, first }) {
  return (
    <div
      className="flex items-center justify-between gap-6 py-5"
      style={first ? undefined : { borderTop: `1px solid ${c.border}` }}
    >
      <div>
        <p className="text-sm font-medium" style={{ color: c.text }}>{label}</p>
        {hint && <p className="mt-1 text-[13px] leading-snug" style={{ color: c.textMuted }}>{hint}</p>}
      </div>
      <div className="flex-shrink-0">{children}</div>
    </div>
  );
}

function AccountPanel({ c, user, onSignOut }) {
  const orgId = user?.uid || "—";
  const sessionDate = useMemo(() => {
    const d = new Date();
    return d.toLocaleString(undefined, { month: "short", day: "numeric", year: "numeric", hour: "numeric", minute: "2-digit" });
  }, []);
  const browser = useMemo(() => {
    const ua = typeof navigator !== "undefined" ? navigator.userAgent : "";
    if (/Edg\//.test(ua)) return "Edge";
    if (/Chrome\//.test(ua)) return "Chrome";
    if (/Firefox\//.test(ua)) return "Firefox";
    if (/Safari\//.test(ua)) return "Safari";
    return "Browser";
  }, []);

  const outlineBtn = {
    background: c.fieldBg,
    border: `1px solid ${c.borderInput}`,
    color: c.text,
  };

  return (
    <div className="px-8 py-7">
      <h3 className="text-[15px] font-semibold" style={{ color: c.text }}>Account</h3>

      <div className="mt-3">
        <ActionRow c={c} label="Log out of all devices" first>
          <button
            type="button"
            onClick={onSignOut}
            className="h-9 rounded-lg px-4 text-sm font-medium transition"
            style={outlineBtn}
            onMouseEnter={(e) => (e.currentTarget.style.background = c.hover)}
            onMouseLeave={(e) => (e.currentTarget.style.background = c.fieldBg)}
          >
            Log out
          </button>
        </ActionRow>

        <ActionRow c={c} label="Delete your account">
          <button
            type="button"
            className="h-9 rounded-lg px-4 text-sm font-medium transition"
            style={outlineBtn}
            onMouseEnter={(e) => { e.currentTarget.style.background = c.accent; e.currentTarget.style.color = "#fff"; e.currentTarget.style.borderColor = c.accent; }}
            onMouseLeave={(e) => { e.currentTarget.style.background = c.fieldBg; e.currentTarget.style.color = c.text; e.currentTarget.style.borderColor = c.borderInput; }}
          >
            Delete account
          </button>
        </ActionRow>

        <ActionRow c={c} label="Organization ID">
          <code
            className="rounded-md px-2.5 py-1.5 text-[12px]"
            style={{ background: c.hover, border: `1px solid ${c.border}`, color: c.textMuted, fontFamily: "'JetBrains Mono', monospace" }}
          >
            {orgId}
          </code>
        </ActionRow>
      </div>

      <h3 className="mt-7 text-[15px] font-semibold" style={{ color: c.text }}>Active sessions</h3>
      <div className="mt-4 overflow-hidden rounded-xl" style={{ border: `1px solid ${c.border}` }}>
        <div
          className="grid grid-cols-[1.4fr_1.3fr_1.2fr_1.2fr_auto] gap-3 px-4 py-2.5 text-[12px] font-medium"
          style={{ background: c.hover, color: c.textMuted }}
        >
          <span>Device</span>
          <span>Location</span>
          <span>Created</span>
          <span>Updated</span>
          <span />
        </div>
        <div
          className="grid grid-cols-[1.4fr_1.3fr_1.2fr_1.2fr_auto] items-center gap-3 px-4 py-3 text-[13px]"
          style={{ color: c.text }}
        >
          <span className="flex items-center gap-2">
            {browser}
            <span
              className="rounded px-1.5 py-0.5 text-[11px] font-medium"
              style={{ background: c.accent, color: "#fff" }}
            >
              Current
            </span>
          </span>
          <span style={{ color: c.textMuted }}>—</span>
          <span style={{ color: c.textMuted }}>{sessionDate}</span>
          <span style={{ color: c.textMuted }}>{sessionDate}</span>
          <MoreVertical size={16} style={{ color: c.textFaint }} />
        </div>
      </div>
    </div>
  );
}

export default function SettingsModal({ open, onClose, user, onSignOut, onProfileUpdate }) {
  const [section, setSection] = useState("general");
  const [query, setQuery] = useState("");
  const { preference: themePref, resolved, setTheme } = useTheme();

  const c = resolved === "light" ? THEMES.light : THEMES.dark;

  useEffect(() => {
    if (!open) return undefined;
    const onKey = (e) => { if (e.key === "Escape") onClose?.(); };
    document.addEventListener("keydown", onKey);
    return () => document.removeEventListener("keydown", onKey);
  }, [open, onClose]);

  const filteredNav = useMemo(() => {
    if (!query.trim()) return NAV;
    const q = query.toLowerCase();
    return NAV.filter((item) => item.label.toLowerCase().includes(q));
  }, [query]);

  if (!open) return null;

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center p-4"
      style={{ background: "rgba(15,13,11,0.6)" }}
      onMouseDown={(e) => { if (e.target === e.currentTarget) onClose?.(); }}
    >
      <div
        role="dialog"
        aria-modal="true"
        aria-label="Settings"
        className="flex w-full overflow-hidden rounded-2xl shadow-2xl"
        style={{ maxWidth: "920px", height: "min(760px, 90vh)", background: c.modalBg, color: c.text }}
      >
        {/* Left nav */}
        <aside className="flex w-[270px] flex-none flex-col" style={{ background: c.navBg, borderRight: `1px solid ${c.border}` }}>
          <div className="px-5 pt-6 pb-3">
            <h2 className="text-xl font-semibold" style={{ color: c.text }}>Settings</h2>
            <div className="mt-4 flex items-center gap-2 rounded-lg px-3 h-10" style={{ background: c.fieldBg, border: `1px solid ${c.borderInput}` }}>
              <Search size={16} style={{ color: c.textFaint }} />
              <input
                value={query}
                onChange={(e) => setQuery(e.target.value)}
                placeholder="Search"
                className="w-full bg-transparent text-sm outline-none"
                style={{ color: c.text }}
              />
            </div>
          </div>

          <nav className="flex-1 overflow-y-auto px-3 pb-4">
            {filteredNav.map(({ id, label, icon: Icon }) => {
              const isActive = section === id;
              return (
                <button
                  key={id}
                  type="button"
                  onClick={() => setSection(id)}
                  className="mb-0.5 flex w-full items-center gap-3 rounded-lg px-3 py-2.5 text-left text-sm transition"
                  style={{
                    background: isActive ? c.active : "transparent",
                    color: isActive ? c.text : c.textMuted,
                    fontWeight: isActive ? 600 : 400,
                  }}
                  onMouseEnter={(e) => { if (!isActive) e.currentTarget.style.background = c.hover; }}
                  onMouseLeave={(e) => { if (!isActive) e.currentTarget.style.background = "transparent"; }}
                >
                  <Icon size={18} strokeWidth={1.9} style={{ color: isActive ? c.text : c.textFaint }} />
                  {label}
                </button>
              );
            })}
          </nav>
        </aside>

        {/* Right content */}
        <div className="relative flex-1 overflow-y-auto">
          <button
            type="button"
            onClick={onClose}
            aria-label="Close settings"
            className="absolute right-4 top-4 z-10 flex h-8 w-8 items-center justify-center rounded-lg transition"
            style={{ color: c.textMuted }}
            onMouseEnter={(e) => (e.currentTarget.style.background = c.hover)}
            onMouseLeave={(e) => (e.currentTarget.style.background = "transparent")}
          >
            <X size={18} />
          </button>

          {section === "account" ? (
            <AccountPanel c={c} user={user} onSignOut={onSignOut} />
          ) : (
            <GeneralPanel c={c} user={user} themePref={themePref} onThemeChange={setTheme} onProfileUpdate={onProfileUpdate} />
          )}
        </div>
      </div>
    </div>
  );
}
