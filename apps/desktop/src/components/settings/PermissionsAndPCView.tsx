import React, { useEffect, useState } from "react";
import {
  ShieldCheck,
  FolderLock,
  OctagonAlert,
  PlugZap,
  KeyRound,
  MonitorCog,
  Terminal,
  Laptop,
  Lock,
  ChevronDown,
  ChevronRight,
  Info,
} from "lucide-react";
import { toast } from "sonner";
import { useAksaStore } from "@/stores/useAksaStore";
import {
  fetchSystemPermissionsRemote,
  requestSystemPermissionRemote,
  revokeSystemPermissionRemote,
} from "@/services/engineClient";
import { formatPermissionStatusLabel } from "@/lib/utils";
import {
  PageHeader,
  SectionHeader,
  StatusBadge,
  EmptyStateCard,
  LoadingStateCard,
} from "@/components/ui/UXPrimitives";
import type { CapabilityStatus, WorkspaceFolderPermissionsGranular } from "@/types/aksa";

const GRANULAR_FOLDER_PERMISSION_ITEMS: {
  key: keyof WorkspaceFolderPermissionsGranular;
  label: string;
  description: string;
  isHighRisk?: boolean;
}[] = [
  {
    key: "list_files",
    label: "Melihat daftar file",
    description: "Melihat nama file dan sub-folder yang ada di dalam folder kerja.",
  },
  {
    key: "read_content",
    label: "Membaca isi file",
    description: "Membaca teks, tabel Excel, dokumen Word, dan PDF untuk dianalisis.",
  },
  {
    key: "create_files",
    label: "Membuat file",
    description: "Menyimpan dokumen atau laporan baru hasil pekerjaan AKSA.",
  },
  {
    key: "modify_files",
    label: "Mengubah file",
    description: "Memperbarui isi file yang ada (dilindungi cadangan otomatis).",
  },
  {
    key: "move_files",
    label: "Memindahkan file",
    description: "Merapikan atau mengganti nama file di dalam folder kerja.",
  },
  {
    key: "delete_files",
    label: "Menghapus file",
    description: "Menghapus file secara permanen. Memerlukan kontrol dan kehati-hatian khusus.",
    isHighRisk: true,
  },
  {
    key: "execute_programs",
    label: "Menjalankan program atau skrip",
    description: "Menjalankan skrip pemrosesan data otomatis di dalam Area Kerja Terlindungi.",
    isHighRisk: true,
  },
];

