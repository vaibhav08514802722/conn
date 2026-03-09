"use client";
/**
 * Phase 6 — Documents Management Page
 * Upload PDFs, scrape URLs, list and delete documents.
 */

import { useState, useEffect } from "react";
import { useRouter } from "next/navigation";
import { useAuth } from "@/lib/auth";
import { documentsAPI, DocumentMeta } from "@/lib/api";
import Navbar from "@/components/Navbar";
import DocumentUploader from "@/components/DocumentUploader";
import { FileText, Globe, Trash2, CheckCircle, Clock, XCircle, Loader } from "lucide-react";

const STATUS_ICON: Record<string, React.ReactNode> = {
  complete:   <CheckCircle className="w-4 h-4 text-green-400" />,
  processing: <Loader className="w-4 h-4 text-yellow-400 animate-spin" />,
  pending:    <Clock className="w-4 h-4 text-gray-400" />,
  failed:     <XCircle className="w-4 h-4 text-red-400" />,
};

export default function DocumentsPage() {
  const { token, loading } = useAuth();
  const router = useRouter();

  const [docs,    setDocs]    = useState<DocumentMeta[]>([]);
  const [stats,   setStats]   = useState<{ vectors_count: number; points_count: number } | null>(null);
  const [tab,     setTab]     = useState<"upload" | "scrape">("upload");
  const [deleting, setDeleting] = useState<string | null>(null);

  useEffect(() => {
    if (!loading && !token) router.push("/login");
  }, [loading, token, router]);

  const refresh = async () => {
    if (!token) return;
    const [d, s] = await Promise.all([
      documentsAPI.list(token),
      documentsAPI.stats(token).catch(() => null),
    ]);
    setDocs(d);
    setStats(s);
  };

  useEffect(() => { if (token) refresh(); }, [token]);

  const handleDelete = async (id: string) => {
    if (!token || !confirm("Delete this document and all its vectors?")) return;
    setDeleting(id);
    try {
      await documentsAPI.delete(id, token);
      await refresh();
    } finally {
      setDeleting(null);
    }
  };

  return (
    <div className="min-h-screen bg-gray-950 flex flex-col">
      <Navbar />

      <main className="flex-1 max-w-5xl mx-auto w-full px-4 py-8">

        {/* Header */}
        <div className="mb-8">
          <h1 className="text-2xl font-bold text-white">Knowledge Base</h1>
          <p className="text-gray-400 mt-1">Upload PDFs or scrape legal pages to expand LexBot&apos;s knowledge.</p>
          {stats && (
            <div className="mt-3 inline-flex gap-4 text-sm text-gray-400">
              <span>{stats.points_count} chunks indexed</span>
              <span className="text-gray-700">|</span>
              <span>{docs.length} documents</span>
            </div>
          )}
        </div>

        {/* Add document panel */}
        <div className="bg-gray-900 border border-gray-800 rounded-2xl p-6 mb-8">
          {/* Tabs */}
          <div className="flex gap-2 mb-6">
            {(["upload", "scrape"] as const).map((t) => (
              <button
                key={t}
                onClick={() => setTab(t)}
                className={`flex items-center gap-2 px-4 py-2 rounded-lg text-sm font-medium transition-colors ${
                  tab === t
                    ? "bg-blue-600 text-white"
                    : "bg-gray-800 text-gray-400 hover:text-white"
                }`}
              >
                {t === "upload" ? <FileText className="w-4 h-4" /> : <Globe className="w-4 h-4" />}
                {t === "upload" ? "Upload PDF" : "Scrape URL"}
              </button>
            ))}
          </div>

          <DocumentUploader tab={tab} token={token!} onSuccess={refresh} />
        </div>

        {/* Documents table */}
        <div className="bg-gray-900 border border-gray-800 rounded-2xl overflow-hidden">
          <div className="px-6 py-4 border-b border-gray-800">
            <h2 className="font-semibold text-white">Indexed Documents</h2>
          </div>

          {docs.length === 0 ? (
            <div className="px-6 py-12 text-center text-gray-500">
              No documents yet. Upload a PDF or scrape a legal page to get started.
            </div>
          ) : (
            <table className="w-full text-sm">
              <thead>
                <tr className="text-gray-500 text-left border-b border-gray-800">
                  <th className="px-6 py-3 font-medium">Document</th>
                  <th className="px-6 py-3 font-medium">Type</th>
                  <th className="px-6 py-3 font-medium">Chunks</th>
                  <th className="px-6 py-3 font-medium">Status</th>
                  <th className="px-6 py-3 font-medium">Added</th>
                  <th className="px-6 py-3 font-medium"></th>
                </tr>
              </thead>
              <tbody>
                {docs.map((doc) => (
                  <tr key={doc.id} className="border-b border-gray-800 hover:bg-gray-800/50">
                    <td className="px-6 py-3">
                      <div className="font-medium text-white">{doc.title}</div>
                      {doc.act_name && <div className="text-gray-500 text-xs">{doc.act_name}</div>}
                    </td>
                    <td className="px-6 py-3">
                      <span className={`inline-flex items-center gap-1 px-2 py-0.5 rounded text-xs ${
                        doc.source_type === "pdf"
                          ? "bg-purple-900/40 text-purple-300"
                          : "bg-teal-900/40 text-teal-300"
                      }`}>
                        {doc.source_type === "pdf" ? <FileText className="w-3 h-3" /> : <Globe className="w-3 h-3" />}
                        {doc.source_type}
                      </span>
                    </td>
                    <td className="px-6 py-3 text-gray-300">{doc.chunk_count}</td>
                    <td className="px-6 py-3">
                      <span className="flex items-center gap-1.5 text-gray-300">
                        {STATUS_ICON[doc.status] ?? <Clock className="w-4 h-4" />}
                        {doc.status}
                      </span>
                    </td>
                    <td className="px-6 py-3 text-gray-500">
                      {new Date(doc.uploaded_at).toLocaleDateString()}
                    </td>
                    <td className="px-6 py-3">
                      <button
                        onClick={() => handleDelete(doc.id)}
                        disabled={deleting === doc.id}
                        className="p-1.5 text-gray-500 hover:text-red-400 disabled:opacity-40 transition-colors"
                      >
                        <Trash2 className="w-4 h-4" />
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </div>
      </main>
    </div>
  );
}
