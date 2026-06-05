import React, { useEffect, useState } from "react";
import { BrowserRouter, Navigate, Route, Routes } from "react-router-dom";
import { onAuthStateChanged, sendEmailVerification, signOut } from "firebase/auth";
import { Loader2, LogOut, MailCheck, RefreshCw, Send } from "lucide-react";
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

function isGoogleUser(user) {
  return Boolean(user?.providerData?.some((provider) => provider.providerId === "google.com"));
}

function needsEmailVerification(user) {
  return Boolean(user && !isGoogleUser(user) && !user.emailVerified);
}

function VerificationScreen({ user, onRefresh, onResend, onSignOut, loadingAction, message, error }) {
  return (
    <main className="min-h-screen w-full bg-white text-neutral-900">
      <section className="flex min-h-screen items-center justify-center px-5 py-10 sm:px-12">
        <div className="w-full max-w-md">
          <div className="mb-8">
            <span className="text-lg font-semibold tracking-tight">DeplyzeGPT</span>
          </div>

          <div className="mb-4 flex h-11 w-11 items-center justify-center rounded-lg bg-orange-50 text-orange-500">
            <MailCheck size={22} aria-hidden="true" />
          </div>

          <h1 className="text-2xl font-semibold tracking-tight">Verify your email</h1>
          <p className="mt-2 text-sm leading-relaxed text-neutral-500">
            Check your inbox for the verification link sent to{" "}
            <span className="font-medium text-neutral-800">{user?.email}</span>. After verifying, refresh your session to continue.
          </p>

          {message && (
            <p className="mt-5 rounded-lg border border-emerald-100 bg-emerald-50 px-3.5 py-2 text-sm text-emerald-700">
              {message}
            </p>
          )}

          {error && (
            <p className="mt-5 rounded-lg border border-red-100 bg-red-50 px-3.5 py-2 text-sm text-red-600">
              {error}
            </p>
          )}

          <div className="mt-6 grid gap-3 sm:grid-cols-2">
            <button
              type="button"
              onClick={onRefresh}
              disabled={Boolean(loadingAction)}
              className="flex h-10 items-center justify-center gap-2 rounded-lg bg-neutral-900 px-4 text-sm font-semibold text-white transition hover:bg-neutral-800 disabled:opacity-60"
            >
              {loadingAction === "refresh" ? <Loader2 size={16} className="animate-spin" /> : <RefreshCw size={16} />}
              Refresh
            </button>
            <button
              type="button"
              onClick={onResend}
              disabled={Boolean(loadingAction)}
              className="flex h-10 items-center justify-center gap-2 rounded-lg border border-neutral-200 bg-white px-4 text-sm font-medium text-neutral-800 transition hover:bg-neutral-50 disabled:opacity-60"
            >
              {loadingAction === "resend" ? <Loader2 size={16} className="animate-spin" /> : <Send size={16} />}
              Resend email
            </button>
          </div>

          <button
            type="button"
            onClick={onSignOut}
            disabled={Boolean(loadingAction)}
            className="mt-4 flex h-10 w-full items-center justify-center gap-2 rounded-lg text-sm font-medium text-neutral-500 transition hover:bg-neutral-50 hover:text-neutral-800 disabled:opacity-60"
          >
            <LogOut size={16} />
            Sign out
          </button>
        </div>
      </section>
    </main>
  );
}

function AppRoutes() {
  const [user, setUser] = useState(null);
  const [authReady, setAuthReady] = useState(false);
  // Bumped after a profile edit to force a re-render with the updated
  // displayName/photoURL (updateProfile does not fire onAuthStateChanged).
  const [profileVersion, setProfileVersion] = useState(0);
  const [verificationAction, setVerificationAction] = useState(null);
  const [verificationMessage, setVerificationMessage] = useState("");
  const [verificationError, setVerificationError] = useState("");

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

  const handleVerificationRefresh = async () => {
    if (!auth.currentUser) return;
    setVerificationAction("refresh");
    setVerificationMessage("");
    setVerificationError("");
    try {
      await auth.currentUser.reload();
      await auth.currentUser.getIdToken(true);
      setUser(auth.currentUser);
      setProfileVersion((v) => v + 1);
      if (auth.currentUser.emailVerified) {
        setVerificationMessage("Email verified. Opening your workspace.");
      } else {
        setVerificationError("This email is not verified yet.");
      }
    } catch {
      setVerificationError("Unable to refresh verification status. Please try again.");
    } finally {
      setVerificationAction(null);
    }
  };

  const handleVerificationResend = async () => {
    if (!auth.currentUser) return;
    setVerificationAction("resend");
    setVerificationMessage("");
    setVerificationError("");
    try {
      await sendEmailVerification(auth.currentUser);
      setVerificationMessage("Verification email sent.");
    } catch {
      setVerificationError("Unable to send verification email right now. Please try again later.");
    } finally {
      setVerificationAction(null);
    }
  };

  if (!authReady) return <LoadingScreen />;

  const userNeedsVerification = needsEmailVerification(user);
  const verificationScreen = (
    <VerificationScreen
      user={user}
      onRefresh={handleVerificationRefresh}
      onResend={handleVerificationResend}
      onSignOut={handleSignOut}
      loadingAction={verificationAction}
      message={verificationMessage}
      error={verificationError}
    />
  );

  return (
    <Routes>
      <Route
        path="/auth"
        element={user ? (userNeedsVerification ? verificationScreen : <Navigate to="/" replace />) : <AuthPage />}
      />
      <Route
        path="/"
        element={
          userNeedsVerification ? (
            verificationScreen
          ) : user ? (
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
