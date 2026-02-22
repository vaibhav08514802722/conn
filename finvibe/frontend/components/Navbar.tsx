"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useAuth } from "@/lib/auth";
import { useState } from "react";

export default function Navbar() {
  const { user, logout } = useAuth();
  const pathname = usePathname();
  const [menuOpen, setMenuOpen] = useState(false);

  const isActive = (path: string) =>
    pathname === path
      ? "text-white"
      : "text-slate-400 hover:text-white";

  return (
    <nav className="nav-glass sticky top-0 z-50">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        <div className="flex items-center justify-between h-16">
          {/* ── Logo ── */}
          <Link href="/" className="flex items-center gap-2.5 group">
            <div className="w-9 h-9 rounded-xl bg-gradient-to-br from-indigo-500 to-purple-600 flex items-center justify-center text-white font-bold text-sm shadow-lg shadow-indigo-500/20 group-hover:shadow-indigo-500/40 transition-shadow">
              FV
            </div>
            <span className="text-lg font-bold gradient-text tracking-tight">
              FinVibe AI
            </span>
            <span className="hidden sm:inline-flex badge badge-purple text-[10px] ml-1">
              BETA
            </span>
          </Link>

          {/* ── Desktop Nav Links ── */}
          <div className="hidden md:flex items-center gap-1">
            <Link
              href="/"
              className={`px-3 py-2 rounded-lg text-sm font-medium transition-colors ${isActive("/")}`}
            >
              Home
            </Link>
            {user && (
              <>
                <Link
                  href="/dashboard"
                  className={`px-3 py-2 rounded-lg text-sm font-medium transition-colors ${isActive("/dashboard")}`}
                >
                  Dashboard
                </Link>
                <Link
                  href="/dashboard/my-portfolio"
                  className={`px-3 py-2 rounded-lg text-sm font-medium transition-colors ${isActive("/dashboard/my-portfolio")}`}
                >
                  My Portfolio
                </Link>
                <Link
                  href="/dashboard/ai-portfolio"
                  className={`px-3 py-2 rounded-lg text-sm font-medium transition-colors ${isActive("/dashboard/ai-portfolio")}`}
                >
                  <span className="flex items-center gap-1.5">AI Portfolio <span className="pulse-dot" /></span>
                </Link>
                <Link
                  href="/dashboard/chat"
                  className={`px-3 py-2 rounded-lg text-sm font-medium transition-colors ${isActive("/dashboard/chat")}`}
                >
                  AI Chat
                </Link>
              </>
            )}
            <a
              href="http://localhost:8000/docs"
              target="_blank"
              rel="noopener"
              className="px-3 py-2 rounded-lg text-sm font-medium text-slate-500 hover:text-slate-300 transition-colors"
            >
              API ↗
            </a>
          </div>

          {/* ── Right: Auth Buttons ── */}
          <div className="flex items-center gap-3">
            {user ? (
              <div className="flex items-center gap-3">
                {/* User avatar */}
                <div className="hidden sm:flex items-center gap-2">
                  <div className="w-8 h-8 rounded-full bg-gradient-to-br from-indigo-500 to-purple-600 flex items-center justify-center text-white text-xs font-bold">
                    {user.name?.charAt(0).toUpperCase()}
                  </div>
                  <span className="text-sm text-slate-300 font-medium max-w-[120px] truncate">
                    {user.name}
                  </span>
                </div>
                <button
                  onClick={logout}
                  className="btn-outline px-4 py-1.5 text-sm"
                >
                  Logout
                </button>
              </div>
            ) : (
              <div className="flex items-center gap-2">
                <Link
                  href="/login"
                  className="btn-outline px-5 py-2 text-sm"
                >
                  Login
                </Link>
                <Link
                  href="/signup"
                  className="btn-glow px-5 py-2 text-sm"
                >
                  Sign Up
                </Link>
              </div>
            )}

            {/* Mobile menu button */}
            <button
              onClick={() => setMenuOpen(!menuOpen)}
              className="md:hidden p-2 text-slate-400 hover:text-white"
            >
              <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                {menuOpen ? (
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
                ) : (
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 6h16M4 12h16M4 18h16" />
                )}
              </svg>
            </button>
          </div>
        </div>

        {/* ── Mobile Menu ── */}
        {menuOpen && (
          <div className="md:hidden pb-4 border-t border-white/5 mt-2 pt-3 space-y-1 animate-fade-in">
            <Link href="/" onClick={() => setMenuOpen(false)} className="block px-3 py-2 rounded-lg text-sm text-slate-300 hover:text-white hover:bg-white/5">
              Home
            </Link>
            {user && (
              <>
                <Link href="/dashboard" onClick={() => setMenuOpen(false)} className="block px-3 py-2 rounded-lg text-sm text-slate-300 hover:text-white hover:bg-white/5">
                  Dashboard
                </Link>
                <Link href="/dashboard/my-portfolio" onClick={() => setMenuOpen(false)} className="block px-3 py-2 rounded-lg text-sm text-slate-300 hover:text-white hover:bg-white/5">
                  My Portfolio
                </Link>
                <Link href="/dashboard/ai-portfolio" onClick={() => setMenuOpen(false)} className="block px-3 py-2 rounded-lg text-sm text-slate-300 hover:text-white hover:bg-white/5">
                  AI Portfolio 🟢
                </Link>
                <Link href="/dashboard/chat" onClick={() => setMenuOpen(false)} className="block px-3 py-2 rounded-lg text-sm text-slate-300 hover:text-white hover:bg-white/5">
                  AI Chat
                </Link>
              </>
            )}
          </div>
        )}
      </div>
    </nav>
  );
}
