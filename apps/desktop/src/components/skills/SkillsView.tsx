import React, { useEffect, useState } from "react";
import {
  Sparkles,
  ShieldCheck,
  CheckCircle2,
  Download,
  Trash2,
  Power,
  FileCode2,
  Search,
  AlertTriangle,
  Users,
} from "lucide-react";
import { toast } from "sonner";
import { useAksaStore } from "@/stores/useAksaStore";
import {
  fetchSkillsRemote,
  installCuratedSkillRemote,
  toggleSkillStatusRemote,
  deleteSkillRemote,
} from "@/services/engineClient";
import {
  PageHeader,
  StatusBadge,
  EmptyStateCard,
  LoadingStateCard,
  ErrorStateCard,
} from "@/components/ui/UXPrimitives";
import type { CuratedSkill, SkillItem } from "@/types/aksa";

function getSkillSourceInfo(trustLevel: string, publisher: string): {
  sourceLabel: "Skill bawaan AKSA" | "Skill dari sumber eksternal" | "Skill buatan pengguna";
  verificationLabel: string;
  isTrustedOrigin: boolean;
  tone: "accent" | "success" | "warning";
} {
  const pubLower = (publisher || "").toLowerCase();
  if (trustLevel === "curated" || pubLower.includes("aksa")) {
    return {
      sourceLabel: "Skill bawaan AKSA",
      verificationLabel: "Pemeriksaan paket resmi AKSA",
      isTrustedOrigin: true,
      tone: "accent",
    };
  }
  if (pubLower.includes("pengguna") || pubLower.includes("local") || pubLower.includes("user")) {
    return {
      sourceLabel: "Skill buatan pengguna",
      verificationLabel: "Dibuat di perangkat lokal Anda",
      isTrustedOrigin: true,
      tone: "success",
    };
  }
  return {
    sourceLabel: "Skill dari sumber eksternal",
    verificationLabel:
      trustLevel === "verified_publisher"
        ? "Tanda tangan penerbit terverifikasi"
        : "Sumber komunitas eksternal (periksa izin sebelum memasang)",
    isTrustedOrigin: trustLevel === "verified_publisher",
    tone: "warning",
  };
}

function formatCapabilityHuman(cap: string): string {
  return cap
    .replace("filesystem.workspace.read", "Membaca file di Ruang Kerja")
    .replace("filesystem.workspace.write", "Membuat & menyimpan file di Ruang Kerja")
    .replace("filesystem.workspace.", "Akses Ruang Kerja: ");
}

