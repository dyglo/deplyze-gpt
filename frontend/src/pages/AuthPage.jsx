import React, { useMemo, useState } from "react";
import {
  createUserWithEmailAndPassword,
  GoogleAuthProvider,
  signInWithEmailAndPassword,
  signInWithPopup,
  updateProfile,
} from "firebase/auth";
import { Eye, EyeOff, Loader2 } from "lucide-react";
import { auth } from "../firebase";


function BrandMark() {
  return (
    <svg width="22" height="22" viewBox="0 0 24 24" fill="none" aria-hidden="true">
      <path
        d="M4 16 9 5l3 6 3-6 5 11"
        stroke="#171717"
        strokeWidth="2"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
    </svg>
  );
}

function GoogleIcon() {
  return (
    <svg width="18" height="18" viewBox="0 0 24 24" aria-hidden="true">
      <path fill="#4285F4" d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92a5.06 5.06 0 0 1-2.2 3.32v2.77h3.57c2.08-1.92 3.27-4.74 3.27-8.1Z" />
      <path fill="#34A853" d="M12 23c2.97 0 5.46-.98 7.28-2.65l-3.57-2.77c-.98.66-2.23 1.06-3.71 1.06-2.86 0-5.29-1.93-6.16-4.53H2.18v2.84A11 11 0 0 0 12 23Z" />
      <path fill="#FBBC05" d="M5.84 14.1a6.6 6.6 0 0 1 0-4.22V7.04H2.18a11 11 0 0 0 0 9.9l3.66-2.84Z" />
      <path fill="#EA4335" d="M12 5.38c1.62 0 3.06.56 4.21 1.64l3.15-3.15C17.45 2.09 14.97 1 12 1A11 11 0 0 0 2.18 7.04l3.66 2.84C6.71 7.3 9.14 5.38 12 5.38Z" />
    </svg>
  );
}

function authMessage(error) {
  const code = error?.code || "";
  if (code.includes("invalid-credential") || code.includes("wrong-password")) return "Email or password is incorrect.";
  if (code.includes("email-already-in-use")) return "An account already exists for this email.";
  if (code.includes("weak-password")) return "Use a stronger password.";
  if (code.includes("popup-closed-by-user")) return "Sign-in was closed before it finished.";
  if (code.includes("account-exists-with-different-credential")) return "This email is already linked to another sign-in method.";
  if (code.includes("operation-not-allowed")) return "This sign-in method isn't enabled yet.";
  if (code.includes("too-many-requests")) return "Too many attempts. Try again later.";
  return "Authentication failed. Please try again.";
}

