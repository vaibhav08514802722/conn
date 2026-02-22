"use client";

import { useEffect, useState, useCallback, useRef } from "react";
import { useRouter } from "next/navigation";
import { useAuth } from "@/lib/auth";
import {
  getAIPortfolio,
  getAITrades,
  getAIPortfolioHistory,
  getBulkPredictions,
  runBrainCycle,
  getBrainHistory,
  getBrainStats,
  AIPortfolio,
  AITrade,
  AIHolding,
  AIPrediction,
  PortfolioHistoryPoint,
  BrainCycleLog,
  BrainStats,
} from "@/lib/api";
import {
  ResponsiveContainer,
  AreaChart,
  Area,
  XAxis,
  YAxis,
  Tooltip,
  CartesianGrid,
} from "recharts";

const POLL_INTERVAL = 30_000;

function SignalBadge({ signal }: { signal?: string }) {
  const s = signal?.toUpperCase() || "HOLD";
  const cls =
    s === "BUY"
      ? "bg-emerald-500/20 text-emerald-400 border-emerald-500/30"
      : s === "SELL"
      ? "bg-red-500/20 text-red-400 border-red-500/30"
      : "bg-amber-500/20 text-amber-400 border-amber-500/30";
  return (
    <span className={`text-[10px] font-bold px-2 py-0.5 rounded-full border ${cls}`}>
      {s}
    </span>
  );
}

function VibeBadge({ label }: { label?: string }) {
  if (!label || label === "unknown") return null;
  const l = label.toLowerCase();
  const cls = l.includes("bull") || l.includes("greed")
    ? "bg-emerald-500/10 text-emerald-400 border-emerald-500/20"
    : l.includes("bear") || l.includes("fear") || l.includes("panic")
    ? "bg-red-500/10 text-red-400 border-red-500/20"
    : "bg-slate-500/10 text-slate-400 border-slate-500/20";
  return (
    <span className={`text-[9px] px-1.5 py-0.5 rounded-full border ${cls}`}>
      {label}
    </span>
  );
}

function ConfidenceBar({ value }: { value: number }) {
  const pct = Math.min(Math.max(value * 100, 0), 100);
  const color = pct >= 70 ? "bg-emerald-500" : pct >= 40 ? "bg-amber-500" : "bg-red-500";
  return (
    <div className="flex items-center gap-2">
      <div className="flex-1 h-1.5 rounded-full bg-white/5 overflow-hidden">
        <div className={`h-full rounded-full ${color} transition-all duration-700`} style={{ width: `${pct}%` }} />
      </div>
      <span className="text-[10px] text-slate-500 font-mono">{pct.toFixed(0)}%</span>
    </div>
  );
}

interface PredictionData {
  price: number;
  change_pct: number;
  high: number;
  low: number;
  volume: number;
  vibe_label: string;
  anxiety: number;
  prediction: AIPrediction;
}

