"use client";
/**
 * Phase 6 — Chat Page
 * Full chat interface with session sidebar, message history, citations.
 */

import { useState, useEffect, useRef } from "react";
import { useRouter } from "next/navigation";
import { useAuth } from "@/lib/auth";
import { chatAPI, ChatSession, SessionMessage } from "@/lib/api";
import SessionSidebar from "@/components/SessionSidebar";
import ChatMessage from "@/components/ChatMessage";
import Navbar from "@/components/Navbar";
import { Send, Plus, Scale } from "lucide-react";

// Quick-start example questions shown when chat is empty
const STARTER_QUESTIONS = [
  "What is Section 302 of the Indian Penal Code?",
  "How do I file an FIR?",
  "What are my rights if I am arrested?",
  "Explain the Right to Information Act (RTI).",
  "What is the difference between bail and anticipatory bail?",
];

export default function ChatPage() {
  const { user, token, loading } = useAuth();
  const router = useRouter();

  // ── State ──────────────────────────────────────────────────────────────────
  const [sessions,       setSessions]       = useState<ChatSession[]>([]);
  const [activeSession,  setActiveSession]  = useState<string | null>(null);
  const [messages,       setMessages]       = useState<SessionMessage[]>([]);
  const [input,          setInput]          = useState("");
  const [sending,        setSending]        = useState(false);
  const [sidebarOpen,    setSidebarOpen]    = useState(true);

  const bottomRef = useRef<HTMLDivElement>(null);
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  // ── Auth guard ────────────────────────────────────────────────────────────
  useEffect(() => {
    if (!loading && !token) router.push("/login");
  }, [loading, token, router]);

  // ── Load sessions ─────────────────────────────────────────────────────────
  useEffect(() => {
    if (token) {
      chatAPI.getSessions(token).then(setSessions).catch(console.error);
    }
  }, [token]);

  // ── Auto-scroll to bottom when new message arrives ────────────────────────
  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  // ── Load messages for a session ───────────────────────────────────────────
  const loadSession = async (id: string) => {
    if (!token) return;
    setActiveSession(id);
    try {
      const res = await chatAPI.getSession(id, token);
      setMessages(res.messages);
    } catch {
      setMessages([]);
    }
  };

  // ── New chat ───────────────────────────────────────────────────────────────
  const newChat = () => {
    setActiveSession(null);
    setMessages([]);
    textareaRef.current?.focus();
  };

  // ── Delete session ─────────────────────────────────────────────────────────
  const deleteSession = async (id: string) => {
    if (!token) return;
    await chatAPI.deleteSession(id, token);
    setSessions((prev) => prev.filter((s) => s.id !== id));
    if (activeSession === id) newChat();
  };

  // ── Send message ───────────────────────────────────────────────────────────
  const sendMessage = async (questionOverride?: string) => {
    const question = (questionOverride ?? input).trim();
    if (!question || !token || sending) return;

    setInput("");
    setSending(true);

    // Optimistically add user message to UI
    const userMsg: SessionMessage = {
      role: "user", content: question, citations: [],
      timestamp: new Date().toISOString(),
    };
    setMessages((prev) => [...prev, userMsg]);

    try {
      const res = await chatAPI.ask(question, activeSession, token);

      // If this was a new session, refresh session list + set active
      if (!activeSession) {
        setActiveSession(res.session_id);
        const updated = await chatAPI.getSessions(token);
        setSessions(updated);
      }

      // Add assistant reply
      const botMsg: SessionMessage = {
        role: "assistant",
        content: res.answer,
        citations: res.citations,
        timestamp: new Date().toISOString(),
      };
      setMessages((prev) => [...prev, botMsg]);

      // Add related questions as a special assistant message if any exist
      if (res.related_questions.length > 0) {
        // We store them embedded in the last message via a special field
        // handled by ChatMessage component
        setMessages((prev) => {
          const last = { ...prev[prev.length - 1] } as any;
          last.relatedQuestions = res.related_questions;
          last.confidence = res.confidence;
          last.disclaimer = res.disclaimer;
          return [...prev.slice(0, -1), last];
        });
      }
    } catch (err: any) {
      const errMsg: SessionMessage = {
        role: "assistant",
        content: `Sorry, I encountered an error: ${err.message}`,
        citations: [],
        timestamp: new Date().toISOString(),
      };
      setMessages((prev) => [...prev, errMsg]);
    } finally {
      setSending(false);
      textareaRef.current?.focus();
    }
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      sendMessage();
    }
  };

  if (loading) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-gray-950">
        <Scale className="w-8 h-8 text-blue-400 animate-pulse" />
      </div>
    );
  }

  return (
    <div className="flex flex-col h-screen bg-gray-950">
      <Navbar onToggleSidebar={() => setSidebarOpen((v) => !v)} />

      <div className="flex flex-1 overflow-hidden">
        {/* ── Sidebar ── */}
        {sidebarOpen && (
          <SessionSidebar
            sessions={sessions}
            activeId={activeSession}
            onSelect={loadSession}
            onNew={newChat}
            onDelete={deleteSession}
          />
        )}

        {/* ── Main chat area ── */}
        <div className="flex flex-col flex-1 overflow-hidden">

          {/* Messages */}
          <div className="flex-1 overflow-y-auto px-4 py-6 space-y-4">

            {messages.length === 0 ? (
              /* Empty state — show starter questions */
              <div className="flex flex-col items-center justify-center h-full gap-6 text-center">
                <div>
                  <Scale className="w-12 h-12 text-blue-400 mx-auto mb-3" />
                  <h2 className="text-2xl font-bold text-white">LexBot</h2>
                  <p className="text-gray-400 mt-1">Ask me anything about Indian law</p>
                </div>
                <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 w-full max-w-2xl">
                  {STARTER_QUESTIONS.map((q) => (
                    <button
                      key={q}
                      onClick={() => sendMessage(q)}
                      className="text-left px-4 py-3 bg-gray-800 hover:bg-gray-700 border border-gray-700 rounded-xl text-sm text-gray-300 transition-colors"
                    >
                      {q}
                    </button>
                  ))}
                </div>
              </div>
            ) : (
              messages.map((msg, i) => (
                <ChatMessage
                  key={i}
                  message={msg}
                  onFollowUp={sendMessage}
                />
              ))
            )}

            {/* Typing indicator */}
            {sending && (
              <div className="flex gap-3 items-start">
                <div className="w-8 h-8 rounded-full bg-blue-600 flex items-center justify-center flex-shrink-0">
                  <Scale className="w-4 h-4 text-white" />
                </div>
                <div className="bg-gray-800 rounded-2xl px-4 py-3">
                  <div className="flex gap-1">
                    <span className="w-2 h-2 bg-gray-400 rounded-full animate-bounce" style={{ animationDelay: "0ms" }} />
                    <span className="w-2 h-2 bg-gray-400 rounded-full animate-bounce" style={{ animationDelay: "150ms" }} />
                    <span className="w-2 h-2 bg-gray-400 rounded-full animate-bounce" style={{ animationDelay: "300ms" }} />
                  </div>
                </div>
              </div>
            )}

            <div ref={bottomRef} />
          </div>

          {/* Input bar */}
          <div className="border-t border-gray-800 px-4 py-4 bg-gray-900">
            <div className="flex gap-3 items-end max-w-4xl mx-auto">
              <textarea
                ref={textareaRef}
                value={input}
                onChange={(e) => setInput(e.target.value)}
                onKeyDown={handleKeyDown}
                rows={1}
                placeholder="Ask a legal question… (Enter to send, Shift+Enter for newline)"
                className="flex-1 resize-none px-4 py-3 bg-gray-800 border border-gray-700 rounded-xl text-white placeholder-gray-500 focus:outline-none focus:ring-2 focus:ring-blue-500 max-h-40 overflow-y-auto"
                style={{ fieldSizing: "content" } as any}
              />
              <button
                onClick={() => sendMessage()}
                disabled={!input.trim() || sending}
                className="p-3 bg-blue-600 hover:bg-blue-500 disabled:opacity-40 rounded-xl text-white transition-colors flex-shrink-0"
              >
                <Send className="w-5 h-5" />
              </button>
            </div>
            <p className="text-center text-xs text-gray-600 mt-2">
              LexBot provides legal information, not legal advice. Always consult a qualified lawyer.
            </p>
          </div>
        </div>
      </div>
    </div>
  );
}