export default function AuthPage() {
  const [mode, setMode] = useState("signup");
  const [form, setForm] = useState({ name: "", email: "", password: "", confirmPassword: "" });
  const [showPassword, setShowPassword] = useState(false);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(null);

  const isSignUp = mode === "signup";
  const heading = useMemo(() => (isSignUp ? "Create an account" : "Welcome back"), [isSignUp]);
  const subheading = useMemo(
    () =>
      isSignUp
        ? "Access your tasks, notes, and projects anytime, anywhere — and keep everything flowing in one place."
        : "Sign in to pick up right where you left off.",
    [isSignUp]
  );
  const submitLabel = isSignUp ? "Create account" : "Sign in";

  const updateField = (event) => {
    setForm((current) => ({ ...current, [event.target.name]: event.target.value }));
  };

  const switchMode = () => {
    setMode((current) => (current === "signup" ? "signin" : "signup"));
    setError("");
  };

  const submitEmail = async (event) => {
    event.preventDefault();
    setError("");

    if (isSignUp && form.confirmPassword && form.password !== form.confirmPassword) {
      setError("Passwords do not match.");
      return;
    }

    setLoading("email");
    try {
      if (isSignUp) {
        const credential = await createUserWithEmailAndPassword(auth, form.email, form.password);
        if (form.name.trim()) {
          await updateProfile(credential.user, { displayName: form.name.trim() });
        }
      } else {
        await signInWithEmailAndPassword(auth, form.email, form.password);
      }
    } catch (err) {
      setError(authMessage(err));
    } finally {
      setLoading(null);
    }
  };

  const submitGoogle = async () => {
    setError("");
    setLoading("google");
    try {
      await signInWithPopup(auth, new GoogleAuthProvider());
    } catch (err) {
      setError(authMessage(err));
    } finally {
      setLoading(null);
    }
  };

  return (
    <main className="min-h-screen w-full grid lg:grid-cols-2 bg-white text-neutral-900">
      {/* Left — brand panel */}
      <aside
        className="relative hidden lg:flex flex-col justify-between p-10 overflow-hidden"
        style={{
          background:
            "radial-gradient(120% 120% at 80% 80%, #FF7A2F 0%, #FF9A52 28%, #FBC9A3 55%, #FBEDE2 78%, #FFFFFF 100%)",
        }}
      >
        <div className="flex items-center gap-2">
          <BrandMark />
          <span className="text-lg font-semibold tracking-tight text-neutral-900">DeplyzeGPT</span>
        </div>

        <div className="max-w-sm">
          <p className="text-sm font-medium text-neutral-800/80">You can easily</p>
          <h2 className="mt-2 text-3xl font-semibold leading-snug tracking-tight text-neutral-900">
            Get access to your personal hub for clarity and productivity.
          </h2>
        </div>
      </aside>

      {/* Right — form panel */}
      <section className="flex items-center justify-center px-6 py-8 sm:px-12">
        <div className="w-full max-w-sm">
          {/* mobile brand */}
          <div className="mb-6 flex items-center gap-2 lg:hidden">
            <BrandMark />
            <span className="text-lg font-semibold tracking-tight">DeplyzeGPT</span>
          </div>

          <div className="text-orange-500 text-xl leading-none mb-3" aria-hidden="true">✳</div>

          <h1 className="text-2xl font-semibold tracking-tight">{heading}</h1>
          <p className="mt-1.5 text-sm leading-relaxed text-neutral-500">{subheading}</p>

          <form onSubmit={submitEmail} className="mt-6 space-y-3.5">
            {isSignUp && (
              <div>
                <label htmlFor="name" className="block text-sm font-medium text-neutral-800">
                  Your name
                </label>
                <input
                  id="name"
                  name="name"
                  value={form.name}
                  onChange={updateField}
                  autoComplete="name"
                  placeholder="Natalia Brak"
                  className="mt-1.5 w-full h-10 rounded-lg border border-neutral-200 bg-white px-3.5 text-sm text-neutral-900 placeholder:text-neutral-400 outline-none transition focus:border-orange-400 focus:ring-2 focus:ring-orange-100"
                />
              </div>
            )}

            <div>
              <label htmlFor="email" className="block text-sm font-medium text-neutral-800">
                Your email
              </label>
              <input
                id="email"
                name="email"
                type="email"
                value={form.email}
                onChange={updateField}
                autoComplete="email"
                required
                placeholder="natalia.brak@knmstudio.com"
                className="mt-1.5 w-full h-10 rounded-lg border border-neutral-200 bg-white px-3.5 text-sm text-neutral-900 placeholder:text-neutral-400 outline-none transition focus:border-orange-400 focus:ring-2 focus:ring-orange-100"
              />
            </div>

            <div>
              <label htmlFor="password" className="block text-sm font-medium text-neutral-800">
                {isSignUp ? "Create password" : "Password"}
              </label>
              <div className="relative mt-1.5">
                <input
                  id="password"
                  name="password"
                  type={showPassword ? "text" : "password"}
                  value={form.password}
                  onChange={updateField}
                  autoComplete={isSignUp ? "new-password" : "current-password"}
                  required
                  placeholder="••••••••••••"
                  className="w-full h-10 rounded-lg border border-neutral-200 bg-white px-3.5 pr-11 text-sm text-neutral-900 placeholder:text-neutral-400 outline-none transition focus:border-orange-400 focus:ring-2 focus:ring-orange-100"
                />
                <button
                  type="button"
                  onClick={() => setShowPassword((v) => !v)}
                  aria-label={showPassword ? "Hide password" : "Show password"}
                  className="absolute inset-y-0 right-0 flex items-center pr-3.5 text-neutral-400 transition hover:text-neutral-600"
                >
                  {showPassword ? <EyeOff size={18} /> : <Eye size={18} />}
                </button>
              </div>
            </div>

            {isSignUp && (
              <div>
                <label htmlFor="confirmPassword" className="block text-sm font-medium text-neutral-800">
                  Confirm password
                </label>
                <input
                  id="confirmPassword"
                  name="confirmPassword"
                  type={showPassword ? "text" : "password"}
                  value={form.confirmPassword}
                  onChange={updateField}
                  autoComplete="new-password"
                  placeholder="••••••••••••"
                  className="mt-1.5 w-full h-10 rounded-lg border border-neutral-200 bg-white px-3.5 text-sm text-neutral-900 placeholder:text-neutral-400 outline-none transition focus:border-orange-400 focus:ring-2 focus:ring-orange-100"
                />
              </div>
            )}

            {error && (
              <p className="rounded-lg border border-red-100 bg-red-50 px-3.5 py-2 text-sm text-red-600">
                {error}
              </p>
            )}

            <button
              type="submit"
              disabled={Boolean(loading)}
              className="flex h-10 w-full items-center justify-center gap-2 rounded-lg bg-neutral-900 text-sm font-semibold text-white transition hover:bg-neutral-800 disabled:opacity-60"
            >
              {loading === "email" && <Loader2 size={16} className="animate-spin" />}
              {submitLabel}
            </button>
          </form>

          <div className="my-5 flex items-center gap-4">
            <div className="h-px flex-1 bg-neutral-200" />
            <span className="text-xs text-neutral-400">or continue with</span>
            <div className="h-px flex-1 bg-neutral-200" />
          </div>

          <button
            type="button"
            onClick={submitGoogle}
            disabled={Boolean(loading)}
            className="flex h-10 w-full items-center justify-center gap-2.5 rounded-lg border border-neutral-200 bg-white text-sm font-medium text-neutral-800 transition hover:bg-neutral-50 disabled:opacity-60"
          >
            {loading === "google" ? <Loader2 size={18} className="animate-spin text-neutral-500" /> : <GoogleIcon />}
            Sign in with Google
          </button>

          <p className="mt-5 text-center text-sm text-neutral-500">
            {isSignUp ? "Already have an account?" : "Don't have an account?"}{" "}
            <button
              type="button"
              onClick={switchMode}
              className="font-medium text-orange-500 transition hover:text-orange-600"
            >
              {isSignUp ? "Sign in" : "Register"}
            </button>
          </p>
        </div>
      </section>
    </main>
  );
}
