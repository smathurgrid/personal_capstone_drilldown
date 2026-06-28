import { useState } from "react";
import type { FormEvent } from "react";
import { ArrowRight, Loader2, Lock, Mail, UserPlus } from "lucide-react";
import type { AuthUser } from "../services/auth-api";
import { login, register } from "../services/auth-api";

type AuthMode = "login" | "register";

interface AuthPageProps {
  onAuthenticated: (user: AuthUser) => void;
}

function friendlyError(error: unknown): string {
  if (!(error instanceof Error)) return "Something went wrong";
  try {
    const parsed = JSON.parse(error.message) as { detail?: string | { msg?: string }[] };
    if (typeof parsed.detail === "string") return parsed.detail;
    if (Array.isArray(parsed.detail) && parsed.detail[0]?.msg) return parsed.detail[0].msg;
  } catch {
    return error.message;
  }
  return error.message;
}

export default function AuthPage({ onAuthenticated }: AuthPageProps) {
  const [mode, setMode] = useState<AuthMode>("login");
  const [name, setName] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  const isRegister = mode === "register";

  const handleSubmit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    setError("");
    setLoading(true);
    try {
      const user = isRegister
        ? await register(name.trim(), email.trim(), password)
        : await login(email.trim(), password);
      onAuthenticated(user);
    } catch (err) {
      setError(friendlyError(err));
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen bg-[#060809] text-on-surface flex flex-col selection:bg-secondary selection:text-on-secondary overflow-hidden">
      <header className="fixed top-0 left-0 w-full z-[1000] bg-navy-mid/75 backdrop-blur-[20px] shadow-[0_40px_80px_rgba(0,0,0,0.4)] border-b border-white/5">
        <div className="flex justify-between items-center h-20 px-8 md:px-16 w-full max-w-[1920px] mx-auto">
          <div className="flex items-center gap-3">
            <span className="font-serif text-2xl font-black tracking-tighter">
              <span className="text-white">Drill</span>
              <span className="text-[#ff6b35]">Down</span>
            </span>
          </div>
          <div className="hidden md:flex items-center gap-2 font-mono text-[10px] uppercase tracking-[2px] text-on-surface-variant">
            <Lock className="w-3.5 h-3.5 text-secondary" />
            Secure Workspace
          </div>
        </div>
      </header>

      <main className="flex-1 flex items-center justify-center px-6 pt-20 relative">
        <div className="absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 w-[680px] h-[680px] rounded-full bg-navy-light/10 blur-[150px] pointer-events-none" />

        <section className="w-full max-w-md z-10 bg-navy-mid/60 backdrop-blur-2xl rounded-2xl border border-white/10 p-5 shadow-[0_30px_60px_rgba(0,0,0,0.5)]">
          <div className="text-center space-y-3 mb-6">
            <p className="font-mono text-[10px] uppercase tracking-[2px] text-secondary">
              {isRegister ? "Create Account" : "Welcome Back"}
            </p>
            <h1 className="font-serif text-4xl font-black tracking-tighter leading-none">
              <span className="text-white">DRILL</span>
              <span className="text-[#ff6b35]">DOWN</span>
            </h1>
          </div>

          <div className="grid grid-cols-2 gap-2 bg-black/30 border border-white/10 rounded-xl p-1 mb-5">
            <button
              type="button"
              onClick={() => setMode("login")}
              className={`py-2 rounded-lg font-mono text-[10px] uppercase font-bold tracking-wider transition-all ${
                !isRegister ? "bg-primary-container text-primary border border-primary/25" : "text-outline hover:text-on-surface"
              }`}
            >
              Login
            </button>
            <button
              type="button"
              onClick={() => setMode("register")}
              className={`py-2 rounded-lg font-mono text-[10px] uppercase font-bold tracking-wider transition-all ${
                isRegister ? "bg-secondary-container/30 text-secondary border border-secondary/25" : "text-outline hover:text-on-surface"
              }`}
            >
              Create
            </button>
          </div>

          <form onSubmit={handleSubmit} className="space-y-3">
            {isRegister && (
              <label className="flex items-center gap-3 bg-black/40 border border-white/5 p-3.5 rounded-xl">
                <UserPlus className="w-5 h-5 text-orange-glow shrink-0" />
                <input
                  value={name}
                  onChange={(event) => setName(event.target.value)}
                  placeholder="Your name"
                  className="w-full bg-transparent border-none text-on-surface placeholder:text-outline-variant focus:outline-none focus:ring-0 text-md font-light"
                  minLength={2}
                  maxLength={120}
                  required
                />
              </label>
            )}

            <label className="flex items-center gap-3 bg-black/40 border border-white/5 p-3.5 rounded-xl">
              <Mail className="w-5 h-5 text-orange-glow shrink-0" />
              <input
                type="email"
                value={email}
                onChange={(event) => setEmail(event.target.value)}
                placeholder="Email address"
                className="w-full bg-transparent border-none text-on-surface placeholder:text-outline-variant focus:outline-none focus:ring-0 text-md font-light"
                required
              />
            </label>

            <label className="flex items-center gap-3 bg-black/40 border border-white/5 p-3.5 rounded-xl">
              <Lock className="w-5 h-5 text-orange-glow shrink-0" />
              <input
                type="password"
                value={password}
                onChange={(event) => setPassword(event.target.value)}
                placeholder="Password"
                className="w-full bg-transparent border-none text-on-surface placeholder:text-outline-variant focus:outline-none focus:ring-0 text-md font-light"
                minLength={isRegister ? 8 : 1}
                maxLength={128}
                required
              />
            </label>

            {error && (
              <div className="bg-red-500/10 border border-red-500/25 text-red-200 rounded-xl px-3 py-2 text-sm">
                {error}
              </div>
            )}

            <button
              type="submit"
              disabled={loading}
              className="w-full flex items-center justify-center gap-2 py-3 bg-orange-glow rounded-xl text-white font-mono text-[11px] uppercase font-black tracking-widest cursor-pointer hover:bg-[#E0784C] transition-all disabled:opacity-60"
            >
              {loading ? <Loader2 className="w-4 h-4 animate-spin" /> : <ArrowRight className="w-4 h-4" />}
              {isRegister ? "Create Account" : "Login"}
            </button>
          </form>
        </section>
      </main>
    </div>
  );
}
