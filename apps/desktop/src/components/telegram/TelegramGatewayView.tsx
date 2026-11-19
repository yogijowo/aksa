import React, { useState, useEffect } from "react";
import {
  Send,
  Smartphone,
  RefreshCw,
  CheckCircle2,
  Activity,
  PlugZap,
  Link2,
  Unlink2,
  ChevronDown,
  ChevronRight,
  Lock,
} from "lucide-react";
import { toast } from "sonner";
import {
  fetchTelegramStatus,
  configureTelegramRemote,
  regenerateTelegramCodeRemote,
} from "@/services/engineClient";
import { useAksaStore } from "@/stores/useAksaStore";
import {
  PageHeader,
  SectionHeader,
  StatusBadge,
  ErrorStateCard,
} from "@/components/ui/UXPrimitives";

interface AuditEntry {
  id: string;
  time: string;
  type: "paired" | "voice_note" | "file_delivered" | "blocked" | "info";
  detail: string;
}

export const TelegramGatewayView: React.FC = () => {
  const { mcpServers, toggleMcpServer } = useAksaStore();
  const [botToken, setBotToken] = useState("");
  const [isConnected, setIsConnected] = useState(false);
  const [botUsername, setBotUsername] = useState("");
  const [pairingCode, setPairingCode] = useState("------");
  const [whitelistCount, setWhitelistCount] = useState(0);
  const [isSubmittingToken, setIsSubmittingToken] = useState(false);
  const [logs, setLogs] = useState<AuditEntry[]>([]);
  const [feedbackNotice, setFeedbackNotice] = useState<string | null>(null);
  const [connectionError, setConnectionError] = useState<string | null>(null);
  const [showTelegramSetup, setShowTelegramSetup] = useState(false);
  const [expandedServiceTech, setExpandedServiceTech] = useState<Record<string, boolean>>({});

  const refreshStatus = async () => {
    try {
      const status = await fetchTelegramStatus();
      if (status) {
        setIsConnected(status.connected ?? false);
        setBotUsername(status.bot_username ?? "");
        if (status.pairing_code) {
          setPairingCode(status.pairing_code);
        }
        if (Array.isArray(status.whitelist_user_ids)) {
          setWhitelistCount(status.whitelist_user_ids.length);
        }
        if (Array.isArray(status.audit_logs) && status.audit_logs.length > 0) {
          setLogs(
            status.audit_logs.map((item: any, idx: number) => ({
              id: item.id || `log_${idx}`,
              time: item.timestamp || "Baru saja",
              type: item.type || "info",
              detail: item.message || item.detail || JSON.stringify(item),
            }))
          );
        }
      }
    } catch {
      // Backend not running yet
    }
  };

  useEffect(() => {
    void refreshStatus();
  }, []);

  const handleConnectBot = async () => {
    if (!botToken.trim()) return;
    setIsSubmittingToken(true);
    setFeedbackNotice(null);
    setConnectionError(null);
    try {
      const res = await configureTelegramRemote(botToken.trim());
      if (res && res.connected) {
        setIsConnected(true);
        setBotUsername(res.bot_username || "@aksa_bot");
        setFeedbackNotice(
          `Telegram berhasil dihubungkan (${res.bot_username}). Token disimpan dengan aman di brankas terenkripsi.`
        );
        setBotToken("");
        setShowTelegramSetup(false);
      } else {
        setConnectionError(
          "Tidak dapat menghubungkan Telegram. Pastikan kode token bot yang Anda masukkan sudah benar."
        );
      }
    } catch (err: any) {
      setConnectionError(
        err?.message || "Terjadi kendala saat menghubungi layanan Telegram."
      );
    } finally {
      setIsSubmittingToken(false);
      void refreshStatus();
    }
  };

  const handleDisconnectTelegram = () => {
    setIsConnected(false);
    setBotUsername("");
    toast.success("Koneksi Telegram telah diputuskan.");
  };

  const handleRegenerateCode = async () => {
    try {
      const newCode = await regenerateTelegramCodeRemote();
      if (newCode) {
        setPairingCode(newCode);
      }
    } catch {
      toast.error("Gagal membuat kode pasangan baru.");
    }
  };

  return (
    <div className="flex-1 p-6 md:p-8 overflow-y-auto bg-[#191918]">
      <div className="max-w-6xl mx-auto space-y-6">
        {/* Page Header (Section 5.8 Integrasi) */}
        <PageHeader
          icon={<PlugZap size={22} className="text-[#D97757]" />}
          title="Integrasi & Koneksi Layanan"
          description="Hubungkan atau putuskan koneksi AKSA dengan layanan eksternal secara mudah. Seluruh kredensial disimpan di brankas keamanan perangkat."
        />

        {feedbackNotice && (
          <div className="rounded-xl bg-emerald-500/10 border border-emerald-500/30 px-4 py-3 text-[13px] text-emerald-200 flex items-center gap-2">
            <CheckCircle2 size={16} className="text-emerald-400 shrink-0" />
            <span>{feedbackNotice}</span>
          </div>
        )}

        {connectionError && (
          <ErrorStateCard
            title="Gagal menghubungkan layanan"
            cause={connectionError}
            nextStep="Periksa kembali pengaturan koneksi layanan Anda lalu coba kembali."
            onDismiss={() => setConnectionError(null)}
          />
        )}

        {/* Section 1: Main External Service Cards (Telegram + MCP Services) */}
        <div className="space-y-4">
          <SectionHeader
            title="Daftar Koneksi Layanan"
            description="Setiap layanan menampilkan fungsi, status koneksi, hak akses yang digunakan, serta tombol untuk menghubungkan atau memutuskan koneksi."
          />

          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            {/* Service Card 1: Telegram Remote Assistant */}
            <div className="rounded-2xl bg-[#21211F] border border-white/[0.08] p-5 flex flex-col justify-between space-y-4">
              <div className="space-y-3">
                <div className="flex items-start justify-between gap-3">
                  <div className="flex items-center gap-3">
                    <div className="rounded-xl bg-sky-500/15 border border-sky-500/30 p-2.5 text-sky-400">
                      <Send size={18} />
                    </div>
                    <div>
                      <h3 className="text-[15.5px] font-semibold text-zinc-100">
                        Pesan Jarak Jauh Telegram
                      </h3>
                      <span className="text-xs text-zinc-400">
                        {isConnected && botUsername
                          ? `Akun bot: ${botUsername}`
                          : "Kendali jarak jauh dari ponsel Anda"}
                      </span>
                    </div>
                  </div>

                  <StatusBadge
                    tone={isConnected ? "success" : "neutral"}
                    label={isConnected ? "Terhubung" : "Belum terhubung"}
                  />
                </div>

                <p className="text-[13px] text-zinc-300 leading-relaxed">
                  Mengirimkan instruksi pekerjaan dari ponsel melalui pesan teks atau suara, serta
                  menerima dokumen hasil kerja AKSA langsung di aplikasi Telegram Anda.
                </p>

                <div className="rounded-xl bg-[#262624] border border-white/[0.06] p-3 space-y-1.5 text-xs">
                  <div className="flex items-center justify-between gap-2">
                    <span className="text-zinc-400">Hak akses yang digunakan:</span>
                    <span className="text-zinc-200 font-medium">
                      Menerima instruksi &amp; mengirim file hasil kerja
                    </span>
                  </div>
                  <div className="flex items-center justify-between gap-2">
                    <span className="text-zinc-400">Perlindungan akses:</span>
                    <span className="text-emerald-300 flex items-center gap-1">
                      <Lock size={12} /> Hanya pengguna terverifikasi ({whitelistCount} akun)
                    </span>
                  </div>
                </div>
              </div>

              {/* Connect / Disconnect & Progressive Disclosure for Credential Setup */}
              <div className="space-y-3 pt-2 border-t border-white/[0.07]">
                <div className="flex items-center justify-between gap-2">
                  <button
                    type="button"
                    onClick={() => setShowTelegramSetup((v) => !v)}
                    className="rounded-xl bg-[#D97757] hover:bg-[#c96a4b] px-4 py-2 text-xs font-semibold text-white flex items-center gap-1.5 transition-colors"
                  >
                    <Link2 size={14} />
                    <span>{isConnected ? "Atur Koneksi Telegram" : "Hubungkan"}</span>
                  </button>

                  {isConnected && (
                    <button
                      type="button"
                      onClick={handleDisconnectTelegram}
                      className="rounded-xl bg-rose-500/15 hover:bg-rose-500/25 border border-rose-500/30 px-3.5 py-2 text-xs font-semibold text-rose-300 flex items-center gap-1.5 transition-colors"
                    >
                      <Unlink2 size={14} />
                      <span>Putuskan Koneksi</span>
                    </button>
                  )}
                </div>

                {showTelegramSetup && (
                  <div className="rounded-xl bg-[#191918] border border-white/[0.08] p-4 space-y-3">
                    <div className="space-y-1">
                      <label
                        htmlFor="aksa-telegram-token-input"
                        className="block text-xs font-semibold text-zinc-200"
                      >
                        Kredensial Koneksi Bot Telegram (Disimpan Terenkripsi)
                      </label>
                      <p className="text-xs text-zinc-400">
                        Masukkan token bot dari @BotFather. Token tidak pernah ditampilkan kembali
                        setelah disimpan.
                      </p>
                    </div>

                    <div className="flex gap-2">
                      <input
                        id="aksa-telegram-token-input"
                        type="password"
                        value={botToken}
                        onChange={(e) => setBotToken(e.target.value)}
                        placeholder="Tempel token bot Telegram Anda..."
                        className="flex-1 rounded-xl bg-[#262624] border border-white/[0.09] px-3 py-2 text-xs text-zinc-100 focus:outline-none focus:border-[#D97757]"
                      />
                      <button
                        type="button"
                        onClick={() => void handleConnectBot()}
                        disabled={isSubmittingToken || !botToken.trim()}
                        className="rounded-xl bg-[#D97757] hover:bg-[#c96a4b] px-3.5 py-2 text-xs font-semibold text-white transition-colors disabled:opacity-50"
                      >
                        {isSubmittingToken ? "Menyimpan..." : "Simpan & Hubungkan"}
                      </button>
                    </div>

                    <div className="rounded-xl bg-[#262624] border border-white/[0.06] p-3 flex items-center justify-between gap-3">
                      <div className="space-y-0.5">
                        <div className="text-xs font-semibold text-zinc-200 flex items-center gap-1.5">
                          <Smartphone size={13} className="text-emerald-400" />
                          <span>Kode Pasangan Ponsel (6 Digit)</span>
                        </div>
                        <p className="text-[11.5px] text-zinc-400">
                          Kirim <code className="text-[#F09373]">/pair {pairingCode}</code> ke bot
                          Telegram Anda.
                        </p>
                      </div>
                      <div className="flex items-center gap-1.5">
                        <span className="rounded-lg bg-black/40 border border-[#D97757]/40 px-3 py-1.5 font-mono text-sm font-bold text-zinc-100">
                          {pairingCode}
                        </span>
                        <button
                          type="button"
                          onClick={() => void handleRegenerateCode()}
                          title="Buat kode pasangan baru"
                          className="rounded-lg bg-[#191918] hover:bg-zinc-800 border border-white/[0.08] p-2 text-zinc-300"
                        >
                          <RefreshCw size={13} />
                        </button>
                      </div>
                    </div>
                  </div>
                )}
              </div>
            </div>

            {/* Service Cards 2..N: External Service Connections (MCP) */}
            {mcpServers.map((server) => {
              const showTech = expandedServiceTech[server.id] ?? false;
              const humanRight =
                server.id === "mcp_filesystem"
                  ? "Membaca & mengelola struktur file di Ruang Kerja"
                  : server.id === "mcp_playwright"
                  ? "Mengoperasikan peramban web otomatis"
                  : "Membaca & menganalisis tabel basis data lokal";

              return (
                <div
                  key={server.id}
                  className="rounded-2xl bg-[#21211F] border border-white/[0.08] p-5 flex flex-col justify-between space-y-4"
                >
                  <div className="space-y-3">
                    <div className="flex items-start justify-between gap-3">
                      <div className="flex items-center gap-3">
                        <div className="rounded-xl bg-[#D97757]/15 border border-[#D97757]/30 p-2.5 text-[#D97757]">
                          <PlugZap size={18} />
                        </div>
                        <div>
                          <h3 className="text-[15.5px] font-semibold text-zinc-100">
                            {server.name.replace(" MCP Server", "").replace(" MCP", "")}
                          </h3>
                          <span className="text-xs text-zinc-400">Koneksi Layanan Tambahan</span>
                        </div>
                      </div>

                      <StatusBadge
                        tone={server.enabled ? "success" : "neutral"}
                        label={server.enabled ? "Terhubung" : "Nonaktif"}
                      />
                    </div>

                    <p className="text-[13px] text-zinc-300 leading-relaxed">
                      {server.description_id}
                    </p>

                    <div className="rounded-xl bg-[#262624] border border-white/[0.06] p-3 space-y-1.5 text-xs">
                      <div className="flex items-center justify-between gap-2">
                        <span className="text-zinc-400">Hak akses yang digunakan:</span>
                        <span className="text-zinc-200 font-medium text-right">{humanRight}</span>
                      </div>
                      <div className="flex items-center justify-between gap-2">
                        <span className="text-zinc-400">Kemampuan tersedia:</span>
                        <span className="text-zinc-300">
                          {server.discovered_tools.length} fungsi layanan
                        </span>
                      </div>
                    </div>
                  </div>

                  <div className="space-y-2.5 pt-2 border-t border-white/[0.07]">
                    <div className="flex items-center justify-between gap-2">
                      {!server.enabled ? (
                        <button
                          type="button"
                          onClick={() => {
                            void toggleMcpServer(server.id, true);
                            toast.success(`Koneksi layanan "${server.name}" diaktifkan.`);
                          }}
                          className="rounded-xl bg-[#D97757] hover:bg-[#c96a4b] px-4 py-2 text-xs font-semibold text-white flex items-center gap-1.5 transition-colors"
                        >
                          <Link2 size={14} />
                          <span>Hubungkan</span>
                        </button>
                      ) : (
                        <button
                          type="button"
                          onClick={() => {
                            void toggleMcpServer(server.id, false);
                            toast.success(`Koneksi layanan "${server.name}" diputuskan.`);
                          }}
                          className="rounded-xl bg-rose-500/15 hover:bg-rose-500/25 border border-rose-500/30 px-4 py-2 text-xs font-semibold text-rose-300 flex items-center gap-1.5 transition-colors"
                        >
                          <Unlink2 size={14} />
                          <span>Putuskan Koneksi</span>
                        </button>
                      )}

                      <button
                        type="button"
                        onClick={() =>
                          setExpandedServiceTech((prev) => ({
                            ...prev,
                            [server.id]: !prev[server.id],
                          }))
                        }
                        className="inline-flex items-center gap-1 text-xs text-zinc-400 hover:text-zinc-200"
                      >
                        {showTech ? <ChevronDown size={13} /> : <ChevronRight size={13} />}
                        <span>Detail teknis</span>
                      </button>
                    </div>

                    {showTech && (
                      <div className="rounded-xl bg-[#191918] border border-white/[0.06] p-2.5 text-[11px] font-mono text-zinc-400 space-y-1">
                        <div>Perintah: {server.command} {server.args.join(" ")}</div>
                        <div>Alat: {server.discovered_tools.join(", ")}</div>
                      </div>
                    )}
                  </div>
                </div>
              );
            })}
          </div>
        </div>

        {/* Recent Connection Activity Log */}
        <div className="rounded-2xl bg-[#21211F] border border-white/[0.08] p-5 space-y-3">
          <SectionHeader
            icon={<Activity size={16} className="text-[#D97757]" />}
            title="Riwayat Aktivitas Koneksi"
            description="Catatan aktivitas terbaru dari koneksi layanan eksternal Anda."
          />

          <div className="space-y-2">
            {logs.length > 0 ? (
              logs.map((entry) => (
                <div
                  key={entry.id}
                  className="rounded-xl bg-[#262624] border border-white/[0.06] px-4 py-2.5 flex items-center justify-between gap-4"
                >
                  <div className="text-[13px] text-zinc-200">{entry.detail}</div>
                  <span className="shrink-0 text-xs font-mono text-zinc-400">{entry.time}</span>
                </div>
              ))
            ) : (
              <div className="rounded-xl bg-[#262624]/40 border border-dashed border-white/[0.07] p-6 text-center space-y-1">
                <p className="text-[13.5px] font-medium text-zinc-200">
                  Belum Ada Riwayat Aktivitas Koneksi
                </p>
                <p className="text-xs text-zinc-400">
                  Hubungkan layanan di atas jika Anda ingin menerima instruksi jarak jauh atau
                  menggunakan layanan tambahan.
                </p>
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
};
