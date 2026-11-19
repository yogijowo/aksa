import React from "react";
import {
  FileSpreadsheet,
  FileText,
  FileCode,
  ExternalLink,
  FolderOpen,
  FolderCheck,
  CheckCircle2,
  ShieldCheck,
  X,
} from "lucide-react";
import { toast } from "sonner";
import { useAksaStore } from "@/stores/useAksaStore";
import { formatNumberID } from "@/lib/utils";
import { openFileInDefaultApp } from "@/services/engineClient";
import type { FileArtifact } from "@/types/aksa";

function getFileIcon(type: FileArtifact["file_type"]) {
  switch (type) {
    case "xlsx":
      return <FileSpreadsheet size={17} className="text-emerald-400" />;
    case "docx":
    case "pdf":
      return <FileText size={17} className="text-sky-400" />;
    default:
      return <FileCode size={17} className="text-zinc-300" />;
  }
}

export function getParentFolderPath(filePath: string): string {
  const idx = Math.max(filePath.lastIndexOf("/"), filePath.lastIndexOf("\\"));
  return idx > 0 ? filePath.slice(0, idx) : filePath;
}

export const ArtifactDrawer: React.FC = () => {
  const {
    isArtifactDrawerOpen,
    setArtifactDrawerOpen,
    artifacts,
    workspaces,
    activeWorkspaceId,
    totalTokensUsed,
    totalTokensSaved,
  } = useAksaStore();

  if (!isArtifactDrawerOpen) return null;

  const activeWorkspace = workspaces.find((w) => w.id === activeWorkspaceId) ?? workspaces[0];

  const handleOpenFile = async (art: FileArtifact) => {
    const ok = await openFileInDefaultApp(art.file_path);
    if (!ok) {
      toast.error(
        `Tidak dapat membuka "${art.name}". Pastikan file masih berada di dalam folder ruang kerja Anda.`
      );
    }
  };

  const handleOpenLocation = async (art: FileArtifact) => {
    const dir = getParentFolderPath(art.file_path);
    const ok = await openFileInDefaultApp(dir);
    if (!ok) {
      toast.error(
        `Tidak dapat membuka lokasi folder "${dir}". Pastikan folder ruang kerja terdaftar dan diizinkan.`
      );
    }
  };

  return (
    <aside
      aria-label="Panel Hasil Pekerjaan"
      className="w-[320px] border-l border-white/[0.06] bg-[#141413] flex flex-col justify-between shrink-0 select-none"
    >
      <div className="p-4 space-y-4 overflow-y-auto">
        {/* Drawer Header */}
        <div className="flex items-center justify-between pb-2.5 border-b border-white/[0.06]">
          <div>
            <h3 className="text-[14px] font-semibold text-zinc-100">Hasil Pekerjaan &amp; File</h3>
            <p className="text-xs text-zinc-400">File yang telah dibuat di Ruang Kerja Anda</p>
          </div>
          <button
            type="button"
            onClick={() => setArtifactDrawerOpen(false)}
            aria-label="Tutup panel hasil pekerjaan"
            className="rounded-lg p-1.5 text-zinc-400 hover:bg-white/[0.06] hover:text-zinc-100 transition-colors"
          >
            <X size={15} />
          </button>
        </div>

        {/* Active Folder Info */}
        <div className="rounded-xl bg-[#1C1C1A] border border-white/[0.07] p-3.5 space-y-2">
          <div className="flex items-center gap-2 text-[13px] font-medium text-zinc-200">
            <FolderCheck size={14} className="text-emerald-400 shrink-0" />
            <span className="truncate">
              {activeWorkspace ? activeWorkspace.name : "Ruang Kerja Lokal"}
            </span>
          </div>
          {activeWorkspace?.folder_path && (
            <p className="text-xs font-mono text-zinc-400 break-all">
              {activeWorkspace.folder_path}
            </p>
          )}
          <div className="flex flex-wrap gap-1.5 pt-0.5">
            <span className="inline-flex items-center gap-1 rounded-md bg-white/[0.04] px-2 py-0.5 text-xs text-zinc-300 border border-white/[0.07]">
              <CheckCircle2 size={11} className="text-emerald-400" />
              Izin Baca &amp; Simpan
            </span>
            <span className="inline-flex items-center gap-1 rounded-md bg-white/[0.04] px-2 py-0.5 text-xs text-zinc-300 border border-white/[0.07]">
              <ShieldCheck size={11} className="text-[#D97757]" />
              Area Kerja Terlindungi
            </span>
          </div>
        </div>

        {/* File Artifact Cards */}
        <div className="space-y-2.5">
          {artifacts.length > 0 ? (
            artifacts.map((art) => (
              <div
                key={art.id}
                className="rounded-xl bg-[#1C1C1A] hover:bg-[#222220] border border-white/[0.07] p-3.5 space-y-2.5 transition-colors"
              >
                <div className="flex items-start gap-2.5">
                  <div className="mt-0.5 rounded-lg bg-white/[0.04] p-2 border border-white/[0.06]">
                    {getFileIcon(art.file_type)}
                  </div>
                  <div className="min-w-0 flex-1">
                    <div
                      className="text-[13px] font-semibold text-zinc-100 truncate"
                      title={art.name}
                    >
                      {art.name}
                    </div>
                    <div className="text-xs text-zinc-400 mt-0.5">
                      {art.size_label} · Dibuat oleh {art.created_by_agent}
                    </div>
                  </div>
                </div>

                <p className="text-xs text-zinc-300 leading-relaxed">{art.summary}</p>

                <div className="flex items-center gap-1.5 pt-1">
                  <button
                    type="button"
                    onClick={() => void handleOpenFile(art)}
                    className="flex-1 flex items-center justify-center gap-1.5 rounded-lg bg-[#D97757] hover:bg-[#c96a4b] px-2.5 py-1.5 text-xs font-semibold text-white transition-colors"
                    title={`Buka ${art.name}`}
                  >
                    <ExternalLink size={12} />
                    Buka Hasil
                  </button>
                  <button
                    type="button"
                    onClick={() => void handleOpenLocation(art)}
                    className="flex items-center justify-center gap-1 rounded-lg bg-white/[0.05] hover:bg-white/[0.1] border border-white/[0.08] px-2.5 py-1.5 text-xs font-medium text-zinc-200 transition-colors"
                    title="Buka folder tempat file ini disimpan"
                  >
                    <FolderOpen size={12} />
                    Buka Lokasi
                  </button>
                </div>
              </div>
            ))
          ) : (
            <div className="rounded-xl bg-[#1C1C1A]/60 border border-dashed border-white/[0.08] p-6 text-center space-y-1.5">
              <p className="text-[13px] font-medium text-zinc-200">Belum ada file hasil pekerjaan</p>
              <p className="text-xs text-zinc-400 leading-relaxed">
                Setiap laporan Word, tabel Excel, presentasi, atau PDF yang dibuat oleh AKSA akan
                muncul di sini agar mudah Anda buka.
              </p>
            </div>
          )}
        </div>
      </div>

      {/* Bottom Summary */}
      <div className="p-3.5 border-t border-white/[0.05] bg-[#141413] text-xs text-zinc-400 space-y-1">
        <div className="flex justify-between">
          <span>Pemakaian Kuota Utama</span>
          <span className="text-zinc-200 font-mono">{formatNumberID(totalTokensUsed)}</span>
        </div>
        <div className="flex justify-between">
          <span>Kuota Dihemat AKSA</span>
          <span className="text-emerald-400 font-mono">+{formatNumberID(totalTokensSaved)}</span>
        </div>
      </div>
    </aside>
  );
};