export const PermissionsAndPCView: React.FC = () => {
  const {
    workspaces,
    teams,
    activeTeamId,
    mcpServers,
    emergencyStopActive,
    updateWorkspacePermissions,
    requestSampleApproval,
    toggleMcpServer,
    toggleEmergencyStop,
    setActiveNav,
  } = useAksaStore();

  const [capabilities, setCapabilities] = useState<CapabilityStatus[]>([]);
  const [loadingCaps, setLoadingCaps] = useState(false);
  const [showAdvancedMatrix, setShowAdvancedMatrix] = useState(false);

  const activeTeam = teams.find((t) => t.id === activeTeamId) ?? teams[0];
  const agents = activeTeam?.agents ?? [];

  const loadCapabilities = async () => {
    setLoadingCaps(true);
    try {
      const data = await fetchSystemPermissionsRemote();
      if (data) setCapabilities(data);
    } catch {
      // Keep clean state
    } finally {
      setLoadingCaps(false);
    }
  };

  useEffect(() => {
    void loadCapabilities();
  }, []);

  const handleRequestCapability = async (capabilityId: string) => {
    const res = await requestSystemPermissionRemote(capabilityId, "workspace");
    if (res && res.granted) {
      toast.success("Izin akses berhasil diaktifkan.");
      await loadCapabilities();
    } else {
      toast.error(
        res?.message ||
          "Izin sistem operasi belum diberikan. Ikuti panduan pengaturan perangkat untuk mengaktifkannya."
      );
      await loadCapabilities();
    }
  };

  const handleRevokeGrant = async (grantId: string) => {
    try {
      const ok = await revokeSystemPermissionRemote(grantId);
      if (ok) {
        toast.success("Izin akses berhasil dicabut setelah dikonfirmasi oleh sistem.");
        await loadCapabilities();
      } else {
        toast.error(
          "Sistem belum mengonfirmasi pencabutan izin. Periksa status layanan atau pengaturan sistem operasi."
        );
      }
    } catch {
      toast.error("Gagal mencabut izin akses.");
    }
  };

  // Map 6 Access Categories required by Section 5.2
  const screenCap = capabilities.find(
    (c) => c.capability_id.includes("screen") || c.capability_id.includes("accessibility")
  );
  const appCap = capabilities.find((c) => c.capability_id.includes("automation"));

  const accessCategories = [
    {
      id: "cat_folders",
      title: "1. Folder dan file",
      icon: <FolderLock size={18} className="text-[#D97757]" />,
      description:
        "Mengatur folder mana saja yang boleh dilihat, dibaca, atau disimpan oleh AKSA di komputer Anda.",
      status: workspaces.length > 0 ? ("granted" as const) : ("not_granted" as const),
      scopeLabel:
        workspaces.length > 0
          ? `${workspaces.length} folder kerja diizinkan (folder lain otomatis terlindungi)`
          : "Belum ada folder yang dipilih",
      agentsUsing: agents
        .filter((a) => a.tool_categories.includes("filesystem"))
        .map((a) => a.name),
      actionLabel: "Atur Folder di Bawah",
      onConfigure: () => {
        document.getElementById("aksa-folder-permissions-section")?.scrollIntoView({
          behavior: "smooth",
        });
      },
    },
    {
      id: "cat_apps",
      title: "2. Aplikasi komputer",
      icon: <Laptop size={18} className="text-sky-400" />,
      description:
        "Mengizinkan AKSA membuka atau membantu mengoperasikan aplikasi yang terpasang seperti Excel, Word, atau browser.",
      status: appCap?.os_status ?? "automatic_sandbox",
      scopeLabel: "Hanya aplikasi yang Anda hubungkan secara eksplisit",
      agentsUsing: agents
        .filter((a) => a.tool_categories.includes("os_automation"))
        .map((a) => a.name),
      actionLabel: "Kelola Aplikasi",
      onConfigure: () => setActiveNav("aplikasi"),
      grantId: appCap?.grant_id,
      revocationGuide: appCap?.revocation_guide,
    },
    {
      id: "cat_screen",
      title: "3. Kontrol layar dan keyboard",
      icon: <MonitorCog size={18} className="text-amber-400" />,
      description:
        "Mengizinkan AKSA melihat layar atau menekan tombol ketika membantu tugas visual atas persetujuan Anda.",
      status: emergencyStopActive
        ? "DENIED"
        : screenCap?.os_status ?? "NEEDS_USER_ACTION",
      scopeLabel: "Memerlukan izin Aksesibilitas perangkat & persetujuan setiap tindakan",
      agentsUsing: agents
        .filter((a) => a.tool_categories.includes("computer_use"))
        .map((a) => a.name),
      actionLabel: screenCap?.capability_id ? "Minta / Periksa Izin" : "Uji Persetujuan",
      onConfigure: () =>
        screenCap?.capability_id
          ? void handleRequestCapability(screenCap.capability_id)
          : void requestSampleApproval(),
      grantId: screenCap?.grant_id,
      revocationGuide: screenCap?.revocation_guide,
    },
    {
      id: "cat_external",
      title: "4. Koneksi eksternal",
      icon: <PlugZap size={18} className="text-emerald-400" />,
      description:
        "Mengatur koneksi AKSA dengan layanan luar seperti Telegram atau layanan tambahan (MCP).",
      status: mcpServers.some((s) => s.enabled) ? "GRANTED" : "DENIED",
      scopeLabel: `${mcpServers.filter((s) => s.enabled).length} dari ${mcpServers.length} koneksi layanan aktif`,
      agentsUsing: agents.filter((a) => a.tool_categories.includes("mcp")).map((a) => a.name),
      actionLabel: "Atur Integrasi",
      onConfigure: () => setActiveNav("telegram"),
    },
    {
      id: "cat_programs",
      title: "5. Perintah dan program",
      icon: <Terminal size={18} className="text-indigo-400" />,
      description:
        "Mengatur izin menjalankan skrip pengolahan data otomatis di dalam Area Kerja Terlindungi.",
      status: workspaces.some((w) => w.allow_execute) ? "GRANTED" : "automatic_sandbox",
      scopeLabel: "Dibatasi di dalam Area Kerja Terlindungi tanpa akses ke file sistem",
      agentsUsing: agents
        .filter((a) => a.tool_categories.includes("uv_python"))
        .map((a) => a.name),
      actionLabel: "Uji Dialog Izin",
      onConfigure: () => void requestSampleApproval(),
    },
    {
      id: "cat_credentials",
      title: "6. Informasi sensitif dan kredensial",
      icon: <Lock size={18} className="text-rose-400" />,
      description:
        "Kunci layanan AI dan token rahasia disimpan terenkripsi di brankas keamanan perangkat serta tidak pernah dibagikan ke skrip eksternal.",
      status: "automatic_sandbox",
      scopeLabel: "Brankas Kredensial Terenkripsi • Pemindaian Data Pribadi Aktif",
      agentsUsing: ["Tidak ada agen yang dapat membaca kunci rahasia mentah"],
      actionLabel: "Kelola Model & Privasi",
      onConfigure: () => setActiveNav("pengaturan"),
    },
  ];

  return (
    <div className="flex-1 p-6 md:p-8 overflow-y-auto bg-[#191918]">
      <div className="max-w-6xl mx-auto space-y-7">
        {/* Page Header (Section 5.2: Pusat Akses AKSA) */}
        <PageHeader
          icon={<ShieldCheck size={22} className="text-emerald-400" />}
          title="Pusat Akses AKSA"
          description="Atur apa saja yang boleh dilakukan AKSA di komputer Anda."
          actions={
            <>
              <button
                type="button"
                onClick={() => void requestSampleApproval()}
                className="rounded-xl bg-amber-500/15 hover:bg-amber-500/25 border border-amber-500/30 px-3.5 py-2 text-[13px] font-medium text-amber-300 transition-colors"
              >
                Contoh Dialog Persetujuan
              </button>
              <button
                type="button"
                onClick={() => void toggleEmergencyStop(!emergencyStopActive)}
                className={`rounded-xl px-4 py-2 text-[13px] font-semibold flex items-center gap-2 border transition-colors ${
                  emergencyStopActive
                    ? "bg-emerald-600/20 border-emerald-500/40 text-emerald-300"
                    : "bg-rose-600/20 hover:bg-rose-600/30 border-rose-500/40 text-rose-300"
                }`}
              >
                <OctagonAlert size={15} />
                {emergencyStopActive
                  ? "Aktifkan Kembali Kontrol Layar"
                  : "Hentikan Kontrol Layar (Ctrl+Shift+Q)"}
              </button>
            </>
          }
        />

        {loadingCaps && capabilities.length === 0 && (
          <LoadingStateCard
            title="Memeriksa status akses perangkat..."
            description="Mengambil informasi izin sistem operasi dan Area Kerja Terlindungi."
          />
        )}

        {/* 6 Access Categories Grid (Section 5.2 Kategori Akses) */}
        <div className="space-y-3">
          <SectionHeader
            title="Kategori Akses Komputer"
            description="Lihat penjelasan setiap akses, agen yang menggunakannya, serta atur atau cabut izin kapan saja."
          />

          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            {accessCategories.map((cat) => {
              const statusInfo = formatPermissionStatusLabel(cat.status);
              return (
                <div
                  key={cat.id}
                  className="rounded-2xl bg-[#21211F] border border-white/[0.08] p-5 flex flex-col justify-between space-y-4"
                >
                  <div className="space-y-2.5">
                    <div className="flex items-start justify-between gap-3">
                      <div className="flex items-center gap-2.5">
                        <div className="rounded-xl bg-white/[0.04] border border-white/[0.07] p-2">
                          {cat.icon}
                        </div>
                        <h3 className="text-[15px] font-semibold text-zinc-100">{cat.title}</h3>
                      </div>
                      <StatusBadge tone={statusInfo.tone} label={statusInfo.label} />
                    </div>

                    <p className="text-[13px] text-zinc-300 leading-relaxed">{cat.description}</p>

                    <div className="rounded-xl bg-[#262624] border border-white/[0.06] p-3 space-y-1.5 text-xs">
                      <div className="flex items-start justify-between gap-2">
                        <span className="text-zinc-400 shrink-0">Cakupan akses:</span>
                        <span className="text-zinc-200 font-medium text-right">
                          {cat.scopeLabel}
                        </span>
                      </div>
                      <div className="flex items-start justify-between gap-2">
                        <span className="text-zinc-400 shrink-0">Digunakan oleh agen:</span>
                        <span className="text-zinc-300 text-right">
                          {cat.agentsUsing.length > 0
                            ? cat.agentsUsing.join(", ")
                            : "Belum ada agen"}
                        </span>
                      </div>
                      {cat.revocationGuide && (
                        <div className="pt-1 border-t border-white/[0.05] text-zinc-400">
                          <strong>Panduan Perangkat:</strong> {cat.revocationGuide}
                        </div>
                      )}
                    </div>
                  </div>

                  <div className="flex items-center justify-between gap-2 pt-2 border-t border-white/[0.06]">
                    <button
                      type="button"
                      onClick={cat.onConfigure}
                      className="rounded-xl bg-white/[0.07] hover:bg-white/[0.13] border border-white/[0.1] px-3.5 py-2 text-xs font-semibold text-zinc-100 transition-colors"
                    >
                      {cat.actionLabel}
                    </button>

                    {cat.grantId && (
                      <button
                        type="button"
                        onClick={() => void handleRevokeGrant(cat.grantId!)}
                        className="rounded-xl bg-rose-500/15 hover:bg-rose-500/25 border border-rose-500/30 px-3.5 py-2 text-xs font-semibold text-rose-300 transition-colors"
                      >
                        Cabut Izin
                      </button>
                    )}
                  </div>
                </div>
              );
            })}
          </div>
        </div>

        {/* Granular Folder Settings (Section 5.2 Pengaturan Folder: 7 Distinct Permissions) */}
        <div
          id="aksa-folder-permissions-section"
          className="rounded-2xl bg-[#21211F] border border-white/[0.08] p-5 md:p-6 space-y-4"
        >
          <SectionHeader
            icon={<FolderLock size={18} className="text-[#D97757]" />}
            title="Pengaturan Izin Folder Ruang Kerja"
            description="Atur secara terpisah apa saja yang boleh dilakukan AKSA di setiap folder kerja. Penghapusan permanen dan eksekusi program dipisahkan agar tetap aman."
            rightElement={
              <StatusBadge tone="accent" label="Folder di luar daftar otomatis diblokir" />
            }
          />

          <div className="space-y-4">
            {workspaces.length > 0 ? (
              workspaces.map((ws) => {
                const granular: WorkspaceFolderPermissionsGranular = ws.granular_permissions ?? {
                  list_files: ws.allow_read,
                  read_content: ws.allow_read,
                  create_files: ws.allow_write,
                  modify_files: ws.allow_write,
                  move_files: ws.allow_write,
                  delete_files: false,
                  execute_programs: ws.allow_execute,
                };

                const toggleGranular = (
                  key: keyof WorkspaceFolderPermissionsGranular,
                  checked: boolean
                ) => {
                  updateWorkspacePermissions(ws.id, {
                    granular_permissions: {
                      ...granular,
                      [key]: checked,
                    },
                  });
                };

                return (
                  <div
                    key={ws.id}
                    className="rounded-2xl bg-[#262624] border border-white/[0.08] p-5 space-y-4"
                  >
                    <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2 pb-3 border-b border-white/[0.07]">
                      <div>
                        <div className="text-[15px] font-semibold text-zinc-100">{ws.name}</div>
                        <div className="text-xs font-mono text-zinc-400">{ws.folder_path}</div>
                      </div>
                      <div className="flex items-center gap-2">
                        <StatusBadge
                          tone={ws.allow_read || ws.allow_write ? "success" : "neutral"}
                          label={ws.allow_read || ws.allow_write ? "Izin diberikan" : "Akses ditolak"}
                        />
                        <button
                          type="button"
                          onClick={() =>
                            updateWorkspacePermissions(ws.id, {
                              allow_read: false,
                              allow_write: false,
                              allow_execute: false,
                              granular_permissions: {
                                list_files: false,
                                read_content: false,
                                create_files: false,
                                modify_files: false,
                                move_files: false,
                                delete_files: false,
                                execute_programs: false,
                              },
                            })
                          }
                          className="rounded-xl bg-rose-500/15 hover:bg-rose-500/25 border border-rose-500/30 px-3 py-1.5 text-xs font-medium text-rose-300 transition-colors"
                        >
                          Cabut Izin Folder
                        </button>
                      </div>
                    </div>

                    <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-2.5">
                      {GRANULAR_FOLDER_PERMISSION_ITEMS.map((item) => {
                        const checked = granular[item.key];
                        return (
                          <label
                            key={item.key}
                            className={`flex items-start gap-2.5 rounded-xl p-3 border cursor-pointer transition-colors ${
                              checked
                                ? item.isHighRisk
                                  ? "bg-amber-500/10 border-amber-500/35"
                                  : "bg-[#191918] border-[#D97757]/40"
                                : "bg-[#191918]/70 border-white/[0.06] hover:border-white/[0.14]"
                            }`}
                          >
                            <input
                              type="checkbox"
                              checked={checked}
                              onChange={(e) => toggleGranular(item.key, e.target.checked)}
                              className="mt-1 accent-[#D97757]"
                            />
                            <div className="space-y-0.5">
                              <div className="text-[13px] font-medium text-zinc-100 flex items-center gap-1.5">
                                <span>{item.label}</span>
                                {item.isHighRisk && (
                                  <span className="rounded bg-amber-500/20 px-1.5 py-0.2 text-[10px] text-amber-300">
                                    Sensitif
                                  </span>
                                )}
                              </div>
                              <p className="text-xs text-zinc-400 leading-relaxed">
                                {item.description}
                              </p>
                            </div>
                          </label>
                        );
                      })}
                    </div>
                  </div>
                );
              })
            ) : (
              <EmptyStateCard
                icon={<FolderLock size={20} />}
                title="Belum ada folder kerja yang dipilih"
                description="Pilih folder di komputer Anda melalui menu di bagian atas layar agar AKSA dapat mulai membantu pekerjaan dokumen Anda."
              />
            )}
          </div>
        </div>

        {/* External Service Connections Quick Control */}
        <div className="rounded-2xl bg-[#21211F] border border-white/[0.08] p-5 md:p-6 space-y-4">
          <SectionHeader
            icon={<PlugZap size={18} className="text-[#D97757]" />}
            title="Koneksi Layanan Tambahan"
            description="Layanan eksternal nonaktif secara default demi keamanan dan hanya berjalan saat Anda mengaktifkannya."
          />

          <div className="grid grid-cols-1 md:grid-cols-3 gap-3.5">
            {mcpServers.map((server) => {
              const statusInfo = formatPermissionStatusLabel(
                server.enabled ? "GRANTED" : "DENIED"
              );
              return (
                <div
                  key={server.id}
                  className="rounded-xl bg-[#262624] border border-white/[0.07] p-4 flex flex-col justify-between space-y-3"
                >
                  <div className="space-y-1.5">
                    <div className="flex items-center justify-between gap-2">
                      <span className="text-[13.5px] font-semibold text-zinc-100">
                        {server.name}
                      </span>
                      <StatusBadge tone={statusInfo.tone} label={statusInfo.label} />
                    </div>
                    <p className="text-xs text-zinc-300 leading-relaxed">{server.description_id}</p>
                  </div>

                  <button
                    type="button"
                    onClick={() => void toggleMcpServer(server.id, !server.enabled)}
                    className={`w-full rounded-xl py-2 text-xs font-semibold transition-colors ${
                      server.enabled
                        ? "bg-rose-500/15 hover:bg-rose-500/25 border border-rose-500/30 text-rose-300"
                        : "bg-[#D97757] hover:bg-[#c96a4b] text-white"
                    }`}
                  >
                    {server.enabled ? "Cabut Izin Koneksi" : "Izinkan Koneksi Layanan"}
                  </button>
                </div>
              );
            })}
          </div>
        </div>

        {/* Progressive Disclosure: Detailed OS Permission Matrix for Advanced Users */}
        <div className="rounded-2xl bg-[#21211F] border border-white/[0.08] p-5 space-y-3">
          <button
            type="button"
            onClick={() => setShowAdvancedMatrix((v) => !v)}
            aria-expanded={showAdvancedMatrix}
            className="w-full flex items-center justify-between text-left"
          >
            <div className="flex items-center gap-2 text-[14px] font-semibold text-zinc-100">
              <KeyRound size={16} className="text-[#D97757]" />
              <span>Rincian Hak Akses Sistem Operasi (Mode Lanjutan)</span>
            </div>
            <span className="inline-flex items-center gap-1 text-xs text-zinc-300">
              {showAdvancedMatrix ? <ChevronDown size={15} /> : <ChevronRight size={15} />}
              <span>{showAdvancedMatrix ? "Sembunyikan" : "Lihat rincian"}</span>
            </span>
          </button>

          {showAdvancedMatrix && (
            <div className="pt-3 border-t border-white/[0.07] space-y-3">
              <p className="text-xs text-zinc-400 flex items-center gap-1.5">
                <Info size={13} className="text-[#D97757] shrink-0" />
                <span>
                  Izin AKSA dan izin bawaan sistem operasi (Windows / macOS / Linux) dikelola
                  secara terpisah demi keamanan perangkat Anda.
                </span>
              </p>

              <div className="overflow-x-auto">
                <table className="w-full text-left text-xs border-collapse">
                  <thead>
                    <tr className="border-b border-white/[0.08] text-xs text-zinc-400 font-semibold">
                      <th className="pb-2.5">Hak Akses</th>
                      <th className="pb-2.5">Cakupan</th>
                      <th className="pb-2.5">Status Perangkat</th>
                      <th className="pb-2.5">Persetujuan AKSA</th>
                      <th className="pb-2.5 text-right">Tindakan</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-white/[0.05]">
                    {capabilities.map((cap) => {
                      const osBadge = formatPermissionStatusLabel(cap.os_status);
                      const aksaBadge = formatPermissionStatusLabel(cap.aksa_status);
                      return (
                        <tr key={cap.capability_id} className="hover:bg-white/[0.02]">
                          <td className="py-3 pr-4">
                            <div className="font-semibold text-zinc-100 text-[13px]">
                              {cap.display_name}
                            </div>
                            <div className="text-xs text-zinc-300 mt-0.5">{cap.description}</div>
                            {cap.revocation_guide && (
                              <div className="text-xs text-zinc-400 mt-1">
                                Panduan: {cap.revocation_guide}
                              </div>
                            )}
                          </td>
                          <td className="py-3 pr-4 whitespace-nowrap text-zinc-300">
                            {cap.scope_type === "workspace" ? "Ruang Kerja" : cap.scope_type}
                          </td>
                          <td className="py-3 pr-4 whitespace-nowrap">
                            <div className="space-y-0.5">
                              <StatusBadge tone={osBadge.tone} label={osBadge.label} />
                              <div className="text-[10.5px] font-mono text-zinc-400">
                                Status OS: {cap.os_status}
                              </div>
                            </div>
                          </td>
                          <td className="py-3 pr-4 whitespace-nowrap">
                            <div className="space-y-0.5">
                              <StatusBadge tone={aksaBadge.tone} label={aksaBadge.label} />
                              <div className="text-[10.5px] font-mono text-zinc-400">
                                Status AKSA: {cap.aksa_status}
                              </div>
                            </div>
                          </td>
                          <td className="py-3 text-right whitespace-nowrap">
                            {cap.grant_id ? (
                              <button
                                type="button"
                                onClick={() => void handleRevokeGrant(cap.grant_id!)}
                                className="px-3 py-1.5 rounded-lg bg-rose-500/15 hover:bg-rose-500/25 border border-rose-500/30 text-xs font-medium text-rose-300 transition-colors"
                              >
                                Cabut Izin
                              </button>
                            ) : (
                              <button
                                type="button"
                                onClick={() => void handleRequestCapability(cap.capability_id)}
                                className="px-3 py-1.5 rounded-lg bg-white/[0.06] hover:bg-white/[0.12] border border-white/[0.1] text-xs font-medium text-zinc-200 transition-colors"
                              >
                                Periksa Izin
                              </button>
                            )}
                          </td>
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
};
