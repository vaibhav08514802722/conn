"use client";

import Link from "next/link";
import { useAuth } from "@/lib/auth";

const features = [
  {
    icon: "🎯",
    title: "Vibe Analysis",
    desc: "AI reads market sentiment, news, and social signals to generate a real-time Vibe Score for every stock.",
    badge: "Core",
  },
  {
    icon: "🤖",
    title: "6-Node Agent Pipeline",
    desc: "Researcher → Analyst → Strategist → Executor → Reflector → Alerter. Fully autonomous decision chain.",
    badge: "Agentic AI",
  },
  {
    icon: "📊",
    title: "Shadow Portfolio",
    desc: "Paper-trade with $1M virtual capital. Track performance, P&L, and compare against benchmarks.",
    badge: "Trading",
  },
  {
    icon: "🧠",
    title: "Memory & Learning",
    desc: "The agent remembers past trades, evaluates outcomes, and generates lessons that improve future strategies.",
    badge: "Adaptive",
  },
  {
    icon: "🚨",
    title: "Crisis Alerts",
    desc: "When market anxiety spikes above threshold, get instant in-app alerts — or even an AI voice call via Vapi.",
    badge: "Real-time",
  },
  {
    icon: "💬",
    title: "Live SSE Chat",
    desc: "Watch the AI pipeline think in real-time. Every node streams its output as it processes your request.",
    badge: "Streaming",
  },
];

const showcaseTickers = [
  { ticker: "AAPL", name: "Apple Inc.", vibe: "Bullish", color: "text-emerald-400", change: "+1.2%", anxiety: 2.3 },
  { ticker: "TSLA", name: "Tesla Inc.", vibe: "Anxious", color: "text-orange-400", change: "-3.5%", anxiety: 7.1 },
  { ticker: "NVDA", name: "NVIDIA Corp.", vibe: "Euphoric", color: "text-green-400", change: "+4.8%", anxiety: 1.1 },
  { ticker: "MSFT", name: "Microsoft Corp.", vibe: "Neutral", color: "text-yellow-400", change: "+0.3%", anxiety: 4.5 },
  { ticker: "AMZN", name: "Amazon.com Inc.", vibe: "Bullish", color: "text-emerald-400", change: "+2.1%", anxiety: 3.2 },
  { ticker: "META", name: "Meta Platforms", vibe: "Neutral", color: "text-yellow-400", change: "-0.8%", anxiety: 5.0 },
];

const stats = [
  { value: "6", label: "AI Agent Nodes" },
  { value: "3", label: "Vector Databases" },
  { value: "$1M", label: "Virtual Capital" },
  { value: "24/7", label: "Autonomous Trading" },
];

