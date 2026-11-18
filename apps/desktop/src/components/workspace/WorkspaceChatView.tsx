import React, { useEffect, useRef, useState } from "react";
import ReactMarkdown from "react-markdown";
import {
  ArrowUp,
  BrainCircuit,
  CheckCircle2,
  ChevronDown,
  ChevronRight,
  FileSpreadsheet,
  FileText,
  ExternalLink,
  Loader2,
  Sparkles,
} from "lucide-react";
import { useAksaStore } from "@/stores/useAksaStore";
import { cn, formatNumberID, getProviderBadgeStyle } from "@/lib/utils";
import { ProviderIcon, ToolCategoryIcon } from "@/components/ui/DynamicIcon";
import { openFileInDefaultApp } from "@/services/engineClient";

const QUICK_PROMPTS: { label: string; prompt: string; category: string }[] = [
  {
    label: "Rekap Excel & Grafik",
    prompt: "Rekap data penjualan di folder ini ke Excel lengkap dengan rumus SUM & grafik",
    category: "office_excel",
  },
  {
    label: "Surat Resmi Word",
    prompt: "Buatkan Surat Penawaran Resmi di Word sesuai arsip proyek di folder ini",
    category: "office_word",
  },
  {
    label: "Riset Dokumen RAG",
    prompt: "Cari semua nomor invoice & nilai kontrak dari PDF di Basis Pengetahuan RAG",
    category: "rag_search",
  },
  {
    label: "Otomasi CSV Python",
    prompt: "Jalankan skrip Python untuk merapikan semua file CSV di folder ini",
    category: "uv_python",
  },
];

