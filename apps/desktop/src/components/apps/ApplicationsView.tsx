import React, { useEffect, useState } from "react";
import {
  LayoutGrid,
  RefreshCw,
  Search,
  ExternalLink,
  Activity,
  Layers,
  ShieldCheck,
  Link2,
  Unlink2,
  FileSpreadsheet,
  Globe,
  Code2,
  MessageSquare,
  Wrench,
  Laptop,
  ChevronDown,
  ChevronRight,
  Info,
} from "lucide-react";
import { toast } from "sonner";
import {
  fetchDesktopAppsRemote,
  refreshDesktopAppsRemote,
  launchDesktopAppRemote,
  toggleDesktopAppConnectionRemote,
} from "@/services/engineClient";
import {
  PageHeader,
  StatusBadge,
  EmptyStateCard,
  LoadingStateCard,
  ErrorStateCard,
} from "@/components/ui/UXPrimitives";
import type { DesktopApp } from "@/types/aksa";

function getFriendlyAppFunction(app: DesktopApp): string {
  const cat = app.category_label || "";
  if (cat.includes("Office")) {
    return "Membaca, membuat, dan merapikan dokumen kerja, tabel, atau presentasi.";
  }
  if (cat.includes("Web")) {
    return "Membuka halaman web dan membantu mencari informasi atau mengunduh dokumen.";
  }
  if (cat.includes("Kode")) {
    return "Membuka dan menyunting file teks, catatan, atau kode program.";
  }
  if (cat.includes("Komunikasi")) {
    return "Membantu komunikasi kerja dan pengelolaan pesan.";
  }
  return "Aplikasi komputer yang dapat dibuka atau dibantu pengoperasiannya oleh AKSA.";
}

