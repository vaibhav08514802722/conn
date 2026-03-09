"use client";
/**
 * Phase 6 — ChatMessage Component
 * Renders a single user or assistant message with citations, confidence,
 * disclaimer, and follow-up question chips.
 */

import { SessionMessage } from "@/lib/api";
import CitationCard from "./CitationCard";
import { Scale, User, ChevronDown, ChevronUp, AlertCircle } from "lucide-react";
import { useState } from "react";

interface Props {
  message: SessionMessage & {
    relatedQuestions?: string[];
    confidence?: number;
    disclaimer?: string;
  };
  onFollowUp?: (q: string) => void;
}

export default function ChatMessage({ message, onFollowUp }: Props) {
  const isUser = message.role === "user";
  const [citationsOpen, setCitationsOpen] = useState(false);

  return (
    <div className={`flex gap-3 items-start ${isUser ? "justify-end" : "justify-start"}`}>
      {/* Avatar — only for assistant */}
      {!isUser && (
        <div className="w-8 h-8 rounded-full bg-blue-600 flex items-center justify-center flex-shrink-0 mt-1">
          <Scale className="w-4 h-4 text-white" />
        </div>
      )}

      <div className={`max-w-2xl flex flex-col gap-2 ${isUser ? "items-end" : "items-start"}`}>
        {/* Bubble */}
        <div
          className={`px-4 py-3 rounded-2xl text-sm leading-relaxed ${
            isUser
              ? "bg-blue-600 text-white rounded-br-md"
              : "bg-gray-800 text-gray-100 rounded-bl-md"
          }`}
        >
          {/* Confidence badge for assistant */}
          {!isUser && message.confidence !== undefined && (
            <div className="flex items-center gap-2 mb-2">
              <span className={`text-xs px-2 py-0.5 rounded-full font-medium ${
                message.confidence > 0.75
                  ? "bg-green-900/60 text-green-300"
                  : message.confidence > 0.5
                  ? "bg-yellow-900/60 text-yellow-300"
                  : "bg-red-900/60 text-red-300"
              }`}>
                {Math.round(message.confidence * 100)}% confidence
              </span>
            </div>
          )}

          {/* Message text */}
          <p style={{ whiteSpace: "pre-wrap" }}>{message.content}</p>
        </div>

        {/* Citations toggle */}
        {!isUser && message.citations && message.citations.length > 0 && (
          <div className="w-full">
            <button
              onClick={() => setCitationsOpen((v) => !v)}
              className="flex items-center gap-1.5 text-xs text-gray-400 hover:text-gray-200 transition-colors mb-1"
            >
              {citationsOpen ? <ChevronUp className="w-3.5 h-3.5" /> : <ChevronDown className="w-3.5 h-3.5" />}
              {message.citations.length} source{message.citations.length > 1 ? "s" : ""}
            </button>

            {citationsOpen && (
              <div className="space-y-1.5 w-full">
                {message.citations.map((c, i) => (
                  <CitationCard key={i} citation={c} index={i + 1} />
                ))}
              </div>
            )}
          </div>
        )}

        {/* Related follow-up questions */}
        {!isUser && message.relatedQuestions && message.relatedQuestions.length > 0 && (
          <div className="flex flex-wrap gap-2 mt-1">
            {message.relatedQuestions.map((q) => (
              <button
                key={q}
                onClick={() => onFollowUp?.(q)}
                className="text-xs px-3 py-1.5 bg-gray-800 hover:bg-gray-700 border border-gray-700 rounded-full text-gray-300 transition-colors"
              >
                {q}
              </button>
            ))}
          </div>
        )}

        {/* Disclaimer */}
        {!isUser && message.disclaimer && (
          <div className="flex items-start gap-1.5 text-xs text-gray-500 max-w-sm">
            <AlertCircle className="w-3.5 h-3.5 flex-shrink-0 mt-0.5" />
            <span>{message.disclaimer}</span>
          </div>
        )}

        {/* Timestamp */}
        <time className="text-xs text-gray-600 px-1">
          {new Date(message.timestamp).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })}
        </time>
      </div>

      {/* Avatar — only for user */}
      {isUser && (
        <div className="w-8 h-8 rounded-full bg-gray-700 flex items-center justify-center flex-shrink-0 mt-1">
          <User className="w-4 h-4 text-gray-300" />
        </div>
      )}
    </div>
  );
}
