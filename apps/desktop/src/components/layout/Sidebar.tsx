import React from "react";
import {
  MessageSquareText,
  Network,
  LayoutGrid,
  Sparkles,
  BookOpenCheck,
  Send,
  ShieldCheck,
  Settings,
  PanelLeftClose,
  PanelLeftOpen,
  Cpu,
} from "lucide-react";
import { useAksaStore } from "@/stores/useAksaStore";
import { cn } from "@/lib/utils";
import { AnimatedBrandIcon } from "@/components/ui/DynamicIcon";
import type { NavSection } from "@/types/aksa";

interface NavGroup {
  groupLabel: string;
  items: { id: NavSection; label: string; icon: React.ElementType }[];
}

const NAV_GROUPS: NavGroup[] = [
  {
    groupLabel: "PEKERJAAN",
    items: [
      {
        id: "ruang_kerja",
        label: "Ruang Kerja",
        icon: MessageSquareText,
      },
      {
        id: "tim_agen",
        label: "Tim AI",
        icon: Network,
      },
    ],
  },
  {
    groupLabel: "KEMAMPUAN",
    items: [
      {
        id: "aplikasi",
        label: "Aplikasi",
        icon: LayoutGrid,
      },
      {
        id: "keahlian",
        label: "Keahlian",
        icon: Sparkles,
      },
      {
        id: "pengetahuan_rag",
        label: "Pengetahuan",
        icon: BookOpenCheck,
      },
      {
        id: "telegram",
        label: "Integrasi",
        icon: Send,
      },
    ],
  },
  {
    groupLabel: "KONTROL",
    items: [
      {
        id: "izin_pc",
        label: "Pusat Akses",
        icon: ShieldCheck,
      },
      {
        id: "pengaturan",
        label: "Pengaturan",
        icon: Settings,
      },
    ],
  },
];

