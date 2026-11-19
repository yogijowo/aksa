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
  Trash2,
  ShieldCheck,
  Users,
  ChevronDown,
  ChevronRight,
} from "lucide-react";
import { toast } from "sonner";
import { useAksaStore } from "@/stores/useAksaStore";
import {
  fetchRAGDocuments,
  deleteRAGDocumentRemote,
  indexWorkspaceFolderRemote,
  searchRAGRemote,
  fetchMemoriesRemote,
  saveMemoryRemote,
  openNativeFolderPicker,
  inspectWorkspacePathRemote,
} from "@/services/engineClient";
import { extractFolderDisplayName } from "@/lib/utils";
import {
  ConfirmDialog,
  PageHeader,
  SectionHeader,
  StatusBadge,
  EmptyStateCard,
  ErrorStateCard,
} from "@/components/ui/UXPrimitives";

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
  const { workspaces, activeWorkspaceId, addWorkspaceFolder, teams, activeTeamId } = useAksaStore();
  const [documents, setDocuments] = useState<RAGDocumentRow[]>([]);
  const [docPendingDelete, setDocPendingDelete] = useState<RAGDocumentRow | null>(null);
  const [isReindexing, setIsReindexing] = useState(false);
  const [isSearching, setIsSearching] = useState(false);
  const [searchQuery, setSearchQuery] = useState("");
  const [searchHits, setSearchHits] = useState<RAGSearchHit[]>([]);
  const [hasSearched, setHasSearched] = useState(false);
  const [memories, setMemories] = useState<Array<{ id: string; category: string; fact: string }>>(
    []
  );
  const [newFact, setNewFact] = useState("");
  const [actionNotice, setActionNotice] = useState<string | null>(null);
  const [processingError, setProcessingError] = useState<string | null>(null);
  const [showTechnicalDetails, setShowTechnicalDetails] = useState(false);

  const activeWorkspace = workspaces.find((w) => w.id === activeWorkspaceId) ?? workspaces[0];
  const activeTeam = teams.find((t) => t.id === activeTeamId) ?? teams[0];
  const agentsWithAccess = (activeTeam?.agents ?? [])
    .filter((a) => a.tool_categories.includes("rag_search"))
    .map((a) => a.name);

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
      // Fall back to empty state
    }
  };

  useEffect(() => {
    void loadData();
  }, [activeWorkspace?.id]);

  const handleManualReindex = async () => {
    if (!activeWorkspace) {
      setProcessingError(
        "Belum ada folder Ruang Kerja yang dipilih. Pilih folder di bagian atas layar terlebih dahulu."
      );
      return;
    }
    setIsReindexing(true);
    setActionNotice(null);
    setProcessingError(null);
    try {
      const res = await indexWorkspaceFolderRemote(
        activeWorkspace.id,
        activeWorkspace.folder_path
      );
      if (res && res.indexed_files !== undefined) {
        setActionNotice(
          `Berhasil memproses ${res.indexed_files} dokumen referensi (${res.total_chunks} bagian siap dicari).`
        );
      } else {
        setProcessingError(
          "Gagal memproses dokumen di folder kerja. Pastikan file tidak rusak dan layanan AKSA aktif."
        );
      }
      await loadData();
    } catch (err: any) {
      setProcessingError(
        err?.message || "Gagal memproses dokumen. Pastikan layanan AKSA sedang berjalan."
      );
    } finally {
      setIsReindexing(false);
    }
  };

  const handleConfirmRemoveDocument = async () => {
    if (!docPendingDelete) return;
    const target = docPendingDelete;
    setDocPendingDelete(null);
    await deleteRAGDocumentRemote(target.id);
    setDocuments((prev) => prev.filter((d) => d.id !== target.id));
    toast.success(
      `Data indeks untuk "${target.file_name}" dihapus dari Pengetahuan AKSA. File asli di folder Anda tetap utuh.`
    );
  };

  const handleConnectKnowledgeFolder = async () => {
    const picked = await openNativeFolderPicker({
      title: "Hubungkan Folder Pengetahuan AKSA",
      defaultPath: activeWorkspace?.folder_path,
    });
    if (!picked) return;
    const inspection = await inspectWorkspacePathRemote(picked);
    if (inspection && !inspection.is_valid_directory) {
      toast.error(inspection.recovery_hint || "Folder tidak dapat diakses.");
      return;
    }
    const folderName = inspection?.name || extractFolderDisplayName(picked);
    const createdWs = await addWorkspaceFolder(picked, folderName, {
      allow_read: true,
      allow_write: inspection ? inspection.writable : true,
      allow_execute: false,
    });
    toast.success(`Folder "${createdWs.name}" berhasil dihubungkan.`);
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
      toast.success("Catatan referensi berhasil disimpan.");
    } catch {
      setMemories((prev) => [
        { id: `mem_${Date.now()}`, category: "preferensi_pengguna", fact: factText },
        ...prev,
      ]);
    }
  };

  return (
    <div className="flex-1 p-6 md:p-8 overflow-y-auto space-y-6 bg-[#191918]">
      {/* Accurate explanation of removing index data vs source file (Section 8.F) */}
      <ConfirmDialog
        open={docPendingDelete !== null}
        title={`Hapus "${docPendingDelete?.file_name ?? ""}" dari indeks pengetahuan?`}
        description="Tindakan ini akan menghapus data indeks pencarian untuk dokumen ini dari Pengetahuan AKSA."
        impactNote="Perbedaan penghapusan: Menghapus dari Pengetahuan AKSA hanya menghapus data indeks pencarian internal agar AKSA tidak lagi mengutip dokumen ini. File dokumen asli di dalam folder komputer Anda TIDAK akan dihapus."
        confirmLabel="Hapus Data Indeks"
        cancelLabel="Batal"
        destructive
        onCancel={() => setDocPendingDelete(null)}
        onConfirm={() => void handleConfirmRemoveDocument()}
      />

      <div className="max-w-6xl mx-auto space-y-6">
        {/* Page Header (Section 8.F Pengetahuan: Tambahkan dokumen & Hubungkan folder) */}
        <PageHeader
          icon={<BookOpenCheck size={22} className="text-[#D97757]" />}
          title="Pengetahuan AKSA"
          description="Kelola sumber dokumen yang terhubung dan lihat bagaimana AKSA mengindeksnya sebagai referensi saat menjawab pertanyaan atau menyusun laporan Anda."
          actions={
            <>
              <button
                type="button"
                onClick={() => void handleConnectKnowledgeFolder()}
                className="rounded-xl bg-[#262624] hover:bg-zinc-700 border border-white/[0.1] px-3.5 py-2 text-[13px] font-medium text-zinc-100 flex items-center gap-2 transition-colors"
              >
                <FolderSync size={14} className="text-[#D97757]" />
                <span>Hubungkan folder</span>
              </button>
              <button
                type="button"
                onClick={() => void handleManualReindex()}
                disabled={isReindexing}
                className="rounded-xl bg-[#D97757] hover:bg-[#c96a4b] px-4 py-2 text-[13px] font-semibold text-white flex items-center gap-2 transition-colors disabled:opacity-50"
              >
                <Plus size={15} />
                <span>{isReindexing ? "Memproses Indeks..." : "Tambahkan dokumen"}</span>
              </button>
            </>
          }
        />

        {/* Clear Security & Access Boundary Explanation (Section 5.7) */}
        <div className="rounded-2xl bg-[#21211F] border border-white/[0.08] p-4 flex flex-col sm:flex-row sm:items-center justify-between gap-3 text-[13px]">
          <div className="flex items-start gap-2.5 text-zinc-300">
            <ShieldCheck size={18} className="text-emerald-400 shrink-0 mt-0.5" />
            <p className="leading-relaxed">
              Menambahkan dokumen ke Pengetahuan AKSA{" "}
              <strong>tidak otomatis memberikan seluruh agen akses tanpa batas</strong>. Hanya agen
              yang memiliki izin <em>Pencarian dalam Dokumen</em> yang dapat membaca referensi ini.
            </p>
          </div>
          <div className="shrink-0 flex items-center gap-2 text-xs text-zinc-300 bg-[#262624] border border-white/[0.07] rounded-xl px-3 py-2">
            <Users size={14} className="text-[#D97757]" />
            <span>
              Agen yang dapat mengakses:{" "}
              <strong>
                {agentsWithAccess.length > 0 ? agentsWithAccess.join(", ") : "Belum ada agen"}
              </strong>
            </span>
          </div>
        </div>

        {actionNotice && (
          <div className="rounded-xl bg-emerald-500/10 border border-emerald-500/30 px-4 py-3 text-[13px] text-emerald-200 flex items-center gap-2">
            <CheckCircle2 size={16} className="text-emerald-400 shrink-0" />
            <span>{actionNotice}</span>
          </div>
        )}

        {processingError && (
          <ErrorStateCard
            title="Pemrosesan dokumen belum berhasil"
            cause={processingError}
            nextStep="Pastikan folder ruang kerja sudah dipilih dan berisi file PDF, Word, Excel, atau teks yang valid."
            onRetry={() => void handleManualReindex()}
            onDismiss={() => setProcessingError(null)}
          />
        )}

        {/* Document List & Processing/Index Status (Section 5.7) */}
        <div className="rounded-2xl bg-[#21211F] border border-white/[0.08] p-5 md:p-6 space-y-4">
          <SectionHeader
            title={`Daftar Dokumen Referensi (${documents.length})`}
            description={`Sumber folder: ${activeWorkspace?.name || "Ruang Kerja"} (${activeWorkspace?.folder_path || "Belum dipilih"})`}
            rightElement={
              <button
                type="button"
                onClick={() => setShowTechnicalDetails((v) => !v)}
                className="inline-flex items-center gap-1 text-xs text-zinc-400 hover:text-zinc-200"
              >
                {showTechnicalDetails ? <ChevronDown size={13} /> : <ChevronRight size={13} />}
                <span>Detail teknis</span>
              </button>
            }
          />

          <div className="space-y-2.5">
            {documents.length > 0 ? (
              documents.map((doc) => (
                <div
                  key={doc.id}
                  className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 rounded-xl bg-[#262624] border border-white/[0.07] px-4 py-3"
                >
                  <div className="space-y-1">
                    <div className="flex items-center gap-2 flex-wrap">
                      <FileText size={15} className="text-[#D97757]" />
                      <span className="text-[14px] font-semibold text-zinc-100">
                        {doc.file_name}
                      </span>
                      <StatusBadge tone="success" label="Siap digunakan (Terindeks)" />
                    </div>
                    <div className="text-xs text-zinc-300">
                      Status pemrosesan: Selesai ({doc.chunk_count} bagian bacaan) • Diakses oleh:{" "}
                      {agentsWithAccess.length > 0
                        ? agentsWithAccess.join(", ")
                        : "Peneliti Dokumen"}
                    </div>
                    {showTechnicalDetails && (
                      <div className="text-[11px] font-mono text-zinc-400">
                        Sidik jari SHA-256: {doc.sha256_short} • Waktu indeks: {doc.indexed_at}
                      </div>
                    )}
                  </div>

                  <div className="flex items-center gap-2 shrink-0">
                    <button
                      type="button"
                      onClick={() => setDocPendingDelete(doc)}
                      className="rounded-xl bg-rose-500/15 hover:bg-rose-500/25 border border-rose-500/30 px-3 py-1.5 text-xs font-medium text-rose-300 flex items-center gap-1.5 transition-colors"
                      title="Hapus data indeks dokumen ini dari Pengetahuan AKSA (file asli tetap aman)"
                    >
                      <Trash2 size={13} />
                      <span>Hapus dari Indeks</span>
                    </button>
                  </div>
                </div>
              ))
            ) : (
              <EmptyStateCard
                icon={<Inbox size={22} />}
                title="Belum ada dokumen di Pengetahuan AKSA"
                description={`Folder kerja aktif (${activeWorkspace?.name || "Ruang Kerja"}) belum dipindai. Tambahkan atau pindai dokumen PDF, Word, Excel, dan PowerPoint agar AKSA dapat menjadikannya referensi.`}
                actionLabel={isReindexing ? "Memproses Dokumen..." : "Tambah & Pindai Dokumen Sekarang"}
                onAction={() => void handleManualReindex()}
              />
            )}
          </div>
        </div>

        {/* Search inside Knowledge Base */}
        <div className="rounded-2xl bg-[#21211F] border border-white/[0.08] p-5 md:p-6 space-y-4">
          <SectionHeader
            icon={<Search size={17} className="text-[#D97757]" />}
            title="Cari Informasi di Dalam Dokumen"
            description="Coba cari nomor surat, isi perjanjian, atau data tabel dari dokumen yang sudah terdaftar."
          />

          <div className="flex gap-2">
            <input
              type="text"
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              onKeyDown={(e) => e.key === "Enter" && void handleSearch()}
              aria-label="Cari isi dokumen"
              placeholder="Ketik kata kunci atau kalimat yang ingin dicari..."
              className="flex-1 rounded-xl bg-[#262624] border border-white/[0.09] px-3.5 py-2.5 text-[13.5px] text-zinc-100 focus:outline-none focus:border-[#D97757]"
            />
            <button
              type="button"
              onClick={() => void handleSearch()}
              disabled={isSearching || !searchQuery.trim()}
              className="rounded-xl bg-[#D97757] hover:bg-[#c96a4b] px-4 py-2.5 text-[13px] font-semibold text-white transition-colors disabled:opacity-50 flex items-center gap-1.5"
            >
              {isSearching ? <RefreshCw size={14} className="animate-spin" /> : null}
              <span>Cari di Dokumen</span>
            </button>
          </div>

          <div className="space-y-2.5">
            {searchHits.length > 0 ? (
              searchHits.map((hit) => (
                <div
                  key={hit.chunk_id}
                  className="rounded-xl bg-[#262624] border border-white/[0.07] p-4 space-y-2"
                >
                  <div className="flex items-center justify-between gap-2">
                    <div className="text-[13.5px] font-semibold text-zinc-100 flex items-center gap-2">
                      <FileText size={14} className="text-[#D97757]" />
                      <span>{hit.file_name}</span>
                      {hit.section_title && (
                        <span className="text-xs text-zinc-400">• {hit.section_title}</span>
                      )}
                    </div>
                    {showTechnicalDetails && (
                      <span className="text-[11px] font-mono text-zinc-400">
                        Skor: {typeof hit.rrf_score === "number" ? hit.rrf_score.toFixed(4) : hit.rrf_score}
                      </span>
                    )}
                  </div>
                  <p className="text-[13px] text-zinc-200 whitespace-pre-wrap bg-[#191918] rounded-xl p-3 border border-white/[0.05] leading-relaxed">
                    {hit.content}
                  </p>
                </div>
              ))
            ) : hasSearched ? (
              <div className="rounded-xl bg-[#262624] border border-white/[0.06] p-4 text-center text-[13px] text-zinc-300">
                Tidak ditemukan kutipan dokumen yang cocok dengan pencarian tersebut.
              </div>
            ) : null}
          </div>
        </div>

        {/* Saved User Preferences & Reference Facts */}
        <div className="rounded-2xl bg-[#21211F] border border-white/[0.08] p-5 md:p-6 space-y-4">
          <SectionHeader
            icon={<Brain size={17} className="text-amber-400" />}
            title="Catatan & Preferensi Kerja Anda"
            description="Simpan aturan atau kebiasaan kerja yang ingin selalu diingat AKSA (misalnya: selalu gunakan Bahasa Indonesia formal dan format Rupiah)."
          />

          <div className="flex gap-2">
            <input
              type="text"
              value={newFact}
              onChange={(e) => setNewFact(e.target.value)}
              onKeyDown={(e) => e.key === "Enter" && void handleAddMemory()}
              aria-label="Tambah catatan preferensi kerja"
              placeholder="Contoh: Selalu gunakan format Rupiah (Rp) dan huruf Calibri pada laporan..."
              className="flex-1 rounded-xl bg-[#262624] border border-white/[0.09] px-3.5 py-2.5 text-[13.5px] text-zinc-100 focus:outline-none focus:border-[#D97757]"
            />
            <button
              type="button"
              onClick={() => void handleAddMemory()}
              disabled={!newFact.trim()}
              className="rounded-xl bg-amber-500/20 hover:bg-amber-500/30 border border-amber-500/40 px-4 py-2.5 text-[13px] font-semibold text-amber-200 flex items-center gap-1.5 transition-colors disabled:opacity-50"
            >
              <Plus size={15} /> Simpan Catatan
            </button>
          </div>

          <div className="space-y-2">
            {memories.length > 0 ? (
              memories.map((m) => (
                <div
                  key={m.id}
                  className="rounded-xl bg-[#262624] border border-white/[0.06] px-4 py-3 flex items-center justify-between gap-3"
                >
                  <span className="text-[13.5px] text-zinc-100">{m.fact}</span>
                  <span className="shrink-0 rounded-md bg-amber-500/15 px-2.5 py-0.5 text-xs text-amber-300">
                    Preferensi Anda
                  </span>
                </div>
              ))
            ) : (
              <div className="rounded-xl bg-[#262624]/40 border border-dashed border-white/[0.07] p-4 text-center text-[13px] text-zinc-400">
                Belum ada catatan preferensi yang disimpan.
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
};
