import React, { useState } from "react";
import {
  History,
  Plus,
  Trash2,
  X,
  MessageSquare,
  FileText,
  Calendar,
  ArrowRight,
  AlertCircle,
} from "lucide-react";
import { toast } from "sonner";
import { useAksaStore } from "@/stores/useAksaStore";
import type { ChatSessionItem } from "@/types/aksa";

export const ChatSessionHistoryDrawer: React.FC = () => {
  const {
    isSessionHistoryOpen,
    setSessionHistoryOpen,
    savedSessions,
    messages,
    switchChatSession,
    deleteChatSession,
    startNewChatSession,
    isExecuting,
  } = useAksaStore();

  const [confirmDeleteId, setConfirmDeleteId] = useState<string | null>(null);

  if (!isSessionHistoryOpen) return null;

  const handleSwitchSession = async (session: ChatSessionItem) => {
    if (isExecuting) {
      toast.warning("Mohon tunggu tugas yang sedang berjalan selesai terlebih dahulu.");
      return;
    }
    await switchChatSession(session.id);
    toast.success(`Beralih ke sesi "${session.title}".`);
  };

  const handleDeleteSession = async (sessionId: string, e: React.MouseEvent) => {
    e.stopPropagation();
    await deleteChatSession(sessionId);
    setConfirmDeleteId(null);
    toast.success("Sesi percakapan berhasil dihapus dari basis data.");
  };

  const handleStartNewSession = async () => {
    if (isExecuting) {
      toast.warning("Mohon tunggu tugas yang sedang berjalan selesai terlebih dahulu.");
      return;
    }
    await startNewChatSession();
    toast.success("Sesi percakapan baru telah dimulai.");
  };

  return (
    <aside
      aria-label="Panel Riwayat Sesi Percakapan"
      className="w-[336px] border-l border-white/[0.06] bg-[#141413] flex flex-col justify-between shrink-0 select-none h-full overflow-hidden z-10 animate-in slide-in-from-right duration-200"
    >
      {/* Drawer Header */}
      <div className="p-4 flex items-center justify-between border-b border-white/[0.06] shrink-0">
        <div className="flex items-center gap-2.5 min-w-0">
          <div className="flex h-8 w-8 items-center justify-center rounded-xl bg-[#D97757]/15 text-[#D97757] shrink-0">
            <History size={16} />
          </div>
          <div className="min-w-0">
            <h3 className="text-[14.5px] font-semibold text-zinc-100 truncate">
              Riwayat Sesi
            </h3>
            <p className="text-xs text-zinc-400 truncate">
              {savedSessions.length} sesi tersimpan di basis data
            </p>
          </div>
        </div>

        <button
          type="button"
          onClick={() => setSessionHistoryOpen(false)}
          aria-label="Tutup panel riwayat sesi"
          className="rounded-lg p-1.5 text-zinc-400 hover:bg-white/[0.06] hover:text-zinc-100 transition-colors shrink-0"
        >
          <X size={16} />
        </button>
      </div>

      {/* Drawer Content */}
      <div className="p-4 space-y-4 overflow-y-auto flex-1">
        {/* Prominent Action Button: Mulai Sesi Baru */}
        <button
          type="button"
          onClick={() => void handleStartNewSession()}
          disabled={isExecuting}
          className="w-full flex items-center justify-center gap-2 rounded-xl bg-[#262624] hover:bg-[#D97757] hover:text-white border border-white/[0.08] text-zinc-200 py-2.5 px-3.5 text-xs font-semibold transition-all shadow-sm active:scale-98 group disabled:opacity-50"
        >
          <Plus size={14} className="text-[#D97757] group-hover:text-white transition-colors" />
          <span>Mulai Sesi Baru</span>
        </button>

        {/* Active Session Indicator (Rendered only when messages exist) */}
        {messages.length > 0 && (
          <div className="rounded-xl border border-emerald-500/25 bg-emerald-500/10 p-3 space-y-1.5">
            <div className="flex items-center justify-between">
              <span className="inline-flex items-center gap-1.5 text-xs font-semibold text-emerald-400">
                <span className="h-2 w-2 rounded-full bg-emerald-400 animate-pulse" />
                Sesi Aktif
              </span>
              <span className="text-[11px] text-zinc-400 font-mono">
                {messages.length} pesan
              </span>
            </div>
            <p className="text-xs text-zinc-300 line-clamp-2 leading-relaxed">
              {messages[0]?.content || "Sesi sedang berlangsung"}
            </p>
          </div>
        )}

        {/* Saved Sessions Section */}
        {savedSessions.length > 0 ? (
          <div className="space-y-2.5">
            <div className="text-[11px] font-semibold text-zinc-400 uppercase tracking-wider px-1">
              Sesi Lampau ({savedSessions.length})
            </div>

            <div className="space-y-2">
              {savedSessions.map((session) => {
                const isDeleting = confirmDeleteId === session.id;

                return (
                  <div
                    key={session.id}
                    onClick={() => void handleSwitchSession(session)}
                    className="group relative rounded-xl bg-[#21211F] hover:bg-[#262624] border border-white/[0.06] hover:border-[#D97757]/40 p-3.5 transition-all cursor-pointer shadow-sm space-y-2"
                  >
                    {/* Date and Badges */}
                    <div className="flex items-center justify-between gap-2 text-xs">
                      <div className="flex items-center gap-1.5 text-zinc-400">
                        <Calendar size={12} className="text-zinc-500 shrink-0" />
                        <span className="truncate">{session.formatted_date}</span>
                      </div>

                      <div className="flex items-center gap-1.5 shrink-0">
                        <span className="inline-flex items-center gap-1 rounded bg-white/[0.06] px-1.5 py-0.5 text-[11px] font-mono text-zinc-300">
                          <MessageSquare size={10} />
                          {session.message_count}
                        </span>
                        {session.artifact_count > 0 && (
                          <span className="inline-flex items-center gap-1 rounded bg-emerald-500/15 border border-emerald-500/30 px-1.5 py-0.5 text-[11px] font-mono text-emerald-300">
                            <FileText size={10} />
                            {session.artifact_count}
                          </span>
                        )}
                      </div>
                    </div>

                    {/* Title / Snippet */}
                    <p className="text-[13px] font-medium text-zinc-200 group-hover:text-white line-clamp-2 leading-relaxed">
                      {session.title}
                    </p>

                    {/* Footer Actions / Inline Delete Confirmation */}
                    {isDeleting ? (
                      <div
                        onClick={(e) => e.stopPropagation()}
                        className="pt-2 border-t border-white/[0.06] flex items-center justify-between gap-2"
                      >
                        <span className="text-[11px] text-rose-400 font-medium flex items-center gap-1">
                          <AlertCircle size={12} /> Hapus sesi?
                        </span>
                        <div className="flex items-center gap-1.5">
                          <button
                            type="button"
                            onClick={(e) => {
                              e.stopPropagation();
                              setConfirmDeleteId(null);
                            }}
                            className="rounded-lg px-2 py-0.5 text-[11px] text-zinc-400 hover:text-zinc-200 bg-white/[0.04] transition-colors"
                          >
                            Batal
                          </button>
                          <button
                            type="button"
                            onClick={(e) => void handleDeleteSession(session.id, e)}
                            className="rounded-lg px-2 py-0.5 text-[11px] font-semibold text-rose-200 bg-rose-500/30 hover:bg-rose-500/40 border border-rose-500/40 transition-colors"
                          >
                            Hapus
                          </button>
                        </div>
                      </div>
                    ) : (
                      <div className="pt-2 border-t border-white/[0.06] flex items-center justify-between text-xs">
                        <span className="inline-flex items-center gap-1 text-[#D97757] font-medium opacity-80 group-hover:opacity-100">
                          <span>Buka sesi</span>
                          <ArrowRight size={12} className="group-hover:translate-x-0.5 transition-transform" />
                        </span>

                        <button
                          type="button"
                          onClick={(e) => {
                            e.stopPropagation();
                            setConfirmDeleteId(session.id);
                          }}
                          title="Hapus sesi ini dari basis data"
                          className="opacity-0 group-hover:opacity-100 p-1 text-zinc-400 hover:text-rose-400 transition-all rounded hover:bg-white/[0.06]"
                        >
                          <Trash2 size={13} />
                        </button>
                      </div>
                    )}
                  </div>
                );
              })}
            </div>
          </div>
        ) : (
          <div className="flex-1 flex flex-col items-center justify-center text-center py-16 px-4 space-y-3">
            <div className="flex h-12 w-12 items-center justify-center rounded-2xl bg-white/[0.04] border border-white/[0.06] text-zinc-400">
              <History size={22} className="text-[#D97757]" />
            </div>
            <div className="space-y-1">
              <h4 className="text-[13.5px] font-semibold text-zinc-200">
                Belum Ada Riwayat Sesi
              </h4>
              <p className="text-xs text-zinc-400 leading-relaxed max-w-[220px]">
                Sesi percakapan Anda akan tersimpan otomatis di sini saat Anda memulai sesi baru.
              </p>
            </div>
          </div>
        )}
      </div>
    </aside>
  );
};
