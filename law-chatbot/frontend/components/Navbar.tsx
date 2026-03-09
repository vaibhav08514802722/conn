"use client";
/**
 * Phase 6 — Navbar Component
 */

import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { useAuth } from "@/lib/auth";
import { Scale, MessageSquare, Database, LogOut, Menu } from "lucide-react";

interface NavbarProps { onToggleSidebar?: () => void }

export default function Navbar({ onToggleSidebar }: NavbarProps) {
  const { user, logout } = useAuth();
  const pathname = usePathname();
  const router = useRouter();

  const handleLogout = () => { logout(); router.push("/login"); };

  const navLink = (href: string, Icon: any, label: string) => (
    <Link
      href={href}
      className={`flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-sm transition-colors ${
        pathname.startsWith(href)
          ? "bg-blue-600 text-white"
          : "text-gray-400 hover:text-white hover:bg-gray-800"
      }`}
    >
      <Icon className="w-4 h-4" />
      {label}
    </Link>
  );

  return (
    <header className="flex items-center gap-4 px-4 py-3 bg-gray-900 border-b border-gray-800 flex-shrink-0">
      {/* Sidebar toggle (chat page only) */}
      {onToggleSidebar && (
        <button onClick={onToggleSidebar} className="p-1.5 text-gray-400 hover:text-white">
          <Menu className="w-5 h-5" />
        </button>
      )}

      {/* Logo */}
      <Link href="/chat" className="flex items-center gap-2 font-bold text-white mr-4">
        <Scale className="w-5 h-5 text-blue-400" />
        LexBot
      </Link>

      {/* Navigation */}
      <nav className="flex items-center gap-1">
        {navLink("/chat", MessageSquare, "Chat")}
        {navLink("/documents", Database, "Knowledge Base")}
      </nav>

      {/* Right side — user */}
      <div className="ml-auto flex items-center gap-3">
        {user && (
          <span className="text-sm text-gray-400 hidden sm:block">{user.name}</span>
        )}
        <button
          onClick={handleLogout}
          className="flex items-center gap-1.5 px-3 py-1.5 text-sm text-gray-400 hover:text-white hover:bg-gray-800 rounded-lg transition-colors"
        >
          <LogOut className="w-4 h-4" />
          Sign out
        </button>
      </div>
    </header>
  );
}
