import React, { useEffect, useState } from "react";
import {
  Sparkles,
  ShieldCheck,
  CheckCircle2,
  Download,
  Trash2,
  Power,
  FileCode2,
} from "lucide-react";
import { toast } from "sonner";
import {
  fetchSkillsRemote,
  installCuratedSkillRemote,
  toggleSkillStatusRemote,
  deleteSkillRemote,
} from "@/services/engineClient";
import type { CuratedSkill, SkillItem } from "@/types/aksa";

export const SkillsView: React.FC = () => {
  const [activeTab, setActiveTab] = useState<"catalog" | "installed">("catalog");
  const [curatedList, setCuratedList] = useState<CuratedSkill[]>([]);
  const [installedList, setInstalledList] = useState<SkillItem[]>([]);
  const [processingId, setProcessingId] = useState<string | null>(null);

  const loadData = async () => {
    try {
      const data = await fetchSkillsRemote();
      if (data) {
        setCuratedList(data.curated_catalog || []);
        setInstalledList(data.installed_skills || []);
      }
    } catch {
      toast.error("Gagal memuat katalog keahlian agen.");
    } finally {
      // Done loading
    }
  };

  useEffect(() => {
    loadData();
  }, []);

  const handleInstall = async (skill: CuratedSkill) => {
    setProcessingId(skill.id);
    try {
      const res = await installCuratedSkillRemote(skill.id);
      if (res?.skill) {
        toast.success(
          `Keahlian '${skill.display_name}' berhasil dipasang (kondisi nonaktif secara default).`
        );
        await loadData();
        setActiveTab("installed");
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
            ? `Keahlian '${skill.display_name}' kini AKTIF.`
            : `Keahlian '${skill.display_name}' DINONAKTIFKAN.`
        );
        await loadData();
      }
    } catch (err: any) {
      toast.error(`Gagal memperbarui status keahlian: ${err?.message || err}`);
    } finally {
      setProcessingId(null);
    }
  };

  const handleDelete = async (skill: SkillItem) => {
    setProcessingId(skill.skill_id);
    try {
      const ok = await deleteSkillRemote(skill.skill_id);
      if (ok) {
        toast.success(`Keahlian '${skill.display_name}' berhasil dicopot.`);
        await loadData();
      }
    } catch (err: any) {
      toast.error(`Gagal mencopot keahlian: ${err?.message || err}`);
    } finally {
      setProcessingId(null);
    }
  };

  return (
    <div className="flex-1 overflow-y-auto px-8 py-8 bg-[#191918] text-[#ECECEB]">
      <div className="max-w-6xl mx-auto space-y-6">
        {/* Header */}
        <div className="flex items-center justify-between">
          <div className="space-y-1">
            <div className="flex items-center gap-2 text-xs font-semibold uppercase tracking-wider text-[#D97757]">
              <Sparkles className="w-4 h-4" />
              <span>Format Standar Agent Skills (SKILL.md)</span>
            </div>
            <h1 className="text-2xl font-bold tracking-tight text-white">Manajer Keahlian Eksternal</h1>
            <p className="text-sm text-[#9C9A92]">
              Pasang keahlian terkurasi untuk memperluas kapabilitas agen dengan isolasi sandbox ketat.
            </p>
          </div>
        </div>

        {/* Security Manifesto Callout */}
        <div className="p-4 rounded-xl bg-[#21211F] border border-[#10B981]/30 flex items-start gap-3">
          <div className="w-8 h-8 rounded-lg bg-[#10B981]/15 flex items-center justify-center text-[#10B981] shrink-0 mt-0.5">
            <ShieldCheck className="w-4 h-4" />
          </div>
          <div className="space-y-1 text-xs">
            <span className="font-semibold text-white">Prinsip Keamanan Keahlian AKSA:</span>
            <p className="text-[#9C9A92] leading-relaxed">
              Setiap paket keahlian yang dipasang otomatis berada dalam kondisi <strong className="text-white">NONAKTIF secara default</strong>. 
              Skrip keahlian tidak pernah dieksekusi saat proses instalasi, tidak memiliki akses ke API key atau token rahasia, dan hanya diizinkan membaca folder kerja yang telah disetujui.
            </p>
          </div>
        </div>

        {/* Tab Toggle */}
        <div className="flex items-center gap-2 p-1 rounded-xl bg-[#21211F] border border-[#FFFFFF]/10 w-fit">
          <button
            onClick={() => setActiveTab("catalog")}
            className={`px-4 py-1.5 rounded-lg text-xs font-semibold transition-all ${
              activeTab === "catalog"
                ? "bg-[#D97757] text-white shadow-sm"
                : "text-[#9C9A92] hover:text-[#ECECEB]"
            }`}
          >
            Katalog Terkurasi ({curatedList.length})
          </button>
          <button
            onClick={() => setActiveTab("installed")}
            className={`px-4 py-1.5 rounded-lg text-xs font-semibold transition-all ${
              activeTab === "installed"
                ? "bg-[#D97757] text-white shadow-sm"
                : "text-[#9C9A92] hover:text-[#ECECEB]"
            }`}
          >
            Keahlian Terpasang ({installedList.length})
          </button>
        </div>

        {/* Tab 1: Curated Catalog */}
        {activeTab === "catalog" && (
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            {curatedList.map((skill) => {
              const isInstalled = installedList.some((i) => i.skill_id === skill.id);
              return (
                <div
                  key={skill.id}
                  className="p-5 rounded-xl bg-[#21211F] border border-[#FFFFFF]/10 hover:border-[#FFFFFF]/20 transition-all flex flex-col justify-between space-y-4"
                >
                  <div className="space-y-2">
                    <div className="flex items-start justify-between gap-3">
                      <div>
                        <div className="flex items-center gap-2">
                          <span className="font-bold text-sm text-white">{skill.display_name}</span>
                          <span className="px-1.5 py-0.5 rounded text-[10px] font-medium bg-[#10B981]/15 text-[#10B981] border border-[#10B981]/30">
                            Kurasi AKSA
                          </span>
                        </div>
                        <div className="text-[11px] text-[#9C9A92] mt-0.5">
                          {skill.publisher} • v{skill.version}
                        </div>
                      </div>
                    </div>

                    <p className="text-xs text-[#ECECEB]/85 leading-relaxed">{skill.description}</p>
                    <p className="text-[11px] text-[#71716E] italic bg-[#1A1A18] p-2.5 rounded-lg border border-[#FFFFFF]/05">
                      "{skill.instructions_preview}"
                    </p>
                  </div>

                  <div className="space-y-3 pt-3 border-t border-[#FFFFFF]/05">
                    {/* Capabilities Required */}
                    <div className="flex flex-wrap items-center gap-1.5">
                      <span className="text-[10px] text-[#71716E]">Izin Diminta:</span>
                      {skill.capabilities.map((cap) => (
                        <span
                          key={cap}
                          className="px-2 py-0.5 rounded text-[10px] font-medium bg-[#2A2A28] text-[#D97757] border border-[#D97757]/30"
                        >
                          {cap.replace("filesystem.workspace.", "Folder Kerja: ")}
                        </span>
                      ))}
                      {skill.has_scripts && (
                        <span className="px-2 py-0.5 rounded text-[10px] font-medium bg-[#8B5CF6]/15 text-[#8B5CF6] border border-[#8B5CF6]/30 flex items-center gap-1">
                          <FileCode2 className="w-3 h-3" />
                          <span>Skrip Terisolasi</span>
                        </span>
                      )}
                    </div>

                    {/* Action button */}
                    <div className="flex items-center justify-between pt-1">
                      <span className="text-[11px] text-[#71716E]">Format: SKILL.md v1.0</span>
                      {isInstalled ? (
                        <span className="flex items-center gap-1 text-xs text-[#10B981] font-semibold">
                          <CheckCircle2 className="w-3.5 h-3.5" />
                          <span>Terpasang</span>
                        </span>
                      ) : (
                        <button
                          onClick={() => handleInstall(skill)}
                          disabled={processingId === skill.id}
                          className="px-3.5 py-1.5 rounded-lg bg-[#D97757] hover:bg-[#E89274] text-white text-xs font-semibold flex items-center gap-1.5 transition-all disabled:opacity-50"
                        >
                          <Download className="w-3.5 h-3.5" />
                          <span>{processingId === skill.id ? "Memasang..." : "Pasang Keahlian"}</span>
                        </button>
                      )}
                    </div>
                  </div>
                </div>
              );
            })}
          </div>
        )}

        {/* Tab 2: Installed Skills */}
        {activeTab === "installed" && (
          <div className="space-y-3">
            {installedList.map((skill) => (
              <div
                key={skill.id}
                className="p-4 rounded-xl bg-[#21211F] border border-[#FFFFFF]/10 flex items-center justify-between gap-4"
              >
                <div className="space-y-1">
                  <div className="flex items-center gap-2">
                    <span className="font-bold text-sm text-white">{skill.display_name}</span>
                    <span
                      className={`px-2 py-0.5 rounded text-[10px] font-semibold ${
                        skill.enabled
                          ? "bg-[#10B981]/15 text-[#10B981] border border-[#10B981]/30"
                          : "bg-[#2A2A28] text-[#71716E]"
                      }`}
                    >
                      {skill.enabled ? "AKTIF" : "NONAKTIF"}
                    </span>
                  </div>
                  <div className="text-xs text-[#9C9A92]">
                    ID: <code className="text-[#ECECEB] bg-[#1A1A18] px-1 rounded">{skill.skill_id}</code> • v
                    {skill.installed_version} • Penerbit: {skill.publisher}
                  </div>
                </div>

                <div className="flex items-center gap-2">
                  <button
                    onClick={() => handleToggle(skill)}
                    disabled={processingId === skill.skill_id}
                    className={`px-3 py-1.5 rounded-lg text-xs font-semibold flex items-center gap-1.5 transition-all ${
                      skill.enabled
                        ? "bg-[#2A2A28] hover:bg-[#343431] text-[#9C9A92] border border-[#FFFFFF]/10"
                        : "bg-[#10B981] hover:bg-[#059669] text-white"
                    }`}
                  >
                    <Power className="w-3.5 h-3.5" />
                    <span>{skill.enabled ? "Nonaktifkan" : "Aktifkan"}</span>
                  </button>

                  <button
                    onClick={() => handleDelete(skill)}
                    disabled={processingId === skill.skill_id}
                    className="p-2 rounded-lg bg-[#2A2A28] hover:bg-[#EF4444]/20 hover:text-[#EF4444] text-[#71716E] border border-[#FFFFFF]/10 transition-all"
                    title="Copot keahlian"
                  >
                    <Trash2 className="w-3.5 h-3.5" />
                  </button>
                </div>
              </div>
            ))}

            {installedList.length === 0 && (
              <div className="py-12 text-center text-[#71716E] text-xs border border-dashed border-[#FFFFFF]/10 rounded-xl">
                Belum ada keahlian yang dipasang. Silakan pilih keahlian di tab <strong>Katalog Terkurasi</strong>.
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  );
};
