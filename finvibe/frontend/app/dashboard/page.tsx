"use client";

import { useState, useCallback, useEffect } from "react";
import { useRouter } from "next/navigation";
import PortfolioChart from "@/components/PortfolioChart";
import VibeGauge from "@/components/VibeGauge";
import TradeLogTable from "@/components/TradeLogTable";
import ReflectionFeed from "@/components/ReflectionFeed";
import { analyzeTickers, AnalyzeResponse } from "@/lib/api";
import { useAuth } from "@/lib/auth";

export default function DashboardPage() {
  const { user, loading: authLoading } = useAuth();
  const router = useRouter();
  const [tickers, setTickers] = useState("AAPL, TSLA, NVDA");
  const [analyzing, setAnalyzing] = useState(false);
  const [result, setResult] = useState<AnalyzeResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [key, setKey] = useState(0);

  // Redirect if not logged in
  useEffect(() => {
    if (!authLoading && !user) {
      router.push("/login");
    }
  }, [authLoading, user, router]);

  const handleAnalyze = useCallback(async () => {
    setAnalyzing(true);
    setError(null);
    setResult(null);
    try {
      const tickerList = tickers
        .split(",")
        .map((t) => t.trim().toUpperCase())
        .filter(Boolean);
      const res = await analyzeTickers(tickerList, user?.id || "demo_user");
      setResult(res);
      setKey((k) => k + 1);
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Analysis failed");
    } finally {
      setAnalyzing(false);
    }
  }, [tickers, user]);

  if (authLoading) {
    return (
      <div className="flex items-center justify-center min-h-[60vh]">
        <div className="w-8 h-8 border-2 border-indigo-500/30 border-t-indigo-500 rounded-full animate-spin" />
      </div>
    );
  }

  if (!user) return null;

  return (
    <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8 space-y-8">
      {/* ── Welcome Header ─────────────────────────────────── */}
      <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold text-white">
            Welcome back, <span className="gradient-text">{user.name}</span>
          </h1>
          <p className="text-sm text-slate-400 mt-1">
            Your AI portfolio advisor is ready. Run an analysis to see real-time insights.
          </p>
        </div>
        <div className="flex items-center gap-2">
          <span className="pulse-dot" />
          <span className="text-xs text-slate-400">Pipeline online</span>
        </div>
      </div>

      {/* ── Analyze Control Bar ────────────────────────────── */}
      <section className="glass-card p-6">
        <div className="flex items-center gap-3 mb-5">
          <div className="w-10 h-10 rounded-xl bg-gradient-to-br from-indigo-500/20 to-purple-500/20 border border-indigo-500/20 flex items-center justify-center text-lg">
            🎯
          </div>
          <div>
            <h2 className="text-lg font-bold text-white">Run Analysis</h2>
            <p className="text-xs text-slate-500">Enter tickers for the 6-node AI pipeline</p>
          </div>
        </div>

        <div className="flex flex-wrap items-end gap-4">
          <div className="flex-1 min-w-[200px]">
            <label className="text-xs text-slate-400 mb-1.5 block font-medium">
              Tickers (comma-separated)
            </label>
            <input
              type="text"
              value={tickers}
              onChange={(e) => setTickers(e.target.value)}
              className="input-dark"
              placeholder="AAPL, TSLA, NVDA, MSFT"
              onKeyDown={(e) => e.key === "Enter" && !analyzing && handleAnalyze()}
            />
          </div>
          <button
            onClick={handleAnalyze}
            disabled={analyzing}
            className="btn-glow px-7 py-3 text-sm disabled:opacity-50 disabled:cursor-not-allowed flex items-center gap-2"
          >
            {analyzing ? (
              <>
                <span className="w-4 h-4 border-2 border-white/30 border-t-white rounded-full animate-spin" />
                Analyzing...
              </>
            ) : (
              <>
                <span>⚡</span> Analyze
              </>
            )}
          </button>
        </div>

        {/* Result banner */}
        {result && (
          <div className="mt-5 p-5 rounded-xl bg-emerald-500/5 border border-emerald-500/20 animate-fade-in">
            <div className="flex items-center gap-2 mb-3">
              <span className="text-emerald-400 text-lg">✓</span>
              <span className="text-emerald-400 font-semibold">Analysis complete</span>
            </div>

            <div className="grid grid-cols-2 sm:grid-cols-4 gap-4 text-sm">
              {[
                { label: "Tickers", val: result.vibe_scores?.map((v: any) => v.ticker).join(", ") || "—" },
                { label: "Trades", val: result.execution_results?.length || 0 },
                { label: "Alert", val: result.alert_sent ? "Yes" : "No" },
                { label: "Status", val: result.status || "—" },
              ].map((s) => (
                <div key={s.label} className="p-3 rounded-lg bg-white/[0.03] border border-white/5">
                  <div className="text-xs text-slate-500 mb-1">{s.label}</div>
                  <div className="font-bold text-white font-mono">{s.val}</div>
                </div>
              ))}
            </div>

            {/* Vibes */}
            {result.vibe_scores && result.vibe_scores.length > 0 && (
              <div className="mt-4 flex flex-wrap gap-2">
                {result.vibe_scores.map((v: any) => (
                  <span
                    key={v.ticker}
                    className={`badge vibe-${v.vibe_label?.toLowerCase()}`}
                    style={{ background: "rgba(255,255,255,0.05)" }}
                  >
                    {v.ticker}: {v.vibe_label} ({v.anxiety_score?.toFixed(1)})
                  </span>
                ))}
              </div>
            )}

            {/* Trades */}
            {result.execution_results && result.execution_results.length > 0 && (
              <div className="mt-3 space-y-1.5">
                {result.execution_results.map((t: any, i: number) => (
                  <div key={i} className="flex items-center gap-3 text-sm">
                    <span className={`badge ${t.action === "BUY" ? "badge-green" : "badge-red"}`}>
                      {t.action}
                    </span>
                    <span className="font-mono font-bold text-white">{t.ticker}</span>
                    <span className="text-slate-400">
                      {t.shares} shares @ ${t.price?.toFixed(2)}
                    </span>
                  </div>
                ))}
              </div>
            )}
          </div>
        )}

        {error && (
          <div className="mt-5 p-4 rounded-xl bg-red-500/5 border border-red-500/20 text-red-400 text-sm animate-fade-in">
            ❌ {error}
          </div>
        )}
      </section>

      {/* ── Row 1 : Portfolio Chart + Vibe Gauge ─────────── */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <div className="glass-card p-6">
          <PortfolioChart key={`chart-${key}`} />
        </div>
        <div className="glass-card p-6">
          <VibeGauge key={`vibe-${key}`} />
        </div>
      </div>

      {/* ── Row 2 : Trade Log + Reflections ──────────────── */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <div className="glass-card p-6">
          <TradeLogTable key={`trades-${key}`} />
        </div>
        <div className="glass-card p-6">
          <ReflectionFeed key={`reflect-${key}`} />
        </div>
      </div>
    </div>
  );
}
