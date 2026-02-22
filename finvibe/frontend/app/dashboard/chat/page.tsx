"use client";

import { useState, useRef, useEffect, useCallback } from "react";
import { useRouter } from "next/navigation";
import { useAuth } from "@/lib/auth";
import {
  askInvestmentChat,
  seedInvestmentKnowledge,
  RAGCitation,
} from "@/lib/api";

interface ChatMessage {
  role: "user" | "assistant";
  content: string;
  citations?: RAGCitation[];
  confidence?: number;
  actionBias?: string;
  timeframe?: string;
  riskNotes?: string[];
  followups?: string[];
  timestamp: Date;
}

export default function ChatPage() {
  const { user, loading: authLoading } = useAuth();
  const router = useRouter();
  const [question, setQuestion] = useState("");
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [sending, setSending] = useState(false);
  const [seeding, setSeeding] = useState(false);
  const [seedStatus, setSeedStatus] = useState<string>("");
  const [openCitations, setOpenCitations] = useState<Record<number, boolean>>({});
  const bottomRef = useRef<HTMLDivElement>(null);

  // Redirect if not logged in
  useEffect(() => {
    if (!authLoading && !user) router.push("/login");
  }, [authLoading, user, router]);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  const handleSeedKnowledge = useCallback(async () => {
    setSeeding(true);
    setSeedStatus("");
    try {
      const res = await seedInvestmentKnowledge();
      if (res.seeded) {
        setSeedStatus(`Seeded ${res.added_docs} knowledge docs.`);
      } else {
        setSeedStatus(`Knowledge already available (${res.existing_docs} docs).`);
      }
    } catch {
      setSeedStatus("Could not seed right now. You can still ask questions.");
    } finally {
      setSeeding(false);
    }
  }, []);

  const sendQuestion = useCallback(async () => {
    const q = question.trim();
    if (!q || sending) return;

    setMessages((prev) => [
      ...prev,
      { role: "user", content: q, timestamp: new Date() },
    ]);
    setQuestion("");
    setSending(true);

    try {
      const res = await askInvestmentChat(q, user?.id || "demo_user", 6);
      setMessages((prev) => [
        ...prev,
        {
          role: "assistant",
          content: res.answer,
          citations: res.citations,
          confidence: res.confidence,
          actionBias: res.action_bias,
          timeframe: res.timeframe,
          riskNotes: res.risk_notes,
          followups: res.followups,
          timestamp: new Date(),
        },
      ]);
    } catch (e: any) {
      setMessages((prev) => [
        ...prev,
        {
          role: "assistant",
          content: `I hit an error while generating advice: ${e.message || "Unknown error"}`,
          timestamp: new Date(),
        },
      ]);
    } finally {
      setSending(false);
    }
  }, [question, sending, user]);

  const quickPrompts = [
    "Should I buy NVDA after a strong run?",
    "Compare AAPL vs MSFT for 12-month investing",
    "Build a medium-risk 5-stock portfolio",
    "How should I size TSLA in my portfolio?",
    "What are key risks before earnings season?",
  ];

  if (authLoading) {
    return (
      <div className="flex items-center justify-center min-h-[60vh]">
        <div className="w-8 h-8 border-2 border-indigo-500/30 border-t-indigo-500 rounded-full animate-spin" />
      </div>
    );
  }

  if (!user) return null;

  return (
    <div className="max-w-4xl mx-auto px-4 sm:px-6 lg:px-8 py-8 flex flex-col h-[calc(100vh-80px)]">
      {/* Header */}
      <div className="flex items-center gap-3 mb-5">
        <div className="w-10 h-10 rounded-xl bg-gradient-to-br from-indigo-500/20 to-purple-500/20 border border-indigo-500/20 flex items-center justify-center text-lg">
          💬
        </div>
        <div>
          <h2 className="text-xl font-bold text-white">AI Chat</h2>
          <p className="text-xs text-slate-500">Investment-focused RAG advisor with evidence-based citations</p>
        </div>
        <button
          onClick={handleSeedKnowledge}
          disabled={seeding}
          className="ml-auto btn-outline px-3 py-2 text-xs"
        >
          {seeding ? "Seeding..." : "Seed Knowledge"}
        </button>
      </div>

      {seedStatus && (
        <div className="mb-3 text-xs text-emerald-400">{seedStatus}</div>
      )}

      {/* ── Messages ─────────────────────────────────────── */}
      <div className="flex-1 overflow-y-auto glass-card p-5 space-y-4 mb-4">
        {messages.length === 0 && (
          <div className="text-center py-16">
            <div className="text-4xl mb-4">🤖</div>
            <p className="text-slate-500 text-sm">
              Ask any investing question and get RAG-grounded answers with sources.
            </p>
            <div className="mt-6 flex flex-wrap justify-center gap-2">
              {quickPrompts.map((t) => (
                <button
                  key={t}
                  onClick={() => setQuestion(t)}
                  className="px-3 py-1.5 rounded-lg text-xs border border-white/10 text-slate-400 hover:text-white hover:border-indigo-500/30 transition"
                >
                  {t}
                </button>
              ))}
            </div>
          </div>
        )}

        {messages.map((msg, idx) => (
          <div
            key={idx}
            className={`flex ${msg.role === "user" ? "justify-end" : "justify-start"} animate-fade-in`}
          >
            <div
              className={`max-w-[85%] rounded-2xl px-5 py-3 ${
                msg.role === "user"
                  ? "bg-gradient-to-br from-indigo-600/30 to-indigo-600/10 border border-indigo-500/20"
                  : "bg-gradient-to-br from-white/5 to-white/[0.02] border border-white/10"
              }`}
            >
              {msg.role === "assistant" && (
                <div className="flex flex-wrap items-center gap-2 text-[10px] mb-2 text-slate-400">
                  {msg.confidence !== undefined && (
                    <span className="px-2 py-0.5 rounded-full border border-indigo-500/30 bg-indigo-500/10">
                      Confidence {(msg.confidence * 100).toFixed(0)}%
                    </span>
                  )}
                  {msg.actionBias && (
                    <span className="px-2 py-0.5 rounded-full border border-white/15 bg-white/5">
                      Bias: {msg.actionBias}
                    </span>
                  )}
                  {msg.timeframe && (
                    <span className="px-2 py-0.5 rounded-full border border-white/15 bg-white/5">
                      Timeframe: {msg.timeframe}
                    </span>
                  )}
                </div>
              )}
              <div className="text-sm whitespace-pre-wrap leading-relaxed">{msg.content}</div>

              {msg.riskNotes && msg.riskNotes.length > 0 && (
                <div className="mt-2 text-xs text-amber-300/90">
                  ⚠️ {msg.riskNotes.join(" • ")}
                </div>
              )}

              {msg.followups && msg.followups.length > 0 && (
                <div className="mt-3 flex flex-wrap gap-2">
                  {msg.followups.slice(0, 3).map((f, i) => (
                    <button
                      key={`${idx}-f-${i}`}
                      onClick={() => setQuestion(f)}
                      className="text-[10px] px-2 py-1 rounded border border-white/10 text-slate-300 hover:border-indigo-500/30"
                    >
                      {f}
                    </button>
                  ))}
                </div>
              )}

              {msg.citations && msg.citations.length > 0 && (
                <div className="mt-3">
                  <button
                    onClick={() => setOpenCitations((prev) => ({ ...prev, [idx]: !prev[idx] }))}
                    className="text-xs text-indigo-300 hover:text-indigo-200"
                  >
                    {openCitations[idx] ? "Hide sources" : `Show sources (${msg.citations.length})`}
                  </button>

                  {openCitations[idx] && (
                    <div className="mt-2 space-y-2">
                      {msg.citations.map((c) => (
                        <div key={`${idx}-c-${c.id}`} className="rounded-lg border border-white/10 bg-white/[0.02] p-2.5">
                          <div className="text-xs text-white font-medium">[{c.id}] {c.title}</div>
                          <div className="text-[10px] text-slate-500 mt-0.5">{c.source}</div>
                          <div className="text-xs text-slate-400 mt-1">{c.snippet}</div>
                          {c.url && (
                            <a
                              href={c.url}
                              target="_blank"
                              rel="noreferrer"
                              className="text-[10px] text-indigo-300 hover:text-indigo-200 mt-1 inline-block"
                            >
                              Open source ↗
                            </a>
                          )}
                        </div>
                      ))}
                    </div>
                  )}
                </div>
              )}

              <div className="text-[10px] text-slate-600 mt-1.5 text-right">{msg.timestamp.toLocaleTimeString()}</div>
            </div>
          </div>
        ))}
        <div ref={bottomRef} />
      </div>

      {/* ── Input bar ──────────────────────────────────────── */}
      <div className="glass-card p-4 flex items-end gap-3">
        <div className="flex-1">
          <textarea
            value={question}
            onChange={(e) => setQuestion(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === "Enter" && !e.shiftKey) {
                e.preventDefault();
                if (!sending) sendQuestion();
              }
            }}
            className="input-dark min-h-[84px] resize-none"
            placeholder="Ask investment questions: valuation, allocation, risk, earnings, buy/hold/sell thesis..."
            disabled={sending}
          />
        </div>
        <button onClick={sendQuestion} disabled={sending || !question.trim()} className="btn-glow px-6 py-3 text-sm disabled:opacity-60">
          {sending ? "Thinking..." : "Send →"}
        </button>
      </div>

      <p className="mt-2 text-[10px] text-slate-500 text-center">
        Educational content only. Not financial advice.
      </p>
    </div>
  );
}
