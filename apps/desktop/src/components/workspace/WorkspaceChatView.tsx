import React, { useEffect, useRef, useState } from "react";
import ReactMarkdown from "react-markdown";
import {
  ArrowUp,
  CheckCircle2,
  ChevronDown,
  ChevronRight,
  FileSpreadsheet,
  FileText,
  ExternalLink,
  FolderOpen,
  Loader2,
  Sparkles,
  Search,
  MonitorCog,
  MessageSquareText,
  ShieldCheck,
  HelpCircle,
  Clock,
  AlertTriangle,
  Paperclip,
} from "lucide-react";
import { toast } from "sonner";
import { useAksaStore } from "@/stores/useAksaStore";
import { cn, formatNumberID, getProviderBadgeStyle } from "@/lib/utils";
import { ProviderIcon } from "@/components/ui/DynamicIcon";
import { ErrorStateCard, StatusBadge } from "@/components/ui/UXPrimitives";
import { openFileInDefaultApp } from "@/services/engineClient";
import { getParentFolderPath } from "@/components/layout/ArtifactDrawer";
import type { FileArtifact } from "@/types/aksa";

interface ActivityCardItem {
  id: string;
  title: string;
  bullets: string[];
  defaultPrompt: string;
  icon: React.ElementType;
  accentClass: string;
}

const ACTIVITY_CARDS: ActivityCardItem[] = [
  {
    id: "olah_dokumen",
    title: "Mengolah dokumen",
    bullets: ["Membaca PDF, Word, dan Excel", "Membuat laporan", "Mengolah data"],
    defaultPrompt:
      "Bantu saya membaca dokumen di folder kerja ini lalu buatkan laporan ringkas dalam format Excel dan Word.",
    icon: FileSpreadsheet,
    accentClass: "text-emerald-400 bg-emerald-500/12 border-emerald-500/25",
  },
  {
    id: "cari_informasi",
    title: "Mencari informasi",
    bullets: ["Mencari informasi", "Merangkum dokumen", "Membandingkan data"],
    defaultPrompt:
      "Cari informasi penting dari dokumen di ruang kerja ini, rangkum poin utamanya, dan bandingkan datanya.",
    icon: Search,
    accentClass: "text-[#D97757] bg-[#D97757]/12 border-[#D97757]/25",
  },
  {
    id: "tugas_komputer",
    title: "Mengerjakan tugas komputer",
    bullets: ["Mengoperasikan aplikasi", "Mengelola file", "Membantu pekerjaan berulang"],
    defaultPrompt:
      "Bantu saya merapikan dan mengelola file di folder kerja ini secara otomatis.",
    icon: MonitorCog,
    accentClass: "text-sky-400 bg-sky-500/12 border-sky-500/25",
  },
  {
    id: "tanya_aksa",
    title: "Bertanya kepada AKSA",
    bullets: ["Tanya jawab", "Brainstorming", "Analisis dan rekomendasi"],
    defaultPrompt:
      "Bantu saya menganalisis rencana pekerjaan hari ini dan berikan rekomendasi langkah yang paling efektif.",
    icon: MessageSquareText,
    accentClass: "text-amber-400 bg-amber-500/12 border-amber-500/25",
  },
];

const ONBOARDING_STEPS = [
  {
    step: 1,
    title: "Selamat datang di AKSA",
    description:
      "AKSA adalah asisten pribadi di komputer Anda yang siap membantu menyelesaikan pekerjaan sehari-hari tanpa perlu mengatur hal teknis.",
  },
  {
    step: 2,
    title: "Bantu pekerjaan dokumen & komputer",
    description:
      "Anda cukup menceritakan pekerjaan yang diinginkan—mulai dari merangkum PDF, membuat laporan Excel atau Word, hingga merapikan file di komputer.",
  },
  {
    step: 3,
    title: "Izin akses hanya diminta saat dibutuhkan",
    description:
      "AKSA bekerja di dalam Area Kerja Terlindungi. AKSA tidak meminta seluruh izin komputer di awal, melainkan hanya meminta persetujuan Anda ketika suatu tindakan memang memerlukannya.",
  },
  {
    step: 4,
    title: "Siap mencoba tugas pertama Anda?",
    description:
      "Pilih salah satu kartu aktivitas di Ruang Kerja atau ketik langsung pekerjaan yang ingin Anda selesaikan di kotak pesan.",
  },
];

