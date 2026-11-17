import React, { useState, useEffect } from "react";
import {
  Send,
  Smartphone,
  ShieldCheck,
  Mic,
  FileSpreadsheet,
  RefreshCw,
  CheckCircle2,
  Activity,
} from "lucide-react";
import {
  fetchTelegramStatus,
  configureTelegramRemote,
  regenerateTelegramCodeRemote,
} from "@/services/engineClient";
import { useAksaStore } from "@/stores/useAksaStore";

interface AuditEntry {
  id: string;
  time: string;
  type: "paired" | "voice_note" | "file_delivered" | "blocked" | "info";
  detail: string;
}

export const TelegramGatewayView: React.FC = () => {
  const { workspaces, activeWorkspaceId } = useAksaStore();
  const [botToken, setBotToken] = useState("");
  const [isConnected, setIsConnected] = useState(false);
  const [botUsername, setBotUsername] = useState("");
  const [pairingCode, setPairingCode] = useState("------");
  const [whitelistCount, setWhitelistCount] = useState(0);
  const [simCommand, setSimCommand] = useState("");
  const [isSubmittingToken, setIsSubmittingToken] = useState(false);
  const [isSimulating, setIsSimulating] = useState(false);
  const [logs, setLogs] = useState<AuditEntry[]>([]);
  const [feedbackNotice, setFeedbackNotice] = useState<string | null>(null);

  const activeWorkspace = workspaces.find((w) => w.id === activeWorkspaceId) ?? workspaces[0];

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
      // Backend not running yet or unreachable
    }
  };

  useEffect(() => {
    void refreshStatus();
  }, []);

  const handleConnectBot = async () => {
    if (!botToken.trim()) return;
    setIsSubmittingToken(true);
    setFeedbackNotice(null);
    try {
      const res = await configureTelegramRemote(botToken.trim());
      if (res && res.connected) {
        setIsConnected(true);
        setBotUsername(res.bot_username || "@aksa_bot");
        setFeedbackNotice(
          `Gateway Telegram berhasil terhubung sebagai ${res.bot_username}. Sekarang kirimkan kode pairing dari HP Anda.`
        );
        setLogs((prev) => [
          {
            id: `log_${Date.now()}`,
            time: "Baru saja",
            type: "info",
            detail: `Gateway Telegram aktif terhubung ke ${res.bot_username}. Siap menerima pesan.`,
          },
          ...prev,
        ]);
        setBotToken("");
      } else {
        setFeedbackNotice("Gagal menghubungkan bot. Periksa kembali format token @BotFather Anda.");
      }
    } catch {
      setFeedbackNotice("Terjadi kesalahan jaringan saat menghubungkan ke gateway Telegram.");
    } finally {
      setIsSubmittingToken(false);
      void refreshStatus();
    }
  };

  const handleRegenerateCode = async () => {
    try {
      const newCode = await regenerateTelegramCodeRemote();
      if (newCode) {
        setPairingCode(newCode);
      } else {
        const p1 = Math.floor(100 + Math.random() * 900);
        const p2 = Math.floor(100 + Math.random() * 900);
        setPairingCode(`${p1}-${p2}`);
      }
    } catch {
      const p1 = Math.floor(100 + Math.random() * 900);
      const p2 = Math.floor(100 + Math.random() * 900);
      setPairingCode(`${p1}-${p2}`);
    }
  };

  const handleSimulateRemoteTask = async () => {
    if (!simCommand.trim()) return;
    const cmd = simCommand.trim();
    setIsSimulating(true);
    try {
      const response = await fetch("http://127.0.0.1:43120/api/v1/telegram/simulate", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          telegram_user_id: 123456789,
          text: cmd,
          username: "pengguna_aksa",
          workspace_path: activeWorkspace?.folder_path || undefined,
        }),
      });

      if (response.ok) {
        const data = await response.json();
        setLogs((prev) => [
          {
            id: `log_${Date.now()}_res`,
            time: "Baru saja",
            type: "file_delivered",
            detail: data.reply || "Tugas berhasil diselesaikan dan artefak siap diakses.",
          },
          {
            id: `log_${Date.now()}_cmd`,
            time: "Baru saja",
            type: "voice_note",
            detail: `Menerima perintah: "${cmd}"`,
          },
          ...prev,
        ]);
        setSimCommand("");
      } else {
        setLogs((prev) => [
          {
            id: `log_${Date.now()}_err`,
            time: "Baru saja",
            type: "blocked",
            detail: "Akses simulasi ditolak oleh Whitelist Guard. Lakukan pairing akun terlebih dahulu.",
          },
          ...prev,
        ]);
      }
    } catch {
      setLogs((prev) => [
        {
          id: `log_${Date.now()}_err`,
          time: "Baru saja",
          type: "blocked",
          detail: "Backend engine belum merespons permintaan simulasi.",
        },
        ...prev,
      ]);
    } finally {
      setIsSimulating(false);
    }
  };

  return (
    <div className="flex-1 p-6 md:p-8 overflow-y-auto bg-[#191918]">
      <div className="max-w-6xl mx-auto space-y-6">
        {/* Header */}
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
          <div>
            <h2 className="text-base font-semibold text-zinc-100 flex items-center gap-2">
              <Send size={18} className="text-sky-400" />
              Koneksi Telegram (Remote Command Center)
            </h2>
            <p className="text-xs text-zinc-400 mt-1">
              Kendalikan agen di PC ini dari HP Anda via chat teks atau Voice Note Bahasa Indonesia,
              dan terima file dokumen hasil kerja langsung di Telegram secara aman.
            </p>
          </div>
          <span
            className={`rounded-xl px-3 py-1.5 text-xs font-medium flex items-center gap-1.5 border ${
              isConnected
                ? "bg-emerald-500/15 border-emerald-500/30 text-emerald-300"
                : "bg-zinc-800/60 border-white/[0.08] text-zinc-400"
            }`}
          >
            <CheckCircle2 size={14} />{" "}
            {isConnected ? `Terhubung (${botUsername})` : "Belum Dikonfigurasi"}
          </span>
        </div>

        {feedbackNotice && (
          <div className="rounded-xl bg-[#21211F] border border-white/[0.08] px-4 py-3 text-xs text-zinc-300 flex items-center gap-2">
            <CheckCircle2 size={15} className="text-[#D97757]" />
            <span>{feedbackNotice}</span>
          </div>
        )}

        {/* Step 1 & Step 2: Token & 6-Digit Pairing */}
        <div className="rounded-2xl bg-[#21211F] border border-white/[0.08] p-5 space-y-4">
          <div className="flex items-center gap-2 text-xs font-semibold text-zinc-200">
            <Smartphone size={15} className="text-sky-400" />
            <span>Langkah 1: Konfigurasi Token Bot Telegram (@BotFather)</span>
          </div>

          <div className="space-y-2">
            <div className="flex gap-2">
              <input
                type="password"
                value={botToken}
                onChange={(e) => setBotToken(e.target.value)}
                placeholder={
                  isConnected
                    ? `Sudah terhubung ke ${botUsername} (Masukkan token baru jika ingin mengganti)`
                    : "Tempel HTTP API Token dari @BotFather (contoh: 748291:AAH...)"
                }
                className="flex-1 rounded-xl bg-[#262624] border border-white/[0.08] px-3.5 py-2.5 text-xs text-zinc-100 focus:outline-none focus:border-[#D97757]/60"
              />
              <button
                onClick={() => void handleConnectBot()}
                disabled={isSubmittingToken || !botToken.trim()}
                className="rounded-xl bg-[#D97757] hover:bg-[#c96a4b] px-4 py-2.5 text-xs font-medium text-white transition-colors disabled:opacity-50 flex items-center gap-1.5"
              >
                {isSubmittingToken ? <RefreshCw size={13} className="animate-spin" /> : null}
                Hubungkan Bot
              </button>
            </div>
            <p className="text-[11px] text-zinc-500 leading-relaxed">
              Koneksi menggunakan mode Outbound Long-Polling. Tidak memerlukan port-forwarding, IP publik statis, ataupun domain eksternal.
            </p>
          </div>

          {/* Pairing Code Section */}
          <div className="rounded-xl bg-[#262624] border border-white/[0.06] p-4 flex flex-col sm:flex-row sm:items-center justify-between gap-4">
            <div className="space-y-1">
              <div className="text-xs font-semibold text-zinc-200 flex items-center gap-1.5">
                <ShieldCheck size={14} className="text-emerald-400" />
                Langkah 2: Kode Pairing Keamanan 6-Digit &amp; Whitelist Akses
              </div>
              <p className="text-[11px] text-zinc-400">
                Kirim pesan <code className="text-[#D97757] font-mono font-medium">/pair {pairingCode}</code> di chat bot Telegram dari HP Anda untuk mengunci akses eksklusif hanya untuk Anda.
              </p>
            </div>
            <div className="flex items-center gap-2">
              <div className="rounded-xl bg-white/[0.06] border border-[#D97757]/30 px-4 py-2 text-base font-mono font-bold text-zinc-200 tracking-wider">
                {pairingCode}
              </div>
              <button
                onClick={() => void handleRegenerateCode()}
                title="Buat kode pairing baru"
                className="rounded-xl bg-[#21211F] hover:bg-[#262624] border border-white/[0.08] p-2.5 text-zinc-300 transition-colors"
              >
                <RefreshCw size={14} />
              </button>
            </div>
          </div>
        </div>

        {/* Remote Command Testing Section */}
        <div className="rounded-2xl bg-[#21211F] border border-white/[0.08] p-5 space-y-3">
          <div className="flex items-center justify-between">
            <span className="text-xs font-semibold text-zinc-100 flex items-center gap-2">
              <Mic size={15} className="text-sky-400" />
              Uji Perintah Jarak Jauh (Simulasi Input Pesan Telegram)
            </span>
            <span className="text-[11px] text-emerald-400 flex items-center gap-1 font-mono">
              <FileSpreadsheet size={12} /> Auto-Send File Hasil Kerja
            </span>
          </div>

          <div className="flex gap-2">
            <input
              type="text"
              value={simCommand}
              onChange={(e) => setSimCommand(e.target.value)}
              onKeyDown={(e) => e.key === "Enter" && void handleSimulateRemoteTask()}
              placeholder="Ketik instruksi simulasi (misal: Tolong buatkan rekap penjualan di Excel)..."
              className="flex-1 rounded-xl bg-[#262624] border border-white/[0.08] px-3.5 py-2 text-xs text-zinc-100 focus:outline-none focus:border-[#D97757]/60"
            />
            <button
              onClick={() => void handleSimulateRemoteTask()}
              disabled={isSimulating || !simCommand.trim()}
              className="rounded-xl bg-sky-600 hover:bg-sky-500 px-4 py-2 text-xs font-medium text-white transition-colors disabled:opacity-50 flex items-center gap-1.5"
            >
              {isSimulating ? <RefreshCw size={13} className="animate-spin" /> : null}
              Uji Kirim
            </button>
          </div>
        </div>

        {/* Live Telegram Activity & Security Log */}
        <div className="rounded-2xl bg-[#21211F] border border-white/[0.08] p-5 space-y-3">
          <div className="flex items-center justify-between">
            <h3 className="text-xs font-semibold uppercase tracking-wider text-zinc-300 flex items-center gap-2">
              <Activity size={14} className="text-[#D97757]" />
              Log Aktivitas &amp; Keamanan Whitelist Telegram
            </h3>
            <span className="text-[11px] text-zinc-400 font-mono">
              {whitelistCount} Akun Terdaftar di Whitelist
            </span>
          </div>

          <div className="space-y-2">
            {logs.length > 0 ? (
              logs.map((entry) => (
                <div
                  key={entry.id}
                  className="rounded-xl bg-[#262624] border border-white/[0.06] px-4 py-2.5 flex items-center justify-between gap-4"
                >
                  <div className="text-xs text-zinc-200">{entry.detail}</div>
                  <span className="shrink-0 text-[10px] font-mono text-zinc-400">{entry.time}</span>
                </div>
              ))
            ) : (
              /* Clean Empty State */
              <div className="rounded-xl bg-[#262624]/40 border border-dashed border-white/[0.06] p-6 text-center space-y-1">
                <p className="text-xs font-medium text-zinc-300">Belum Ada Aktivitas Telegram</p>
                <p className="text-[11.5px] text-zinc-500">
                  Lakukan pairing bot Telegram di atas untuk mulai menerima perintah dan mengirim dokumen langsung ke HP Anda.
                </p>
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
};
