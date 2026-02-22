"use client";

import { useEffect, useState } from "react";
import { getAllVibes, AggregateVibes } from "@/lib/api";

const VIBE_COLORS: Record<string, string> = {
  euphoric: "#22c55e",
  bullish: "#4ade80",
  neutral: "#eab308",
  anxious: "#f97316",
  panic: "#ef4444",
};

function getGaugeColor(anxiety: number): string {
  if (anxiety <= 3) return "#22c55e";
  if (anxiety <= 5) return "#eab308";
  if (anxiety <= 7) return "#f97316";
  return "#ef4444";
}

function getGaugeLabel(anxiety: number): string {
  if (anxiety <= 2) return "Calm";
  if (anxiety <= 4) return "Stable";
  if (anxiety <= 6) return "Cautious";
  if (anxiety <= 8) return "Anxious";
  return "Panic";
}

export default function VibeGauge() {
  const [vibes, setVibes] = useState<AggregateVibes | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    getAllVibes()
      .then(setVibes)
      .catch(() => setVibes(null))
      .finally(() => setLoading(false));
  }, []);

  if (loading) {
    return (
      <div>
        <h3 className="text-lg font-semibold mb-4">🎭 Vibe Gauge</h3>
        <div className="h-48 flex items-center justify-center">
          <div className="w-6 h-6 border-2 border-indigo-500/30 border-t-indigo-500 rounded-full animate-spin" />
        </div>
      </div>
    );
  }

  const anxiety = vibes?.aggregate_anxiety || 0;
  const color = getGaugeColor(anxiety);
  const label = getGaugeLabel(anxiety);
  const rotation = (anxiety / 10) * 180 - 90; // -90 to 90 degrees

  return (
    <div>
      <h3 className="text-lg font-semibold mb-4">🎭 Market Vibe</h3>

      {/* Gauge */}
      <div className="flex flex-col items-center mb-4">
        <div className="relative w-48 h-24 overflow-hidden">
          {/* Background arc */}
          <div
            className="absolute bottom-0 left-0 w-48 h-48 rounded-full border-8"
            style={{
              borderColor: "rgba(99,102,241,0.15)",
              clipPath: "polygon(0 0, 100% 0, 100% 50%, 0 50%)",
            }}
          />
          {/* Colored arc */}
          <div
            className="absolute bottom-0 left-1/2 w-2 h-20 origin-bottom transition-transform duration-700"
            style={{
              transform: `translateX(-50%) rotate(${rotation}deg)`,
              background: color,
              borderRadius: "2px",
            }}
          />
          {/* Center dot */}
          <div
            className="absolute bottom-0 left-1/2 w-4 h-4 rounded-full -translate-x-1/2 translate-y-1/2"
            style={{ background: color }}
          />
        </div>
        <div className="text-center mt-2">
          <span className="text-3xl font-bold" style={{ color }}>
            {anxiety.toFixed(1)}
          </span>
          <span className="text-slate-400 text-sm">/10</span>
        </div>
        <span className="text-sm font-medium mt-1" style={{ color }}>
          {label}
        </span>
      </div>

      {/* Per-ticker breakdown */}
      {vibes?.tickers && vibes.tickers.length > 0 && (
        <div className="space-y-2 mt-4 border-t border-white/5 pt-4">
          {vibes.tickers.map((t) => (
            <div
              key={t.ticker}
              className="flex items-center justify-between text-sm"
            >
              <div className="flex items-center gap-2">
                <span className="font-mono font-bold">{t.ticker}</span>
                <span
                  className="text-xs px-1.5 py-0.5 rounded"
                  style={{
                    background: `${VIBE_COLORS[t.latest_vibe] || "#eab308"}20`,
                    color: VIBE_COLORS[t.latest_vibe] || "#eab308",
                  }}
                >
                  {t.latest_vibe}
                </span>
              </div>
              <div className="flex items-center gap-3 text-slate-400">
                <span>S: {t.latest_sentiment?.toFixed(2)}</span>
                <span
                  style={{
                    color: getGaugeColor(t.latest_anxiety),
                  }}
                >
                  A: {t.latest_anxiety?.toFixed(1)}
                </span>
              </div>
            </div>
          ))}
        </div>
      )}

      {!vibes?.tickers?.length && (
        <p className="text-slate-500 text-sm text-center">
          No vibe data yet. Run an analysis first!
        </p>
      )}
    </div>
  );
}
