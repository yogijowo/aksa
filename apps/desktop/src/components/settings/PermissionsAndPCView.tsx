import React, { useEffect, useState } from "react";
import {
  ShieldCheck,
  FolderLock,
  OctagonAlert,
  PlugZap,
  KeyRound,
  CheckCircle2,
  AlertCircle,
} from "lucide-react";
import { toast } from "sonner";
import { useAksaStore } from "@/stores/useAksaStore";
import {
  fetchSystemPermissionsRemote,
  revokeSystemPermissionRemote,
} from "@/services/engineClient";
import type { CapabilityStatus } from "@/types/aksa";

export const PermissionsAndPCView: React.FC = () => {
  const {
    workspaces,
    mcpServers,
    emergencyStopActive,
    updateWorkspacePermissions,
    requestSampleApproval,
    toggleMcpServer,
    toggleEmergencyStop,
  } = useAksaStore();

  const [capabilities, setCapabilities] = useState<CapabilityStatus[]>([]);

  const loadCapabilities = async () => {
    try {
      const data = await fetchSystemPermissionsRemote();
      if (data) setCapabilities(data);
    } catch {
      // Graceful fallback
    } finally {
      // Done loading
    }
  };

  useEffect(() => {
    loadCapabilities();
  }, []);

  const handleRevokeGrant = async (grantId: string) => {
    try {
      const ok = await revokeSystemPermissionRemote(grantId);
      if (ok) {
        toast.success("Izin kapabilitas berhasil dicabut.");
        await loadCapabilities();
      }
    } catch {
      toast.error("Gagal mencabut izin.");
    }
  };

  return (
    <div className="flex-1 p-6 md:p-8 overflow-y-auto bg-[#191918]">
      <div className="max-w-6xl mx-auto space-y-6">
        {/* Header & Emergency Stop Banner */}
        <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
          <div>
            <h2 className="text-base font-semibold text-zinc-100 flex items-center gap-2">
              <ShieldCheck size={18} className="text-emerald-400" />
              Pusat Izin Sistem Operasi &amp; Sandbox AKSA
            </h2>
            <p className="text-xs text-zinc-400 mt-1">
              Evaluasi izin native OS (Accessibility, TCC, Windows ACL), persetujuan konsen AKSA, serta tombol darurat kontrol layar Tier 3.
            </p>
          </div>

          <div className="flex items-center gap-2">
            <button
              onClick={() => void requestSampleApproval()}
              className="rounded-xl bg-amber-500/15 hover:bg-amber-500/25 border border-amber-500/30 px-3.5 py-2 text-xs font-medium text-amber-300 transition-colors"
            >
              Simulasi Konfirmasi HITL
            </button>
            <button
              onClick={() => void toggleEmergencyStop(!emergencyStopActive)}
              className={`rounded-xl px-3.5 py-2 text-xs font-semibold flex items-center gap-1.5 border transition-colors ${
                emergencyStopActive
                  ? "bg-emerald-600/20 border-emerald-500/40 text-emerald-300"
                  : "bg-rose-600/20 hover:bg-rose-600/30 border-rose-500/40 text-rose-300"
              }`}
            >
              <OctagonAlert size={14} />
              {emergencyStopActive
                ? "Aktifkan Kembali Tier 3 GUI"
                : "Stop Darurat GUI (Ctrl+Shift+Q)"}
            </button>
          </div>
        </div>

        {/* Section 0: Native OS Permission Broker Table */}
        <div className="rounded-2xl bg-[#21211F] border border-white/[0.08] p-5 space-y-4">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2 text-xs font-semibold text-zinc-100">
              <KeyRound size={15} className="text-[#D97757]" />
              <span>Matriks Kapabilitas: Status Sistem Operasi vs Konsen AKSA</span>
            </div>
            <span className="text-[11px] text-zinc-400">
              Pemisahan ketat izin platform OS dan persetujuan pengguna
            </span>
          </div>

          <div className="overflow-x-auto">
            <table className="w-full text-left text-xs border-collapse">
              <thead>
                <tr className="border-b border-white/[0.08] text-[11px] text-zinc-400 font-semibold uppercase tracking-wider">
                  <th className="pb-2.5">Kapabilitas</th>
                  <th className="pb-2.5">Cakupan</th>
                  <th className="pb-2.5">Status Platform OS</th>
                  <th className="pb-2.5">Konsen AKSA</th>
                  <th className="pb-2.5 text-right">Aksi</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-white/[0.04]">
                {capabilities.map((cap) => (
                  <tr key={cap.capability_id} className="hover:bg-white/[0.02] transition-colors">
                    <td className="py-3 pr-4">
                      <div className="font-semibold text-zinc-100">{cap.display_name}</div>
                      <div className="text-[11px] text-zinc-400 mt-0.5">{cap.description}</div>
                    </td>
                    <td className="py-3 pr-4 whitespace-nowrap">
                      <span className="px-2 py-0.5 rounded text-[10px] bg-[#2A2A28] text-zinc-300 border border-white/5 font-mono">
                        {cap.scope_type}
                      </span>
                    </td>
                    <td className="py-3 pr-4 whitespace-nowrap">
                      <span
                        className={`inline-flex items-center gap-1 px-2 py-0.5 rounded text-[10px] font-semibold ${
                          cap.os_status === "GRANTED"
                            ? "bg-emerald-500/15 text-emerald-400 border border-emerald-500/30"
                            : cap.os_status === "NEEDS_USER_ACTION"
                            ? "bg-amber-500/15 text-amber-300 border border-amber-500/30"
                            : cap.os_status === "DENIED"
                            ? "bg-rose-500/15 text-rose-400 border border-rose-500/30"
                            : "bg-zinc-800 text-zinc-400"
                        }`}
                      >
                        {cap.os_status === "GRANTED" && <CheckCircle2 size={11} />}
                        {cap.os_status === "NEEDS_USER_ACTION" && <AlertCircle size={11} />}
                        <span>{cap.os_status}</span>
                      </span>
                    </td>
                    <td className="py-3 pr-4 whitespace-nowrap">
                      <span
                        className={`inline-flex items-center gap-1 px-2 py-0.5 rounded text-[10px] font-medium ${
                          cap.aksa_status === "granted"
                            ? "bg-[#D97757]/15 text-[#D97757] border border-[#D97757]/30"
                            : cap.aksa_status === "automatic_sandbox"
                            ? "bg-zinc-800 text-zinc-300"
                            : "bg-zinc-800/60 text-zinc-400"
                        }`}
                      >
                        {cap.aksa_status === "granted"
                          ? "Izin Diberikan"
                          : cap.aksa_status === "automatic_sandbox"
                          ? "Sandbox Otomatis"
                          : "Perlu Persetujuan"}
                      </span>
                    </td>
                    <td className="py-3 text-right whitespace-nowrap">
                      {cap.grant_id ? (
                        <button
                          onClick={() => handleRevokeGrant(cap.grant_id!)}
                          className="px-2.5 py-1 rounded bg-rose-500/15 hover:bg-rose-500/25 border border-rose-500/30 text-[10px] font-medium text-rose-300 transition-colors"
                        >
                          Cabut Izin
                        </button>
                      ) : (
                        <span className="text-[11px] text-zinc-600">—</span>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>

        {/* Section 1: Workspace Folder Sandbox & Granular Permissions */}
        <div className="rounded-2xl bg-[#21211F] border border-white/[0.08] p-5 space-y-4">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2 text-xs font-semibold text-zinc-100">
              <FolderLock size={15} className="text-[#D97757]" />
              <span>Sandbox Folder Kerja Diizinkan (`allowed_paths` Path Jail)</span>
            </div>
            <span className="text-[11px] text-emerald-400">
              Path di luar daftar ini otomatis diblokir
            </span>
          </div>

          <div className="space-y-3">
            {workspaces.map((ws) => (
              <div
                key={ws.id}
                className="rounded-xl bg-[#262624] border border-white/[0.06] p-4 flex flex-col md:flex-row md:items-center justify-between gap-4"
              >
                <div className="space-y-1">
                  <div className="text-xs font-semibold text-zinc-100">{ws.name}</div>
                  <div className="text-[11px] font-mono text-zinc-400">{ws.folder_path}</div>
                </div>

                <div className="flex flex-wrap items-center gap-2">
                  <label className="flex items-center gap-1.5 rounded-lg bg-[#21211F] border border-white/[0.07] px-3 py-1.5 text-[11px] text-zinc-200 cursor-pointer">
                    <input
                      type="checkbox"
                      checked={ws.allow_read}
                      onChange={(e) =>
                        void updateWorkspacePermissions(ws.id, { allow_read: e.target.checked })
                      }
                      className="accent-[#D97757]"
                    />
                    <span>Baca (Read)</span>
                  </label>

                  <label className="flex items-center gap-1.5 rounded-lg bg-[#21211F] border border-white/[0.07] px-3 py-1.5 text-[11px] text-zinc-200 cursor-pointer">
                    <input
                      type="checkbox"
                      checked={ws.allow_write}
                      onChange={(e) =>
                        void updateWorkspacePermissions(ws.id, { allow_write: e.target.checked })
                      }
                      className="accent-[#D97757]"
                    />
                    <span>Tulis &amp; Backup</span>
                  </label>

                  <label className="flex items-center gap-1.5 rounded-lg bg-[#21211F] border border-white/[0.07] px-3 py-1.5 text-[11px] text-zinc-200 cursor-pointer">
                    <input
                      type="checkbox"
                      checked={ws.allow_execute}
                      onChange={(e) =>
                        void updateWorkspacePermissions(ws.id, { allow_execute: e.target.checked })
                      }
                      className="accent-[#D97757]"
                    />
                    <span>Eksekusi Skrip (uv)</span>
                  </label>
                </div>
              </div>
            ))}

            {workspaces.length === 0 && (
              <div className="text-center py-6 text-xs text-zinc-500">
                Belum ada Folder Kerja yang didaftarkan. Pilih folder di bilah atas aplikasi.
              </div>
            )}
          </div>
        </div>

        {/* Section 2: Model Context Protocol (MCP) Server Registry */}
        <div className="rounded-2xl bg-[#21211F] border border-white/[0.08] p-5 space-y-4">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2 text-xs font-semibold text-zinc-100">
              <PlugZap size={15} className="text-[#D97757]" />
              <span>Integrasi Eksternal Model Context Protocol (MCP)</span>
            </div>
            <span className="text-[11px] text-zinc-400">Nonaktif secara default demi keamanan</span>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
            {mcpServers.map((server) => (
              <div
                key={server.id}
                className="rounded-xl bg-[#262624] border border-white/[0.06] p-4 flex flex-col justify-between space-y-3"
              >
                <div className="space-y-1">
                  <div className="flex items-center justify-between">
                    <span className="text-xs font-semibold text-zinc-100">{server.name}</span>
                    <span
                      className={`text-[10px] font-medium px-2 py-0.5 rounded-full ${
                        server.enabled
                          ? "bg-emerald-500/15 text-emerald-400 border border-emerald-500/30"
                          : "bg-zinc-800 text-zinc-400"
                      }`}
                    >
                      {server.enabled ? "Aktif" : "Nonaktif"}
                    </span>
                  </div>
                  <p className="text-[11px] text-zinc-400 leading-relaxed">{server.description_id}</p>
                </div>

                <div className="space-y-2 pt-2 border-t border-white/[0.04]">
                  <div className="flex flex-wrap gap-1">
                    {server.discovered_tools.map((tool) => (
                      <span
                        key={tool}
                        className="text-[10px] font-mono px-1.5 py-0.5 rounded bg-[#21211F] text-zinc-300 border border-white/[0.05]"
                      >
                        {tool}
                      </span>
                    ))}
                  </div>

                  <button
                    onClick={() => void toggleMcpServer(server.id, !server.enabled)}
                    className={`w-full rounded-lg py-1.5 text-xs font-medium transition-colors ${
                      server.enabled
                        ? "bg-zinc-800 hover:bg-zinc-700 text-zinc-300"
                        : "bg-[#D97757] hover:bg-[#E89274] text-white"
                    }`}
                  >
                    {server.enabled ? "Nonaktifkan Server" : "Aktifkan Server MCP"}
                  </button>
                </div>
              </div>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
};