export default function LandingPage() {
  const { user } = useAuth();

  return (
    <div className="relative">
      {/* ════════════ HERO SECTION ════════════ */}
      <section className="relative min-h-[90vh] flex items-center justify-center overflow-hidden">
        {/* Background Orbs */}
        <div className="orb orb-1" />
        <div className="orb orb-2" />
        <div className="orb orb-3" />

        {/* Grid pattern overlay */}
        <div
          className="absolute inset-0 opacity-[0.03]"
          style={{
            backgroundImage: `linear-gradient(rgba(99,102,241,0.3) 1px, transparent 1px),
                              linear-gradient(90deg, rgba(99,102,241,0.3) 1px, transparent 1px)`,
            backgroundSize: "60px 60px",
          }}
        />

        <div className="relative z-10 max-w-6xl mx-auto px-4 text-center">
          {/* Badge */}
          <div className="animate-fade-in-up inline-flex items-center gap-2 px-4 py-1.5 rounded-full border border-indigo-500/20 bg-indigo-500/5 mb-8">
            <span className="pulse-dot" />
            <span className="text-sm text-indigo-300 font-medium">
              Powered by Advanced AI + LangGraph
            </span>
          </div>

          {/* Headline */}
          <h1 className="animate-fade-in-up delay-100 text-5xl sm:text-6xl lg:text-7xl font-extrabold leading-tight tracking-tight mb-6">
            <span className="text-white">AI-Powered</span>
            <br />
            <span className="gradient-text">Portfolio Advisor</span>
          </h1>

          {/* Subtitle */}
          <p className="animate-fade-in-up delay-200 text-lg sm:text-xl text-slate-400 max-w-2xl mx-auto mb-10 leading-relaxed">
            FinVibe uses a <strong className="text-slate-200">6-node agentic AI pipeline</strong> to
            analyze market sentiment, generate vibe scores, execute paper trades, and
            learn from its own mistakes — <span className="text-indigo-400">all autonomously</span>.
          </p>

          {/* CTA Buttons */}
          <div className="animate-fade-in-up delay-300 flex flex-wrap items-center justify-center gap-4 mb-16">
            {user ? (
              <Link href="/dashboard" className="btn-glow px-8 py-3.5 text-base">
                Go to Dashboard →
              </Link>
            ) : (
              <>
                <Link href="/signup" className="btn-glow px-8 py-3.5 text-base">
                  Get Started Free →
                </Link>
                <Link href="/login" className="btn-outline px-8 py-3.5 text-base">
                  Login
                </Link>
              </>
            )}
          </div>

          {/* Stats Row */}
          <div className="animate-fade-in-up delay-400 grid grid-cols-2 sm:grid-cols-4 gap-6 max-w-3xl mx-auto">
            {stats.map((s) => (
              <div key={s.label} className="text-center">
                <div className="stat-value">{s.value}</div>
                <div className="text-xs text-slate-500 mt-1 uppercase tracking-wider">
                  {s.label}
                </div>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* ════════════ TICKER MARQUEE ════════════ */}
      <section className="border-y border-white/5 py-4 overflow-hidden bg-white/[0.01]">
        <div className="animate-ticker flex gap-8 whitespace-nowrap">
          {[...showcaseTickers, ...showcaseTickers].map((s, i) => (
            <div key={i} className="inline-flex items-center gap-3 px-4">
              <span className="font-mono font-bold text-white text-sm">{s.ticker}</span>
              <span className={`text-sm font-medium ${s.change.startsWith("+") ? "text-emerald-400" : "text-red-400"}`}>
                {s.change}
              </span>
              <span className={`text-xs font-semibold ${s.color}`}>{s.vibe}</span>
            </div>
          ))}
        </div>
      </section>

      {/* ════════════ FEATURES GRID ════════════ */}
      <section className="py-24 px-4">
        <div className="max-w-6xl mx-auto">
          {/* Section header */}
          <div className="text-center mb-16">
            <h2 className="text-3xl sm:text-4xl font-bold mb-4">
              <span className="gradient-text">Institutional-Grade AI</span>
              <br />
              <span className="text-white">for Every Investor</span>
            </h2>
            <p className="text-slate-400 max-w-xl mx-auto">
              Six autonomous AI agents work together to research, analyze,
              decide, execute, reflect, and alert — so you don&apos;t have to.
            </p>
          </div>

          {/* Feature Cards */}
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
            {features.map((f, i) => (
              <div
                key={f.title}
                className={`feature-card animate-fade-in-up delay-${(i + 1) * 100}`}
              >
                <div className="flex items-start justify-between mb-4">
                  <span className="text-3xl">{f.icon}</span>
                  <span className="badge badge-purple">{f.badge}</span>
                </div>
                <h3 className="text-lg font-bold text-white mb-2">{f.title}</h3>
                <p className="text-sm text-slate-400 leading-relaxed">
                  {f.desc}
                </p>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* ════════════ FEATURED STOCKS ════════════ */}
      <section className="py-24 px-4 relative">
        <div className="absolute inset-0 bg-gradient-to-b from-transparent via-indigo-500/[0.02] to-transparent" />
        <div className="max-w-6xl mx-auto relative z-10">
          <div className="text-center mb-16">
            <h2 className="text-3xl sm:text-4xl font-bold mb-4">
              <span className="text-white">Featured </span>
              <span className="gradient-text">Vibe Scores</span>
            </h2>
            <p className="text-slate-400 max-w-xl mx-auto">
              Real-time AI sentiment analysis powered by news, social signals, and market data.
            </p>
          </div>

          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-5">
            {showcaseTickers.map((s, i) => (
              <div
                key={s.ticker}
                className={`stock-card animate-fade-in-up delay-${(i + 1) * 100}`}
              >
                {/* Header */}
                <div className="flex items-center justify-between mb-4">
                  <div className="flex items-center gap-3">
                    <div className="w-10 h-10 rounded-xl bg-gradient-to-br from-indigo-500/20 to-purple-500/20 border border-indigo-500/20 flex items-center justify-center font-mono font-bold text-sm text-white">
                      {s.ticker.slice(0, 2)}
                    </div>
                    <div>
                      <div className="font-bold text-white text-sm">{s.ticker}</div>
                      <div className="text-xs text-slate-500">{s.name}</div>
                    </div>
                  </div>
                  <span
                    className={`text-sm font-bold ${
                      s.change.startsWith("+") ? "text-emerald-400" : "text-red-400"
                    }`}
                  >
                    {s.change}
                  </span>
                </div>

                {/* AI Forecast Row */}
                <div className="flex items-center justify-between py-3 border-t border-white/5">
                  <span className="text-xs text-slate-500 uppercase tracking-wider">
                    AI Vibe
                  </span>
                  <span className={`font-bold text-sm ${s.color}`}>
                    {s.vibe}
                  </span>
                </div>
                <div className="flex items-center justify-between py-3 border-t border-white/5">
                  <span className="text-xs text-slate-500 uppercase tracking-wider">
                    Anxiety Index
                  </span>
                  <span className="font-mono text-sm text-white">
                    {s.anxiety.toFixed(1)}
                    <span className="text-slate-500">/10</span>
                  </span>
                </div>
                <div className="flex items-center justify-between py-3 border-t border-white/5">
                  <span className="text-xs text-slate-500 uppercase tracking-wider">
                    AI Action
                  </span>
                  <span className="badge badge-blue text-xs">
                    {s.anxiety < 3 ? "Buy" : s.anxiety < 6 ? "Hold" : "Sell"}
                  </span>
                </div>

                {/* Anxiety bar */}
                <div className="mt-3">
                  <div className="h-1.5 w-full bg-white/5 rounded-full overflow-hidden">
                    <div
                      className="h-full rounded-full transition-all duration-500"
                      style={{
                        width: `${s.anxiety * 10}%`,
                        background: s.anxiety < 3
                          ? "linear-gradient(90deg, #10b981, #34d399)"
                          : s.anxiety < 6
                          ? "linear-gradient(90deg, #f59e0b, #fbbf24)"
                          : "linear-gradient(90deg, #ef4444, #f87171)",
                      }}
                    />
                  </div>
                </div>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* ════════════ HOW IT WORKS ════════════ */}
      <section className="py-24 px-4">
        <div className="max-w-5xl mx-auto">
          <div className="text-center mb-16">
            <h2 className="text-3xl sm:text-4xl font-bold mb-4 text-white">
              How <span className="gradient-text">FinVibe</span> Works
            </h2>
          </div>

          <div className="space-y-0">
            {[
              { step: "01", title: "Researcher", desc: "Fetches live prices via yfinance and latest news from NewsAPI. Stores context in Qdrant vector DB.", icon: "🔍" },
              { step: "02", title: "Vibe Analyst", desc: "AI reads news sentiment and generates a vibe label (Euphoric → Panic) with anxiety index 0-10.", icon: "🎭" },
              { step: "03", title: "Strategist", desc: "Analyzes vibes + portfolio state + past memories. Proposes BUY/SELL trades with confidence levels.", icon: "🧮" },
              { step: "04", title: "Executor", desc: "Paper-executes trades in the shadow portfolio. Validates against risk limits and cash balance.", icon: "⚡" },
              { step: "05", title: "Reflector", desc: "Evaluates past trade predictions. Generates lessons stored in Qdrant + Mem0 graph memory.", icon: "🧠" },
              { step: "06", title: "Alerter", desc: "Checks if anxiety > threshold. Triggers in-app alert or emergency AI voice call via Vapi.ai.", icon: "🚨" },
            ].map((s, i) => (
              <div
                key={s.step}
                className={`flex items-start gap-6 py-8 ${
                  i < 5 ? "border-b border-white/5" : ""
                } animate-fade-in-up`}
              >
                <div className="flex-shrink-0 w-14 h-14 rounded-2xl bg-gradient-to-br from-indigo-500/10 to-purple-500/10 border border-indigo-500/20 flex items-center justify-center text-2xl">
                  {s.icon}
                </div>
                <div>
                  <div className="flex items-center gap-3 mb-2">
                    <span className="text-xs font-mono text-indigo-400">{s.step}</span>
                    <h3 className="text-lg font-bold text-white">{s.title}</h3>
                  </div>
                  <p className="text-sm text-slate-400 leading-relaxed max-w-xl">
                    {s.desc}
                  </p>
                </div>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* ════════════ CTA SECTION ════════════ */}
      <section className="py-24 px-4 relative overflow-hidden">
        <div className="absolute inset-0 bg-gradient-to-r from-indigo-500/5 via-purple-500/5 to-indigo-500/5" />
        <div className="relative z-10 max-w-3xl mx-auto text-center">
          <h2 className="text-3xl sm:text-4xl font-bold mb-6 text-white">
            Ready to <span className="gradient-text">Vibe-Check</span> Your Portfolio?
          </h2>
          <p className="text-slate-400 mb-10 text-lg">
            Join FinVibe and let autonomous AI agents manage your research,
            sentiment analysis, and trading — while you learn from every decision.
          </p>
          {user ? (
            <Link href="/dashboard" className="btn-glow px-10 py-4 text-lg inline-block">
              Open Dashboard →
            </Link>
          ) : (
            <Link href="/signup" className="btn-glow px-10 py-4 text-lg inline-block">
              Create Free Account →
            </Link>
          )}
        </div>
      </section>

      {/* ════════════ FOOTER ════════════ */}
      <footer className="border-t border-white/5 py-10 px-4">
        <div className="max-w-6xl mx-auto flex flex-col sm:flex-row items-center justify-between gap-4">
          <div className="flex items-center gap-2">
            <div className="w-7 h-7 rounded-lg bg-gradient-to-br from-indigo-500 to-purple-600 flex items-center justify-center text-white text-xs font-bold">
              FV
            </div>
            <span className="text-sm text-slate-500">
              © 2026 FinVibe AI. All rights reserved.
            </span>
          </div>
          <p className="text-xs text-slate-600 max-w-md text-center sm:text-right">
            AI-generated insights are for informational purposes only.
            Not financial advice. Past performance does not guarantee future results.
          </p>
        </div>
      </footer>
    </div>
  );
}
