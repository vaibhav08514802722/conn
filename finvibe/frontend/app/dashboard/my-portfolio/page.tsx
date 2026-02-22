"use client";

import { useEffect, useState, useCallback, useRef } from "react";
import { useRouter } from "next/navigation";
import { useAuth } from "@/lib/auth";
import {
  getUserPortfolioAuth,
  addUserHolding,
  removeUserHolding,
  refreshUserPortfolio,
  searchStock,
  UserHolding,
  StockSearchResult,
} from "@/lib/api";

const POLL_INTERVAL = 30_000; // 30 seconds

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

export default function MyPortfolioPage() {
  const { user, token, loading: authLoading } = useAuth();
  const router = useRouter();

  // Portfolio state
  const [holdings, setHoldings] = useState<UserHolding[]>([]);
  const [totalInvested, setTotalInvested] = useState(0);
  const [currentValue, setCurrentValue] = useState(0);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [lastUpdated, setLastUpdated] = useState<Date | null>(null);
  const [autoRefresh, setAutoRefresh] = useState(true);
  const [expandedTicker, setExpandedTicker] = useState<string | null>(null);
  const pollRef = useRef<NodeJS.Timeout | null>(null);

  // Add holding form
  const [showAdd, setShowAdd] = useState(false);
  const [searchQuery, setSearchQuery] = useState("");
  const [searchResults, setSearchResults] = useState<StockSearchResult[]>([]);
  const [searching, setSearching] = useState(false);
  const [selectedStock, setSelectedStock] = useState<StockSearchResult | null>(null);
  const [addShares, setAddShares] = useState("");
  const [addCost, setAddCost] = useState("");
  const [addType, setAddType] = useState("stock");
  const [addSip, setAddSip] = useState("");
  const [addNotes, setAddNotes] = useState("");
  const [adding, setAdding] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => {
    if (!authLoading && !user) router.replace("/login");
  }, [authLoading, user, router]);

  const fetchPortfolio = useCallback(async () => {
    if (!token) return;
    try {
      const res = await getUserPortfolioAuth(token);
      setHoldings(res.portfolio.holdings || []);
      setTotalInvested(res.portfolio.total_invested || 0);
      setCurrentValue(res.portfolio.current_value || 0);
    } catch {
      /* ignore */
    } finally {
      setLoading(false);
    }
  }, [token]);

  // Refresh with AI predictions (calls the enriched endpoint)
  const handleRefresh = useCallback(async (silent = false) => {
    if (!token) return;
    if (!silent) setRefreshing(true);
    try {
      const res = await refreshUserPortfolio(token);
      setHoldings(res.portfolio.holdings || []);
      setTotalInvested(res.portfolio.total_invested || 0);
      setCurrentValue(res.portfolio.current_value || 0);
      setLastUpdated(new Date());
    } catch {
      /* ignore */
    } finally {
      if (!silent) setRefreshing(false);
    }
  }, [token]);

  useEffect(() => {
    if (token) fetchPortfolio();
  }, [token, fetchPortfolio]);

  // Auto-refresh polling
  useEffect(() => {
    if (pollRef.current) clearInterval(pollRef.current);
    if (autoRefresh && token) {
      // Initial refresh with AI predictions on mount
      handleRefresh(true);
      pollRef.current = setInterval(() => handleRefresh(true), POLL_INTERVAL);
    }
    return () => {
      if (pollRef.current) clearInterval(pollRef.current);
    };
  }, [autoRefresh, token, handleRefresh]);

  // Search stocks
  const handleSearch = async () => {
    if (!searchQuery.trim()) return;
    setSearching(true);
    setSearchResults([]);
    try {
      const res = await searchStock(searchQuery.trim());
      setSearchResults(res.results || []);
    } catch {
      setSearchResults([]);
    } finally {
      setSearching(false);
    }
  };

  // Add holding
  const handleAdd = async () => {
    if (!selectedStock || !addShares || !addCost || !token) return;
    setAdding(true);
    setError("");
    try {
      await addUserHolding(token, {
        ticker: selectedStock.ticker,
        shares: parseFloat(addShares),
        avg_cost: parseFloat(addCost),
        investment_type: addType,
        sip_amount: addSip ? parseFloat(addSip) : undefined,
        notes: addNotes || undefined,
      });
      setShowAdd(false);
      setSelectedStock(null);
      setSearchQuery("");
      setSearchResults([]);
      setAddShares("");
      setAddCost("");
      setAddSip("");
      setAddNotes("");
      fetchPortfolio();
    } catch (e: any) {
      setError(e.message || "Failed to add");
    } finally {
      setAdding(false);
    }
  };

  // Remove holding
  const handleRemove = async (ticker: string) => {
    if (!token || !confirm(`Remove ${ticker} from your portfolio?`)) return;
    try {
      await removeUserHolding(token, ticker);
      fetchPortfolio();
    } catch {
      /* ignore */
    }
  };

  if (authLoading || loading) {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <div className="w-8 h-8 border-2 border-indigo-500/30 border-t-indigo-500 rounded-full animate-spin" />
      </div>
    );
  }

  const totalPnl = currentValue - totalInvested;
  const totalPnlPct = totalInvested > 0 ? (totalPnl / totalInvested) * 100 : 0;

  return (
    <div className="min-h-screen pt-8 pb-20">
      {/* Background orbs */}
      <div className="orb orb-1" />
      <div className="orb orb-2" />

      <div className="max-w-7xl mx-auto px-4 sm:px-6 relative z-10">
        {/* Header */}
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 mb-8">
          <div>
            <h1 className="text-3xl font-bold">
              <span className="gradient-text">My Portfolio</span>
            </h1>
            <p className="text-slate-400 text-sm mt-1 flex items-center gap-3">
              Track your personal investments across global markets
              {lastUpdated && (
                <span className="text-[10px] text-slate-600">
                  Updated {lastUpdated.toLocaleTimeString()}
                </span>
              )}
            </p>
          </div>
          <div className="flex items-center gap-3">
            {/* Auto-refresh toggle */}
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
              onClick={() => handleRefresh(false)}
              disabled={refreshing}
              className="btn-outline px-4 py-2 text-sm flex items-center gap-2"
            >
              {refreshing ? (
                <span className="w-4 h-4 border-2 border-indigo-500/30 border-t-indigo-500 rounded-full animate-spin" />
              ) : (
                <span>🔄</span>
              )}
              Refresh + AI
            </button>
            <button
              onClick={() => setShowAdd(true)}
              className="btn-glow px-5 py-2 text-sm flex items-center gap-2"
            >
              <span>＋</span> Add Stock
            </button>
          </div>
        </div>

        {/* Summary Cards */}
        <div className="grid grid-cols-2 lg:grid-cols-4 gap-4 mb-8">
          {[
            { label: "Total Invested", value: `$${totalInvested.toLocaleString(undefined, { maximumFractionDigits: 0 })}`, icon: "💰" },
            { label: "Current Value", value: `$${currentValue.toLocaleString(undefined, { maximumFractionDigits: 0 })}`, icon: "📊" },
            {
              label: "Total P&L",
              value: `${totalPnl >= 0 ? "+" : ""}$${totalPnl.toLocaleString(undefined, { maximumFractionDigits: 0 })}`,
              icon: totalPnl >= 0 ? "📈" : "📉",
              color: totalPnl >= 0 ? "text-emerald-400" : "text-red-400",
            },
            {
              label: "Return %",
              value: `${totalPnlPct >= 0 ? "+" : ""}${totalPnlPct.toFixed(2)}%`,
              icon: "🎯",
              color: totalPnlPct >= 0 ? "text-emerald-400" : "text-red-400",
            },
          ].map((card) => (
            <div key={card.label} className="glass-card p-5">
              <div className="flex items-center gap-2 mb-2">
                <span className="text-lg">{card.icon}</span>
                <span className="text-xs text-slate-500 uppercase tracking-wider">{card.label}</span>
              </div>
              <div className={`text-2xl font-bold font-mono ${(card as any).color || "text-white"}`}>
                {card.value}
              </div>
            </div>
          ))}
        </div>

        {/* Holdings Table */}
        <div className="glass-card p-6">
          <h2 className="text-lg font-semibold mb-4 flex items-center gap-2">
            <span>📋</span> Holdings
            <span className="text-sm text-slate-500 font-normal">({holdings.length})</span>
          </h2>

          {holdings.length === 0 ? (
            <div className="text-center py-16">
              <div className="text-4xl mb-3">📭</div>
              <p className="text-slate-400 mb-4">Your portfolio is empty</p>
              <button onClick={() => setShowAdd(true)} className="btn-glow px-6 py-2 text-sm">
                Add Your First Stock
              </button>
            </div>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b border-white/5 text-slate-500 text-xs uppercase tracking-wider">
                    <th className="text-left py-3 px-2">Stock</th>
                    <th className="text-left py-3 px-2">Type</th>
                    <th className="text-right py-3 px-2">Shares</th>
                    <th className="text-right py-3 px-2">Avg Cost</th>
                    <th className="text-right py-3 px-2">Live Price</th>
                    <th className="text-right py-3 px-2">Day Range</th>
                    <th className="text-right py-3 px-2">Value</th>
                    <th className="text-right py-3 px-2">P&L</th>
                    <th className="text-center py-3 px-2">AI Signal</th>
                    <th className="text-center py-3 px-2"></th>
                  </tr>
                </thead>
                <tbody>
                  {holdings.map((h) => {
                    const value = h.shares * (h.current_price || h.avg_cost);
                    const costBasis = h.shares * h.avg_cost;
                    const pnl = value - costBasis;
                    const pnlPct = h.avg_cost > 0 ? ((h.current_price - h.avg_cost) / h.avg_cost) * 100 : 0;
                    const isUp = pnl >= 0;
                    const isExpanded = expandedTicker === h.ticker;

                    return (
                      <>
                        <tr
                          key={h.ticker}
                          className={`border-b border-white/5 hover:bg-white/[0.03] transition cursor-pointer ${isExpanded ? "bg-white/[0.02]" : ""}`}
                          onClick={() => setExpandedTicker(isExpanded ? null : h.ticker)}
                        >
                          <td className="py-3 px-2">
                            <div className="flex items-center gap-2">
                              <div>
                                <div className="font-bold text-white font-mono">{h.ticker}</div>
                                <div className="flex items-center gap-1 mt-0.5">
                                  {h.sip_amount && (
                                    <span className="text-[10px] text-indigo-400">SIP: ${h.sip_amount}/mo</span>
                                  )}
                                  <VibeBadge label={h.vibe_label} />
                                </div>
                              </div>
                            </div>
                          </td>
                          <td className="py-3 px-2">
                            <span className="badge badge-purple text-[10px]">{h.investment_type?.toUpperCase() || "STOCK"}</span>
                          </td>
                          <td className="py-3 px-2 text-right font-mono text-slate-300">{h.shares.toFixed(2)}</td>
                          <td className="py-3 px-2 text-right font-mono text-slate-300">${h.avg_cost.toFixed(2)}</td>
                          <td className="py-3 px-2 text-right">
                            <div className="font-mono text-white font-medium">${(h.current_price || h.avg_cost).toFixed(2)}</div>
                            <div className={`text-[10px] font-mono ${(h.change_pct || 0) >= 0 ? "text-emerald-400" : "text-red-400"}`}>
                              {(h.change_pct || 0) >= 0 ? "+" : ""}{(h.change_pct || 0).toFixed(2)}%
                            </div>
                          </td>
                          <td className="py-3 px-2 text-right">
                            {h.day_low && h.day_high ? (
                              <div className="text-[10px] text-slate-500 font-mono">
                                ${h.day_low.toFixed(2)} – ${h.day_high.toFixed(2)}
                              </div>
                            ) : (
                              <span className="text-slate-600">—</span>
                            )}
                          </td>
                          <td className="py-3 px-2 text-right font-mono text-white">${value.toFixed(0)}</td>
                          <td className={`py-3 px-2 text-right font-mono font-medium ${isUp ? "text-emerald-400" : "text-red-400"}`}>
                            <div>{isUp ? "+" : ""}${pnl.toFixed(0)}</div>
                            <div className="text-[10px]">{isUp ? "+" : ""}{pnlPct.toFixed(2)}%</div>
                          </td>
                          <td className="py-3 px-2 text-center">
                            <SignalBadge signal={h.ai_signal} />
                          </td>
                          <td className="py-3 px-2 text-center">
                            <button
                              onClick={(e) => { e.stopPropagation(); handleRemove(h.ticker); }}
                              className="text-slate-600 hover:text-red-400 transition text-sm"
                              title="Remove"
                            >
                              ✕
                            </button>
                          </td>
                        </tr>
                        {/* Expanded AI Prediction Row */}
                        {isExpanded && (h.ai_prediction || h.ai_reason) && (
                          <tr key={`${h.ticker}-ai`} className="border-b border-white/5 bg-gradient-to-r from-indigo-500/[0.03] to-purple-500/[0.03]">
                            <td colSpan={10} className="py-3 px-4">
                              <div className="flex flex-col sm:flex-row sm:items-center gap-4">
                                <div className="flex-1">
                                  <div className="flex items-center gap-2 mb-1.5">
                                    <span className="text-[10px] uppercase tracking-wider text-indigo-400 font-bold">🤖 AI Insight</span>
                                    <SignalBadge signal={h.ai_signal} />
                                  </div>
                                  <p className="text-sm text-slate-300">
                                    {h.ai_prediction || "No prediction available"}
                                  </p>
                                  {h.ai_reason && (
                                    <p className="text-xs text-slate-500 mt-1">
                                      💡 {h.ai_reason}
                                    </p>
                                  )}
                                </div>
                                <div className="flex items-center gap-6 text-xs">
                                  {h.ai_target ? (
                                    <div>
                                      <div className="text-slate-500 text-[10px] uppercase">Target</div>
                                      <div className="font-mono text-white font-bold">${h.ai_target.toFixed(2)}</div>
                                      <div className={`text-[10px] font-mono ${(h.ai_target_pct ?? (((h.ai_target - h.current_price) / h.current_price) * 100)) >= 0 ? "text-emerald-400" : "text-red-400"}`}>
                                        {(h.ai_target_pct ?? (((h.ai_target - h.current_price) / h.current_price) * 100)) >= 0 ? "+" : ""}
                                        {(h.ai_target_pct ?? (((h.ai_target - h.current_price) / h.current_price) * 100)).toFixed(1)}% in {h.ai_horizon_days || 7}d
                                      </div>
                                    </div>
                                  ) : null}
                                  {h.ai_confidence !== undefined && h.ai_confidence > 0 ? (
                                    <div className="w-24">
                                      <div className="text-slate-500 text-[10px] uppercase mb-1">Confidence</div>
                                      <ConfidenceBar value={h.ai_confidence} />
                                    </div>
                                  ) : null}
                                  {h.volume ? (
                                    <div>
                                      <div className="text-slate-500 text-[10px] uppercase">Volume</div>
                                      <div className="font-mono text-slate-300">{(h.volume / 1e6).toFixed(1)}M</div>
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
      </div>

      {/* ── Add Stock Modal ── */}
      {showAdd && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm p-4" onClick={() => setShowAdd(false)}>
          <div className="glass-card p-6 w-full max-w-lg animate-fade-in-up" onClick={(e) => e.stopPropagation()}>
            <div className="flex items-center justify-between mb-5">
              <h3 className="text-lg font-bold gradient-text">Add to Portfolio</h3>
              <button onClick={() => setShowAdd(false)} className="text-slate-500 hover:text-white text-lg">✕</button>
            </div>

            {/* Search */}
            <div className="flex gap-2 mb-4">
              <input
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                onKeyDown={(e) => e.key === "Enter" && handleSearch()}
                placeholder="Search ticker (e.g. AAPL, RELIANCE.NS, TSLA)"
                className="input-dark flex-1"
              />
              <button onClick={handleSearch} disabled={searching} className="btn-glow px-4 py-2 text-sm">
                {searching ? "..." : "Search"}
              </button>
            </div>

            {/* Search Results */}
            {searchResults.length > 0 && !selectedStock && (
              <div className="space-y-2 max-h-52 overflow-y-auto mb-4 custom-scrollbar">
                {searchResults.map((r) => (
                  <button
                    key={r.ticker}
                    onClick={() => {
                      setSelectedStock(r);
                      setAddCost(r.price.toString());
                    }}
                    className="w-full text-left p-3 rounded-xl bg-white/[0.03] border border-white/5 hover:border-indigo-500/30 transition"
                  >
                    <div className="flex items-center justify-between">
                      <div>
                        <span className="font-mono font-bold text-white">{r.ticker}</span>
                        <span className="text-slate-400 text-sm ml-2">{r.name}</span>
                      </div>
                      <div className="text-right">
                        <span className="text-white font-mono font-bold">${r.price}</span>
                        <div className="text-[10px] text-slate-500">{r.exchange} · {r.currency}</div>
                      </div>
                    </div>
                    {r.sector && <div className="text-[10px] text-slate-500 mt-1">{r.sector} · {r.industry}</div>}
                  </button>
                ))}
              </div>
            )}

            {/* Selected stock form */}
            {selectedStock && (
              <div className="space-y-4">
                <div className="p-3 rounded-xl bg-indigo-500/10 border border-indigo-500/20 flex items-center justify-between">
                  <div>
                    <span className="font-mono font-bold text-white">{selectedStock.ticker}</span>
                    <span className="text-slate-400 text-sm ml-2">{selectedStock.name}</span>
                  </div>
                  <button onClick={() => setSelectedStock(null)} className="text-slate-500 hover:text-white text-sm">Change</button>
                </div>

                <div className="grid grid-cols-2 gap-3">
                  <div>
                    <label className="text-xs text-slate-500 mb-1 block">Shares *</label>
                    <input
                      type="number"
                      value={addShares}
                      onChange={(e) => setAddShares(e.target.value)}
                      placeholder="10"
                      className="input-dark w-full"
                      step="any"
                    />
                  </div>
                  <div>
                    <label className="text-xs text-slate-500 mb-1 block">Avg Cost ($) *</label>
                    <input
                      type="number"
                      value={addCost}
                      onChange={(e) => setAddCost(e.target.value)}
                      placeholder={selectedStock.price.toString()}
                      className="input-dark w-full"
                      step="any"
                    />
                  </div>
                </div>

                <div className="grid grid-cols-2 gap-3">
                  <div>
                    <label className="text-xs text-slate-500 mb-1 block">Type</label>
                    <select
                      value={addType}
                      onChange={(e) => setAddType(e.target.value)}
                      className="input-dark w-full"
                    >
                      <option value="stock">Stock</option>
                      <option value="etf">ETF</option>
                      <option value="mf">Mutual Fund</option>
                      <option value="sip">SIP</option>
                      <option value="crypto">Crypto</option>
                    </select>
                  </div>
                  {addType === "sip" && (
                    <div>
                      <label className="text-xs text-slate-500 mb-1 block">Monthly SIP ($)</label>
                      <input
                        type="number"
                        value={addSip}
                        onChange={(e) => setAddSip(e.target.value)}
                        placeholder="500"
                        className="input-dark w-full"
                      />
                    </div>
                  )}
                </div>

                <div>
                  <label className="text-xs text-slate-500 mb-1 block">Notes (optional)</label>
                  <input
                    value={addNotes}
                    onChange={(e) => setAddNotes(e.target.value)}
                    placeholder="Long-term hold, DCA strategy..."
                    className="input-dark w-full"
                  />
                </div>

                {error && <p className="text-red-400 text-sm">{error}</p>}

                <button
                  onClick={handleAdd}
                  disabled={adding || !addShares || !addCost}
                  className="btn-glow w-full py-3 text-sm flex items-center justify-center gap-2"
                >
                  {adding ? (
                    <span className="w-4 h-4 border-2 border-white/30 border-t-white rounded-full animate-spin" />
                  ) : (
                    <>
                      <span>＋</span> Add to Portfolio
                    </>
                  )}
                </button>
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
