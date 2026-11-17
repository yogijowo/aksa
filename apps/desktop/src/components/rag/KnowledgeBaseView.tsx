import React, { useState, useEffect } from "react";
import {
  BookOpenCheck,
  FolderSync,
  Search,
  RefreshCw,
  FileText,
  Brain,
  Plus,
  CheckCircle2,
  Inbox,
} from "lucide-react";
import { useAksaStore } from "@/stores/useAksaStore";
import {
  fetchRAGDocuments,
  indexWorkspaceFolderRemote,
  searchRAGRemote,
  fetchMemoriesRemote,
  saveMemoryRemote,
} from "@/services/engineClient";

interface RAGDocumentRow {
  id: string;
  file_name: string;
  file_ext: string;
  chunk_count: number;
  sha256_short: string;
  indexed_at: string;
}

interface RAGSearchHit {
  chunk_id: string;
  file_name: string;
  section_title: string;
  content: string;
  rrf_score: number;
  vector_rank: number | null;
  fts5_rank: number | null;
}

export const KnowledgeBaseView: React.FC = () => {
  const { workspaces, activeWorkspaceId } = useAksaStore();
  const [documents, setDocuments] = useState<RAGDocumentRow[]>([]);
  const [isReindexing, setIsReindexing] = useState(false);
  const [isSearching, setIsSearching] = useState(false);
  const [searchQuery, setSearchQuery] = useState("");
  const [searchHits, setSearchHits] = useState<RAGSearchHit[]>([]);
  const [hasSearched, setHasSearched] = useState(false);
  const [memories, setMemories] = useState<Array<{ id: string; category: string; fact: string }>>([]);
  const [newFact, setNewFact] = useState("");
  const [actionNotice, setActionNotice] = useState<string | null>(null);

  const activeWorkspace = workspaces.find((w) => w.id === activeWorkspaceId) ?? workspaces[0];

  const loadData = async () => {
    try {
      const docs = await fetchRAGDocuments(activeWorkspace?.id);
      if (docs && Array.isArray(docs)) {
        setDocuments(docs);
      }

      const mems = await fetchMemoriesRemote();
      if (mems && Array.isArray(mems)) {
        setMemories(mems);
      }
    } catch {
      // Silently fall back to empty state
    }
  };

  useEffect(() => {
    void loadData();
  }, [activeWorkspace?.id]);

  const handleManualReindex = async () => {
    if (!activeWorkspace) return;
    setIsReindexing(true);
    setActionNotice(null);
    try {
      const res = await indexWorkspaceFolderRemote(
        activeWorkspace.id,
        activeWorkspace.folder_path
      );
      if (res && res.indexed_files !== undefined) {
        setActionNotice(
          `Berhasil mengindeks ${res.indexed_files} file (${res.total_chunks} potongan semantik).`
        );
      }
      await loadData();
    } catch {
      setActionNotice("Gagal mengindeks folder kerja. Pastikan backend engine berjalan.");
    } finally {
      setIsReindexing(false);
    }
  };

  const handleSearch = async () => {
    if (!searchQuery.trim()) return;
    setIsSearching(true);
    setHasSearched(true);
    try {
      const hits = await searchRAGRemote(searchQuery.trim(), activeWorkspace?.id);
      if (hits && Array.isArray(hits)) {
        setSearchHits(hits);
      } else {
        setSearchHits([]);
      }
    } catch {
      setSearchHits([]);
    } finally {
      setIsSearching(false);
    }
  };

  const handleAddMemory = async () => {
    if (!newFact.trim()) return;
    const factText = newFact.trim();
    setNewFact("");
    try {
      const saved = await saveMemoryRemote(factText, "preferensi_pengguna");
      if (saved) {
        setMemories((prev) => [saved, ...prev]);
      } else {
        setMemories((prev) => [
          { id: `mem_${Date.now()}`, category: "preferensi_pengguna", fact: factText },
          ...prev,
        ]);
      }
    } catch {
      setMemories((prev) => [
        { id: `mem_${Date.now()}`, category: "preferensi_pengguna", fact: factText },
        ...prev,
      ]);
    }
  };

  return (
    <div className="flex-1 p-6 md:p-8 overflow-y-auto space-y-6 bg-[#191918]">
      <div className="max-w-6xl mx-auto space-y-6">
        {/* Header */}
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
          <div>
            <h2 className="text-base font-semibold text-zinc-100 flex items-center gap-2">
              <BookOpenCheck size={18} className="text-[#D97757]" />
              Basis Pengetahuan Lokal (Hybrid RAG)
            </h2>
            <p className="text-xs text-zinc-400 mt-1">
              Pencarian Hibrida Reciprocal Rank Fusion (RRF) untuk pemahaman semantik sekaligus
              kecocokan persis nomor surat, klausul kontrak, dan tabel data.
            </p>
          </div>
          <div className="flex items-center gap-2">
            <button
              onClick={() => void handleManualReindex()}
              disabled={isReindexing}
              className="rounded-xl bg-[#D97757]/15 hover:bg-[#D97757]/25 border border-[#D97757]/40 px-3.5 py-2 text-xs font-medium text-[#D97757] flex items-center gap-1.5 transition-colors disabled:opacity-50"
            >
              <RefreshCw size={13} className={isReindexing ? "animate-spin" : ""} />
              {isReindexing ? "Memindai Folder..." : "Indeks Ulang Folder"}
            </button>
            <span className="rounded-xl bg-emerald-500/15 border border-emerald-500/30 px-3 py-2 text-xs font-medium text-emerald-300 flex items-center gap-1.5">
              <FolderSync size={14} /> Watchdog Aktif
            </span>
          </div>
        </div>

        {actionNotice && (
          <div className="rounded-xl bg-[#21211F] border border-white/[0.08] px-4 py-2.5 text-xs text-zinc-300 flex items-center gap-2">
            <CheckCircle2 size={14} className="text-emerald-400" />
            <span>{actionNotice}</span>
          </div>
        )}

        {/* Live Hybrid RAG Search Section */}
        <div className="rounded-2xl bg-[#21211F] border border-white/[0.08] p-5 space-y-4">
          <div className="flex items-center justify-between">
            <span className="text-xs font-semibold text-zinc-100 flex items-center gap-2">
              <Search size={14} className="text-[#D97757]" />
              Uji Pencarian Hibrida (Dense Vector + BM25 Keyword RRF)
            </span>
            <span className="text-[11px] text-emerald-400 font-mono">
              Hemat Token • Hanya Kutipan Relevan
            </span>
          </div>

          <div className="flex gap-2">
            <input
              type="text"
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              onKeyDown={(e) => e.key === "Enter" && void handleSearch()}
              placeholder="Cari nomor surat resmi, klausa dokumen, atau isi tabel..."
              className="flex-1 rounded-xl bg-[#262624] border border-white/[0.08] px-3.5 py-2 text-xs text-zinc-100 focus:outline-none focus:border-[#D97757]/60"
            />
            <button
              onClick={() => void handleSearch()}
              disabled={isSearching || !searchQuery.trim()}
              className="rounded-xl bg-[#D97757] hover:bg-[#c96a4b] px-4 py-2 text-xs font-medium text-white transition-colors disabled:opacity-50 flex items-center gap-1.5"
            >
              {isSearching ? <RefreshCw size={13} className="animate-spin" /> : null}
              Cari Kutipan
            </button>
          </div>

          <div className="space-y-2.5">
            {searchHits.length > 0 ? (
              searchHits.map((hit) => (
                <div
                  key={hit.chunk_id}
                  className="rounded-xl bg-[#262624] border border-white/[0.06] p-3.5 space-y-1.5"
                >
                  <div className="flex items-center justify-between gap-2">
                    <div className="text-xs font-semibold text-zinc-200 flex items-center gap-1.5">
                      <FileText size={13} className="text-zinc-400" />
                      {hit.file_name} • <span className="text-zinc-400">{hit.section_title}</span>
                    </div>
                    <div className="flex items-center gap-1.5 text-[10px] font-mono">
                      <span className="rounded bg-white/[0.06] px-2 py-0.5 text-zinc-200">
                        RRF: {typeof hit.rrf_score === "number" ? hit.rrf_score.toFixed(4) : hit.rrf_score}
                      </span>
                      <span className="rounded bg-emerald-500/15 px-2 py-0.5 text-emerald-300">
                        Vec #{hit.vector_rank ?? "-"} • FTS5 #{hit.fts5_rank ?? "-"}
                      </span>
                    </div>
                  </div>
                  <p className="text-xs text-zinc-300 font-mono whitespace-pre-wrap bg-[#21211F] rounded-lg p-2.5 border border-white/[0.04]">
                    {hit.content}
                  </p>
                </div>
              ))
            ) : hasSearched ? (
              <div className="rounded-xl bg-[#262624] border border-white/[0.06] p-4 text-center text-xs text-zinc-400">
                Tidak ada kutipan dokumen yang cocok dengan kata kunci tersebut. Coba gunakan kata kunci lain atau lakukan indeks ulang folder.
              </div>
            ) : (
              <div className="rounded-xl bg-[#262624]/50 border border-dashed border-white/[0.06] p-4 text-center text-xs text-zinc-500">
                Ketikkan kata kunci di atas untuk menguji pencarian semantik dan BM25 di seluruh dokumen kerja Anda.
              </div>
            )}
          </div>
        </div>

        {/* Indexed Documents Table */}
        <div className="rounded-2xl bg-[#21211F] border border-white/[0.08] p-5 space-y-3">
          <div className="flex items-center justify-between">
            <h3 className="text-xs font-semibold uppercase tracking-wider text-zinc-300">
              Dokumen Terindeks di Folder Kerja ({documents.length} Dokumen)
            </h3>
            <span className="text-[11px] text-zinc-400">Diff Inkremental SHA-256</span>
          </div>

          <div className="space-y-2">
            {documents.length > 0 ? (
              documents.map((doc) => (
                <div
                  key={doc.id}
                  className="flex items-center justify-between rounded-xl bg-[#262624] border border-white/[0.06] px-4 py-2.5"
                >
                  <div className="space-y-0.5">
                    <div className="text-xs font-semibold text-zinc-100">{doc.file_name}</div>
                    <div className="text-[11px] text-zinc-400 font-mono">
                      {doc.chunk_count} Potongan Semantik • SHA-256: {doc.sha256_short}
                    </div>
                  </div>
                  <span className="rounded-lg bg-emerald-500/15 px-2.5 py-1 text-[11px] text-emerald-300 border border-emerald-500/30 flex items-center gap-1">
                    <CheckCircle2 size={12} /> {doc.indexed_at}
                  </span>
                </div>
              ))
            ) : (
              /* Clean Empty State */
              <div className="rounded-xl bg-[#262624]/40 border border-dashed border-white/[0.08] p-8 text-center space-y-3">
                <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-white/[0.04] text-zinc-400 mx-auto">
                  <Inbox size={20} strokeWidth={1.8} />
                </div>
                <div className="space-y-1">
                  <p className="text-xs font-medium text-zinc-200">
                    Belum Ada Dokumen Terindeks
                  </p>
                  <p className="text-[11.5px] text-zinc-400 max-w-sm mx-auto leading-relaxed">
                    Folder kerja aktif ({activeWorkspace?.folder_path || activeWorkspace?.name}) belum dipindai.
                    Klik tombol di bawah untuk memindai file .pdf, .docx, .xlsx, .pptx, dan .md.
                  </p>
                </div>
                <button
                  onClick={() => void handleManualReindex()}
                  disabled={isReindexing}
                  className="inline-flex items-center gap-1.5 rounded-xl bg-[#D97757] hover:bg-[#c96a4b] px-4 py-2 text-xs font-medium text-white transition-colors disabled:opacity-50"
                >
                  <RefreshCw size={13} className={isReindexing ? "animate-spin" : ""} />
                  {isReindexing ? "Memindai Folder..." : "Indeks Folder Kerja Sekarang"}
                </button>
              </div>
            )}
          </div>
        </div>

        {/* Multi-Tier Agent Memory Manager */}
        <div className="rounded-2xl bg-[#21211F] border border-white/[0.08] p-5 space-y-3">
          <div className="flex items-center justify-between">
            <h3 className="text-xs font-semibold text-zinc-100 flex items-center gap-2">
              <Brain size={15} className="text-amber-400" />
              Memori Jangka Panjang Agen (`user_memories` &amp; `.aksa/MEMORY.md`)
            </h3>
            <span className="text-[11px] text-zinc-400">Diingat Lintas Sesi</span>
          </div>

          <div className="flex gap-2">
            <input
              type="text"
              value={newFact}
              onChange={(e) => setNewFact(e.target.value)}
              onKeyDown={(e) => e.key === "Enter" && void handleAddMemory()}
              placeholder="Tambahkan aturan tetap / fakta proyek (misal: Selalu gunakan format Rupiah Rp dan font Calibri)..."
              className="flex-1 rounded-xl bg-[#262624] border border-white/[0.08] px-3.5 py-2 text-xs text-zinc-100 focus:outline-none focus:border-[#D97757]/60"
            />
            <button
              onClick={() => void handleAddMemory()}
              disabled={!newFact.trim()}
              className="rounded-xl bg-amber-500/20 hover:bg-amber-500/30 border border-amber-500/40 px-3.5 py-2 text-xs font-medium text-amber-300 flex items-center gap-1.5 transition-colors disabled:opacity-50"
            >
              <Plus size={14} /> Simpan Memori
            </button>
          </div>

          <div className="space-y-2">
            {memories.length > 0 ? (
              memories.map((m) => (
                <div
                  key={m.id}
                  className="rounded-xl bg-[#262624] border border-white/[0.06] px-3.5 py-2.5 flex items-center justify-between gap-3"
                >
                  <span className="text-xs text-zinc-200">{m.fact}</span>
                  <span className="shrink-0 rounded-md bg-amber-500/15 px-2 py-0.5 text-[10px] font-mono text-amber-300">
                    {m.category}
                  </span>
                </div>
              ))
            ) : (
              <div className="rounded-xl bg-[#262624]/40 border border-dashed border-white/[0.06] p-4 text-center text-xs text-zinc-500">
                Belum ada memori jangka panjang tersimpan. Simpan preferensi format laporan atau aturan penulisan yang ingin selalu diingat oleh agen di setiap sesi.
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
};
