"use client";
/**
 * Phase 6 — CitationCard Component
 * Expandable card showing the legal source for an answer.
 */

import { useState } from "react";
import { Citation } from "@/lib/api";
import { BookOpen, ChevronDown, ChevronUp, ExternalLink } from "lucide-react";

export default function CitationCard({ citation, index }: { citation: Citation; index: number }) {
  const [open, setOpen] = useState(false);

  return (
    <div className="border border-gray-700 rounded-lg overflow-hidden text-xs">
      {/* Header — always visible */}
      <button
        onClick={() => setOpen((v) => !v)}
        className="w-full flex items-center gap-2 px-3 py-2 bg-gray-800/60 hover:bg-gray-800 text-left transition-colors"
      >
        <BookOpen className="w-3.5 h-3.5 text-blue-400 flex-shrink-0" />
        <span className="font-medium text-gray-200 flex-1 truncate">
          [{index}] {citation.section || citation.act}
        </span>
        <span className="text-gray-500 mr-1">
          {Math.round(citation.relevance_score * 100)}% match
        </span>
        {open ? <ChevronUp className="w-3.5 h-3.5 text-gray-500" /> : <ChevronDown className="w-3.5 h-3.5 text-gray-500" />}
      </button>

      {/* Expanded detail */}
      {open && (
        <div className="px-3 py-2 bg-gray-900 space-y-1 text-gray-400">
          {citation.section && <div><span className="text-gray-600">Section:</span> {citation.section}</div>}
          {citation.act     && <div><span className="text-gray-600">Act:</span> {citation.act}</div>}
          {citation.chapter && <div><span className="text-gray-600">Chapter:</span> {citation.chapter}</div>}
          {citation.page    && <div><span className="text-gray-600">Page:</span> {citation.page}</div>}
          {citation.source  && (
            <div className="flex items-center gap-1">
              <span className="text-gray-600">Source:</span>
              {citation.source.startsWith("http") ? (
                <a
                  href={citation.source}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="text-blue-400 hover:text-blue-300 flex items-center gap-0.5"
                >
                  {new URL(citation.source).hostname} <ExternalLink className="w-3 h-3" />
                </a>
              ) : (
                <span>{citation.source}</span>
              )}
            </div>
          )}
        </div>
      )}
    </div>
  );
}
