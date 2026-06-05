import React, { useEffect, useState } from "react";
import { BrowserRouter, Navigate, Route, Routes } from "react-router-dom";
import { onAuthStateChanged, signOut } from "firebase/auth";
import Studio from "./components/Studio";
import AuthPage from "./pages/AuthPage";
import { ThemeProvider } from "./theme";
import { auth, initializeAnalytics } from "./firebase";
import "./App.css";


function LoadingScreen() {
  return (
    <div className="h-screen w-full flex items-center justify-center" style={{ background: "#111111", color: "#F5F4EF" }}>
      <div className="flex items-center gap-3 text-sm" style={{ color: "#A1A1AA" }}>
        <span className="h-2 w-2 rounded-full animate-pulse" style={{ background: "#C96A2A" }} />
        Loading
      </div>
    </div>
  );
}

function AppRoutes() {
  const [user, setUser] = useState(null);
  const [authReady, setAuthReady] = useState(false);
  // Bumped after a profile edit to force a re-render with the updated
  // displayName/photoURL (updateProfile does not fire onAuthStateChanged).
  const [profileVersion, setProfileVersion] = useState(0);

  useEffect(() => {
    initializeAnalytics().catch(() => null);
    return onAuthStateChanged(auth, (nextUser) => {
      setUser(nextUser);
      setAuthReady(true);
    });
  }, []);

  const handleSignOut = async () => {
    Object.keys(localStorage)
      .filter((key) => key.startsWith("deplyzegpt.activeSession."))
      .forEach((key) => localStorage.removeItem(key));
    await signOut(auth);
  };

  // updateProfile() mutates auth.currentUser in place without firing
  // onAuthStateChanged, so bump a version to re-render with the new values.
  const handleProfileUpdate = () => setProfileVersion((v) => v + 1);

  if (!authReady) return <LoadingScreen />;

  return (
    <Routes>
      <Route path="/auth" element={user ? <Navigate to="/" replace /> : <AuthPage />} />
      <Route
        path="/"
        element={
          user ? (
            <Studio
              user={user}
              onSignOut={handleSignOut}
              onProfileUpdate={handleProfileUpdate}
              profileVersion={profileVersion}
            />
          ) : (
            <Navigate to="/auth" replace />
          )
        }
      />
      <Route path="*" element={<Navigate to={user ? "/" : "/auth"} replace />} />
    </Routes>
  );
}

export default function App() {
  return (
    <ThemeProvider>
      <BrowserRouter>
        <AppRoutes />
      </BrowserRouter>
    </ThemeProvider>
  );
}
