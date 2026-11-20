import React, { useState } from "react";
import {
  FolderOpen,
  FolderPlus,
  Check,
  PanelRightOpen,
  PanelRightClose,
  ChevronDown,
  ShieldCheck,
  ExternalLink,
  History,
} from "lucide-react";
import { toast } from "sonner";
import { useAksaStore } from "@/stores/useAksaStore";
import { cn, extractFolderDisplayName } from "@/lib/utils";
import {
  inspectWorkspacePathRemote,
  openFileInDefaultApp,
  openNativeFolderPicker,
} from "@/services/engineClient";

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
    isSessionHistoryOpen,
    setSessionHistoryOpen,
    savedSessions,
    artifacts,
    engineHealth,
    setActiveNav,
  } = useAksaStore();

  const [isFolderMenuOpen, setIsFolderMenuOpen] = useState(false);

  const activeWorkspace = workspaces.find((w) => w.id === activeWorkspaceId) ?? workspaces[0];
  const activeTeam = teams.find((t) => t.id === activeTeamId) ?? teams[0];

  const handlePickNativeWorkspaceFolder = async () => {
    const picked = await openNativeFolderPicker({
      title: "Pilih Folder Ruang Kerja AKSA",
      defaultPath: activeWorkspace?.folder_path,
    });
    if (!picked) {
      return;
    }
    const inspection = await inspectWorkspacePathRemote(picked);
    if (inspection && !inspection.is_valid_directory) {
      toast.error(inspection.recovery_hint || "Folder tidak dapat diakses.");
      return;
    }
    const folderName = inspection?.name || extractFolderDisplayName(picked);
    await addWorkspaceFolder(picked, folderName, {
      allow_read: true,
      allow_write: inspection ? inspection.writable : true,
      allow_execute: false,
    });
    setIsFolderMenuOpen(false);
    toast.success(`Folder "${folderName}" dipilih sebagai Ruang Kerja aktif.`);
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
            className="flex items-center gap-2 rounded-xl hover:bg-white/[0.06] px-3 py-1.5 text-[13px] text-zinc-200 transition-colors"
          >
            <FolderOpen size={15} className="text-[#D97757] shrink-0" />
            <span className="font-semibold text-zinc-100">
              {activeWorkspace ? activeWorkspace.name : "Pilih Folder Ruang Kerja"}
            </span>
            <ChevronDown size={14} className="text-zinc-400" />
          </button>

          {isFolderMenuOpen && (
            <div className="absolute left-0 mt-1.5 w-96 rounded-2xl bg-[#21211F] border border-white/[0.1] shadow-2xl p-3.5 space-y-3 z-50">
              <div className="flex items-center justify-between px-1">
                <span className="text-xs font-semibold text-zinc-200">
                  Folder Ruang Kerja Anda
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
                        <div className="font-semibold truncate">{ws.name}</div>
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
                    Belum ada folder kerja yang dipilih. Klik tombol Pilih folder… di bawah ini.
                  </p>
                )}
              </div>

              <div className="pt-2.5 border-t border-white/[0.07] flex items-center justify-between gap-2">
                <button
                  type="button"
                  onClick={() => void handlePickNativeWorkspaceFolder()}
                  className="flex-1 flex items-center justify-center gap-1.5 rounded-xl bg-[#D97757] hover:bg-[#c96a4b] px-3 py-2 text-xs font-semibold text-white transition-colors"
                >
                  <FolderPlus size={14} />
                  <span>Pilih folder…</span>
                </button>

                {activeWorkspace && (
                  <button
                    type="button"
                    onClick={() => {
                      void openFileInDefaultApp(activeWorkspace.folder_path);
                      setIsFolderMenuOpen(false);
                    }}
                    className="flex items-center justify-center gap-1.5 rounded-xl bg-[#262624] hover:bg-zinc-700 border border-white/[0.1] px-3 py-2 text-xs font-medium text-zinc-200 transition-colors"
                  >
                    <ExternalLink size={13} />
                    <span>Buka folder</span>
                  </button>
                )}
              </div>
            </div>
          )}
        </div>

        <span className="text-zinc-500" aria-hidden="true">
          •
        </span>

        <button
          type="button"
          onClick={() => setActiveNav("tim_agen")}
          className="hidden sm:flex items-center gap-1.5 rounded-xl hover:bg-white/[0.06] px-3 py-1.5 text-[13px] text-zinc-300 hover:text-zinc-100 transition-colors"
        >
          <span>{activeTeam?.name}</span>
          <span className="text-xs text-zinc-400">({activeTeam?.agents.length} agen)</span>
        </button>
      </div>

      {/* Right: Integration Status, Session History & Work Results Drawer Toggle */}
      <div className="flex items-center gap-2">
        <button
          type="button"
          onClick={() => setActiveNav("telegram")}
          className="flex items-center gap-1.5 rounded-xl hover:bg-white/[0.06] px-3 py-1.5 text-[13px] text-zinc-300 hover:text-zinc-100 transition-colors"
        >
          <span
            className={cn(
              "h-2 w-2 rounded-full",
              engineHealth.telegram_connected ? "bg-emerald-400" : "bg-zinc-500"
            )}
          />
          <span className="hidden sm:inline">Integrasi</span>
        </button>

        <button
          type="button"
          onClick={() => {
            if (!isSessionHistoryOpen && isArtifactDrawerOpen) {
              setArtifactDrawerOpen(false);
            }
            setSessionHistoryOpen(!isSessionHistoryOpen);
          }}
          title="Buka atau tutup riwayat sesi percakapan"
          aria-expanded={isSessionHistoryOpen}
          className={cn(
            "flex items-center gap-1.5 rounded-xl border px-3 py-1.5 text-[13px] font-medium transition-colors",
            isSessionHistoryOpen
              ? "bg-white/[0.09] text-zinc-100 border-[#D97757]/60 text-[#D97757]"
              : "bg-transparent text-zinc-300 border-white/[0.08] hover:bg-white/[0.05] hover:text-zinc-100"
          )}
        >
          <History size={15} />
          <span className="hidden sm:inline">Riwayat Sesi</span>
          {savedSessions.length > 0 && (
            <span className="rounded-md bg-white/[0.1] px-1.5 py-0.5 text-xs text-zinc-200">
              {savedSessions.length}
            </span>
          )}
        </button>

        <button
          type="button"
          onClick={() => {
            if (!isArtifactDrawerOpen && isSessionHistoryOpen) {
              setSessionHistoryOpen(false);
            }
            setArtifactDrawerOpen(!isArtifactDrawerOpen);
          }}
          title="Buka atau tutup daftar file hasil pekerjaan"
          aria-expanded={isArtifactDrawerOpen}
          className={cn(
            "flex items-center gap-1.5 rounded-xl border px-3 py-1.5 text-[13px] font-medium transition-colors",
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