export default function AIPortfolioPage() {
  const { user, loading: authLoading } = useAuth();
  const router = useRouter();

  const [portfolio, setPortfolio] = useState<AIPortfolio | null>(null);
  const [trades, setTrades] = useState<AITrade[]>([]);
  const [history, setHistory] = useState<PortfolioHistoryPoint[]>([]);
  const [predictions, setPredictions] = useState<Record<string, PredictionData>>({});
  const [loading, setLoading] = useState(true);
  const [activeTab, setActiveTab] = useState<"holdings" | "trades" | "brain">("holdings");
  const [refreshing, setRefreshing] = useState(false);
  const [lastUpdated, setLastUpdated] = useState<Date | null>(null);
  const [autoRefresh, setAutoRefresh] = useState(true);
  const [expandedTicker, setExpandedTicker] = useState<string | null>(null);
  const pollRef = useRef<NodeJS.Timeout | null>(null);

  // Brain state
  const [brainRunning, setBrainRunning] = useState(false);
  const [brainLog, setBrainLog] = useState<BrainCycleLog | null>(null);
  const [brainHistory, setBrainHistory] = useState<BrainCycleLog[]>([]);
  const [brainStats, setBrainStats] = useState<BrainStats | null>(null);
  const [brainStep, setBrainStep] = useState("");

  useEffect(() => {
    if (!authLoading && !user) router.replace("/login");
  }, [authLoading, user, router]);

  const fetchAll = useCallback(async (silent = false) => {
    try {
      const [pRes, tRes, hRes] = await Promise.all([
        getAIPortfolio(),
        getAITrades(30),
        getAIPortfolioHistory(30),
      ]);
      setPortfolio(pRes.portfolio);
      setTrades(tRes.trades || []);
      setHistory(hRes.history || []);

      // Fetch AI predictions for all holdings
      const tickers = (pRes.portfolio?.holdings || []).map((h: AIHolding) => h.ticker);
      if (tickers.length > 0) {
        try {
          const predRes = await getBulkPredictions(tickers);
          setPredictions(predRes.predictions || {});
        } catch {
          /* ignore prediction errors */
        }
      }
      setLastUpdated(new Date());
    } catch {
      /* ignore */
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  }, []);

  useEffect(() => {
    if (user) fetchAll();
  }, [user, fetchAll]);

  // Auto-refresh polling
  useEffect(() => {
    if (pollRef.current) clearInterval(pollRef.current);
    if (autoRefresh && user) {
      pollRef.current = setInterval(() => fetchAll(true), POLL_INTERVAL);
    }
    return () => {
      if (pollRef.current) clearInterval(pollRef.current);
    };
  }, [autoRefresh, user, fetchAll]);

  const handleRefresh = () => {
    setRefreshing(true);
    fetchAll();
  };

  // Fetch brain history and stats
  const fetchBrainData = useCallback(async () => {
    try {
      const [hRes, sRes] = await Promise.all([
        getBrainHistory(5),
        getBrainStats(),
      ]);
      setBrainHistory(hRes.logs || []);
      setBrainStats(sRes.stats || null);
    } catch {
      /* ignore */
    }
  }, []);

  useEffect(() => {
    if (user) fetchBrainData();
  }, [user, fetchBrainData]);

  // Run AI brain cycle
  const handleRunBrain = async () => {
    setBrainRunning(true);
    setBrainLog(null);
    setBrainStep("🔍 Scanning global markets for opportunities...");
    try {
      const res = await runBrainCycle();
      setBrainLog(res.log);
      setBrainStep("");
      // Refresh everything after brain trades
      fetchAll();
      fetchBrainData();
    } catch (e: any) {
      setBrainStep(`❌ Error: ${e.message}`);
    } finally {
      setBrainRunning(false);
    }
  };

  if (authLoading || loading) {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <div className="w-8 h-8 border-2 border-indigo-500/30 border-t-indigo-500 rounded-full animate-spin" />
      </div>
    );
  }

  const p = portfolio;

  return (
    <div className="min-h-screen pt-8 pb-20">
      {/* Background orbs */}
      <div className="orb orb-1" />
      <div className="orb orb-3" />

      <div className="max-w-7xl mx-auto px-4 sm:px-6 relative z-10">
        {/* Header */}
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 mb-8">
          <div>
            <h1 className="text-3xl font-bold flex items-center gap-3">
              <span className="gradient-text">AI Portfolio</span>
              <span className="pulse-dot" />
              <span className="text-xs text-emerald-400 font-normal uppercase tracking-wider">Live</span>
            </h1>
            <p className="text-slate-400 text-sm mt-1 flex items-center gap-3">
              AI agent autonomously trades with $1M virtual capital — real-time P&L + predictions
              {lastUpdated && (
                <span className="text-[10px] text-slate-600">
                  Updated {lastUpdated.toLocaleTimeString()}
                </span>
              )}
            </p>
          </div>
          <div className="flex items-center gap-3">
            <button
              onClick={() => setAutoRefresh(!autoRefresh)}
              className={`text-xs px-3 py-1.5 rounded-full border transition ${
                autoRefresh
                  ? "border-emerald-500/30 bg-emerald-500/10 text-emerald-400"
                  : "border-white/10 bg-white/5 text-slate-500"
              }`}
            >
              <span className={`inline-block w-1.5 h-1.5 rounded-full mr-1.5 ${autoRefresh ? "bg-emerald-400 animate-pulse" : "bg-slate-600"}`} />
              Live {autoRefresh ? "ON" : "OFF"}
            </button>
            <button
              onClick={handleRefresh}
              disabled={refreshing}
              className="btn-outline px-5 py-2 text-sm flex items-center gap-2"
            >
              {refreshing ? (
                <span className="w-4 h-4 border-2 border-indigo-500/30 border-t-indigo-500 rounded-full animate-spin" />
              ) : (
                <span>🔄</span>
              )}
              Refresh + AI
            </button>
            <button
              onClick={handleRunBrain}
              disabled={brainRunning}
              className="btn-glow px-5 py-2 text-sm flex items-center gap-2"
            >
              {brainRunning ? (
                <span className="w-4 h-4 border-2 border-white/30 border-t-white rounded-full animate-spin" />
              ) : (
                <span>🧠</span>
              )}
              {brainRunning ? "Brain Working..." : "Run AI Brain"}
            </button>
          </div>
        </div>

        {/* Hero Stats */}
        {p && (
          <div className="grid grid-cols-2 lg:grid-cols-5 gap-4 mb-8">
            <div className="glass-card p-5 col-span-2 lg:col-span-1">
              <div className="text-xs text-slate-500 uppercase tracking-wider mb-1">Portfolio Value</div>
              <div className="text-2xl font-bold text-white font-mono">
                ${p.total_portfolio_value.toLocaleString(undefined, { maximumFractionDigits: 0 })}
              </div>
              <div className="text-xs text-slate-500 mt-1">of $1,000,000 capital</div>
            </div>
            <div className="glass-card p-5">
              <div className="text-xs text-slate-500 uppercase tracking-wider mb-1">Total P&L</div>
              <div className={`text-2xl font-bold font-mono ${p.total_pnl >= 0 ? "text-emerald-400" : "text-red-400"}`}>
                {p.total_pnl >= 0 ? "+" : ""}${p.total_pnl.toLocaleString(undefined, { maximumFractionDigits: 0 })}
              </div>
              <div className={`text-xs mt-1 ${p.total_pnl_pct >= 0 ? "text-emerald-400/70" : "text-red-400/70"}`}>
                {p.total_pnl_pct >= 0 ? "+" : ""}{p.total_pnl_pct.toFixed(2)}%
              </div>
            </div>
            <div className="glass-card p-5">
              <div className="text-xs text-slate-500 uppercase tracking-wider mb-1">Cash</div>
              <div className="text-2xl font-bold text-white font-mono">
                ${p.cash_balance.toLocaleString(undefined, { maximumFractionDigits: 0 })}
              </div>
              <div className="text-xs text-slate-500 mt-1">Available balance</div>
            </div>
            <div className="glass-card p-5">
              <div className="text-xs text-slate-500 uppercase tracking-wider mb-1">Invested</div>
              <div className="text-2xl font-bold text-white font-mono">
                ${p.invested_value.toLocaleString(undefined, { maximumFractionDigits: 0 })}
              </div>
              <div className="text-xs text-slate-500 mt-1">{p.holdings_count} positions</div>
            </div>
            <div className="glass-card p-5">
              <div className="text-xs text-slate-500 uppercase tracking-wider mb-1">Market Value</div>
              <div className="text-2xl font-bold text-white font-mono">
                ${p.current_value.toLocaleString(undefined, { maximumFractionDigits: 0 })}
              </div>
              <div className="text-xs text-slate-500 mt-1">Live valuation</div>
            </div>
          </div>
        )}

        {/* Chart */}
        {history.length > 0 && (
          <div className="glass-card p-6 mb-8">
            <h2 className="text-lg font-semibold mb-4 flex items-center gap-2">
              <span>📈</span> Portfolio Value Over Time
            </h2>
            <div className="h-72">
              <ResponsiveContainer width="100%" height="100%">
                <AreaChart data={history}>
                  <defs>
                    <linearGradient id="aiGrad" x1="0" y1="0" x2="0" y2="1">
                      <stop offset="5%" stopColor="#6366f1" stopOpacity={0.3} />
                      <stop offset="95%" stopColor="#6366f1" stopOpacity={0} />
                    </linearGradient>
                  </defs>
                  <CartesianGrid strokeDasharray="3 3" stroke="rgba(99,102,241,0.1)" />
                  <XAxis
                    dataKey="date"
                    tick={{ fill: "#64748b", fontSize: 11 }}
                    tickFormatter={(d) => d.slice(5)}
                    stroke="transparent"
                  />
                  <YAxis
                    tick={{ fill: "#64748b", fontSize: 11 }}
                    stroke="transparent"
                    tickFormatter={(v) => `$${(v / 1000).toFixed(0)}k`}
                  />
                  <Tooltip
                    contentStyle={{
                      background: "#0f1737",
                      border: "1px solid rgba(99,102,241,0.2)",
                      borderRadius: "12px",
                      color: "#f0f4ff",
                    }}
                    formatter={(v: number) => [`$${v.toLocaleString()}`, "Value"]}
                  />
                  <Area
                    type="monotone"
                    dataKey="total_value"
                    stroke="#6366f1"
                    strokeWidth={2}
                    fill="url(#aiGrad)"
                  />
                </AreaChart>
              </ResponsiveContainer>
            </div>
          </div>
        )}

        {/* Tab Toggle */}
        <div className="flex gap-1 mb-6 p-1 rounded-xl bg-white/[0.03] border border-white/5 w-fit">
          {(["holdings", "trades", "brain"] as const).map((tab) => (
            <button
              key={tab}
              onClick={() => setActiveTab(tab)}
              className={`px-5 py-2 rounded-lg text-sm font-medium transition-all ${
                activeTab === tab
                  ? "bg-indigo-500/20 text-indigo-300 shadow-lg shadow-indigo-500/10"
                  : "text-slate-500 hover:text-slate-300"
              }`}
            >
              {tab === "holdings" ? "📊 Holdings" : tab === "trades" ? "📜 Trade History" : "🧠 AI Brain"}
            </button>
          ))}
        </div>

        {/* Holdings Tab */}
        {activeTab === "holdings" && p && (
          <div className="glass-card p-6">
            <h2 className="text-lg font-semibold mb-4">AI Holdings ({p.holdings_count})</h2>
            {p.holdings.length === 0 ? (
              <div className="text-center py-12">
                <div className="text-4xl mb-3">🤖</div>
                <p className="text-slate-400">AI hasn&apos;t made any trades yet.</p>
                <p className="text-slate-500 text-sm mt-1">Run an analysis from the Dashboard to trigger the agent pipeline.</p>
              </div>
            ) : (
              <div className="overflow-x-auto">
                <table className="w-full text-sm">
                  <thead>
                    <tr className="border-b border-white/5 text-slate-500 text-xs uppercase tracking-wider">
                      <th className="text-left py-3 px-2">Ticker</th>
                      <th className="text-right py-3 px-2">Shares</th>
                      <th className="text-right py-3 px-2">Avg Cost</th>
                      <th className="text-right py-3 px-2">Live Price</th>
                      <th className="text-right py-3 px-2">Day Range</th>
                      <th className="text-right py-3 px-2">Market Value</th>
                      <th className="text-right py-3 px-2">P&L</th>
                      <th className="text-center py-3 px-2">AI Signal</th>
                    </tr>
                  </thead>
                  <tbody>
                    {p.holdings.map((h: AIHolding) => {
                      const pred = predictions[h.ticker];
                      const isExpanded = expandedTicker === h.ticker;

                      return (
                        <>
                          <tr
                            key={h.ticker}
                            className={`border-b border-white/5 hover:bg-white/[0.03] transition cursor-pointer ${isExpanded ? "bg-white/[0.02]" : ""}`}
                            onClick={() => setExpandedTicker(isExpanded ? null : h.ticker)}
                          >
                            <td className="py-3 px-2">
                              <div className="font-mono font-bold text-white">{h.ticker}</div>
                              <div className="flex items-center gap-1 mt-0.5">
                                <VibeBadge label={pred?.vibe_label || h.vibe_label} />
                                <span className={`text-[10px] font-mono ${h.day_change_pct >= 0 ? "text-emerald-400" : "text-red-400"}`}>
                                  {h.day_change_pct >= 0 ? "+" : ""}{h.day_change_pct.toFixed(2)}%
                                </span>
                              </div>
                            </td>
                            <td className="py-3 px-2 text-right font-mono text-slate-300">{h.shares.toFixed(2)}</td>
                            <td className="py-3 px-2 text-right font-mono text-slate-300">${h.avg_cost.toFixed(2)}</td>
                            <td className="py-3 px-2 text-right font-mono text-white font-medium">${h.current_price.toFixed(2)}</td>
                            <td className="py-3 px-2 text-right">
                              {pred ? (
                                <div className="text-[10px] text-slate-500 font-mono">
                                  ${pred.low.toFixed(2)} – ${pred.high.toFixed(2)}
                                </div>
                              ) : (
                                <span className="text-slate-600">—</span>
                              )}
                            </td>
                            <td className="py-3 px-2 text-right font-mono text-white">
                              ${h.market_value.toLocaleString(undefined, { maximumFractionDigits: 0 })}
                            </td>
                            <td className={`py-3 px-2 text-right font-mono font-medium ${h.pnl >= 0 ? "text-emerald-400" : "text-red-400"}`}>
                              <div>{h.pnl >= 0 ? "+" : ""}${h.pnl.toLocaleString(undefined, { maximumFractionDigits: 0 })}</div>
                              <div className="text-[10px]">{h.pnl_pct >= 0 ? "+" : ""}{h.pnl_pct.toFixed(2)}%</div>
                            </td>
                            <td className="py-3 px-2 text-center">
                              <SignalBadge signal={pred?.prediction?.signal || h.ai_signal} />
                            </td>
                          </tr>
                          {/* Expanded AI Prediction Row */}
                          {isExpanded && pred && (
                            <tr key={`${h.ticker}-ai`} className="border-b border-white/5 bg-gradient-to-r from-indigo-500/[0.03] to-purple-500/[0.03]">
                              <td colSpan={8} className="py-3 px-4">
                                <div className="flex flex-col sm:flex-row sm:items-center gap-4">
                                  <div className="flex-1">
                                    <div className="flex items-center gap-2 mb-1.5">
                                      <span className="text-[10px] uppercase tracking-wider text-indigo-400 font-bold">🤖 AI Insight</span>
                                      <SignalBadge signal={pred.prediction?.signal} />
                                    </div>
                                    <p className="text-sm text-slate-300">
                                      {pred.prediction?.prediction || "No prediction available"}
                                    </p>
                                    {pred.prediction?.reason && (
                                      <p className="text-xs text-slate-500 mt-1">
                                        💡 {pred.prediction.reason}
                                      </p>
                                    )}
                                  </div>
                                  <div className="flex items-center gap-6 text-xs">
                                    {pred.prediction?.target_price ? (
                                      <div>
                                        <div className="text-slate-500 text-[10px] uppercase">Target</div>
                                        <div className="font-mono text-white font-bold">${pred.prediction.target_price.toFixed(2)}</div>
                                        <div className={`text-[10px] font-mono ${((pred.prediction.target_pct ?? (((pred.prediction.target_price - h.current_price) / h.current_price) * 100)) >= 0) ? "text-emerald-400" : "text-red-400"}`}>
                                          {((pred.prediction.target_pct ?? (((pred.prediction.target_price - h.current_price) / h.current_price) * 100)) >= 0) ? "+" : ""}
                                          {(pred.prediction.target_pct ?? (((pred.prediction.target_price - h.current_price) / h.current_price) * 100)).toFixed(1)}% in {pred.prediction.horizon_days || 7}d
                                        </div>
                                      </div>
                                    ) : null}
                                    {pred.prediction?.confidence !== undefined && pred.prediction.confidence > 0 ? (
                                      <div className="w-24">
                                        <div className="text-slate-500 text-[10px] uppercase mb-1">Confidence</div>
                                        <ConfidenceBar value={pred.prediction.confidence} />
                                      </div>
                                    ) : null}
                                    {pred.volume ? (
                                      <div>
                                        <div className="text-slate-500 text-[10px] uppercase">Volume</div>
                                        <div className="font-mono text-slate-300">{(pred.volume / 1e6).toFixed(1)}M</div>
                                      </div>
                                    ) : null}
                                    {pred.anxiety !== undefined ? (
                                      <div>
                                        <div className="text-slate-500 text-[10px] uppercase">Anxiety</div>
                                        <div className={`font-mono font-bold ${pred.anxiety >= 7 ? "text-red-400" : pred.anxiety >= 4 ? "text-amber-400" : "text-emerald-400"}`}>
                                          {pred.anxiety}/10
                                        </div>
                                      </div>
                                    ) : null}
                                  </div>
                                </div>
                              </td>
                            </tr>
                          )}
                        </>
                      );
                    })}
                  </tbody>
                </table>
                <p className="text-[10px] text-slate-600 mt-3 text-center">
                  Click any row to see AI prediction • {autoRefresh ? `Auto-refreshing every ${POLL_INTERVAL / 1000}s` : "Auto-refresh paused"}
                </p>
              </div>
            )}
          </div>
        )}

        {/* Trades Tab */}
        {activeTab === "trades" && (
          <div className="glass-card p-6">
            <h2 className="text-lg font-semibold mb-4">Trade History ({trades.length})</h2>
            {trades.length === 0 ? (
              <div className="text-center py-12">
                <div className="text-4xl mb-3">📜</div>
                <p className="text-slate-400">No trades recorded yet.</p>
              </div>
            ) : (
              <div className="space-y-3 max-h-[500px] overflow-y-auto custom-scrollbar">
                {trades.map((t) => {
                  const isBuy = t.action === "BUY";
                  const hasPrediction = t.rationale?.prediction;
                  const hasOutcome = t.outcome;

                  return (
                    <div
                      key={t.trade_id}
                      className="border border-white/5 rounded-xl p-4 bg-white/[0.03] hover:bg-white/[0.06] transition"
                    >
                      <div className="flex items-center justify-between mb-2">
                        <div className="flex items-center gap-3">
                          <span className={`badge ${isBuy ? "badge-green" : "badge-red"}`}>{t.action}</span>
                          <span className="font-mono font-bold text-white">{t.ticker}</span>
                          <span className="text-slate-400 text-sm">
                            {t.shares} shares @ ${t.price_at_execution?.toFixed(2)}
                          </span>
                        </div>
                        <div className="text-right">
                          <div className="font-mono text-white text-sm">Now: ${t.current_price?.toFixed(2)}</div>
                          <div className={`text-xs font-mono ${t.live_pnl_pct >= 0 ? "text-emerald-400" : "text-red-400"}`}>
                            {t.live_pnl_pct >= 0 ? "+" : ""}{t.live_pnl_pct}%
                          </div>
                        </div>
                      </div>

                      {/* AI Prediction */}
                      {hasPrediction && (
                        <div className="mt-2 p-2.5 rounded-lg bg-indigo-500/5 border border-indigo-500/10 text-xs">
                          <span className="text-indigo-400 font-medium">🤖 AI Prediction: </span>
                          <span className="text-slate-300">
                            {t.rationale.prediction} — Target: {t.rationale.target_pct}% in {t.rationale.horizon_days}d
                            {t.rationale.confidence && (
                              <span className="text-slate-500"> (Confidence: {(t.rationale.confidence * 100).toFixed(0)}%)</span>
                            )}
                          </span>
                        </div>
                      )}

                      {/* Outcome */}
                      {hasOutcome && (
                        <div className={`mt-2 p-2.5 rounded-lg text-xs ${
                          t.outcome.success
                            ? "bg-emerald-500/5 border border-emerald-500/10"
                            : "bg-red-500/5 border border-red-500/10"
                        }`}>
                          <span className={t.outcome.success ? "text-emerald-400" : "text-red-400"}>
                            {t.outcome.success ? "✅ Correct" : "❌ Missed"} — Actual: {t.outcome.actual_pct?.toFixed(2)}%
                          </span>
                          {t.outcome.lesson_learned && (
                            <span className="text-slate-500 ml-2">"{t.outcome.lesson_learned}"</span>
                          )}
                        </div>
                      )}

                      <div className="text-xs text-slate-600 mt-2">
                        {new Date(t.timestamp).toLocaleString()}
                      </div>
                    </div>
                  );
                })}
              </div>
            )}
          </div>
        )}

        {/* Brain Tab */}
        {activeTab === "brain" && (
          <div className="space-y-6">
            {/* Brain Stats Cards */}
            {brainStats && (
              <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
                <div className="glass-card p-5">
                  <div className="text-xs text-slate-500 uppercase tracking-wider mb-1">Brain Cycles</div>
                  <div className="text-2xl font-bold text-indigo-400 font-mono">{brainStats.brain_cycles}</div>
                  <div className="text-xs text-slate-500 mt-1">Total runs</div>
                </div>
                <div className="glass-card p-5">
                  <div className="text-xs text-slate-500 uppercase tracking-wider mb-1">Brain Trades</div>
                  <div className="text-2xl font-bold text-white font-mono">{brainStats.brain_trades}</div>
                  <div className="text-xs text-slate-500 mt-1">Executed autonomously</div>
                </div>
                <div className="glass-card p-5">
                  <div className="text-xs text-slate-500 uppercase tracking-wider mb-1">Positions</div>
                  <div className="text-2xl font-bold text-white font-mono">{brainStats.holdings_count}</div>
                  <div className="text-xs text-slate-500 mt-1">Active holdings</div>
                </div>
                <div className="glass-card p-5">
                  <div className="text-xs text-slate-500 uppercase tracking-wider mb-1">Brain P&L</div>
                  <div className={`text-2xl font-bold font-mono ${brainStats.total_pnl >= 0 ? "text-emerald-400" : "text-red-400"}`}>
                    {brainStats.total_pnl >= 0 ? "+" : ""}${brainStats.total_pnl.toLocaleString(undefined, { maximumFractionDigits: 0 })}
                  </div>
                  <div className={`text-xs mt-1 ${brainStats.total_pnl_pct >= 0 ? "text-emerald-400/70" : "text-red-400/70"}`}>
                    {brainStats.total_pnl_pct >= 0 ? "+" : ""}{brainStats.total_pnl_pct.toFixed(2)}%
                  </div>
                </div>
              </div>
            )}

            {/* Brain Control Panel */}
            <div className="glass-card p-6">
              <div className="flex items-center justify-between mb-4">
                <h2 className="text-lg font-semibold flex items-center gap-2">
                  <span>🧠</span> AI Brain — Autonomous Trader
                </h2>
                <button
                  onClick={handleRunBrain}
                  disabled={brainRunning}
                  className="btn-glow px-6 py-2.5 text-sm flex items-center gap-2"
                >
                  {brainRunning ? (
                    <span className="w-4 h-4 border-2 border-white/30 border-t-white rounded-full animate-spin" />
                  ) : (
                    <span>⚡</span>
                  )}
                  {brainRunning ? "Running Full Cycle..." : "Run Investment Cycle"}
                </button>
              </div>

              <p className="text-slate-400 text-sm mb-4">
                The AI Brain scans 80+ global stocks, analyzes candidates with real-time data + news,
                reviews your current holdings, and autonomously executes buy/sell trades — just like a human fund manager.
              </p>

              {/* Progress indicator */}
              {brainRunning && (
                <div className="p-4 rounded-xl bg-indigo-500/5 border border-indigo-500/20 mb-4">
                  <div className="flex items-center gap-3">
                    <div className="w-5 h-5 border-2 border-indigo-500/30 border-t-indigo-500 rounded-full animate-spin" />
                    <div>
                      <div className="text-sm text-indigo-300 font-medium">{brainStep || "Processing..."}</div>
                      <div className="text-[10px] text-slate-500 mt-0.5">
                        This may take 30-60 seconds as the AI analyzes multiple stocks
                      </div>
                    </div>
                  </div>
                </div>
              )}

              {/* Latest brain cycle result */}
              {brainLog && (
                <div className="space-y-4">
                  <div className="flex items-center gap-3">
                    <span className={`text-lg ${brainLog.status === "completed" ? "" : "text-red-400"}`}>
                      {brainLog.status === "completed" ? "✅" : "❌"}
                    </span>
                    <div>
                      <div className="text-sm text-white font-medium">{brainLog.summary}</div>
                      <div className="text-[10px] text-slate-500">
                        Completed in {brainLog.duration_sec}s • {brainLog.cycle_id}
                      </div>
                    </div>
                  </div>

                  {/* Scanned Stocks */}
                  {brainLog.scan.length > 0 && (
                    <div>
                      <h3 className="text-xs uppercase tracking-wider text-slate-500 font-bold mb-2">
                        🔍 Scanned Candidates ({brainLog.scan.length})
                      </h3>
                      <div className="flex flex-wrap gap-2">
                        {brainLog.scan.map((c) => (
                          <div key={c.ticker} className="px-3 py-1.5 rounded-lg bg-white/[0.03] border border-white/5 text-xs">
                            <span className="font-mono font-bold text-white">{c.ticker}</span>
                            <span className="text-slate-500 ml-2">{c.reason}</span>
                          </div>
                        ))}
                      </div>
                    </div>
                  )}

                  {/* Analysis Results */}
                  {brainLog.analyses.length > 0 && (
                    <div>
                      <h3 className="text-xs uppercase tracking-wider text-slate-500 font-bold mb-2">
                        📊 Analysis Results ({brainLog.analyses.length})
                      </h3>
                      <div className="grid grid-cols-1 md:grid-cols-2 gap-2">
                        {brainLog.analyses.filter(a => !a.error).map((a) => {
                          const actionCls =
                            a.action?.includes("BUY") ? "text-emerald-400 bg-emerald-500/10 border-emerald-500/20"
                            : a.action?.includes("SELL") ? "text-red-400 bg-red-500/10 border-red-500/20"
                            : "text-amber-400 bg-amber-500/10 border-amber-500/20";
                          return (
                            <div key={a.ticker} className="p-3 rounded-xl bg-white/[0.02] border border-white/5">
                              <div className="flex items-center justify-between mb-1">
                                <div className="flex items-center gap-2">
                                  <span className="font-mono font-bold text-white text-sm">{a.ticker}</span>
                                  <span className={`text-[10px] font-bold px-2 py-0.5 rounded-full border ${actionCls}`}>
                                    {a.action}
                                  </span>
                                </div>
                                <div className="text-right">
                                  <span className="font-mono text-white text-sm">${a.current_price?.toFixed(2)}</span>
                                  <span className={`text-[10px] ml-1 ${(a.change_pct || 0) >= 0 ? "text-emerald-400" : "text-red-400"}`}>
                                    {(a.change_pct || 0) >= 0 ? "+" : ""}{(a.change_pct || 0).toFixed(1)}%
                                  </span>
                                </div>
                              </div>
                              <p className="text-xs text-slate-400">{a.analysis}</p>
                              <div className="flex items-center gap-3 mt-1.5 text-[10px] text-slate-500">
                                <span>🎯 Target: ${a.target_price?.toFixed(2)}</span>
                                <span>⚡ Risk: {a.risk_level}</span>
                                <span>📊 Conviction: {((a.conviction || 0) * 100).toFixed(0)}%</span>
                              </div>
                            </div>
                          );
                        })}
                      </div>
                    </div>
                  )}

                  {/* Hold Decisions */}
                  {brainLog.hold_decisions.length > 0 && (
                    <div>
                      <h3 className="text-xs uppercase tracking-wider text-slate-500 font-bold mb-2">
                        🔄 Portfolio Review ({brainLog.hold_decisions.length})
                      </h3>
                      <div className="space-y-1">
                        {brainLog.hold_decisions.map((d) => {
                          const dCls =
                            d.decision === "BUY_MORE" ? "text-emerald-400"
                            : d.decision === "SELL_ALL" || d.decision === "TRIM" ? "text-red-400"
                            : "text-amber-400";
                          return (
                            <div key={d.ticker} className="flex items-center justify-between p-2 rounded-lg bg-white/[0.02]">
                              <div className="flex items-center gap-3">
                                <span className="font-mono font-bold text-white text-sm">{d.ticker}</span>
                                <span className={`text-xs font-bold ${dCls}`}>{d.decision}</span>
                                <span className="text-xs text-slate-500">{d.reason}</span>
                              </div>
                              <span className={`font-mono text-xs ${d.pnl_pct >= 0 ? "text-emerald-400" : "text-red-400"}`}>
                                {d.pnl_pct >= 0 ? "+" : ""}{d.pnl_pct}%
                              </span>
                            </div>
                          );
                        })}
                      </div>
                    </div>
                  )}

                  {/* Executed Trades */}
                  {brainLog.trades.length > 0 && (
                    <div>
                      <h3 className="text-xs uppercase tracking-wider text-slate-500 font-bold mb-2">
                        ⚡ Trades Executed ({brainLog.trades.length})
                      </h3>
                      <div className="space-y-2">
                        {brainLog.trades.map((t) => {
                          const isBuy = t.action === "BUY" || t.action === "BUY_MORE";
                          return (
                            <div key={t.trade_id} className={`p-3 rounded-xl border ${
                              isBuy 
                                ? "bg-emerald-500/5 border-emerald-500/20"
                                : "bg-red-500/5 border-red-500/20"
                            }`}>
                              <div className="flex items-center justify-between">
                                <div className="flex items-center gap-3">
                                  <span className={`text-xs font-bold px-2 py-0.5 rounded-full ${
                                    isBuy ? "bg-emerald-500/20 text-emerald-400" : "bg-red-500/20 text-red-400"
                                  }`}>
                                    {t.action}
                                  </span>
                                  <span className="font-mono font-bold text-white">{t.ticker}</span>
                                  <span className="text-xs text-slate-400">
                                    {t.shares} shares @ ${t.price.toFixed(2)}
                                  </span>
                                </div>
                                <span className="font-mono text-sm text-white">
                                  ${t.value.toLocaleString(undefined, { maximumFractionDigits: 0 })}
                                </span>
                              </div>
                              <p className="text-xs text-slate-500 mt-1">{t.reason}</p>
                            </div>
                          );
                        })}
                      </div>
                    </div>
                  )}

                  {brainLog.trades.length === 0 && brainLog.status === "completed" && (
                    <div className="text-center py-6">
                      <div className="text-2xl mb-2">🤔</div>
                      <p className="text-slate-400 text-sm">
                        Brain analyzed the market but decided no trades were needed right now.
                      </p>
                    </div>
                  )}
                </div>
              )}

              {/* No brain log yet */}
              {!brainLog && !brainRunning && (
                <div className="text-center py-10">
                  <div className="text-5xl mb-4">🧠</div>
                  <p className="text-slate-300 font-medium mb-2">Ready to think</p>
                  <p className="text-slate-500 text-sm max-w-md mx-auto">
                    Click &quot;Run Investment Cycle&quot; to let the AI Brain scan global markets,
                    find opportunities, and autonomously buy/sell stocks with its $1M capital.
                  </p>
                </div>
              )}
            </div>

            {/* Brain History */}
            {brainHistory.length > 0 && (
              <div className="glass-card p-6">
                <h2 className="text-lg font-semibold mb-4 flex items-center gap-2">
                  <span>📜</span> Brain Cycle History
                </h2>
                <div className="space-y-2">
                  {brainHistory.map((log) => (
                    <button
                      key={log.cycle_id}
                      onClick={() => setBrainLog(log)}
                      className="w-full text-left p-3 rounded-xl bg-white/[0.02] border border-white/5 hover:border-indigo-500/20 transition"
                    >
                      <div className="flex items-center justify-between">
                        <div className="flex items-center gap-3">
                          <span>{log.status === "completed" ? "✅" : "❌"}</span>
                          <div>
                            <div className="text-sm text-white">{log.summary || `Cycle ${log.cycle_id}`}</div>
                            <div className="text-[10px] text-slate-500">
                              {new Date(log.started_at).toLocaleString()} • {log.duration_sec}s
                            </div>
                          </div>
                        </div>
                        <div className="text-right">
                          <div className="text-xs text-slate-400">
                            {log.trades?.length || 0} trades
                          </div>
                          <div className="text-[10px] text-slate-600">
                            {log.scan?.length || 0} scanned
                          </div>
                        </div>
                      </div>
                    </button>
                  ))}
                </div>
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  );
}
