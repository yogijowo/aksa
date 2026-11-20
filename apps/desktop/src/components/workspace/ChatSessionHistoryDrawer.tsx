import React, { useState } from "react";
import {
  History,
  Plus,
  Trash2,
  X,
  MessageSquare,
  FileCheck2,
  Calendar,
  ArrowRight,
  AlertCircle,
  Database,
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
  } = useAksaStore();

  const [confirmDeleteId, setConfirmDeleteId] = useState<string | null>(null);

  if (!isSessionHistoryOpen) return null;

  const handleSwitchSession = async (session: ChatSessionItem) => {
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
    await startNewChatSession();
    toast.success("Sesi percakapan baru telah dimulai.");
  };

  return (
    <aside
      aria-label="Riwayat Sesi Percakapan"
      className="w-[360px] border-l border-white/[0.08] bg-[#1C1C1A] flex flex-col h-full overflow-hidden shrink-0 z-10 animate-in slide-in-from-right duration-200"
    >
      {/* Header */}
      <div className="p-4 border-b border-white/[0.08] flex items-center justify-between shrink-0 bg-[#21211F]/70">
        <div className="flex items-center gap-2.5">
          <div className="flex h-8 w-8 items-center justify-center rounded-xl bg-[#D97757]/15 text-[#D97757]">
            <History size={16} />
          </div>
          <div>
            <h2 className="text-[14px] font-semibold text-zinc-100">Riwayat Sesi</h2>
            <p className="text-[11px] text-zinc-400">
              {savedSessions.length} sesi tersimpan di basis data
            </p>
          </div>
        </div>

        <div className="flex items-center gap-1">
          <button
            type="button"
            onClick={() => void handleStartNewSession()}
            title="Mulai sesi baru"
            className="flex items-center gap-1.5 rounded-lg bg-[#D97757] hover:bg-[#c96a4b] text-white px-2.5 py-1.5 text-xs font-semibold transition-colors shadow-sm"
          >
            <Plus size={13} />
            <span>Sesi Baru</span>
          </button>
          <button
            type="button"
            onClick={() => setSessionHistoryOpen(false)}
            title="Tutup riwayat sesi"
            className="rounded-lg p-1.5 text-zinc-400 hover:text-zinc-100 hover:bg-white/[0.06] transition-colors"
          >
            <X size={16} />
          </button>
        </div>
      </div>

      {/* Active Session Status Card */}
      <div className="p-3.5 border-b border-white/[0.06] bg-[#21211F]/40 shrink-0">
        <div className="rounded-xl border border-emerald-500/30 bg-emerald-500/10 p-3 space-y-1.5">
          <div className="flex items-center justify-between">
            <span className="inline-flex items-center gap-1.5 text-xs font-semibold text-emerald-400">
              <span className="h-2 w-2 rounded-full bg-emerald-400 animate-pulse" />
              Sesi Aktif Saat Ini
            </span>
            <span className="text-[11px] text-zinc-400 font-medium">
              {messages.length} pesan
            </span>
          </div>
          <p className="text-xs text-zinc-300 line-clamp-2">
            {messages.length > 0
              ? messages[0].content
              : "Belum ada pesan pada sesi ini. Ketik tugas pertama Anda di bawah."}
          </p>
        </div>
      </div>

      {/* Session List */}
      <div className="flex-1 overflow-y-auto p-3.5 space-y-2.5">
        {savedSessions.length === 0 ? (
          <div className="py-12 px-4 text-center space-y-3">
            <div className="mx-auto flex h-12 w-12 items-center justify-center rounded-2xl bg-white/[0.04] text-zinc-400">
              <Database size={22} />
            </div>
            <div className="space-y-1">
              <h3 className="text-[13.5px] font-semibold text-zinc-200">
                Belum Ada Riwayat Sesi
              </h3>
              <p className="text-xs text-zinc-400 leading-relaxed max-w-[240px] mx-auto">
                Setiap kali Anda menekan tombol Sesi Baru, percakapan Anda akan tersimpan otomatis di sini.
              </p>
            </div>
          </div>
        ) : (
          savedSessions.map((session) => {
            const isDeleting = confirmDeleteId === session.id;

            return (
              <div
                key={session.id}
                onClick={() => void handleSwitchSession(session)}
                className="group relative rounded-xl bg-[#21211F] hover:bg-[#262624] border border-white/[0.06] hover:border-[#D97757]/40 p-3.5 transition-all cursor-pointer shadow-sm space-y-2"
              >
                {/* Header row: date & badges */}
                <div className="flex items-center justify-between gap-2 text-xs">
                  <div className="flex items-center gap-1.5 text-zinc-400">
                    <Calendar size={12} className="text-zinc-500" />
                    <span>{session.formatted_date}</span>
                  </div>

                  <div className="flex items-center gap-1.5">
                    <span className="inline-flex items-center gap-1 rounded bg-white/[0.06] px-1.5 py-0.5 text-[11px] font-mono text-zinc-300">
                      <MessageSquare size={10} />
                      {session.message_count}
                    </span>
                    {session.artifact_count > 0 && (
                      <span className="inline-flex items-center gap-1 rounded bg-emerald-500/15 border border-emerald-500/30 px-1.5 py-0.5 text-[11px] font-mono text-emerald-300">
                        <FileCheck2 size={10} />
                        {session.artifact_count}
                      </span>
                    )}
                  </div>
                </div>

                {/* Session Snippet */}
                <p className="text-[13px] font-medium text-zinc-200 group-hover:text-white line-clamp-2 leading-snug">
                  {session.title}
                </p>

                {/* Footer action buttons / delete confirmation */}
                {isDeleting ? (
                  <div
                    onClick={(e) => e.stopPropagation()}
                    className="pt-2 border-t border-white/[0.06] flex items-center justify-between gap-2"
                  >
                    <span className="text-[11px] text-rose-400 font-medium flex items-center gap-1">
                      <AlertCircle size={12} /> Hapus sesi ini?
                    </span>
                    <div className="flex items-center gap-1">
                      <button
                        type="button"
                        onClick={(e) => {
                          e.stopPropagation();
                          setConfirmDeleteId(null);
                        }}
                        className="rounded px-2 py-0.5 text-[11px] text-zinc-400 hover:text-zinc-200 bg-white/[0.04]"
                      >
                        Batal
                      </button>
                      <button
                        type="button"
                        onClick={(e) => void handleDeleteSession(session.id, e)}
                        className="rounded px-2 py-0.5 text-[11px] font-semibold text-rose-200 bg-rose-500/30 hover:bg-rose-500/40 border border-rose-500/40"
                      >
                        Hapus
                      </button>
                    </div>
                  </div>
                ) : (
                  <div className="pt-2 border-t border-white/[0.06] flex items-center justify-between text-xs">
                    <span className="inline-flex items-center gap-1 text-[#D97757] font-medium opacity-80 group-hover:opacity-100">
                      <span>Buka Sesi</span>
                      <ArrowRight size={12} />
                    </span>

                    <button
                      type="button"
                      onClick={(e) => {
                        e.stopPropagation();
                        setConfirmDeleteId(session.id);
                      }}
                      title="Hapus sesi ini dari basis data"
                      className="opacity-0 group-hover:opacity-100 p-1 text-zinc-500 hover:text-rose-400 transition-all rounded hover:bg-white/[0.06]"
                    >
                      <Trash2 size={13} />
                    </button>
                  </div>
                )}
              </div>
            );
          })
        )}
      </div>
    </aside>
  );
};