export const WorkspaceChatView: React.FC = () => {
  const {
    messages,
    sendUserPrompt,
    workspaces,
    activeWorkspaceId,
    isExecuting,
    activeAgentStep,
    liveExecutionSteps,
    pendingApprovals,
    setActiveNav,
  } = useAksaStore();

  const [inputPrompt, setInputPrompt] = useState("");
  const [emptyHintWarning, setEmptyHintWarning] = useState<string | null>(null);
  const [sendError, setSendError] = useState<string | null>(null);
  const [expandedTraces, setExpandedTraces] = useState<Record<string, boolean>>({});
  const [showLiveDetails, setShowLiveDetails] = useState(false);
  const [onboardingStep, setOnboardingStep] = useState<number | null>(() => {
    if (typeof window !== "undefined") {
      try {
        const done = localStorage.getItem("aksa_onboarding_completed");
        return done === "true" ? null : 0;
      } catch {}
    }
    return null;
  });

  const messagesEndRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLInputElement>(null);
  const activeWorkspace = workspaces.find((w) => w.id === activeWorkspaceId) ?? workspaces[0];

  const completeOnboarding = () => {
    if (typeof window !== "undefined") {
      try {
        localStorage.setItem("aksa_onboarding_completed", "true");
      } catch {}
    }
    setOnboardingStep(null);
  };

  const scrollToBottom = (behavior: ScrollBehavior = "smooth") => {
    messagesEndRef.current?.scrollIntoView({ behavior, block: "end" });
  };

  useEffect(() => {
    scrollToBottom();
  }, [messages.length, isExecuting, liveExecutionSteps.length]);

  const handleSelectActivity = (promptText: string) => {
    setInputPrompt(promptText);
    setEmptyHintWarning(null);
    inputRef.current?.focus();
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (isExecuting) return;
    if (!inputPrompt.trim()) {
      setEmptyHintWarning(
        "Silakan tuliskan pekerjaan yang ingin Anda selesaikan terlebih dahulu, atau pilih salah satu contoh aktivitas di atas."
      );
      inputRef.current?.focus();
      return;
    }
    setEmptyHintWarning(null);
    setSendError(null);
    const promptToSend = inputPrompt;
    setInputPrompt("");
    try {
      await sendUserPrompt(promptToSend);
    } catch (err: any) {
      setInputPrompt(promptToSend);
      setSendError(err?.message || "Gagal mengirim instruksi ke AKSA.");
    }
  };

  const toggleTrace = (msgId: string) => {
    setExpandedTraces((prev) => ({ ...prev, [msgId]: !prev[msgId] }));
  };

  const handleOpenArtifact = async (art: FileArtifact) => {
    const ok = await openFileInDefaultApp(art.file_path);
    if (!ok) {
      toast.error(
        `Tidak dapat membuka file "${art.name}". Pastikan file berada di dalam folder ruang kerja yang diizinkan.`
      );
    }
  };

  const handleOpenArtifactFolder = async (art: FileArtifact) => {
    const folder = getParentFolderPath(art.file_path);
    const ok = await openFileInDefaultApp(folder);
    if (!ok) {
      toast.error(
        `Tidak dapat membuka lokasi folder "${folder}". Periksa pengaturan folder di Pusat Akses.`
      );
    }
  };

  return (
    <div className="flex-1 flex flex-col h-full bg-[#191918] overflow-hidden">
      {/* Skippable First-Time Onboarding Modal */}
      {onboardingStep !== null && (
        <div
          role="dialog"
          aria-modal="true"
          aria-labelledby="aksa-onboarding-title"
          className="fixed inset-0 z-40 flex items-center justify-center bg-black/75 backdrop-blur-sm p-4"
        >
          <div className="w-full max-w-lg rounded-2xl bg-[#21211F] border border-white/[0.12] shadow-2xl p-6 space-y-5">
            <div className="flex items-center justify-between">
              <span className="inline-flex items-center gap-1.5 rounded-full bg-[#D97757]/15 border border-[#D97757]/30 px-3 py-1 text-xs font-semibold text-[#F09373]">
                Panduan Singkat • Langkah {onboardingStep + 1} dari {ONBOARDING_STEPS.length}
              </span>
              <button
                type="button"
                onClick={completeOnboarding}
                className="text-xs text-zinc-400 hover:text-zinc-100 underline-offset-2 hover:underline"
              >
                Lewati panduan
              </button>
            </div>

            <div className="space-y-2">
              <h2 id="aksa-onboarding-title" className="text-[20px] font-semibold text-zinc-100">
                {ONBOARDING_STEPS[onboardingStep].title}
              </h2>
              <p className="text-[14px] text-zinc-300 leading-relaxed">
                {ONBOARDING_STEPS[onboardingStep].description}
              </p>
            </div>

            {/* Step indicators */}
            <div className="flex items-center gap-1.5 pt-1">
              {ONBOARDING_STEPS.map((s, idx) => (
                <div
                  key={s.step}
                  className={cn(
                    "h-1.5 rounded-full transition-all",
                    idx === onboardingStep ? "w-8 bg-[#D97757]" : "w-3 bg-white/[0.12]"
                  )}
                />
              ))}
            </div>

            <div className="flex items-center justify-between pt-2 border-t border-white/[0.07]">
              <button
                type="button"
                disabled={onboardingStep === 0}
                onClick={() => setOnboardingStep((prev) => (prev && prev > 0 ? prev - 1 : 0))}
                className="rounded-xl bg-[#262624] hover:bg-zinc-700 disabled:opacity-30 border border-white/[0.08] px-3.5 py-2 text-xs font-medium text-zinc-200 transition-colors"
              >
                Sebelumnya
              </button>

              {onboardingStep < ONBOARDING_STEPS.length - 1 ? (
                <button
                  type="button"
                  onClick={() => setOnboardingStep((prev) => (prev !== null ? prev + 1 : 0))}
                  className="rounded-xl bg-[#D97757] hover:bg-[#c96a4b] px-4 py-2 text-[13px] font-semibold text-white transition-colors"
                >
                  Lanjut
                </button>
              ) : (
                <button
                  type="button"
                  onClick={() => {
                    completeOnboarding();
                    handleSelectActivity(ACTIVITY_CARDS[0].defaultPrompt);
                  }}
                  className="rounded-xl bg-[#D97757] hover:bg-[#c96a4b] px-4 py-2 text-[13px] font-semibold text-white transition-colors"
                >
                  Coba Tugas Pertama
                </button>
              )}
            </div>
          </div>
        </div>
      )}

      {/* Main Conversation Stream */}
      <div className="flex-1 overflow-y-auto px-6 py-8">
        <div className="max-w-[780px] mx-auto space-y-8">
          {messages.length === 0 ? (
            /* Everyday User Home / Welcome State (Section 5.1) */
            <div className="min-h-[60vh] flex flex-col items-center justify-center space-y-7 py-4">
              <div className="text-center space-y-3 max-w-xl">
                <div className="flex h-12 w-12 items-center justify-center rounded-2xl bg-[#D97757]/12 border border-[#D97757]/35 text-[#D97757] shadow-lg shadow-[#D97757]/5 mx-auto">
                  <svg
                    width={28}
                    height={28}
                    viewBox="0 0 256 256"
                    fill="none"
                    xmlns="http://www.w3.org/2000/svg"
                  >
                    <polygon points="94,164 128,138 128,164 86,194" fill="#FFD0BF" />
                    <polygon points="128,138 162,164 170,194 128,164" fill="#F09373" />
                    <path
                      d="M 128 36 C 135 36 141 40 144 47 L 208 191 C 211 198 206 205 198 205 L 179 205 C 173 205 168 201 166 195 L 128 80 Z"
                      fill="#C65D3D"
                    />
                    <path
                      d="M 128 36 L 128 80 L 90 195 C 88 201 83 205 77 205 L 58 205 C 50 205 45 198 48 191 L 112 47 C 115 40 121 36 128 36 Z"
                      fill="#E88464"
                    />
                    <path
                      d="M 128 103 C 129.3 111 131.8 113.5 140 115 C 131.8 116.5 129.3 119 128 127 C 126.7 119 124.2 116.5 116 115 C 124.2 113.5 126.7 111 128 103 Z"
                      fill="#FFF5F0"
                    />
                  </svg>
                </div>

                <h1 className="text-[22px] sm:text-[24px] font-semibold tracking-tight text-zinc-100">
                  Halo, apa yang ingin Anda kerjakan?
                </h1>
                <p className="text-[14px] text-zinc-300 leading-relaxed">
                  Ceritakan pekerjaan yang ingin diselesaikan. AKSA akan membantu menentukan langkah
                  yang diperlukan.
                </p>
              </div>

              {/* 4 Everyday Activity Cards */}
              <div className="w-full grid grid-cols-1 sm:grid-cols-2 gap-3.5">
                {ACTIVITY_CARDS.map((card) => {
                  const Icon = card.icon;
                  return (
                    <button
                      type="button"
                      key={card.id}
                      onClick={() => handleSelectActivity(card.defaultPrompt)}
                      className="group rounded-2xl bg-[#21211F] hover:bg-[#262624] border border-white/[0.08] hover:border-[#D97757]/50 p-4 text-left transition-all shadow-sm focus:outline-none focus:ring-2 focus:ring-[#D97757]/50 space-y-2.5"
                    >
                      <div className="flex items-center justify-between">
                        <div className="flex items-center gap-2.5">
                          <div
                            className={cn(
                              "flex h-9 w-9 items-center justify-center rounded-xl border",
                              card.accentClass
                            )}
                          >
                            <Icon size={18} />
                          </div>
                          <h2 className="text-[15px] font-semibold text-zinc-100 group-hover:text-white">
                            {card.title}
                          </h2>
                        </div>
                        <span className="text-xs text-[#D97757] opacity-80 group-hover:opacity-100 font-medium">
                          Pilih →
                        </span>
                      </div>

                      <ul className="space-y-1 pl-1 text-[13px] text-zinc-300">
                        {card.bullets.map((b) => (
                          <li key={b} className="flex items-center gap-2">
                            <span className="h-1.5 w-1.5 rounded-full bg-zinc-500 shrink-0" />
                            <span>{b}</span>
                          </li>
                        ))}
                      </ul>
                    </button>
                  );
                })}
              </div>

              <div className="flex flex-wrap items-center justify-center gap-3 text-xs text-zinc-400">
                <span className="inline-flex items-center gap-1.5">
                  <ShieldCheck size={14} className="text-emerald-400" />
                  <span>Izin akses hanya diminta saat dibutuhkan</span>
                </span>
                <span>•</span>
                <button
                  type="button"
                  onClick={() => setOnboardingStep(0)}
                  className="inline-flex items-center gap-1 text-zinc-300 hover:text-white underline-offset-2 hover:underline"
                >
                  <HelpCircle size={13} />
                  <span>Lihat panduan singkat AKSA</span>
                </button>
              </div>
            </div>
          ) : (
            messages.map((msg) => {
              const isUser = msg.sender_role === "user";
              const isExpanded = expandedTraces[msg.id] ?? false;
              const totalSavedInMsg =
                msg.execution_steps?.reduce((acc, s) => acc + s.tokens_saved, 0) ?? 0;

              if (isUser) {
                return (
                  <div key={msg.id} className="flex justify-end">
                    <div className="max-w-[82%] rounded-2xl bg-[#262624] border border-white/[0.08] px-4 py-3 text-[14px] leading-relaxed text-zinc-100">
                      {msg.content}
                    </div>
                  </div>
                );
              }

              return (
                <div key={msg.id} className="space-y-3.5">
                  {/* Sender Header & Work Status */}
                  <div className="flex flex-wrap items-center justify-between gap-2">
                    <div className="flex items-center gap-2">
                      <div className="flex h-6 w-6 items-center justify-center rounded-lg bg-[#D97757]/15 text-[#D97757]">
                        <Sparkles size={13} strokeWidth={2} />
                      </div>
                      <span className="text-[13px] font-semibold text-zinc-200">
                        AKSA ({msg.sender_name})
                      </span>
                      <span className="text-xs text-zinc-400">{msg.timestamp_label}</span>
                    </div>

                    <StatusBadge tone="success" label="Pekerjaan Selesai" />
                  </div>

                  {/* Step Summary & Collapsible "Detail aktivitas" (Section 5.1) */}
                  {msg.execution_steps && msg.execution_steps.length > 0 && (
                    <div className="rounded-xl bg-[#21211F] border border-white/[0.07] p-3.5 space-y-2.5">
                      <div className="flex flex-wrap items-center justify-between gap-2">
                        <div className="text-[13px] font-medium text-zinc-200 flex items-center gap-2">
                          <CheckCircle2 size={15} className="text-emerald-400 shrink-0" />
                          <span>
                            Menyelesaikan {msg.execution_steps.length} tahapan pekerjaan
                          </span>
                        </div>

                        <button
                          type="button"
                          onClick={() => toggleTrace(msg.id)}
                          aria-expanded={isExpanded}
                          className="inline-flex items-center gap-1.5 rounded-lg py-1 px-2.5 text-xs font-medium text-zinc-300 hover:text-white bg-white/[0.04] hover:bg-white/[0.08] transition-colors"
                        >
                          {isExpanded ? <ChevronDown size={13} /> : <ChevronRight size={13} />}
                          <span>Detail aktivitas</span>
                        </button>
                      </div>

                      {/* Friendly Step List Always Readable */}
                      <ol className="space-y-1.5 pl-1 text-[13px] text-zinc-300">
                        {msg.execution_steps.map((step, i) => (
                          <li key={step.id} className="flex items-center justify-between gap-2">
                            <span className="truncate">
                              {i + 1}. {step.action_label}
                            </span>
                            <span className="text-xs font-medium text-emerald-400 shrink-0">
                              Selesai
                            </span>
                          </li>
                        ))}
                      </ol>

                      {/* Progressive Disclosure: Technical Agent, Model, Provider & Token Details */}
                      {isExpanded && (
                        <div className="mt-2 pt-2.5 border-t border-white/[0.07] space-y-2.5">
                          <div className="text-xs text-zinc-400 flex items-center justify-between">
                            <span>Rincian Teknis Agen &amp; Model AI</span>
                            <span>Kuota dihemat: {formatNumberID(totalSavedInMsg)} token</span>
                          </div>
                          {msg.execution_steps.map((step) => {
                            const badge = getProviderBadgeStyle(step.provider);
                            return (
                              <div
                                key={`${step.id}_tech`}
                                className="rounded-lg bg-[#191918] border border-white/[0.06] p-2.5 space-y-1"
                              >
                                <div className="flex flex-wrap items-center gap-2">
                                  <span className="text-xs font-semibold text-zinc-200">
                                    {step.agent_name}
                                  </span>
                                  <span
                                    className={cn(
                                      "inline-flex items-center gap-1 rounded border px-1.5 py-0.5 text-[11px]",
                                      badge.badgeClass
                                    )}
                                  >
                                    <ProviderIcon provider={step.provider} size={11} />
                                    <span>
                                      {badge.label} · {step.model_id}
                                    </span>
                                  </span>
                                  <span className="text-[11px] text-zinc-400 font-mono">
                                    {formatNumberID(step.tokens_used)} token
                                  </span>
                                </div>
                                <div className="text-xs text-zinc-300">{step.detail}</div>
                              </div>
                            );
                          })}
                        </div>
                      )}
                    </div>
                  )}

                  {/* Result Summary Content */}
                  <div className="rounded-2xl bg-[#21211F]/60 border border-white/[0.06] p-4 text-[14px] leading-relaxed text-zinc-100 space-y-3">
                    <ReactMarkdown
                      components={{
                        p: ({ children }) => (
                          <p className="mb-3 leading-7 text-zinc-100 last:mb-0">{children}</p>
                        ),
                        strong: ({ children }) => (
                          <strong className="font-semibold text-white">{children}</strong>
                        ),
                        ul: ({ children }) => (
                          <ul className="list-disc pl-5 mb-3 space-y-1.5 text-zinc-200">
                            {children}
                          </ul>
                        ),
                        ol: ({ children }) => (
                          <ol className="list-decimal pl-5 mb-3 space-y-1.5 text-zinc-200">
                            {children}
                          </ol>
                        ),
                        li: ({ children }) => <li className="leading-6 text-zinc-200">{children}</li>,
                        code: ({ children, className }) => {
                          const isInline = !className;
                          return isInline ? (
                            <code className="rounded bg-white/[0.08] px-1.5 py-0.5 font-mono text-xs text-[#F09373]">
                              {children}
                            </code>
                          ) : (
                            <pre className="rounded-xl bg-black/40 border border-white/[0.08] p-3 overflow-x-auto text-xs font-mono text-zinc-200 my-2">
                              <code>{children}</code>
                            </pre>
                          );
                        },
                      }}
                    >
                      {msg.content}
                    </ReactMarkdown>

                    {/* Work Artifacts & Actionable Next Steps (Section 5.1) */}
                    {msg.artifacts && msg.artifacts.length > 0 && (
                      <div className="pt-3 border-t border-white/[0.07] space-y-2.5">
                        <div className="text-xs font-semibold text-zinc-300">
                          File Hasil Pekerjaan ({msg.artifacts.length}):
                        </div>
                        <div className="grid grid-cols-1 gap-2.5">
                          {msg.artifacts.map((art) => (
                            <div
                              key={art.id}
                              className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 rounded-xl bg-[#262624] border border-white/[0.09] p-3.5"
                            >
                              <div className="flex items-center gap-3 min-w-0 flex-1">
                                <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl bg-white/[0.05] border border-white/[0.08]">
                                  {art.file_type === "xlsx" ? (
                                    <FileSpreadsheet size={18} className="text-emerald-400" />
                                  ) : (
                                    <FileText size={18} className="text-sky-400" />
                                  )}
                                </div>
                                <div className="min-w-0 flex-1">
                                  <div className="text-[13.5px] font-semibold text-zinc-100 truncate">
                                    {art.name}
                                  </div>
                                  <div className="text-xs text-zinc-400 truncate mt-0.5">
                                    {art.summary || `Dokumen ${art.file_type.toUpperCase()} (${art.size_label})`}
                                  </div>
                                </div>
                              </div>

                              <div className="flex items-center gap-2 shrink-0">
                                <button
                                  type="button"
                                  onClick={() => void handleOpenArtifact(art)}
                                  className="flex items-center gap-1.5 rounded-xl bg-[#D97757] hover:bg-[#c96a4b] text-white px-3 py-1.5 text-xs font-semibold transition-colors"
                                >
                                  <ExternalLink size={12} />
                                  <span>Buka Hasil</span>
                                </button>
                                <button
                                  type="button"
                                  onClick={() => void handleOpenArtifactFolder(art)}
                                  className="flex items-center gap-1.5 rounded-xl bg-white/[0.06] hover:bg-white/[0.12] border border-white/[0.1] text-zinc-200 px-3 py-1.5 text-xs font-medium transition-colors"
                                >
                                  <FolderOpen size={12} />
                                  <span>Buka Lokasi File</span>
                                </button>
                              </div>
                            </div>
                          ))}
                        </div>
                      </div>
                    )}

                    {/* Relevant Follow-up Suggestions */}
                    <div className="pt-2 flex flex-wrap items-center gap-2 text-xs text-zinc-400">
                      <span>Langkah lanjutan:</span>
                      <button
                        type="button"
                        onClick={() =>
                          handleSelectActivity("Buatkan ringkasan poin penting dari hasil pekerjaan di atas.")
                        }
                        className="rounded-lg bg-white/[0.04] hover:bg-white/[0.09] border border-white/[0.07] px-2.5 py-1 text-zinc-300 hover:text-white transition-colors"
                      >
                        Rangkum hasil
                      </button>
                      <button
                        type="button"
                        onClick={() =>
                          handleSelectActivity("Rapikan kembali format laporan tersebut agar siap dipresentasikan.")
                        }
                        className="rounded-lg bg-white/[0.04] hover:bg-white/[0.09] border border-white/[0.07] px-2.5 py-1 text-zinc-300 hover:text-white transition-colors"
                      >
                        Sesuaikan format
                      </button>
                    </div>
                  </div>
                </div>
              );
            })
          )}

          {/* Live Execution Status Card (Section 5.1 Status Eksekusi) */}
          {isExecuting && (
            <div
              role="status"
              aria-live="polite"
              className="rounded-2xl bg-[#21211F] border border-white/[0.1] p-5 space-y-4 shadow-xl"
            >
              <div className="flex flex-wrap items-center justify-between gap-2 border-b border-white/[0.07] pb-3">
                <div className="flex items-center gap-2.5">
                  <div className="flex h-7 w-7 items-center justify-center rounded-lg bg-[#D97757]/20 text-[#D97757]">
                    <Loader2 size={15} className="animate-spin" />
                  </div>
                  <div>
                    <div className="text-[14px] font-semibold text-zinc-100">
                      {activeAgentStep || "Sedang mengerjakan permintaan Anda..."}
                    </div>
                    <div className="text-xs text-zinc-400">
                      AKSA sedang menjalankan langkah-langkah yang diperlukan
                    </div>
                  </div>
                </div>

                <span className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full bg-emerald-500/15 border border-emerald-500/30 text-xs text-emerald-300 font-medium">
                  <span className="w-2 h-2 rounded-full bg-emerald-400 animate-ping" />
                  <span>Sedang dikerjakan</span>
                </span>
              </div>

              {/* Numbered Steps Checklist: Completed, Running, Next Pending */}
              <ol className="space-y-2.5 text-[13.5px]">
                {liveExecutionSteps.map((step, idx) => {
                  const isRunning = step.status === "running";
                  const isDone = step.status === "completed";
                  return (
                    <li
                      key={step.id || idx}
                      className="flex items-center justify-between gap-3 rounded-xl bg-[#262624]/80 border border-white/[0.06] px-3.5 py-2.5"
                    >
                      <div className="flex items-center gap-2.5 min-w-0">
                        {isDone ? (
                          <CheckCircle2 size={16} className="text-emerald-400 shrink-0" />
                        ) : isRunning ? (
                          <Loader2 size={16} className="text-[#D97757] animate-spin shrink-0" />
                        ) : (
                          <Clock size={16} className="text-zinc-500 shrink-0" />
                        )}
                        <span className="text-zinc-100 truncate">
                          {idx + 1}. {step.action_label}
                        </span>
                      </div>
                      <span
                        className={cn(
                          "text-xs font-medium shrink-0",
                          isDone
                            ? "text-emerald-400"
                            : isRunning
                            ? "text-[#F09373]"
                            : "text-zinc-400"
                        )}
                      >
                        {isDone ? "Selesai" : isRunning ? "Sedang dikerjakan" : "Menunggu"}
                      </span>
                    </li>
                  );
                })}
                <li className="flex items-center justify-between gap-3 rounded-xl bg-[#191918]/60 border border-white/[0.05] px-3.5 py-2 text-zinc-400">
                  <div className="flex items-center gap-2.5">
                    <Clock size={15} className="text-zinc-500 shrink-0" />
                    <span>{liveExecutionSteps.length + 1}. Menyimpan dan menyiapkan hasil akhir</span>
                  </div>
                  <span className="text-xs">Menunggu</span>
                </li>
              </ol>

              {/* Notice if User Approval is Pending */}
              {pendingApprovals.length > 0 && (
                <div className="rounded-xl bg-amber-500/15 border border-amber-500/35 p-3 flex items-center justify-between gap-3 text-xs text-amber-200">
                  <div className="flex items-center gap-2">
                    <AlertTriangle size={15} className="text-amber-400 shrink-0" />
                    <span>
                      Tindakan memerlukan persetujuan Anda sebelum AKSA dapat melanjutkan.
                    </span>
                  </div>
                  <span className="font-semibold">Menunggu Persetujuan</span>
                </div>
              )}

              {/* Progressive Disclosure for Technical Execution Details */}
              <div className="pt-1">
                <button
                  type="button"
                  onClick={() => setShowLiveDetails((v) => !v)}
                  className="inline-flex items-center gap-1.5 text-xs text-zinc-400 hover:text-zinc-200"
                >
                  {showLiveDetails ? <ChevronDown size={13} /> : <ChevronRight size={13} />}
                  <span>Detail aktivitas</span>
                </button>
                {showLiveDetails && (
                  <div className="mt-2 space-y-2 rounded-xl bg-[#191918] border border-white/[0.06] p-3 text-xs text-zinc-300">
                    {liveExecutionSteps.map((step) => {
                      const badge = getProviderBadgeStyle(step.provider);
                      return (
                        <div key={`${step.id}_live_detail`} className="flex flex-wrap items-center justify-between gap-2">
                          <span>
                            <strong>{step.agent_name}</strong> — {step.detail}
                          </span>
                          <span className="font-mono text-[11px] text-zinc-400">
                            {badge.label} · {step.model_id}
                          </span>
                        </div>
                      );
                    })}
                  </div>
                )}
              </div>
            </div>
          )}

          {sendError && (
            <ErrorStateCard
              title="Instruksi belum berhasil dikirim"
              cause={sendError}
              nextStep="Periksa apakah layanan AKSA aktif atau klik Coba Lagi."
              onRetry={() => {
                if (inputPrompt.trim()) {
                  void sendUserPrompt(inputPrompt);
                }
              }}
              onDismiss={() => setSendError(null)}
            />
          )}

          <div ref={messagesEndRef} />
        </div>
      </div>

      {/* Bottom Instruction Composer (Section 5.1 Input Instruksi) */}
      <div className="px-6 pb-5 pt-2 bg-gradient-to-t from-[#191918] via-[#191918] to-transparent">
        <div className="max-w-[740px] mx-auto space-y-2">
          {emptyHintWarning && (
            <div
              role="alert"
              className="rounded-xl bg-amber-500/12 border border-amber-500/30 px-3.5 py-2 text-xs text-amber-200 flex items-center justify-between"
            >
              <span>{emptyHintWarning}</span>
              <button
                type="button"
                onClick={() => setEmptyHintWarning(null)}
                className="text-amber-300 hover:text-white ml-2 font-medium"
              >
                Tutup
              </button>
            </div>
          )}

          <form
            onSubmit={(e) => void handleSubmit(e)}
            className="flex items-center gap-2.5 rounded-2xl bg-[#21211F] border border-white/[0.1] focus-within:border-[#D97757]/70 shadow-xl px-4 py-3 transition-colors"
          >
            <button
              type="button"
              onClick={() => setActiveNav("izin_pc")}
              title={
                activeWorkspace
                  ? `Menggunakan file di folder: ${activeWorkspace.name}`
                  : "Pilih folder ruang kerja untuk membaca atau menyimpan file"
              }
              className="flex items-center gap-1.5 rounded-xl bg-white/[0.05] hover:bg-white/[0.1] border border-white/[0.08] px-2.5 py-1.5 text-xs text-zinc-300 shrink-0 transition-colors"
            >
              <Paperclip size={13} className="text-[#D97757]" />
              <span className="hidden sm:inline max-w-[130px] truncate">
                {activeWorkspace ? activeWorkspace.name : "Folder Kerja"}
              </span>
            </button>

            <input
              ref={inputRef}
              type="text"
              value={inputPrompt}
              onChange={(e) => {
                setInputPrompt(e.target.value);
                if (emptyHintWarning) setEmptyHintWarning(null);
              }}
              aria-label="Ceritakan pekerjaan yang ingin Anda selesaikan"
              placeholder="Ceritakan pekerjaan yang ingin Anda selesaikan..."
              className="flex-1 bg-transparent text-[14px] text-zinc-100 placeholder:text-zinc-400 focus:outline-none"
            />

            <button
              type="submit"
              disabled={isExecuting}
              className={cn(
                "flex items-center gap-1.5 rounded-xl px-3.5 py-2 text-[13px] font-semibold transition-all shrink-0 focus:outline-none focus:ring-2 focus:ring-[#D97757]/50",
                inputPrompt.trim() && !isExecuting
                  ? "bg-[#D97757] hover:bg-[#c96a4b] text-white"
                  : "bg-white/[0.07] text-zinc-300 hover:bg-white/[0.12]"
              )}
              title="Kirim Instruksi"
            >
              <span>Kirim</span>
              <ArrowUp size={15} strokeWidth={2.2} />
            </button>
          </form>

          {/* File Type Guidance Note */}
          <div className="flex flex-wrap items-center justify-between gap-2 px-1 text-xs text-zinc-400">
            <span>
              Mendukung dokumen: <strong>PDF, Word (.docx), Excel (.xlsx), PowerPoint (.pptx), CSV</strong>, dan file teks di Ruang Kerja Anda.
            </span>
            <span>AKSA memilih agen &amp; model secara otomatis</span>
          </div>
        </div>
      </div>
    </div>
  );
};