export const Sidebar: React.FC = () => {
  const {
    activeNav,
    setActiveNav,
    isSidebarCollapsed,
    toggleSidebar,
    engineHealth,
    totalTokensUsed,
    totalTokensSaved,
    isExecuting,
  } = useAksaStore();

  const hasTokenActivity = totalTokensUsed + totalTokensSaved > 0;
  const savingsRatio = hasTokenActivity
    ? Math.round((totalTokensSaved / (totalTokensUsed + totalTokensSaved)) * 100)
    : 0;

  return (
    <aside
      aria-label="Navigasi Utama AKSA"
      className={cn(
        "flex flex-col justify-between border-r border-white/[0.06] bg-[#141413] transition-all duration-200 select-none shrink-0",
        isSidebarCollapsed ? "w-[64px]" : "w-[236px]"
      )}
    >
      {/* Top Brand Header */}
      <div className="overflow-y-auto">
        <div className="flex items-center justify-between h-13 px-3 border-b border-white/[0.05]">
          {!isSidebarCollapsed && (
            <div className="flex items-center gap-2.5 pl-1">
              <AnimatedBrandIcon size={19} />
              <div className="flex items-baseline gap-1.5">
                <span className="font-semibold tracking-tight text-[14.5px] text-zinc-100">
                  AKSA
                </span>
                <span className="text-xs font-medium text-zinc-400">Asisten</span>
              </div>
            </div>
          )}

          <button
            type="button"
            onClick={toggleSidebar}
            aria-label={isSidebarCollapsed ? "Perluas Navigasi" : "Ciutkan Navigasi"}
            title={isSidebarCollapsed ? "Perluas Navigasi" : "Ciutkan Navigasi"}
            className={cn(
              "flex h-8 w-8 items-center justify-center rounded-lg text-zinc-400 hover:bg-white/[0.06] hover:text-zinc-100 transition-colors focus:outline-none focus:ring-2 focus:ring-[#D97757]/50",
              isSidebarCollapsed && "mx-auto"
            )}
          >
            {isSidebarCollapsed ? <PanelLeftOpen size={16} /> : <PanelLeftClose size={16} />}
          </button>
        </div>

        {/* Grouped Navigation Links */}
        <nav className="p-2.5 space-y-4">
          {NAV_GROUPS.map((group) => (
            <div key={group.groupLabel} className="space-y-1">
              {!isSidebarCollapsed && (
                <div className="px-2.5 pt-1 pb-0.5 text-[11px] font-semibold uppercase tracking-wider text-zinc-400">
                  {group.groupLabel}
                </div>
              )}

              <div className="space-y-0.5">
                {group.items.map((item) => {
                  const Icon = item.icon;
                  const isActive = activeNav === item.id;
                  const showRunningDot = item.id === "ruang_kerja" && isExecuting;
                  return (
                    <button
                      type="button"
                      key={item.id}
                      onClick={() => setActiveNav(item.id)}
                      aria-current={isActive ? "page" : undefined}
                      title={isSidebarCollapsed ? `${item.label} (${group.groupLabel})` : undefined}
                      className={cn(
                        "group relative w-full flex items-center gap-3 rounded-xl px-2.5 py-2 text-left transition-all duration-150 focus:outline-none focus:ring-2 focus:ring-[#D97757]/40",
                        isActive
                          ? "bg-white/[0.09] text-zinc-100 font-medium shadow-sm"
                          : "text-zinc-300 hover:bg-white/[0.04] hover:text-zinc-100",
                        isSidebarCollapsed && "justify-center px-0"
                      )}
                    >
                      {isActive && (
                        <span
                          aria-hidden="true"
                          className="absolute left-0 top-1.5 bottom-1.5 w-1 rounded-r-full bg-[#D97757]"
                        />
                      )}
                      <Icon
                        size={17}
                        strokeWidth={1.85}
                        className={cn(
                          "shrink-0 transition-transform duration-150 group-hover:scale-105",
                          isActive ? "text-[#D97757]" : "text-zinc-400 group-hover:text-zinc-200"
                        )}
                      />
                      {!isSidebarCollapsed && (
                        <span className="text-[13.5px] truncate leading-snug flex-1">
                          {item.label}
                        </span>
                      )}
                      {showRunningDot && (
                        <span
                          title="Pekerjaan sedang berjalan"
                          className="h-2 w-2 rounded-full bg-emerald-400 animate-pulse shrink-0"
                        />
                      )}
                    </button>
                  );
                })}
              </div>
            </div>
          ))}
        </nav>
      </div>

      {/* Quiet Minimal Status Footer */}
      <div className="p-2.5 border-t border-white/[0.05]">
        {!isSidebarCollapsed ? (
          <div className="rounded-xl bg-white/[0.02] border border-white/[0.06] px-3 py-2.5 space-y-2">
            <div className="flex items-center justify-between text-xs">
              <div className="flex items-center gap-1.5 text-zinc-300">
                <Cpu size={13} className="text-zinc-400" />
                <span>AI Lokal (Ollama)</span>
              </div>
              <span className="flex items-center gap-1.5 text-xs text-zinc-200 font-medium">
                <span
                  className={cn(
                    "h-2 w-2 rounded-full",
                    engineHealth.ollama_online ? "bg-emerald-400" : "bg-zinc-500"
                  )}
                />
                {engineHealth.ollama_online ? "Siap" : "Nonaktif"}
              </span>
            </div>

            <div className="flex items-center justify-between text-xs pt-1.5 border-t border-white/[0.05]">
              <span className="text-zinc-400">Penghematan Kuota</span>
              <span className="font-mono text-xs text-zinc-200">
                {hasTokenActivity ? `Hemat ${savingsRatio}%` : "Siap bekerja"}
              </span>
            </div>
          </div>
        ) : (
          <div className="flex flex-col items-center py-1">
            <span
              title={`AI Lokal (Ollama): ${engineHealth.ollama_online ? "Siap" : "Nonaktif"} • ${
                hasTokenActivity ? `Hemat ${savingsRatio}%` : "Siap bekerja"
              }`}
              className={cn(
                "h-2.5 w-2.5 rounded-full",
                engineHealth.ollama_online ? "bg-emerald-400" : "bg-zinc-500"
              )}
            />
          </div>
        )}
      </div>
    </aside>
  );
};
