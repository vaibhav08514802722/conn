"use client";
/**
 * Phase 6 — Session Sidebar
 * Lists chat sessions; supports creating a new session and deleting existing ones.
 */

import { ChatSession } from "@/lib/api";
import { MessageSquare, Plus, Trash2 } from "lucide-react";

interface Props {
  sessions:  ChatSession[];
  activeId:  string | null;
  onSelect:  (id: string) => void;
  onNew:     () => void;
  onDelete:  (id: string) => void;
}

export default function SessionSidebar({ sessions, activeId, onSelect, onNew, onDelete }: Props) {
  return (
    <aside className="w-64 flex-shrink-0 bg-gray-900 border-r border-gray-800 flex flex-col">
      {/* New chat button */}
      <div className="p-3 border-b border-gray-800">
        <button
          onClick={onNew}
          className="w-full flex items-center gap-2 px-3 py-2 bg-blue-600 hover:bg-blue-500 text-white rounded-lg text-sm font-medium transition-colors"
        >
          <Plus className="w-4 h-4" />
          New Chat
        </button>
      </div>

      {/* Session list */}
      <div className="flex-1 overflow-y-auto py-2">
        {sessions.length === 0 ? (
          <p className="px-4 py-6 text-xs text-gray-600 text-center">
            No previous chats.<br />Start a new conversation.
          </p>
        ) : (
          sessions.map((s) => (
            <div
              key={s.id}
              className={`group flex items-center gap-2 px-3 py-2 mx-2 rounded-lg cursor-pointer transition-colors ${
                activeId === s.id
                  ? "bg-gray-800 text-white"
                  : "text-gray-400 hover:bg-gray-800 hover:text-white"
              }`}
              onClick={() => onSelect(s.id)}
            >
              <MessageSquare className="w-4 h-4 flex-shrink-0" />
              <span className="flex-1 text-sm truncate">{s.title}</span>
              {/* Delete button — visible on hover */}
              <button
                onClick={(e) => { e.stopPropagation(); onDelete(s.id); }}
                className="opacity-0 group-hover:opacity-100 p-1 text-gray-500 hover:text-red-400 transition-all"
              >
                <Trash2 className="w-3.5 h-3.5" />
              </button>
            </div>
          ))
        )}
      </div>

      {/* Footer */}
      <div className="p-3 border-t border-gray-800 text-xs text-gray-600 text-center">
        {sessions.length} session{sessions.length !== 1 ? "s" : ""}
      </div>
    </aside>
  );
}