export const WorkspaceChatView: React.FC = () => {
  const {
    messages,
    sendUserPrompt,
    workspaces,
    activeWorkspaceId,
    isExecuting,
    activeAgentId,
    activeAgentStep,
    liveExecutionSteps,
    teams,
    activeTeamId,
  } = useAksaStore();
  const [inputPrompt, setInputPrompt] = useState("");
  const [expandedTraces, setExpandedTraces] = useState<Record<string, boolean>>({
    msg_2: false,
  });

  const messagesEndRef = useRef<HTMLDivElement>(null);
  const activeWorkspace = workspaces.find((w) => w.id === activeWorkspaceId) ?? workspaces[0];
  const activeTeam = teams.find((t) => t.id === activeTeamId) ?? teams[0];
  const currentActiveAgent = activeTeam?.agents.find((a) => a.id === activeAgentId) ?? null;

  const scrollToBottom = (behavior: ScrollBehavior = "smooth") => {
    messagesEndRef.current?.scrollIntoView({ behavior, block: "end" });
  };

  useEffect(() => {
    scrollToBottom();
  }, [messages.length, isExecuting, liveExecutionSteps.length]);

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!inputPrompt.trim() || isExecuting) return;
    const promptToSend = inputPrompt;
    setInputPrompt("");
    void sendUserPrompt(promptToSend);
  };

  const toggleTrace = (msgId: string) => {
    setExpandedTraces((prev) => ({ ...prev, [msgId]: !prev[msgId] }));
  };

  return (
    <div className="flex-1 flex flex-col h-full bg-[#191918] overflow-hidden">
      {/* Main Conversation Stream (Claude Desktop Editorial Layout) */}
      <div className="flex-1 overflow-y-auto px-6 py-8">
        <div className="max-w-[720px] mx-auto space-y-8">
          {messages.length === 0 ? (
            /* Minimal Clean Empty State */
            <div className="min-h-[58vh] flex flex-col items-center justify-center text-center space-y-3.5">
              <div className="flex h-12 w-12 items-center justify-center rounded-2xl bg-[#D97757]/12 border border-[#D97757]/35 text-[#D97757] shadow-lg shadow-[#D97757]/5">
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

              <div className="space-y-1.5">
                <h1 className="text-lg sm:text-xl font-semibold tracking-tight text-zinc-100">
                  Apa yang bisa AKSA bantu hari ini?
                </h1>
                <p className="text-xs text-zinc-400 max-w-md mx-auto">
                  Berikan instruksi pembuatan dokumen, analisis arsip, atau automasi PC ke tim agen Anda.
                </p>
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
                  <div className="max-w-[82%] rounded-2xl bg-[#262624] border border-white/[0.06] px-4 py-3 text-[13.5px] leading-relaxed text-zinc-100">
                    {msg.content}
                  </div>
                </div>
              );
            }

            return (
              <div key={msg.id} className="space-y-3.5">
                {/* Sender Header */}
                <div className="flex items-center gap-2">
                  <div className="flex h-5 w-5 items-center justify-center rounded-md bg-[#D97757]/15 text-[#D97757]">
                    <Sparkles size={11} strokeWidth={2} />
                  </div>
                  <span className="text-xs font-medium text-zinc-300">{msg.sender_name}</span>
                  <span className="text-[11px] text-zinc-500">{msg.timestamp_label}</span>
                </div>

                {/* Claude-style Subtle Collapsible "Thinking / Sub-Agent Delegation" Accordion */}
                {msg.execution_steps && msg.execution_steps.length > 0 && (
                  <div className="pl-1">
                    <button
                      onClick={() => toggleTrace(msg.id)}
                      className="inline-flex items-center gap-2 rounded-lg py-1 px-2 -ml-2 text-xs text-zinc-400 hover:text-zinc-200 hover:bg-white/[0.04] transition-colors"
                    >
                      {isExpanded ? <ChevronDown size={13} /> : <ChevronRight size={13} />}
                      <span>
                        Mengoordinasikan {msg.execution_steps.length} sub-agen spesialis
                      </span>
                      <span className="text-zinc-600">•</span>
                      <span className="text-[11px] text-zinc-500">
                        Hemat {formatNumberID(totalSavedInMsg)} token
                      </span>
                    </button>

                    {isExpanded && (
                      <div className="mt-2 ml-1.5 pl-3.5 border-l border-white/[0.08] space-y-3 py-1">
                        {msg.execution_steps.map((step) => {
                          const badge = getProviderBadgeStyle(step.provider);
                          return (
                            <div key={step.id} className="space-y-1">
                              <div className="flex flex-wrap items-center gap-2">
                                <span className="text-xs font-medium text-zinc-200">
                                  {step.agent_name}
                                </span>
                                <span
                                  className={cn(
                                    "inline-flex items-center gap-1 rounded border px-1.5 py-0.5 text-[10px]",
                                    badge.badgeClass
                                  )}
                                >
                                  <ProviderIcon provider={step.provider} size={10} />
                                  <span>
                                    {badge.label} · {step.model_id}
                                  </span>
                                </span>
                                <span className="text-[10px] text-zinc-500 font-mono">
                                  {formatNumberID(step.tokens_used)} tok
                                </span>
                              </div>
                              <div className="text-xs text-zinc-400">{step.action_label}</div>
                              <div className="text-[11px] text-zinc-500">{step.detail}</div>
                            </div>
                          );
                        })}
                      </div>
                    )}
                  </div>
                )}

                {/* Assistant Editorial Text with Rich Markdown Rendering */}
                <div className="pl-1 text-[13.5px] leading-relaxed text-zinc-200">
                  <ReactMarkdown
                    components={{
                      p: ({ children }) => (
                        <p className="mb-3.5 leading-7 text-zinc-200 last:mb-0">{children}</p>
                      ),
                      strong: ({ children }) => (
                        <strong className="font-semibold text-zinc-100">{children}</strong>
                      ),
                      ul: ({ children }) => (
                        <ul className="list-disc pl-5 mb-3.5 space-y-1.5 text-zinc-200">
                          {children}
                        </ul>
                      ),
                      ol: ({ children }) => (
                        <ol className="list-decimal pl-5 mb-3.5 space-y-1.5 text-zinc-200">
                          {children}
                        </ol>
                      ),
                      li: ({ children }) => <li className="leading-6 text-zinc-200">{children}</li>,
                      h1: ({ children }) => (
                        <h1 className="text-base font-bold text-zinc-100 mt-4 mb-2">{children}</h1>
                      ),
                      h2: ({ children }) => (
                        <h2 className="text-sm font-bold text-zinc-100 mt-3.5 mb-2">{children}</h2>
                      ),
                      h3: ({ children }) => (
                        <h3 className="text-xs font-semibold text-zinc-200 mt-2.5 mb-1.5">
                          {children}
                        </h3>
                      ),
                      code: ({ children, className }) => {
                        const isInline = !className;
                        return isInline ? (
                          <code className="rounded bg-white/[0.08] px-1.5 py-0.5 font-mono text-[12px] text-[#D97757]">
                            {children}
                          </code>
                        ) : (
                          <pre className="rounded-xl bg-black/40 border border-white/[0.08] p-3 overflow-x-auto text-xs font-mono text-zinc-200 my-2">
                            <code>{children}</code>
                          </pre>
                        );
                      },
                      hr: () => <hr className="border-white/[0.08] my-4" />,
                      blockquote: ({ children }) => (
                        <blockquote className="border-l-2 border-[#D97757] pl-3 italic text-zinc-400 my-2">
                          {children}
                        </blockquote>
                      ),
                    }}
                  >
                    {msg.content}
                  </ReactMarkdown>
                </div>

                {/* Claude-style Clean Artifact Cards */}
                {msg.artifacts && msg.artifacts.length > 0 && (
                  <div className="pl-1 grid grid-cols-1 sm:grid-cols-2 gap-2.5 pt-1">
                    {msg.artifacts.map((art) => (
                      <div
                        key={art.id}
                        className="group flex items-center justify-between gap-3 rounded-xl bg-[#21211F] hover:bg-[#262624] border border-white/[0.07] hover:border-white/[0.14] p-3 text-left transition-all"
                      >
                        <div
                          className="flex items-center gap-3 min-w-0 flex-1 cursor-pointer"
                          onClick={() => void openFileInDefaultApp(art.file_path)}
                          title="Klik untuk membuka file di aplikasi Office default"
                        >
                          <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-lg bg-white/[0.04] border border-white/[0.06] group-hover:border-[#D97757]/40 transition-colors">
                            {art.file_type === "xlsx" ? (
                              <FileSpreadsheet size={16} className="text-emerald-400/90" />
                            ) : (
                              <FileText size={16} className="text-sky-400/90" />
                            )}
                          </div>
                          <div className="min-w-0 flex-1">
                            <div className="text-xs font-medium text-zinc-100 truncate group-hover:text-white transition-colors">
                              {art.name}
                            </div>
                            <div className="text-[11px] text-zinc-500 truncate mt-0.5">
                              Dokumen {art.file_type.toUpperCase()} · {art.size_label}
                            </div>
                          </div>
                        </div>

                        <button
                          onClick={() => void openFileInDefaultApp(art.file_path)}
                          className="shrink-0 flex items-center gap-1 rounded-lg bg-white/[0.05] hover:bg-[#D97757] text-zinc-300 hover:text-white border border-white/[0.08] px-2.5 py-1 text-[11px] font-medium transition-colors"
                          title="Buka langsung di aplikasi PC"
                        >
                          <ExternalLink size={11} />
                          <span>Buka</span>
                        </button>
                      </div>
                    ))}
                  </div>
                )}
              </div>
            );
          })
        )}

          {/* Claude / ChatGPT Signature Live Thought & Execution Trace Card */}
          {isExecuting && (
            <div className="space-y-3.5 pt-2 animate-in fade-in duration-300">
              {/* Active Agent Live Header */}
              <div className="flex items-center gap-2">
                <div className="flex h-5 w-5 items-center justify-center rounded-md bg-[#D97757]/20 text-[#D97757]">
                  <Loader2 size={12} className="animate-spin text-[#D97757]" />
                </div>
                <span className="text-xs font-semibold text-zinc-200">
                  {currentActiveAgent?.name ?? "Manajer Eksekutif"}
                </span>
                <span className="inline-flex items-center gap-1.5 px-2 py-0.5 rounded-full bg-emerald-500/15 border border-emerald-500/30 text-[10.5px] text-emerald-400 font-medium">
                  <span className="w-1.5 h-1.5 rounded-full bg-emerald-400 animate-ping" />
                  <span>Sedang Bekerja...</span>
                </span>
              </div>

              {/* Minimalist Structured Execution Box */}
              <div className="rounded-2xl bg-[#21211F]/95 border border-white/[0.09] p-4 space-y-3 shadow-xl backdrop-blur-sm">
                <div className="flex items-center justify-between text-xs text-zinc-400 border-b border-white/[0.06] pb-2.5">
                  <div className="flex items-center gap-2">
                    <BrainCircuit size={13} className="text-[#D97757]" />
                    <span className="font-medium text-zinc-200">
                      Alur Koordinasi &amp; Eksekusi Tim Agen
                    </span>
                  </div>
                  <span className="text-[11px] text-zinc-400 font-mono">
                    {activeAgentStep || "Menganalisis..."}
                  </span>
                </div>

                {/* Live Steps Progression */}
                <div className="space-y-3 pt-1">
                  {liveExecutionSteps.map((step, idx) => {
                    const isRunning = step.status === "running";
                    const isDone = step.status === "completed";
                    const badge = getProviderBadgeStyle(step.provider);

                    return (
                      <div key={step.id || idx} className="flex items-start gap-3 text-xs">
                        <div className="mt-0.5 shrink-0">
                          {isRunning ? (
                            <div className="w-4 h-4 rounded-full border-2 border-emerald-400 border-t-transparent animate-spin" />
                          ) : isDone ? (
                            <CheckCircle2 size={16} className="text-emerald-400" />
                          ) : (
                            <div className="w-4 h-4 rounded-full border border-zinc-600 bg-zinc-800" />
                          )}
                        </div>
                        <div className="flex-1 min-w-0 space-y-1">
                          <div className="flex flex-wrap items-center gap-2">
                            <span
                              className={cn(
                                "font-medium",
                                isRunning
                                  ? "text-emerald-300 font-semibold"
                                  : isDone
                                  ? "text-zinc-200"
                                  : "text-zinc-400"
                              )}
                            >
                              {step.agent_name}
                            </span>
                            <span
                              className={cn(
                                "inline-flex items-center gap-1 rounded border px-1.5 py-0.2 text-[9.5px]",
                                badge.badgeClass
                              )}
                            >
                              <ProviderIcon provider={step.provider} size={9} />
                              <span>
                                {badge.label} · {step.model_id}
                              </span>
                            </span>
                          </div>
                          <p className="text-[12px] text-zinc-300 leading-relaxed font-medium">
                            {step.action_label}
                          </p>
                          {step.detail && (
                            <p className="text-[11px] text-zinc-500 leading-relaxed">
                              {step.detail}
                            </p>
                          )}
                        </div>
                      </div>
                    );
                  })}
                </div>
              </div>
            </div>
          )}

          <div ref={messagesEndRef} />
        </div>
      </div>

      {/* Bottom Floating Composer (Simple & Clean) */}
      <div className="px-6 pb-5 pt-2 bg-gradient-to-t from-[#191918] via-[#191918] to-transparent">
        <div className="max-w-[680px] mx-auto space-y-2.5">
          <form
            onSubmit={handleSubmit}
            className="flex items-center gap-2 rounded-2xl bg-[#21211F] border border-white/[0.09] focus-within:border-white/[0.18] shadow-xl px-4 py-2.5 transition-colors"
          >
            <input
              type="text"
              value={inputPrompt}
              onChange={(e) => setInputPrompt(e.target.value)}
              placeholder={`Beri instruksi ke tim agen${activeWorkspace?.name ? ` (${activeWorkspace.name})` : ""}...`}
              className="flex-1 bg-transparent text-[13.5px] text-zinc-100 placeholder:text-zinc-500 focus:outline-none"
            />

            <button
              type="submit"
              disabled={!inputPrompt.trim()}
              className={cn(
                "flex h-8 w-8 shrink-0 items-center justify-center rounded-xl transition-all",
                inputPrompt.trim()
                  ? "bg-[#D97757] hover:bg-[#c96a4b] text-white"
                  : "bg-white/[0.06] text-zinc-500 cursor-not-allowed"
              )}
              title="Kirim Instruksi"
            >
              <ArrowUp size={15} strokeWidth={2.2} />
            </button>
          </form>

          {messages.length === 0 && (
            <div className="flex flex-wrap items-center justify-center gap-1.5">
              {QUICK_PROMPTS.map((qp) => (
                <button
                  key={qp.label}
                  onClick={() => setInputPrompt(qp.prompt)}
                  className="inline-flex items-center gap-1.5 rounded-full bg-white/[0.02] hover:bg-white/[0.06] border border-white/[0.07] px-3 py-1 text-[11px] text-zinc-400 hover:text-zinc-200 transition-colors"
                >
                  <ToolCategoryIcon category={qp.category} size={11} />
                  <span>{qp.label}</span>
                </button>
              ))}
            </div>
          )}
        </div>
      </div>
    </div>
  );
};
