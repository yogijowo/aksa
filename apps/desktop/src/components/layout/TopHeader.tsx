import React, { useState } from "react";
import {
  FolderOpen,
  Plus,
  Check,
  PanelRightOpen,
  PanelRightClose,
  ChevronDown,
  ShieldCheck,
} from "lucide-react";
import { useAksaStore } from "@/stores/useAksaStore";
import { cn } from "@/lib/utils";

export const TopHeader: React.FC = () => {
  const {
    workspaces,
    activeWorkspaceId,
    setActiveWorkspace,
    addWorkspaceFolder,
    teams,
    activeTeamId,
    isArtifactDrawerOpen,
    setArtifactDrawerOpen,
    artifacts,
    setActiveNav,
  } = useAksaStore();

  const [isFolderMenuOpen, setIsFolderMenuOpen] = useState(false);
  const [customPathInput, setCustomPathInput] = useState("");

  const activeWorkspace = workspaces.find((w) => w.id === activeWorkspaceId) ?? workspaces[0];
  const activeTeam = teams.find((t) => t.id === activeTeamId) ?? teams[0];

  const handleAddCustomFolder = (e: React.FormEvent) => {
    e.preventDefault();
    if (!customPathInput.trim()) return;
    addWorkspaceFolder(customPathInput.trim());
    setCustomPathInput("");
    setIsFolderMenuOpen(false);
  };

  return (
    <header className="relative h-13 border-b border-white/[0.06] bg-[#191918]/95 backdrop-blur-md px-5 flex items-center justify-between shrink-0 z-20">
      {/* Left: Workspace & Team Context */}
      <div className="flex items-center gap-2">
        <div className="relative">
          <button
            type="button"
            onClick={() => setIsFolderMenuOpen((v) => !v)}
            aria-expanded={isFolderMenuOpen}
            className="flex items-center gap-2 rounded-xl hover:bg-white/[0.06] px-3 py-1.5 text-[13px] text-zinc-200 transition-colors focus:outline-none focus:ring-2 focus:ring-[#D97757]/40"
          >
            <FolderOpen size={15} className="text-[#D97757] shrink-0" />
            <span className="font-medium text-zinc-100">
              {activeWorkspace ? activeWorkspace.name : "Pilih Folder Ruang Kerja"}
            </span>
            {activeWorkspace?.folder_path && (
              <span className="hidden md:inline text-xs text-zinc-400 font-mono truncate max-w-[240px]">
                ({activeWorkspace.folder_path})
              </span>
            )}
            <ChevronDown size={14} className="text-zinc-400" />
          </button>

          {isFolderMenuOpen && (
            <div className="absolute left-0 mt-1.5 w-96 rounded-2xl bg-[#21211F] border border-white/[0.1] shadow-2xl p-3.5 space-y-3 z-50">
              <div className="flex items-center justify-between px-1">
                <span className="text-xs font-semibold text-zinc-200">
                  Folder Ruang Kerja yang Diizinkan
                </span>
                <span className="inline-flex items-center gap-1 text-xs text-emerald-300 font-medium">
                  <ShieldCheck size={13} className="text-emerald-400" />
                  Area Kerja Terlindungi
                </span>
              </div>

              <div className="space-y-1 max-h-52 overflow-y-auto">
                {workspaces.length > 0 ? (
                  workspaces.map((ws) => (
                    <button
                      type="button"
                      key={ws.id}
                      onClick={() => {
                        setActiveWorkspace(ws.id);
                        setIsFolderMenuOpen(false);
                      }}
                      className={cn(
                        "w-full flex items-center justify-between rounded-xl px-3 py-2 text-left text-[13px] transition-colors",
                        ws.id === activeWorkspaceId
                          ? "bg-white/[0.08] text-zinc-100"
                          : "hover:bg-white/[0.04] text-zinc-300"
                      )}
                    >
                      <div className="truncate pr-2">
                        <div className="font-medium truncate">{ws.name}</div>
                        <div className="text-xs text-zinc-400 font-mono truncate">
                          {ws.folder_path}
                        </div>
                      </div>
                      {ws.id === activeWorkspaceId && (
                        <Check size={14} className="text-[#D97757] shrink-0" />
                      )}
                    </button>
                  ))
                ) : (
                  <p className="px-2 py-3 text-xs text-zinc-400 text-center">
                    Belum ada folder kerja yang dipilih. Tambahkan lokasi folder di bawah ini.
                  </p>
                )}
              </div>

              <form
                onSubmit={handleAddCustomFolder}
                className="pt-2.5 border-t border-white/[0.07] space-y-2"
              >
                <label className="block text-xs text-zinc-300 px-0.5">
                  Tambahkan folder kerja baru di komputer Anda:
                </label>
                <div className="flex gap-1.5">
                  <input
                    type="text"
                    value={customPathInput}
                    onChange={(e) => setCustomPathInput(e.target.value)}
                    placeholder="Contoh: /Users/nama/Documents/Laporan"
                    aria-label="Lokasi folder kerja baru"
                    className="flex-1 rounded-xl bg-[#141413] border border-white/[0.1] px-3 py-1.5 text-xs text-zinc-100 placeholder:text-zinc-500 focus:outline-none focus:border-[#D97757]"
                  />
                  <button
                    type="submit"
                    disabled={!customPathInput.trim()}
                    className="flex items-center gap-1 rounded-xl bg-[#D97757] hover:bg-[#c96a4b] disabled:opacity-40 px-3 py-1.5 text-xs font-semibold text-white transition-colors"
                  >
                    <Plus size={14} /> Tambah
                  </button>
                </div>
              </form>
            </div>
          )}
        </div>

        <span className="text-zinc-700" aria-hidden="true">
          •
        </span>

        <button
          type="button"
          onClick={() => setActiveNav("tim_agen")}
          className="hidden sm:flex items-center gap-1.5 rounded-xl hover:bg-white/[0.06] px-3 py-1.5 text-[13px] text-zinc-300 hover:text-zinc-100 transition-colors focus:outline-none focus:ring-2 focus:ring-[#D97757]/40"
        >
          <span>{activeTeam?.name}</span>
          <span className="text-xs text-zinc-400">({activeTeam?.agents.length} agen)</span>
        </button>
      </div>

      {/* Right: Integration Status & Work Results Drawer Toggle */}
      <div className="flex items-center gap-2">
        <button
          type="button"
          onClick={() => setActiveNav("telegram")}
          className="flex items-center gap-1.5 rounded-xl hover:bg-white/[0.06] px-3 py-1.5 text-[13px] text-zinc-300 hover:text-zinc-100 transition-colors focus:outline-none focus:ring-2 focus:ring-[#D97757]/40"
        >
          <span className="h-2 w-2 rounded-full bg-emerald-400" />
          <span className="hidden sm:inline">Integrasi</span>
        </button>

        <button
          type="button"
          onClick={() => setArtifactDrawerOpen(!isArtifactDrawerOpen)}
          title="Buka atau tutup daftar file hasil pekerjaan"
          aria-expanded={isArtifactDrawerOpen}
          className={cn(
            "flex items-center gap-1.5 rounded-xl border px-3 py-1.5 text-[13px] font-medium transition-colors focus:outline-none focus:ring-2 focus:ring-[#D97757]/40",
            isArtifactDrawerOpen
              ? "bg-white/[0.09] text-zinc-100 border-white/[0.14]"
              : "bg-transparent text-zinc-300 border-white/[0.08] hover:bg-white/[0.05] hover:text-zinc-100"
          )}
        >
          {isArtifactDrawerOpen ? <PanelRightClose size={15} /> : <PanelRightOpen size={15} />}
          <span className="hidden sm:inline">Hasil Pekerjaan</span>
          <span className="rounded-md bg-white/[0.1] px-1.5 py-0.5 text-xs text-zinc-200">
            {artifacts.length}
          </span>
        </button>
      </div>
    </header>
  );
};
