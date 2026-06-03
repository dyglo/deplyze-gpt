import React, { createContext, useCallback, useContext, useEffect, useMemo, useState } from "react";

const STORAGE_KEY = "deplyze-theme";
const ThemeContext = createContext(null);

function readStoredPreference() {
  if (typeof window === "undefined") return "dark";
  const stored = window.localStorage.getItem(STORAGE_KEY);
  return stored === "light" || stored === "dark" || stored === "system" ? stored : "dark";
}

function systemPrefersDark() {
  return typeof window !== "undefined" && window.matchMedia
    ? window.matchMedia("(prefers-color-scheme: dark)").matches
    : true;
}

/** Resolve a preference ("system" | "light" | "dark") to the concrete theme. */
function resolveTheme(preference) {
  if (preference === "system") return systemPrefersDark() ? "dark" : "light";
  return preference;
}

function applyTheme(resolved) {
  if (typeof document === "undefined") return;
  document.documentElement.setAttribute("data-theme", resolved);
  document.documentElement.style.colorScheme = resolved;
}

export function ThemeProvider({ children }) {
  const [preference, setPreference] = useState(readStoredPreference);
  const [resolved, setResolved] = useState(() => resolveTheme(readStoredPreference()));

  // Apply theme + persist preference whenever it changes.
  useEffect(() => {
    const next = resolveTheme(preference);
    setResolved(next);
    applyTheme(next);
    if (typeof window !== "undefined") window.localStorage.setItem(STORAGE_KEY, preference);
  }, [preference]);

  // When following the system, react to OS-level theme changes.
  useEffect(() => {
    if (preference !== "system" || typeof window === "undefined" || !window.matchMedia) return undefined;
    const media = window.matchMedia("(prefers-color-scheme: dark)");
    const handler = () => {
      const next = systemPrefersDark() ? "dark" : "light";
      setResolved(next);
      applyTheme(next);
    };
    media.addEventListener("change", handler);
    return () => media.removeEventListener("change", handler);
  }, [preference]);

  const value = useMemo(
    () => ({ preference, resolved, setTheme: (next) => setPreference(next) }),
    [preference, resolved]
  );

  return <ThemeContext.Provider value={value}>{children}</ThemeContext.Provider>;
}

export function useTheme() {
  const ctx = useContext(ThemeContext);
  if (!ctx) throw new Error("useTheme must be used within a ThemeProvider");
  return ctx;
}
