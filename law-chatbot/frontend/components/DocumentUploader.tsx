"use client";
/**
 * Phase 6 — DocumentUploader Component
 * Handles PDF file upload and URL scraping in two tabs.
 */

import { useState, useRef } from "react";
import { documentsAPI } from "@/lib/api";
import { Upload, Globe, CheckCircle, XCircle, Loader } from "lucide-react";

interface Props { tab: "upload" | "scrape"; token: string; onSuccess: () => void }

export default function DocumentUploader({ tab, token, onSuccess }: Props) {
  // ── Upload state ──────────────────────────────────────────────────────────
  const [file,     setFile]     = useState<File | null>(null);
  const [title,    setTitle]    = useState("");
  const [actName,  setActName]  = useState("");

  // ── Scrape state ─────────────────────────────────────────────────────────
  const [url,      setUrl]      = useState("");
  const [scrTitle, setScrTitle] = useState("");
  const [scrAct,   setScrAct]   = useState("");

  // ── Shared ────────────────────────────────────────────────────────────────
  const [status, setStatus] = useState<"idle" | "loading" | "success" | "error">("idle");
  const [msg,    setMsg]    = useState("");
  const fileRef = useRef<HTMLInputElement>(null);

  const reset = () => {
    setStatus("idle"); setMsg("");
    setFile(null); setTitle(""); setActName("");
    setUrl(""); setScrTitle(""); setScrAct("");
  };

  // ── Handle PDF upload ─────────────────────────────────────────────────────
  const handleUpload = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!file || !title) return;
    setStatus("loading");
    try {
      const res: any = await documentsAPI.upload(file, title, actName, token);
      setMsg(`✓ Uploaded — ${res.chunk_count} chunks stored`);
      setStatus("success");
      onSuccess();
      setTimeout(reset, 3000);
    } catch (err: any) {
      setMsg(err.message);
      setStatus("error");
    }
  };

  // ── Handle URL scrape ──────────────────────────────────────────────────────
  const handleScrape = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!url || !scrAct) return;
    setStatus("loading");
    try {
      const res: any = await documentsAPI.scrape(url, scrAct, scrTitle || scrAct, token);
      setMsg(`✓ Scraped — ${res.chunk_count} chunks stored`);
      setStatus("success");
      onSuccess();
      setTimeout(reset, 3000);
    } catch (err: any) {
      setMsg(err.message);
      setStatus("error");
    }
  };

  const inputCls = "w-full px-3 py-2 bg-gray-800 border border-gray-700 rounded-lg text-white placeholder-gray-500 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500";

  // ── Status banner ─────────────────────────────────────────────────────────
  const Banner = () => {
    if (status === "idle") return null;
    if (status === "loading") return (
      <div className="flex items-center gap-2 text-yellow-300 text-sm mt-3">
        <Loader className="w-4 h-4 animate-spin" /> Processing…
      </div>
    );
    if (status === "success") return (
      <div className="flex items-center gap-2 text-green-300 text-sm mt-3">
        <CheckCircle className="w-4 h-4" /> {msg}
      </div>
    );
    return (
      <div className="flex items-center gap-2 text-red-300 text-sm mt-3">
        <XCircle className="w-4 h-4" /> {msg}
      </div>
    );
  };

  // ── Render ────────────────────────────────────────────────────────────────
  if (tab === "upload") {
    return (
      <form onSubmit={handleUpload} className="space-y-4">
        {/* Drop zone */}
        <div
          onClick={() => fileRef.current?.click()}
          className={`border-2 border-dashed rounded-xl p-8 text-center cursor-pointer transition-colors ${
            file ? "border-blue-500 bg-blue-900/10" : "border-gray-700 hover:border-blue-600"
          }`}
        >
          <Upload className="w-8 h-8 mx-auto mb-2 text-gray-500" />
          <p className="text-sm text-gray-400">
            {file ? file.name : "Click to select a PDF, or drag and drop"}
          </p>
          <input
            ref={fileRef}
            type="file"
            accept=".pdf"
            className="hidden"
            onChange={(e) => { const f = e.target.files?.[0]; if (f) { setFile(f); setTitle(f.name.replace(".pdf", "")); } }}
          />
        </div>

        <input className={inputCls} placeholder="Document title *" value={title} onChange={(e) => setTitle(e.target.value)} required />
        <input className={inputCls} placeholder="Act name (e.g. Indian Penal Code, 1860)" value={actName} onChange={(e) => setActName(e.target.value)} />

        <button
          type="submit"
          disabled={!file || !title || status === "loading"}
          className="flex items-center gap-2 px-5 py-2 bg-blue-600 hover:bg-blue-500 disabled:opacity-40 rounded-lg text-sm font-medium text-white transition-colors"
        >
          <Upload className="w-4 h-4" /> Upload & Index
        </button>
        <Banner />
      </form>
    );
  }

  return (
    <form onSubmit={handleScrape} className="space-y-4">
      <div className="flex items-center gap-2 text-sm text-gray-400 bg-gray-800/60 rounded-lg px-3 py-2">
        <Globe className="w-4 h-4 text-blue-400 flex-shrink-0" />
        Paste any publicly accessible legal page (e.g. IndiaCode, LII)
      </div>

      <input className={inputCls} placeholder="Page URL *" value={url} onChange={(e) => setUrl(e.target.value)} required type="url" />
      <input className={inputCls} placeholder="Act name *  (e.g. Consumer Protection Act, 2019)" value={scrAct} onChange={(e) => setScrAct(e.target.value)} required />
      <input className={inputCls} placeholder="Title (optional — defaults to act name)" value={scrTitle} onChange={(e) => setScrTitle(e.target.value)} />

      <button
        type="submit"
        disabled={!url || !scrAct || status === "loading"}
        className="flex items-center gap-2 px-5 py-2 bg-teal-600 hover:bg-teal-500 disabled:opacity-40 rounded-lg text-sm font-medium text-white transition-colors"
      >
        <Globe className="w-4 h-4" /> Scrape & Index
      </button>
      <Banner />
    </form>
  );
}
