import React, { useState } from "react";
import {
  FolderOpen,
  Plus,
  Check,
  PanelRightOpen,
  PanelRightClose,
  ChevronDown,
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
    <header className="relative h-12 border-b border-white/[0.05] bg-[#191918]/90 backdrop-blur-md px-5 flex items-center justify-between shrink-0 z-20">
      {/* Left: Clean Breadcrumb Context (Folder & Team) */}
      <div className="flex items-center gap-2">
        <div className="relative">
          <button
            onClick={() => setIsFolderMenuOpen((v) => !v)}
            className="flex items-center gap-2 rounded-lg hover:bg-white/[0.05] px-2.5 py-1.5 text-xs text-zinc-300 transition-colors"
          >
            <FolderOpen size={14} className="text-zinc-400 shrink-0" />
            <span className="font-medium text-zinc-200">{activeWorkspace?.name}</span>
            <span className="hidden md:inline text-[11px] text-zinc-500 font-mono">
              ({activeWorkspace?.folder_path})
            </span>
            <ChevronDown size={13} className="text-zinc-500" />
          </button>

          {isFolderMenuOpen && (
            <div className="absolute left-0 mt-1.5 w-88 rounded-xl bg-[#21211F] border border-white/[0.09] shadow-2xl p-3 space-y-2.5 z-50">
              <div className="flex items-center justify-between px-1">
                <span className="text-[11px] font-medium text-zinc-400">
                  Folder Kerja PC Diizinkan
                </span>
                <span className="text-[10px] text-emerald-400/90">Sandbox Aktif</span>
              </div>

              <div className="space-y-1 max-h-48 overflow-y-auto">
                {workspaces.map((ws) => (
                  <button
                    key={ws.id}
                    onClick={() => {
                      setActiveWorkspace(ws.id);
                      setIsFolderMenuOpen(false);
                    }}
                    className={cn(
                      "w-full flex items-center justify-between rounded-lg px-2.5 py-2 text-left text-xs transition-colors",
                      ws.id === activeWorkspaceId
                        ? "bg-white/[0.07] text-zinc-100"
                        : "hover:bg-white/[0.04] text-zinc-300"
                    )}
                  >
                    <div className="truncate pr-2">
                      <div className="font-medium truncate">{ws.name}</div>
                      <div className="text-[10px] text-zinc-500 font-mono truncate">
                        {ws.folder_path}
                      </div>
                    </div>
                    {ws.id === activeWorkspaceId && (
                      <Check size={13} className="text-[#D97757] shrink-0" />
                    )}
                  </button>
                ))}
              </div>

              <form
                onSubmit={handleAddCustomFolder}
                className="pt-2 border-t border-white/[0.06] space-y-1.5"
              >
                <div className="flex gap-1.5">
                  <input
                    type="text"
                    value={customPathInput}
                    onChange={(e) => setCustomPathInput(e.target.value)}
                    placeholder="Tambah path folder PC..."
                    className="flex-1 rounded-lg bg-[#141413] border border-white/[0.08] px-2.5 py-1.5 text-xs text-zinc-200 placeholder:text-zinc-500 focus:outline-none focus:border-white/[0.2]"
                  />
                  <button
                    type="submit"
                    className="flex items-center gap-1 rounded-lg bg-[#D97757] hover:bg-[#c96a4b] px-2.5 py-1.5 text-xs font-medium text-white transition-colors"
                  >
                    <Plus size={13} /> Tambah
                  </button>
                </div>
              </form>
            </div>
          )}
        </div>

        <span className="text-zinc-700">•</span>

        <button
          onClick={() => setActiveNav("tim_agen")}
          className="hidden sm:flex items-center gap-1.5 rounded-lg hover:bg-white/[0.05] px-2.5 py-1.5 text-xs text-zinc-400 hover:text-zinc-200 transition-colors"
        >
          <span>{activeTeam?.name}</span>
          <span className="text-[11px] text-zinc-500">({activeTeam?.agents.length} agen)</span>
        </button>
      </div>

      {/* Right: Minimal Status & Claude-style Artifacts Toggle */}
      <div className="flex items-center gap-2">
        <button
          onClick={() => setActiveNav("telegram")}
          className="flex items-center gap-1.5 rounded-lg hover:bg-white/[0.05] px-2.5 py-1.5 text-xs text-zinc-400 hover:text-zinc-200 transition-colors"
        >
          <span className="h-1.5 w-1.5 rounded-full bg-emerald-400" />
          <span className="hidden sm:inline">Telegram</span>
        </button>

        <button
          onClick={() => setArtifactDrawerOpen(!isArtifactDrawerOpen)}
          title="Buka/Tutup Panel Artefak"
          className={cn(
            "flex items-center gap-1.5 rounded-lg border px-2.5 py-1.5 text-xs transition-colors",
            isArtifactDrawerOpen
              ? "bg-white/[0.08] text-zinc-100 border-white/[0.12]"
              : "bg-transparent text-zinc-400 border-white/[0.07] hover:bg-white/[0.04] hover:text-zinc-200"
          )}
        >
          {isArtifactDrawerOpen ? <PanelRightClose size={14} /> : <PanelRightOpen size={14} />}
          <span className="hidden sm:inline">Artefak</span>
          <span className="rounded bg-white/[0.08] px-1.5 py-0.2 text-[10px] text-zinc-300">
            {artifacts.length}
          </span>
        </button>
      </div>
    </header>
  );
};
