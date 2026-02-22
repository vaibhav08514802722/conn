"use client";

import { useEffect, useState } from "react";
import { getTradeHistory, TradeLog } from "@/lib/api";

export default function TradeLogTable() {
  const [trades, setTrades] = useState<TradeLog[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    getTradeHistory(20)
      .then((res) => setTrades(res.trades || []))
      .catch(() => setTrades([]))
      .finally(() => setLoading(false));
  }, []);

  if (loading) {
    return (
      <div>
        <h3 className="text-lg font-semibold mb-4">💹 Recent Trades</h3>
        <div className="flex items-center justify-center py-8">
          <div className="w-6 h-6 border-2 border-indigo-500/30 border-t-indigo-500 rounded-full animate-spin" />
        </div>
      </div>
    );
  }

  return (
    <div>
      <h3 className="text-lg font-semibold mb-4">💹 Recent Trades</h3>

      {!trades.length ? (
        <p className="text-slate-500 text-sm text-center py-8">
          No trades yet. The agent hasn&apos;t executed any trades.
        </p>
      ) : (
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-white/5 text-slate-500 text-xs uppercase tracking-wider">
                <th className="text-left py-2 pr-4">Ticker</th>
                <th className="text-left py-2 pr-4">Action</th>
                <th className="text-right py-2 pr-4">Shares</th>
                <th className="text-right py-2 pr-4">Price</th>
                <th className="text-left py-2 pr-4">Signal</th>
                <th className="text-center py-2">Outcome</th>
              </tr>
            </thead>
            <tbody>
              {trades.map((trade) => (
                <tr
                  key={trade.trade_id}
                  className="border-b border-white/5 hover:bg-white/[0.03] transition"
                >
                  <td className="py-2.5 pr-4 font-mono font-bold">
                    {trade.ticker}
                  </td>
                  <td className="py-2.5 pr-4">
                    <span
                      className={`px-2 py-0.5 rounded text-xs font-bold ${
                        trade.action === "BUY"
                          ? "bg-green-500/20 text-green-400"
                          : "bg-red-500/20 text-red-400"
                      }`}
                    >
                      {trade.action}
                    </span>
                  </td>
                  <td className="py-2.5 pr-4 text-right">{trade.shares}</td>
                  <td className="py-2.5 pr-4 text-right font-mono">
                    ${trade.price_at_execution?.toFixed(2)}
                  </td>
                  <td className="py-2.5 pr-4 text-slate-400 max-w-[200px] truncate">
                    {trade.rationale?.signal || "—"}
                  </td>
                  <td className="py-2.5 text-center">
                    {trade.outcome ? (
                      <span
                        className={`text-xs font-bold ${
                          trade.outcome.success
                            ? "text-green-400"
                            : "text-red-400"
                        }`}
                      >
                        {trade.outcome.success ? "✓ Win" : "✗ Loss"}
                        <br />
                        <span className="text-slate-400 font-normal">
                          {trade.outcome.actual_pct?.toFixed(1)}%
                        </span>
                      </span>
                    ) : (
                      <span className="text-slate-500 text-xs">Pending</span>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