export const SkillsView: React.FC = () => {
  const { teams, activeTeamId } = useAksaStore();
  const [activeTab, setActiveTab] = useState<"catalog" | "installed">("catalog");
  const [curatedList, setCuratedList] = useState<CuratedSkill[]>([]);
  const [installedList, setInstalledList] = useState<SkillItem[]>([]);
  const [loading, setLoading] = useState(false);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [processingId, setProcessingId] = useState<string | null>(null);
  const [search, setSearch] = useState("");
  const [selectedTag, setSelectedTag] = useState<string>("all");
  const [skillPendingInstall, setSkillPendingInstall] = useState<CuratedSkill | null>(null);

  const activeTeam = teams.find((t) => t.id === activeTeamId) ?? teams[0];
  const agents = activeTeam?.agents ?? [];

  const getAgentsUsingSkill = (skillId: string): string[] => {
    return agents
      .filter(
        (a) =>
          a.tool_categories.includes(`skill:${skillId}`) ||
          a.tool_categories.includes(skillId)
      )
      .map((a) => a.name);
  };

  const loadData = async () => {
    setLoading(true);
    setLoadError(null);
    try {
      const data = await fetchSkillsRemote();
      if (data) {
        setCuratedList(data.curated_catalog || []);
        setInstalledList(data.installed_skills || []);
      }
    } catch (err: any) {
      setLoadError(err?.message || "Gagal memuat daftar keahlian.");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    void loadData();
  }, []);

  const handleConfirmInstall = async (skill: CuratedSkill) => {
    setSkillPendingInstall(null);
    setProcessingId(skill.id);
    try {
      const res = await installCuratedSkillRemote(skill.id);
      if (res?.skill) {
        toast.success(
          `Keahlian "${skill.display_name}" berhasil dipasang (dalam kondisi nonaktif agar Anda dapat memeriksanya terlebih dahulu).`
        );
        await loadData();
        setActiveTab("installed");
      } else {
        toast.error("Gagal memasang keahlian.");
      }
    } catch (err: any) {
      toast.error(`Gagal memasang keahlian: ${err?.message || err}`);
    } finally {
      setProcessingId(null);
    }
  };

  const handleToggle = async (skill: SkillItem) => {
    setProcessingId(skill.skill_id);
    const nextState = !skill.enabled;
    try {
      const res = await toggleSkillStatusRemote(skill.skill_id, nextState);
      if (res?.skill) {
        toast.success(
          nextState
            ? `Keahlian "${skill.display_name}" kini aktif.`
            : `Keahlian "${skill.display_name}" telah dinonaktifkan.`
        );
        await loadData();
      }
    } catch (err: any) {
      toast.error(`Gagal mengubah status keahlian: ${err?.message || err}`);
    } finally {
      setProcessingId(null);
    }
  };

  const handleDelete = async (skill: SkillItem) => {
    setProcessingId(skill.skill_id);
    try {
      const ok = await deleteSkillRemote(skill.skill_id);
      if (ok) {
        toast.success(`Keahlian "${skill.display_name}" berhasil dihapus.`);
        await loadData();
      }
    } catch (err: any) {
      toast.error(`Gagal menghapus keahlian: ${err?.message || err}`);
    } finally {
      setProcessingId(null);
    }
  };

  const filteredCurated = curatedList.filter((s) => {
    const q = search.toLowerCase();
    const matchesSearch =
      s.display_name.toLowerCase().includes(q) ||
      s.description.toLowerCase().includes(q) ||
      s.publisher.toLowerCase().includes(q);

    if (!matchesSearch) return false;

    if (selectedTag === "office") {
      return (
        s.id.includes("excel") ||
        s.id.includes("word") ||
        s.id.includes("naskah") ||
        s.id.includes("pdf") ||
        s.id.includes("pitch")
      );
    }
    if (selectedTag === "code") {
      return (
        s.id.includes("git") ||
        s.id.includes("sql") ||
        s.id.includes("python") ||
        s.id.includes("security")
      );
    }
    if (selectedTag === "finance") {
      return (
        s.id.includes("financial") ||
        s.id.includes("tax") ||
        s.id.includes("pajak") ||
        s.id.includes("reconciliation")
      );
    }
    if (selectedTag === "research") {
      return (
        s.id.includes("research") || s.id.includes("academic") || s.id.includes("meeting")
      );
    }

    return true;
  });

  const filteredInstalled = installedList.filter((s) => {
    const q = search.toLowerCase();
    return (
      s.display_name.toLowerCase().includes(q) ||
      s.skill_id.toLowerCase().includes(q) ||
      s.publisher.toLowerCase().includes(q)
    );
  });

  const activeInstalledCount = installedList.filter((s) => s.enabled).length;

  return (
    <div className="flex-1 overflow-y-auto px-6 md:px-8 py-8 bg-[#191918] text-[#ECECEB]">
      {/* Pre-Installation Review & Verification Modal (Section 5.6) */}
      {skillPendingInstall && (
        <div
          role="dialog"
          aria-modal="true"
          aria-labelledby="aksa-skill-install-title"
          className="fixed inset-0 z-50 flex items-center justify-center bg-black/75 backdrop-blur-sm p-4"
        >
          <div className="w-full max-w-lg rounded-2xl bg-[#21211F] border border-white/[0.12] shadow-2xl p-6 space-y-4">
            {(() => {
              const srcInfo = getSkillSourceInfo(
                skillPendingInstall.trust_level,
                skillPendingInstall.publisher
              );
              return (
                <>
                  <div className="space-y-1.5">
                    <StatusBadge tone={srcInfo.tone} label={srcInfo.sourceLabel} />
                    <h2
                      id="aksa-skill-install-title"
                      className="text-[18px] font-semibold text-zinc-100 pt-1"
                    >
                      Pasang keahlian "{skillPendingInstall.display_name}"?
                    </h2>
                    <p className="text-[13.5px] text-zinc-300 leading-relaxed">
                      {skillPendingInstall.description}
                    </p>
                  </div>

                  <div className="rounded-xl bg-[#262624] border border-white/[0.08] p-4 space-y-2.5 text-[13px]">
                    <div className="flex items-center justify-between gap-2">
                      <span className="text-zinc-400">Asal sumber:</span>
                      <span className="font-semibold text-zinc-100">
                        {skillPendingInstall.publisher} ({srcInfo.sourceLabel})
                      </span>
                    </div>

                    <div className="flex items-center justify-between gap-2">
                      <span className="text-zinc-400">Status verifikasi:</span>
                      <span className="text-zinc-200 text-right">{srcInfo.verificationLabel}</span>
                    </div>

                    <div className="space-y-1 pt-1 border-t border-white/[0.06]">
                      <span className="text-zinc-400 block">
                        Izin &amp; kemampuan yang diminta:
                      </span>
                      <div className="flex flex-wrap gap-1.5 pt-0.5">
                        {skillPendingInstall.capabilities.map((cap) => (
                          <span
                            key={cap}
                            className="rounded-lg bg-[#191918] border border-[#D97757]/35 px-2.5 py-1 text-xs text-[#F09373]"
                          >
                            {formatCapabilityHuman(cap)}
                          </span>
                        ))}
                        {skillPendingInstall.has_scripts && (
                          <span className="rounded-lg bg-[#191918] border border-white/[0.1] px-2.5 py-1 text-xs text-zinc-300">
                            Menjalankan pemrosesan di Area Kerja Terlindungi
                          </span>
                        )}
                      </div>
                    </div>
                  </div>

                  {/* Mandatory Warning Note (Section 5.6: Verified is not an absolute security guarantee) */}
                  <div className="rounded-xl bg-amber-500/10 border border-amber-500/30 p-3.5 flex items-start gap-2.5 text-xs text-amber-200 leading-relaxed">
                    <AlertTriangle size={16} className="text-amber-400 shrink-0 mt-0.5" />
                    <div>
                      <strong>Catatan Keamanan:</strong> Status terverifikasi menunjukkan bahwa
                      keutuhan paket telah diperiksa, namun bukan jaminan keamanan mutlak. Setiap
                      keahlian baru dipasang dalam keadaan <strong>Nonaktif</strong> hingga Anda
                      mengaktifkannya sendiri.
                    </div>
                  </div>

                  <div className="flex items-center justify-end gap-2.5 pt-2">
                    <button
                      type="button"
                      onClick={() => setSkillPendingInstall(null)}
                      className="rounded-xl bg-[#262624] hover:bg-zinc-700 border border-white/[0.1] px-4 py-2 text-[13px] font-medium text-zinc-200 transition-colors"
                    >
                      Batal
                    </button>
                    <button
                      type="button"
                      onClick={() => void handleConfirmInstall(skillPendingInstall)}
                      className="rounded-xl bg-[#D97757] hover:bg-[#c96a4b] px-4 py-2 text-[13px] font-semibold text-white transition-colors"
                    >
                      Mengerti &amp; Pasang Keahlian
                    </button>
                  </div>
                </>
              );
            })()}
          </div>
        </div>
      )}

      <div className="max-w-6xl mx-auto space-y-6">
        <PageHeader
          icon={<Sparkles className="w-5 h-5 text-[#D97757]" />}
          title="Keahlian AKSA"
          description="Tambahkan kemampuan khusus bagi AKSA—seperti menyusun laporan keuangan, surat resmi, atau analisis dokumen—tanpa perlu mengatur file teknis."
        />

        {/* Security & Source Distinction Banner (Section 5.6) */}
        <div className="p-4 rounded-2xl bg-[#21211F] border border-emerald-500/30 flex items-start gap-3.5">
          <div className="w-9 h-9 rounded-xl bg-emerald-500/15 flex items-center justify-center text-emerald-400 shrink-0 mt-0.5">
            <ShieldCheck className="w-5 h-5" />
          </div>
          <div className="space-y-1 text-[13px]">
            <span className="font-semibold text-white">
              Perlindungan Keamanan Keahlian:
            </span>
            <p className="text-zinc-300 leading-relaxed">
              Setiap keahlian yang baru dipasang otomatis berada dalam kondisi{" "}
              <strong className="text-white">Nonaktif</strong> dan tidak pernah mendapatkan akses ke
              kunci rahasia Anda. Label verifikasi menandakan pemeriksaan paket, namun Anda tetap
              memegang kendali penuh atas izin folder dan agen yang menggunakannya.
            </p>
          </div>
        </div>

        {/* Search & Tabs */}
        <div className="space-y-3">
          <div className="flex flex-col md:flex-row items-stretch md:items-center justify-between gap-3">
            <div className="relative flex-1">
              <Search className="w-4 h-4 absolute left-3.5 top-1/2 -translate-y-1/2 text-zinc-400" />
              <input
                type="text"
                aria-label="Cari keahlian"
                placeholder="Cari keahlian berdasarkan pekerjaan (misal: Excel, Pajak, Surat Resmi, PDF)..."
                value={search}
                onChange={(e) => setSearch(e.target.value)}
                className="w-full bg-[#21211F] border border-white/10 rounded-xl pl-10 pr-4 py-2.5 text-[13.5px] text-zinc-100 placeholder-zinc-500 focus:outline-none focus:border-[#D97757]"
              />
            </div>

            <div className="flex items-center gap-1.5 p-1 rounded-xl bg-[#21211F] border border-white/10 shrink-0">
              <button
                type="button"
                onClick={() => setActiveTab("catalog")}
                className={`px-3.5 py-1.5 rounded-lg text-xs font-semibold transition-all ${
                  activeTab === "catalog"
                    ? "bg-[#D97757] text-white shadow-sm"
                    : "text-zinc-300 hover:text-white"
                }`}
              >
                Pilihan Keahlian ({curatedList.length})
              </button>
              <button
                type="button"
                onClick={() => setActiveTab("installed")}
                className={`px-3.5 py-1.5 rounded-lg text-xs font-semibold transition-all flex items-center gap-1.5 ${
                  activeTab === "installed"
                    ? "bg-emerald-600 text-white shadow-sm"
                    : "text-zinc-300 hover:text-white"
                }`}
              >
                <CheckCircle2 className="w-3.5 h-3.5" />
                <span>Terpasang ({installedList.length})</span>
                {activeInstalledCount > 0 && (
                  <span className="px-1.5 py-0.2 rounded-full text-[10px] bg-white/20 font-mono">
                    {activeInstalledCount} aktif
                  </span>
                )}
              </button>
            </div>
          </div>

          {activeTab === "catalog" && (
            <div className="flex items-center gap-1.5 overflow-x-auto pb-1 text-xs">
              <span className="text-zinc-400 text-xs whitespace-nowrap">Bidang Pekerjaan:</span>
              {[
                { id: "all", label: `Semua (${curatedList.length})` },
                { id: "office", label: "Dokumen & Office" },
                { id: "finance", label: "Keuangan & Pajak" },
                { id: "code", label: "Olah Data & Kode" },
                { id: "research", label: "Riset & Ringkasan" },
              ].map((pill) => (
                <button
                  type="button"
                  key={pill.id}
                  onClick={() => setSelectedTag(pill.id)}
                  className={`px-3 py-1 rounded-full text-xs font-medium transition-all whitespace-nowrap ${
                    selectedTag === pill.id
                      ? "bg-white/[0.12] text-white border border-white/[0.2]"
                      : "bg-[#21211F] text-zinc-300 hover:text-white border border-transparent"
                  }`}
                >
                  {pill.label}
                </button>
              ))}
            </div>
          )}
        </div>

        {loadError && (
          <ErrorStateCard
            title="Daftar keahlian belum dapat dimuat"
            cause={loadError}
            nextStep="Klik Coba Lagi untuk memuat ulang katalog keahlian."
            onRetry={() => void loadData()}
          />
        )}

        {loading && curatedList.length === 0 ? (
          <LoadingStateCard
            title="Memuat daftar keahlian AKSA..."
            description="Menyiapkan informasi fungsi, asal sumber, dan status verifikasi setiap keahlian."
          />
        ) : activeTab === "catalog" ? (
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            {filteredCurated.map((skill) => {
              const isInstalled = installedList.some((i) => i.skill_id === skill.id);
              const srcInfo = getSkillSourceInfo(skill.trust_level, skill.publisher);
              const assignedAgents = getAgentsUsingSkill(skill.id);

              return (
                <div
                  key={skill.id}
                  className="p-5 rounded-2xl bg-[#21211F] border border-white/10 hover:border-white/20 transition-all flex flex-col justify-between space-y-4"
                >
                  <div className="space-y-2.5">
                    <div className="flex items-start justify-between gap-3">
                      <div className="space-y-1">
                        <div className="flex items-center gap-2 flex-wrap">
                          <h3 className="font-semibold text-[15.5px] text-white">
                            {skill.display_name}
                          </h3>
                          <StatusBadge tone={srcInfo.tone} label={srcInfo.sourceLabel} />
                        </div>
                        <div className="text-xs text-zinc-400">
                          Sumber: {skill.publisher} • Versi {skill.version}
                        </div>
                      </div>
                    </div>

                    <p className="text-[13.5px] text-zinc-200 leading-relaxed">
                      {skill.description}
                    </p>

                    <div className="rounded-xl bg-[#1A1A18] p-3 border border-white/[0.06] space-y-1">
                      <div className="text-xs font-semibold text-zinc-300">Fungsi utama:</div>
                      <p className="text-xs text-zinc-300 leading-relaxed">
                        {skill.instructions_preview}
                      </p>
                    </div>
                  </div>

                  <div className="space-y-3 pt-3 border-t border-white/[0.07]">
                    <div className="space-y-1.5 text-xs">
                      <div className="flex items-center justify-between text-zinc-300">
                        <span className="text-zinc-400">Status verifikasi:</span>
                        <span>{srcInfo.verificationLabel}</span>
                      </div>
                      <div className="flex items-center justify-between text-zinc-300">
                        <span className="text-zinc-400 flex items-center gap-1">
                          <Users size={12} /> Digunakan oleh agen:
                        </span>
                        <span>
                          {assignedAgents.length > 0
                            ? assignedAgents.join(", ")
                            : "Belum ditugaskan ke agen"}
                        </span>
                      </div>
                    </div>

                    <div className="flex flex-wrap items-center gap-1.5">
                      <span className="text-xs text-zinc-400">Izin yang dibutuhkan:</span>
                      {skill.capabilities.map((cap) => (
                        <span
                          key={cap}
                          className="px-2 py-0.5 rounded-md text-xs font-medium bg-[#2A2A28] text-[#F09373] border border-[#D97757]/30"
                        >
                          {formatCapabilityHuman(cap)}
                        </span>
                      ))}
                      {skill.has_scripts && (
                        <span className="px-2 py-0.5 rounded-md text-xs font-medium bg-indigo-500/15 text-indigo-300 border border-indigo-500/30 flex items-center gap-1">
                          <FileCode2 className="w-3 h-3" />
                          <span>Area Kerja Terlindungi</span>
                        </span>
                      )}
                    </div>

                    <div className="flex items-center justify-between pt-1">
                      <span className="text-xs text-zinc-400">
                        Status: {isInstalled ? "Sudah terpasang" : "Belum dipasang"}
                      </span>
                      {isInstalled ? (
                        <StatusBadge tone="success" label="Terpasang" />
                      ) : (
                        <button
                          type="button"
                          onClick={() => setSkillPendingInstall(skill)}
                          disabled={processingId === skill.id}
                          className="px-4 py-2 rounded-xl bg-[#D97757] hover:bg-[#c96a4b] text-white text-xs font-semibold flex items-center gap-1.5 transition-all disabled:opacity-50"
                        >
                          <Download className="w-3.5 h-3.5" />
                          <span>
                            {processingId === skill.id ? "Memasang..." : "Tinjau & Pasang"}
                          </span>
                        </button>
                      )}
                    </div>
                  </div>
                </div>
              );
            })}

            {filteredCurated.length === 0 && (
              <div className="col-span-full">
                <EmptyStateCard
                  icon={<Sparkles size={22} />}
                  title="Tidak ada keahlian yang cocok"
                  description={`Tidak ditemukan keahlian dengan kata kunci "${search}".`}
                />
              </div>
            )}
          </div>
        ) : (
          /* Tab 2: Installed Skills */
          <div className="space-y-3">
            {filteredInstalled.map((skill) => {
              const srcInfo = getSkillSourceInfo(skill.trust_level, skill.publisher);
              const assignedAgents = getAgentsUsingSkill(skill.skill_id);
              return (
                <div
                  key={skill.id}
                  className="p-5 rounded-2xl bg-[#21211F] border border-white/10 flex flex-col sm:flex-row sm:items-center justify-between gap-4"
                >
                  <div className="space-y-1.5">
                    <div className="flex items-center gap-2 flex-wrap">
                      <span className="font-semibold text-[15px] text-white">
                        {skill.display_name}
                      </span>
                      <StatusBadge
                        tone={skill.enabled ? "success" : "neutral"}
                        label={skill.enabled ? "Aktif" : "Nonaktif"}
                      />
                      <StatusBadge tone={srcInfo.tone} label={srcInfo.sourceLabel} />
                    </div>
                    <div className="text-xs text-zinc-300">
                      Sumber: {skill.publisher} • Versi {skill.installed_version} •{" "}
                      {srcInfo.verificationLabel}
                    </div>
                    <div className="text-xs text-zinc-400">
                      Digunakan oleh agen:{" "}
                      <strong className="text-zinc-200">
                        {assignedAgents.length > 0
                          ? assignedAgents.join(", ")
                          : "Belum ditugaskan (atur di menu Tim AI)"}
                      </strong>
                    </div>
                  </div>

                  <div className="flex items-center gap-2 shrink-0">
                    <button
                      type="button"
                      onClick={() => void handleToggle(skill)}
                      disabled={processingId === skill.skill_id}
                      className={`px-3.5 py-2 rounded-xl text-xs font-semibold flex items-center gap-1.5 transition-all ${
                        skill.enabled
                          ? "bg-[#262624] hover:bg-[#343431] text-zinc-200 border border-white/10"
                          : "bg-emerald-600 hover:bg-emerald-500 text-white"
                      }`}
                    >
                      <Power className="w-3.5 h-3.5" />
                      <span>{skill.enabled ? "Nonaktifkan" : "Aktifkan"}</span>
                    </button>

                    <button
                      type="button"
                      onClick={() => void handleDelete(skill)}
                      disabled={processingId === skill.skill_id}
                      className="p-2 rounded-xl bg-[#262624] hover:bg-rose-500/20 hover:text-rose-300 text-zinc-400 border border-white/10 transition-all"
                      title="Hapus keahlian ini"
                    >
                      <Trash2 className="w-4 h-4" />
                    </button>
                  </div>
                </div>
              );
            })}

            {filteredInstalled.length === 0 && (
              <EmptyStateCard
                icon={<Sparkles size={22} />}
                title="Belum ada keahlian yang dipasang"
                description="Pilih keahlian dari tab Pilihan Keahlian untuk menambahkan kemampuan baru bagi AKSA."
                actionLabel="Lihat Pilihan Keahlian"
                onAction={() => setActiveTab("catalog")}
              />
            )}
          </div>
        )}
      </div>
    </div>
  );
};
