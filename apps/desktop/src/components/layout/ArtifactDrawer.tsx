import React from "react";
import {
  FileSpreadsheet,
  FileText,
  FileCode,
  ExternalLink,
  Send,
  FolderCheck,
  CheckCircle2,
  ShieldCheck,
  X,
} from "lucide-react";
import { useAksaStore } from "@/stores/useAksaStore";
import { formatNumberID } from "@/lib/utils";
import { openFileInDefaultApp } from "@/services/engineClient";
import type { FileArtifact } from "@/types/aksa";

function getFileIcon(type: FileArtifact["file_type"]) {
  switch (type) {
    case "xlsx":
      return <FileSpreadsheet size={16} className="text-emerald-400/90" />;
    case "docx":
    case "pdf":
      return <FileText size={16} className="text-sky-400/90" />;
    default:
      return <FileCode size={16} className="text-zinc-400" />;
  }
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

  return (
    <aside className="w-[300px] border-l border-white/[0.06] bg-[#141413] flex flex-col justify-between shrink-0 select-none">
      <div className="p-4 space-y-4 overflow-y-auto">
        {/* Drawer Header */}
        <div className="flex items-center justify-between pb-2 border-b border-white/[0.05]">
          <div>
            <h3 className="text-xs font-medium text-zinc-200">Artefak & Dokumen</h3>
            <p className="text-[11px] text-zinc-500">Tersimpan di Folder Kerja PC</p>
          </div>
          <button
            onClick={() => setArtifactDrawerOpen(false)}
            className="rounded-lg p-1 text-zinc-500 hover:bg-white/[0.05] hover:text-zinc-200 transition-colors"
          >
            <X size={14} />
          </button>
        </div>

        {/* Active Folder Sandbox Info */}
        <div className="rounded-xl bg-[#1C1C1A] border border-white/[0.06] p-3 space-y-2">
          <div className="flex items-center gap-1.5 text-xs font-medium text-zinc-300">
            <FolderCheck size={13} className="text-emerald-400/90 shrink-0" />
            <span className="truncate">{activeWorkspace?.name}</span>
          </div>
          <p className="text-[10.5px] font-mono text-zinc-500 break-all">
            {activeWorkspace?.folder_path}
          </p>
          <div className="flex flex-wrap gap-1.5 pt-0.5">
            <span className="inline-flex items-center gap-1 rounded bg-white/[0.04] px-1.5 py-0.5 text-[10px] text-zinc-400 border border-white/[0.06]">
              <CheckCircle2 size={10} className="text-emerald-400/90" />
              Baca & Tulis
            </span>
            <span className="inline-flex items-center gap-1 rounded bg-white/[0.04] px-1.5 py-0.5 text-[10px] text-zinc-400 border border-white/[0.06]">
              <ShieldCheck size={10} className="text-zinc-400" />
              Auto-Backup
            </span>
          </div>
        </div>

        {/* File Artifact Cards */}
        <div className="space-y-2">
          {artifacts.map((art) => (
            <div
              key={art.id}
              className="rounded-xl bg-[#1C1C1A] hover:bg-[#222220] border border-white/[0.06] p-3 space-y-2.5 transition-colors"
            >
              <div className="flex items-start gap-2.5">
                <div className="mt-0.5 rounded-lg bg-white/[0.03] p-2 border border-white/[0.05]">
                  {getFileIcon(art.file_type)}
                </div>
                <div className="min-w-0 flex-1">
                  <div className="text-xs font-medium text-zinc-200 truncate" title={art.name}>
                    {art.name}
                  </div>
                  <div className="text-[10.5px] text-zinc-500 mt-0.5">
                    {art.size_label} · {art.created_by_agent}
                  </div>
                </div>
              </div>

              <p className="text-[11px] text-zinc-400 leading-relaxed">{art.summary}</p>

              <div className="flex items-center gap-1.5 pt-0.5">
                <button
                  onClick={async () => {
                    const ok = await openFileInDefaultApp(art.file_path);
                    if (!ok) {
                      alert(`Gagal membuka berkas:\n${art.file_path}\nPastikan berkas tersedia di folder kerja PC Anda.`);
                    }
                  }}
                  className="flex-1 flex items-center justify-center gap-1.5 rounded-lg bg-white/[0.06] hover:bg-[#D97757] hover:text-white border border-white/[0.07] px-2.5 py-1.5 text-[11px] font-medium text-zinc-200 transition-colors"
                  title={`Buka ${art.name} di aplikasi PC`}
                >
                  <ExternalLink size={11} />
                  Buka File
                </button>
                <button
                  onClick={() =>
                    alert(`Mengirim file ${art.name} langsung ke chat Telegram Anda...`)
                  }
                  className="flex items-center justify-center gap-1 rounded-lg bg-transparent hover:bg-white/[0.05] border border-white/[0.07] px-2.5 py-1.5 text-[11px] text-zinc-400 hover:text-zinc-200 transition-colors"
                  title="Kirim file ini ke Telegram"
                >
                  <Send size={11} />
                  Telegram
                </button>
              </div>
            </div>
          ))}
        </div>
      </div>

      {/* Quiet Bottom Token Summary */}
      <div className="p-3.5 border-t border-white/[0.05] bg-[#141413] text-[11px] text-zinc-500 space-y-1">
        <div className="flex justify-between">
          <span>Token Manajer Utama</span>
          <span className="text-zinc-300 font-mono">{formatNumberID(totalTokensUsed)}</span>
        </div>
        <div className="flex justify-between">
          <span>Token Dihemat (Isolasi)</span>
          <span className="text-emerald-400/90 font-mono">+{formatNumberID(totalTokensSaved)}</span>
        </div>
      </div>
    </aside>
  );
};
