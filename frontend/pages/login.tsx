import React, { useState } from "react";
import Head from "next/head";
import Link from "next/link";
import { useRouter } from "next/router";
import { BrainCircuit, Lock, Mail, ArrowRight, AlertTriangle } from "lucide-react";
import { api } from "../services/api";

export default function Login() {
  const router = useRouter();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoading(true);
    setError("");
    try {
      await api.login({ email, password });
      router.push("/dashboard");
    } catch (err: any) {
      setError(err.message || "Invalid email or password.");
    } finally {
      setLoading(false);
    }
  };

  return (
    <>
      <Head>
        <title>Sign In – EduGenAI Platform</title>
      </Head>

      <div className="min-h-screen bg-[#0a0a0c] text-slate-100 flex items-center justify-center p-6 relative overflow-hidden">
        {/* Glow circles */}
        <div className="absolute top-[-20%] left-[-20%] w-[600px] h-[600px] rounded-full bg-purple-900/10 blur-[150px] pointer-events-none" />
        <div className="absolute bottom-[-20%] right-[-20%] w-[600px] h-[600px] rounded-full bg-indigo-900/10 blur-[150px] pointer-events-none" />

        <div className="w-full max-w-md relative z-10">
          <div className="text-center mb-8">
            <Link href="/" className="inline-flex items-center space-x-2 mb-4">
              <div className="p-2 bg-purple-600/20 border border-purple-500/30 rounded-lg">
                <BrainCircuit className="h-6 w-6 text-purple-400" />
              </div>
              <span className="text-2xl font-bold tracking-tight bg-gradient-to-r from-purple-400 to-indigo-300 bg-clip-text text-transparent">
                EduGenAI
              </span>
            </Link>
            <h2 className="text-2xl font-semibold">Welcome Back</h2>
            <p className="text-slate-400 text-sm mt-2">Sign in to your SPPU academic learning dashboard.</p>
          </div>

          <div className="backdrop-blur-md bg-white/[0.01] border border-white/5 p-8 rounded-2xl shadow-xl">
            {error && (
              <div className="mb-6 p-4 bg-red-500/10 border border-red-500/20 text-red-400 text-sm rounded-xl flex items-center space-x-2">
                <AlertTriangle className="h-5 w-5 shrink-0" />
                <span>{error}</span>
              </div>
            )}

            <form onSubmit={handleSubmit} className="space-y-6">
              <div>
                <label className="block text-xs font-semibold uppercase tracking-wider text-slate-400 mb-2">
                  SPPU Email Address
                </label>
                <div className="relative">
                  <Mail className="absolute left-3.5 top-3.5 h-5 w-5 text-slate-500" />
                  <input
                    type="email"
                    required
                    placeholder="student@sppu.edu.in"
                    value={email}
                    onChange={(e) => setEmail(e.target.value)}
                    className="w-full pl-11 pr-4 py-3 bg-white/[0.02] border border-white/5 hover:border-white/10 focus:border-purple-500/50 focus:bg-white/[0.04] text-slate-100 rounded-xl outline-none transition-all"
                  />
                </div>
              </div>

              <div>
                <div className="flex items-center justify-between mb-2">
                  <label className="block text-xs font-semibold uppercase tracking-wider text-slate-400">
                    Password
                  </label>
                </div>
                <div className="relative">
                  <Lock className="absolute left-3.5 top-3.5 h-5 w-5 text-slate-500" />
                  <input
                    type="password"
                    required
                    placeholder="••••••••"
                    value={password}
                    onChange={(e) => setPassword(e.target.value)}
                    className="w-full pl-11 pr-4 py-3 bg-white/[0.02] border border-white/5 hover:border-white/10 focus:border-purple-500/50 focus:bg-white/[0.04] text-slate-100 rounded-xl outline-none transition-all"
                  />
                </div>
              </div>

              <button
                type="submit"
                disabled={loading}
                className="w-full py-3.5 bg-gradient-to-r from-purple-600 to-indigo-600 hover:from-purple-500 hover:to-indigo-500 text-white font-semibold rounded-xl flex items-center justify-center space-x-2 transition-transform duration-300 hover:scale-[1.02] active:scale-[0.98] disabled:opacity-50"
              >
                <span>{loading ? "Signing In..." : "Sign In"}</span>
                <ArrowRight className="h-5 w-5" />
              </button>
            </form>

            <div className="mt-8 text-center text-sm text-slate-400 border-t border-white/5 pt-6">
              Don't have an account?{" "}
              <Link href="/register" className="text-purple-400 hover:text-purple-300 transition-colors font-medium">
                Register here
              </Link>
            </div>
          </div>
        </div>
      </div>
    </>
  );
}
