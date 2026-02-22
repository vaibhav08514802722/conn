"use client";

import { useEffect, useState } from "react";
import { getReflections, Reflection } from "@/lib/api";

export default function ReflectionFeed() {
  const [reflections, setReflections] = useState<Reflection[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    getReflections()
      .then((res) => setReflections(res.reflections))
      .catch(() => setReflections([]))
      .finally(() => setLoading(false));
  }, []);

  if (loading) {
    return (
      <div>
        <h3 className="text-lg font-semibold mb-4">🧠 Agent Reflections</h3>
        <div className="flex items-center justify-center py-8">
          <div className="w-6 h-6 border-2 border-indigo-500/30 border-t-indigo-500 rounded-full animate-spin" />
        </div>
      </div>
    );
  }

  return (
    <div>
      <h3 className="text-lg font-semibold mb-4">🧠 Agent Reflections</h3>

      {!reflections.length ? (
        <p className="text-slate-500 text-sm text-center py-8">
          No reflections yet. The agent learns after evaluating past trades.
        </p>
      ) : (
        <div className="space-y-3 max-h-[350px] overflow-y-auto pr-2 custom-scrollbar">
          {reflections.map((ref, idx) => (
            <div
              key={idx}
              className="border border-white/5 rounded-xl p-4 bg-white/[0.03] hover:bg-white/[0.06] transition"
            >
              {/* Lesson */}
              <p className="text-sm leading-relaxed mb-2">
                {ref.lesson}
              </p>

              {/* Meta row */}
              <div className="flex items-center gap-3 text-xs text-slate-500">
                {ref.ticker && (
                  <span className="px-1.5 py-0.5 bg-indigo-500/20 text-indigo-300 rounded font-mono">
                    {ref.ticker}
                  </span>
                )}
                {ref.created_at && (
                  <span>
                    {new Date(ref.created_at).toLocaleDateString()}
                  </span>
                )}
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
