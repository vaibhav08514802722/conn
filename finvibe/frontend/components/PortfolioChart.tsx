"use client";

import { useEffect, useState } from "react";
import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
} from "recharts";
import { getPortfolioHistory, PortfolioHistoryPoint } from "@/lib/api";

export default function PortfolioChart() {
  const [data, setData] = useState<PortfolioHistoryPoint[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    getPortfolioHistory()
      .then((history) => {
        setData(Array.isArray(history) ? history : []);
      })
      .catch(() => setData([]))
      .finally(() => setLoading(false));
  }, []);

  if (loading) {
    return (
      <div>
        <h3 className="text-lg font-semibold mb-4">📈 Portfolio Value</h3>
        <div className="h-64 flex items-center justify-center text-slate-500">
          <div className="w-6 h-6 border-2 border-indigo-500/30 border-t-indigo-500 rounded-full animate-spin" />
        </div>
      </div>
    );
  }

  if (!data.length) {
    return (
      <div>
        <h3 className="text-lg font-semibold mb-4">📈 Portfolio Value</h3>
        <div className="h-64 flex items-center justify-center text-slate-500 text-sm">
          No portfolio history yet. Run an analysis first!
        </div>
      </div>
    );
  }

  const latestValue = data[data.length - 1]?.total_value || 0;
  const startValue = data[0]?.total_value || 1000000;
  const changePct = ((latestValue - startValue) / startValue) * 100;

  return (
    <div>
      <div className="flex items-center justify-between mb-4">
        <h3 className="text-lg font-semibold">📈 Shadow Portfolio</h3>
        <div className="text-right">
          <div className="text-2xl font-bold">
            ${latestValue.toLocaleString(undefined, { maximumFractionDigits: 0 })}
          </div>
          <div
            className={`text-sm font-medium ${
              changePct >= 0 ? "text-green-400" : "text-red-400"
            }`}
          >
            {changePct >= 0 ? "+" : ""}
            {changePct.toFixed(2)}%
          </div>
        </div>
      </div>
      <ResponsiveContainer width="100%" height={250}>
        <LineChart data={data}>
          <CartesianGrid strokeDasharray="3 3" stroke="rgba(99,102,241,0.1)" />
          <XAxis
            dataKey="date"
            stroke="#94a3b8"
            fontSize={12}
            tickFormatter={(val) => val.slice(5)} // MM-DD
          />
          <YAxis
            stroke="#94a3b8"
            fontSize={12}
            tickFormatter={(val) =>
              `$${(val / 1000).toFixed(0)}k`
            }
          />
          <Tooltip
            contentStyle={{
              background: "#0f1737",
              border: "1px solid rgba(99,102,241,0.2)",
              borderRadius: "12px",
              color: "#f0f4ff",
            }}
            formatter={(value: number) => [
              `$${value.toLocaleString(undefined, { maximumFractionDigits: 2 })}`,
              "Value",
            ]}
          />
          <Line
            type="monotone"
            dataKey="total_value"
            stroke="#6366f1"
            strokeWidth={2}
            dot={false}
            activeDot={{ r: 4, fill: "#6366f1" }}
          />
        </LineChart>
      </ResponsiveContainer>
    </div>
  );
}