export const ApplicationsView: React.FC = () => {
  const [apps, setApps] = useState<DesktopApp[]>([]);
  const [search, setSearch] = useState("");
  const [loading, setLoading] = useState(false);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [launchingId, setLaunchingId] = useState<string | null>(null);
  const [connectingId, setConnectingId] = useState<string | null>(null);
  const [statusFilter, setStatusFilter] = useState<"all" | "connected" | "disconnected">("all");
  const [selectedCategory, setSelectedCategory] = useState<string>("all");
  const [expandedTechIds, setExpandedTechIds] = useState<Record<string, boolean>>({});

  const loadApps = async () => {
    setLoading(true);
    setLoadError(null);
    try {
      const data = await fetchDesktopAppsRemote();
      if (data) setApps(data);
    } catch (err: any) {
      setLoadError(err?.message || "Gagal memuat daftar aplikasi dari komputer Anda.");
    } finally {
      setLoading(false);
    }
  };

  const handleRefresh = async () => {
    setLoading(true);
    setLoadError(null);
    try {
      const data = await refreshDesktopAppsRemote();
      if (data) {
        setApps(data);
        toast.success(`Berhasil menemukan ${data.length} aplikasi di komputer Anda.`);
      }
    } catch (err: any) {
      setLoadError(err?.message || "Gagal memindai ulang aplikasi di perangkat.");
      toast.error("Gagal memindai ulang aplikasi di perangkat.");
    } finally {
      setLoading(false);
    }
  };

  const handleToggleConnection = async (app: DesktopApp) => {
    setConnectingId(app.id);
    const nextState = !app.is_connected;
    try {
      const res = await toggleDesktopAppConnectionRemote(app.id, nextState);
      if (res && res.success) {
        toast.success(
          nextState
            ? `Izin akses aplikasi "${app.display_name}" berhasil diberikan.`
            : `Izin akses aplikasi "${app.display_name}" berhasil dicabut.`
        );
        setApps((prev) =>
          prev.map((item) =>
            item.id === app.id ? { ...item, is_connected: nextState } : item
          )
        );
      } else {
        toast.error("Gagal memperbarui izin akses aplikasi.");
      }
    } catch (err: any) {
      toast.error(`Gagal mengubah izin aplikasi: ${err?.message || err}`);
    } finally {
      setConnectingId(null);
    }
  };

  const handleLaunch = async (app: DesktopApp) => {
    setLaunchingId(app.id);
    try {
      const res = await launchDesktopAppRemote(app.id);
      if (res.success) {
        toast.success(res.message);
      } else {
        toast.error(res.message);
      }
    } catch (err: any) {
      toast.error(`Gagal membuka aplikasi: ${err?.message || err}`);
    } finally {
      setLaunchingId(null);
    }
  };

  useEffect(() => {
    void loadApps();
  }, []);

  const categories = Array.from(
    new Set(apps.map((a) => a.category_label || "Aplikasi Komputer Umum"))
  );

  const filteredApps = apps.filter((a) => {
    const q = search.toLowerCase();
    const matchesSearch =
      a.display_name.toLowerCase().includes(q) ||
      (a.publisher && a.publisher.toLowerCase().includes(q)) ||
      (a.category_label && a.category_label.toLowerCase().includes(q));

    const matchesStatus =
      statusFilter === "all"
        ? true
        : statusFilter === "connected"
        ? Boolean(a.is_connected)
        : !a.is_connected;

    const matchesCategory =
      selectedCategory === "all" ||
      (a.category_label || "Aplikasi Komputer Umum") === selectedCategory;

    return matchesSearch && matchesStatus && matchesCategory;
  });

  const getCategoryIcon = (category?: string) => {
    switch (category) {
      case "Otomasi Dokumen Office":
        return <FileSpreadsheet className="w-4 h-4 text-[#D97757]" />;
      case "Navigasi & Analisis Web":
        return <Globe className="w-4 h-4 text-[#38BDF8]" />;
      case "Penyunting Kode & Teks":
        return <Code2 className="w-4 h-4 text-[#A78BFA]" />;
      case "Komunikasi & Produktivitas":
        return <MessageSquare className="w-4 h-4 text-[#34D399]" />;
      case "Alat Sistem & Utilitas":
        return <Wrench className="w-4 h-4 text-[#FBBF24]" />;
      default:
        return <Laptop className="w-4 h-4 text-[#9C9A92]" />;
    }
  };

  const connectedCount = apps.filter((a) => a.is_connected).length;
  const runningCount = apps.filter((a) => a.is_running).length;

  return (
    <div className="flex-1 overflow-y-auto px-6 md:px-8 py-8 bg-[#191918] text-[#ECECEB]">
      <div className="max-w-6xl mx-auto space-y-6">
        <PageHeader
          icon={<LayoutGrid className="w-5 h-5 text-[#D97757]" />}
          title="Aplikasi Komputer"
          description="Lihat aplikasi yang terdeteksi di komputer Anda dan atur aplikasi mana saja yang boleh digunakan oleh AKSA."
          actions={
            <button
              type="button"
              onClick={() => void handleRefresh()}
              disabled={loading}
              className="flex items-center gap-2 px-4 py-2 rounded-xl bg-[#242422] hover:bg-[#2a2a28] border border-white/10 text-[13px] font-medium transition-all text-zinc-100 disabled:opacity-50"
            >
              <RefreshCw className={`w-4 h-4 ${loading ? "animate-spin" : ""}`} />
              <span>Periksa Ulang Aplikasi</span>
            </button>
          }
        />

        {/* Clear Security Notice (Section 5.5) */}
        <div className="rounded-2xl bg-[#21211F] border border-white/[0.08] p-4 flex items-start gap-3 text-[13px] text-zinc-300">
          <Info size={18} className="text-[#D97757] shrink-0 mt-0.5" />
          <p className="leading-relaxed">
            Aplikasi yang terdeteksi di komputer Anda <strong>tidak otomatis dapat dikontrol oleh AKSA</strong>.{" "}
            AKSA dapat menggunakan aplikasi ini setelah Anda memberikan izin yang diperlukan.
          </p>
        </div>

        {/* Summary Cards */}
        <div className="grid grid-cols-1 md:grid-cols-3 gap-3.5">
          <div className="p-4 rounded-2xl bg-[#21211F] border border-white/10 flex items-center gap-3.5">
            <div className="w-10 h-10 rounded-xl bg-[#D97757]/15 flex items-center justify-center text-[#D97757]">
              <Layers className="w-5 h-5" />
            </div>
            <div>
              <div className="text-xl font-bold text-white">{apps.length}</div>
              <div className="text-xs text-zinc-400">Aplikasi Terdeteksi di Perangkat</div>
            </div>
          </div>

          <div className="p-4 rounded-2xl bg-[#21211F] border border-white/10 flex items-center gap-3.5">
            <div className="w-10 h-10 rounded-xl bg-emerald-500/15 flex items-center justify-center text-emerald-400">
              <ShieldCheck className="w-5 h-5" />
            </div>
            <div>
              <div className="text-xl font-bold text-white">{connectedCount}</div>
              <div className="text-xs text-zinc-400">Izin Diberikan ke AKSA</div>
            </div>
          </div>

          <div className="p-4 rounded-2xl bg-[#21211F] border border-white/10 flex items-center gap-3.5">
            <div className="w-10 h-10 rounded-xl bg-sky-500/15 flex items-center justify-center text-sky-400">
              <Activity className="w-5 h-5" />
            </div>
            <div>
              <div className="text-xl font-bold text-white">{runningCount}</div>
              <div className="text-xs text-zinc-400">Sedang Terbuka Saat Ini</div>
            </div>
          </div>
        </div>

        {/* Search & Filters */}
        <div className="space-y-3">
          <div className="flex flex-col md:flex-row items-stretch md:items-center justify-between gap-3">
            <div className="relative flex-1">
              <Search className="w-4 h-4 absolute left-3.5 top-1/2 -translate-y-1/2 text-zinc-400" />
              <input
                type="text"
                aria-label="Cari aplikasi komputer"
                placeholder="Cari nama aplikasi (misal: Excel, Word, Chrome)..."
                value={search}
                onChange={(e) => setSearch(e.target.value)}
                className="w-full bg-[#21211F] border border-white/10 rounded-xl pl-10 pr-4 py-2.5 text-[13.5px] text-zinc-100 placeholder-zinc-500 focus:outline-none focus:border-[#D97757]"
              />
            </div>

            <div className="flex items-center gap-1.5 p-1 rounded-xl bg-[#21211F] border border-white/10 shrink-0">
              <button
                type="button"
                onClick={() => setStatusFilter("all")}
                className={`px-3 py-1.5 rounded-lg text-xs font-semibold transition-all ${
                  statusFilter === "all"
                    ? "bg-[#D97757] text-white"
                    : "text-zinc-300 hover:text-white"
                }`}
              >
                Semua ({apps.length})
              </button>
              <button
                type="button"
                onClick={() => setStatusFilter("connected")}
                className={`px-3 py-1.5 rounded-lg text-xs font-semibold transition-all flex items-center gap-1.5 ${
                  statusFilter === "connected"
                    ? "bg-emerald-600 text-white"
                    : "text-zinc-300 hover:text-white"
                }`}
              >
                <ShieldCheck className="w-3.5 h-3.5" />
                <span>Izin diberikan ({connectedCount})</span>
              </button>
              <button
                type="button"
                onClick={() => setStatusFilter("disconnected")}
                className={`px-3 py-1.5 rounded-lg text-xs font-semibold transition-all ${
                  statusFilter === "disconnected"
                    ? "bg-[#262624] text-white border border-white/10"
                    : "text-zinc-300 hover:text-white"
                }`}
              >
                Belum diizinkan ({apps.length - connectedCount})
              </button>
            </div>
          </div>

          {categories.length > 0 && (
            <div className="flex items-center gap-1.5 overflow-x-auto pb-1 text-xs">
              <span className="text-zinc-400 text-xs whitespace-nowrap">Jenis Aplikasi:</span>
              <button
                type="button"
                onClick={() => setSelectedCategory("all")}
                className={`px-3 py-1 rounded-full text-xs font-medium transition-all whitespace-nowrap ${
                  selectedCategory === "all"
                    ? "bg-white/[0.12] text-white border border-white/[0.2]"
                    : "bg-[#21211F] text-zinc-300 hover:text-white border border-transparent"
                }`}
              >
                Semua Jenis
              </button>
              {categories.map((cat) => (
                <button
                  type="button"
                  key={cat}
                  onClick={() => setSelectedCategory(cat)}
                  className={`px-3 py-1 rounded-full text-xs font-medium transition-all flex items-center gap-1.5 whitespace-nowrap ${
                    selectedCategory === cat
                      ? "bg-white/[0.12] text-white border border-white/[0.2]"
                      : "bg-[#21211F] text-zinc-300 hover:text-white border border-transparent"
                  }`}
                >
                  {getCategoryIcon(cat)}
                  <span>{cat}</span>
                </button>
              ))}
            </div>
          )}
        </div>

        {loadError && (
          <ErrorStateCard
            title="Daftar aplikasi belum dapat dimuat"
            cause={loadError}
            nextStep="Klik tombol Coba Lagi atau Periksa Ulang Aplikasi di sudut kanan atas."
            onRetry={() => void loadApps()}
          />
        )}

        {loading && apps.length === 0 ? (
          <LoadingStateCard
            title="Memindai aplikasi yang terpasang di komputer Anda..."
            description="AKSA sedang mengenali aplikasi produktivitas agar Anda dapat mengatur aksesnya dengan mudah."
          />
        ) : (
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            {filteredApps.map((app) => {
              const showTech = expandedTechIds[app.id] ?? false;
              return (
                <div
                  key={app.id}
                  className={`p-5 rounded-2xl bg-[#21211F] border transition-all flex flex-col justify-between space-y-4 ${
                    app.is_connected
                      ? "border-emerald-500/40 shadow-sm"
                      : "border-white/10 hover:border-white/20"
                  }`}
                >
                  <div className="space-y-2.5">
                    <div className="flex items-start justify-between gap-3">
                      <div className="flex items-start gap-3">
                        <div className="w-10 h-10 rounded-xl bg-white/[0.04] border border-white/[0.08] flex items-center justify-center shrink-0 mt-0.5">
                          {getCategoryIcon(app.category_label)}
                        </div>
                        <div>
                          <div className="flex items-center gap-2 flex-wrap">
                            <h3 className="font-semibold text-[15px] text-white">
                              {app.display_name}
                            </h3>
                            <StatusBadge
                              tone={app.is_installed ? "neutral" : "warning"}
                              label={app.is_installed ? "Terdeteksi" : "Tidak terdeteksi"}
                            />
                            {app.is_running && (
                              <StatusBadge tone="success" label="Sedang berjalan" />
                            )}
                          </div>
                          <div className="text-xs text-zinc-400 mt-0.5">
                            {app.category_label || "Aplikasi Komputer Umum"}
                            {app.version ? ` • Versi ${app.version}` : ""}
                          </div>
                        </div>
                      </div>

                      <button
                        type="button"
                        onClick={() => void handleLaunch(app)}
                        disabled={launchingId === app.id}
                        className="px-3 py-1.5 rounded-xl bg-[#262624] hover:bg-[#343431] border border-white/10 text-xs font-medium text-zinc-100 flex items-center gap-1.5 transition-all disabled:opacity-50 shrink-0"
                        title="Buka aplikasi ini di komputer Anda"
                      >
                        <ExternalLink className="w-3.5 h-3.5" />
                        <span>{launchingId === app.id ? "Membuka..." : "Buka Aplikasi"}</span>
                      </button>
                    </div>

                    <p className="text-[13px] text-zinc-300 leading-relaxed">
                      {getFriendlyAppFunction(app)}
                    </p>
                  </div>

                  {/* Permission Status & Action (Section 5.5) */}
                  <div className="space-y-3 pt-3 border-t border-white/[0.07]">
                    <div className="flex items-center justify-between gap-2">
                      <span className="text-xs text-zinc-400">Status izin AKSA:</span>
                      <StatusBadge
                        tone={app.is_connected ? "success" : "neutral"}
                        label={app.is_connected ? "Izin diberikan" : "Belum diizinkan"}
                      />
                    </div>

                    <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
                      <p className="text-xs text-zinc-300 leading-relaxed">
                        AKSA dapat menggunakan aplikasi ini setelah Anda memberikan izin yang
                        diperlukan.
                      </p>

                      <button
                        type="button"
                        onClick={() => void handleToggleConnection(app)}
                        disabled={connectingId === app.id}
                        className={`px-3.5 py-2 rounded-xl text-xs font-semibold flex items-center justify-center gap-1.5 transition-all disabled:opacity-50 shrink-0 ${
                          app.is_connected
                            ? "bg-[#262624] hover:bg-rose-500/15 border border-white/10 hover:border-rose-500/30 text-rose-300"
                            : "bg-[#D97757] hover:bg-[#c96a4b] text-white shadow-sm"
                        }`}
                      >
                        {connectingId === app.id ? (
                          <RefreshCw className="w-3.5 h-3.5 animate-spin" />
                        ) : app.is_connected ? (
                          <Unlink2 className="w-3.5 h-3.5" />
                        ) : (
                          <Link2 className="w-3.5 h-3.5" />
                        )}
                        <span>
                          {connectingId === app.id
                            ? "Memproses..."
                            : app.is_connected
                            ? "Cabut Akses"
                            : "Hubungkan & Atur Akses"}
                        </span>
                      </button>
                    </div>

                    {/* Advanced Technical Details Disclosure */}
                    <div className="pt-1">
                      <button
                        type="button"
                        onClick={() =>
                          setExpandedTechIds((prev) => ({ ...prev, [app.id]: !prev[app.id] }))
                        }
                        className="inline-flex items-center gap-1 text-[11.5px] text-zinc-400 hover:text-zinc-200"
                      >
                        {showTech ? <ChevronDown size={12} /> : <ChevronRight size={12} />}
                        <span>Detail teknis (Mode Lanjutan)</span>
                      </button>
                      {showTech && (
                        <div className="mt-2 rounded-xl bg-[#191918] border border-white/[0.06] p-2.5 text-[11px] font-mono text-zinc-400 space-y-1">
                          <div>ID: {app.platform_app_id || app.id}</div>
                          {app.install_location && <div>Lokasi: {app.install_location}</div>}
                          {app.available_adapters.length > 0 && (
                            <div>Jembatan: {app.available_adapters.join(", ")}</div>
                          )}
                        </div>
                      )}
                    </div>
                  </div>
                </div>
              );
            })}

            {filteredApps.length === 0 && !loading && (
              <div className="col-span-full">
                <EmptyStateCard
                  icon={<Laptop size={22} />}
                  title="Belum ada aplikasi yang cocok"
                  description={
                    search
                      ? `Tidak ditemukan aplikasi dengan kata kunci "${search}". Coba gunakan kata kunci lain.`
                      : "Klik tombol Periksa Ulang Aplikasi untuk mendeteksi aplikasi yang terpasang di komputer Anda."
                  }
                  actionLabel="Periksa Ulang Aplikasi"
                  onAction={() => void handleRefresh()}
                />
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  );
};
