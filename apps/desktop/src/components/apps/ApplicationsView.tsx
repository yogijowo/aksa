import React, { useEffect, useState } from "react";
import {
  LayoutGrid,
  RefreshCw,
  Search,
  ExternalLink,
  Activity,
  Layers,
  ShieldCheck,
  ShieldAlert,
  Link2,
  Unlink2,
  FileSpreadsheet,
  Globe,
  Code2,
  MessageSquare,
  Wrench,
  Laptop,
} from "lucide-react";
import { toast } from "sonner";
import {
  fetchDesktopAppsRemote,
  refreshDesktopAppsRemote,
  launchDesktopAppRemote,
  toggleDesktopAppConnectionRemote,
} from "@/services/engineClient";
import type { DesktopApp } from "@/types/aksa";

export const ApplicationsView: React.FC = () => {
  const [apps, setApps] = useState<DesktopApp[]>([]);
  const [search, setSearch] = useState("");
  const [loading, setLoading] = useState(false);
  const [launchingId, setLaunchingId] = useState<string | null>(null);
  const [connectingId, setConnectingId] = useState<string | null>(null);
  const [statusFilter, setStatusFilter] = useState<"all" | "connected" | "disconnected">("all");
  const [selectedCategory, setSelectedCategory] = useState<string>("all");

  const loadApps = async () => {
    setLoading(true);
    try {
      const data = await fetchDesktopAppsRemote();
      if (data) setApps(data);
    } catch {
      toast.error("Gagal memuat daftar aplikasi dari sistem.");
    } finally {
      setLoading(false);
    }
  };

  const handleRefresh = async () => {
    setLoading(true);
    try {
      const data = await refreshDesktopAppsRemote();
      if (data) {
        setApps(data);
        toast.success(`Berhasil memperbarui ${data.length} aplikasi terpasang di komputer.`);
      }
    } catch {
      toast.error("Gagal memindai ulang aplikasi di sistem.");
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
            ? `Aplikasi '${app.display_name}' berhasil dihubungkan ke AKSA.`
            : `Izin akses aplikasi '${app.display_name}' berhasil diputuskan.`
        );
        setApps((prev) =>
          prev.map((item) =>
            item.id === app.id ? { ...item, is_connected: nextState } : item
          )
        );
      } else {
        toast.error("Gagal mengubah status izin aplikasi.");
      }
    } catch (err: any) {
      toast.error(`Gagal menghubungkan aplikasi: ${err?.message || err}`);
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
      toast.error(`Gagal meluncurkan aplikasi: ${err?.message || err}`);
    } finally {
      setLaunchingId(null);
    }
  };

  useEffect(() => {
    loadApps();
  }, []);

  const categories = Array.from(
    new Set(apps.map((a) => a.category_label || "Aplikasi Komputer Umum"))
  );

  const filteredApps = apps.filter((a) => {
    const q = search.toLowerCase();
    const matchesSearch =
      a.display_name.toLowerCase().includes(q) ||
      (a.publisher && a.publisher.toLowerCase().includes(q)) ||
      (a.category_label && a.category_label.toLowerCase().includes(q)) ||
      a.available_adapters.some((ad) => ad.toLowerCase().includes(q));

    const matchesStatus =
      statusFilter === "all"
        ? true
        : statusFilter === "connected"
        ? Boolean(a.is_connected)
        : !a.is_connected;

    const matchesCategory =
      selectedCategory === "all" || (a.category_label || "Aplikasi Komputer Umum") === selectedCategory;

    return matchesSearch && matchesStatus && matchesCategory;
  });

  const getCategoryIcon = (category?: string) => {
    switch (category) {
      case "Otomasi Dokumen Office":
        return <FileSpreadsheet className="w-3.5 h-3.5 text-[#D97757]" />;
      case "Navigasi & Analisis Web":
        return <Globe className="w-3.5 h-3.5 text-[#38BDF8]" />;
      case "Penyunting Kode & Teks":
        return <Code2 className="w-3.5 h-3.5 text-[#A78BFA]" />;
      case "Komunikasi & Produktivitas":
        return <MessageSquare className="w-3.5 h-3.5 text-[#34D399]" />;
      case "Alat Sistem & Utilitas":
        return <Wrench className="w-3.5 h-3.5 text-[#FBBF24]" />;
      default:
        return <Laptop className="w-3.5 h-3.5 text-[#9C9A92]" />;
    }
  };

  const connectedCount = apps.filter((a) => a.is_connected).length;
  const runningCount = apps.filter((a) => a.is_running).length;

  return (
    <div className="flex-1 overflow-y-auto px-8 py-8 bg-[#191918] text-[#ECECEB]">
      <div className="max-w-6xl mx-auto space-y-6">
        {/* Header */}
        <div className="flex items-center justify-between">
          <div className="space-y-1">
            <div className="flex items-center gap-2 text-xs font-semibold uppercase tracking-wider text-[#D97757]">
              <LayoutGrid className="w-4 h-4" />
              <span>Intelijensi Desktop &amp; Aplikasi PC</span>
            </div>
            <h1 className="text-2xl font-bold tracking-tight text-white">Aplikasi PC Terinstall</h1>
            <p className="text-sm text-[#9C9A92]">
              Daftar aplikasi yang terdeteksi di komputer Anda. Hubungkan atau putuskan izin akses agen ke aplikasi secara mandiri tanpa harus membuka aplikasinya terlebih dahulu.
            </p>
          </div>

          <button
            onClick={handleRefresh}
            disabled={loading}
            className="flex items-center gap-2 px-3.5 py-2 rounded-lg bg-[#242422] hover:bg-[#2a2a28] border border-[#FFFFFF]/10 text-xs font-medium transition-all text-[#ECECEB] disabled:opacity-50"
          >
            <RefreshCw className={`w-3.5 h-3.5 ${loading ? "animate-spin" : ""}`} />
            <span>Pindai Ulang Perangkat</span>
          </button>
        </div>

        {/* Stats Row */}
        <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
          <div className="p-4 rounded-xl bg-[#21211F] border border-[#FFFFFF]/10 flex items-center gap-3">
            <div className="w-9 h-9 rounded-lg bg-[#D97757]/15 flex items-center justify-center text-[#D97757]">
              <Layers className="w-5 h-5" />
            </div>
            <div>
              <div className="text-xl font-bold text-white">{apps.length}</div>
              <div className="text-[11px] text-[#9C9A92]">Total Aplikasi Terinstall</div>
            </div>
          </div>

          <div className="p-4 rounded-xl bg-[#21211F] border border-[#FFFFFF]/10 flex items-center gap-3">
            <div className="w-9 h-9 rounded-lg bg-[#10B981]/15 flex items-center justify-center text-[#10B981]">
              <ShieldCheck className="w-5 h-5" />
            </div>
            <div>
              <div className="text-xl font-bold text-white">{connectedCount}</div>
              <div className="text-[11px] text-[#9C9A92]">Diizinkan &amp; Terhubung ke AKSA</div>
            </div>
          </div>

          <div className="p-4 rounded-xl bg-[#21211F] border border-[#FFFFFF]/10 flex items-center gap-3">
            <div className="w-9 h-9 rounded-lg bg-[#38BDF8]/15 flex items-center justify-center text-[#38BDF8]">
              <Activity className="w-5 h-5" />
            </div>
            <div>
              <div className="text-xl font-bold text-white">{runningCount}</div>
              <div className="text-[11px] text-[#9C9A92]">Sedang Berjalan di Sistem</div>
            </div>
          </div>
        </div>

        {/* Filters and Search Bar */}
        <div className="space-y-3">
          <div className="flex flex-col md:flex-row items-stretch md:items-center justify-between gap-3">
            {/* Search Input */}
            <div className="relative flex-1">
              <Search className="w-4 h-4 absolute left-3.5 top-1/2 -translate-y-1/2 text-[#71716E]" />
              <input
                type="text"
                placeholder="Cari nama aplikasi, penerbit, atau kategori (misal: Excel, Chrome, VS Code)..."
                value={search}
                onChange={(e) => setSearch(e.target.value)}
                className="w-full bg-[#21211F] border border-[#FFFFFF]/10 rounded-lg pl-10 pr-4 py-2.5 text-xs text-[#ECECEB] placeholder-[#71716E] focus:outline-none focus:border-[#D97757]/60"
              />
            </div>

            {/* Status Filter Tabs */}
            <div className="flex items-center gap-1.5 p-1 rounded-lg bg-[#21211F] border border-[#FFFFFF]/10 shrink-0">
              <button
                onClick={() => setStatusFilter("all")}
                className={`px-3 py-1.5 rounded-md text-xs font-medium transition-all ${
                  statusFilter === "all"
                    ? "bg-[#D97757] text-white"
                    : "text-[#9C9A92] hover:text-[#ECECEB]"
                }`}
              >
                Semua ({apps.length})
              </button>
              <button
                onClick={() => setStatusFilter("connected")}
                className={`px-3 py-1.5 rounded-md text-xs font-medium transition-all flex items-center gap-1.5 ${
                  statusFilter === "connected"
                    ? "bg-[#10B981] text-white"
                    : "text-[#9C9A92] hover:text-[#ECECEB]"
                }`}
              >
                <ShieldCheck className="w-3.5 h-3.5" />
                <span>Terhubung ({connectedCount})</span>
              </button>
              <button
                onClick={() => setStatusFilter("disconnected")}
                className={`px-3 py-1.5 rounded-md text-xs font-medium transition-all ${
                  statusFilter === "disconnected"
                    ? "bg-[#262624] text-white border border-white/[0.08]"
                    : "text-[#9C9A92] hover:text-[#ECECEB]"
                }`}
              >
                Belum Diizinkan ({apps.length - connectedCount})
              </button>
            </div>
          </div>

          {/* Category Filter Pills */}
          {categories.length > 0 && (
            <div className="flex items-center gap-1.5 overflow-x-auto pb-1 text-xs">
              <span className="text-[#71716E] text-[11px] whitespace-nowrap">Kategori:</span>
              <button
                onClick={() => setSelectedCategory("all")}
                className={`px-2.5 py-1 rounded-full text-[11px] font-medium transition-all whitespace-nowrap ${
                  selectedCategory === "all"
                    ? "bg-white/[0.12] text-white border border-white/[0.2]"
                    : "bg-[#21211F] text-[#9C9A92] hover:text-white border border-transparent"
                }`}
              >
                Semua Kategori
              </button>
              {categories.map((cat) => (
                <button
                  key={cat}
                  onClick={() => setSelectedCategory(cat)}
                  className={`px-2.5 py-1 rounded-full text-[11px] font-medium transition-all flex items-center gap-1.5 whitespace-nowrap ${
                    selectedCategory === cat
                      ? "bg-white/[0.12] text-white border border-white/[0.2]"
                      : "bg-[#21211F] text-[#9C9A92] hover:text-white border border-transparent"
                  }`}
                >
                  {getCategoryIcon(cat)}
                  <span>{cat}</span>
                </button>
              ))}
            </div>
          )}
        </div>

        {/* Application Cards List */}
        <div className="grid grid-cols-1 md:grid-cols-2 gap-3.5">
          {filteredApps.map((app) => (
            <div
              key={app.id}
              className={`p-4 rounded-xl bg-[#21211F] border transition-all flex flex-col justify-between space-y-3 ${
                app.is_connected
                  ? "border-[#10B981]/40 shadow-sm"
                  : "border-[#FFFFFF]/10 hover:border-[#FFFFFF]/20"
              }`}
            >
              <div className="flex items-start justify-between gap-3">
                <div className="space-y-1.5">
                  <div className="flex items-center gap-2 flex-wrap">
                    <span className="font-semibold text-sm text-white">{app.display_name}</span>
                    {app.is_running && (
                      <span className="flex items-center gap-1 px-1.5 py-0.5 rounded text-[10px] font-medium bg-[#10B981]/15 text-[#10B981] border border-[#10B981]/30">
                        <span className="w-1.5 h-1.5 rounded-full bg-[#10B981] animate-pulse" />
                        Sedang Berjalan
                      </span>
                    )}
                  </div>

                  <div className="text-xs text-[#9C9A92]">
                    {app.publisher || "Penerbit Terverifikasi Sistem"}
                    {app.version && <span className="ml-1.5 text-[#71716E]">v{app.version}</span>}
                  </div>
                </div>

                <div className="flex items-center gap-1.5 shrink-0">
                  <button
                    onClick={() => handleLaunch(app)}
                    disabled={launchingId === app.id}
                    className="px-2.5 py-1.5 rounded-md bg-[#262624] hover:bg-[#343431] border border-[#FFFFFF]/10 text-[11px] font-medium text-[#ECECEB] flex items-center gap-1 transition-all disabled:opacity-50"
                    title="Buka aplikasi langsung di sistem operasi"
                  >
                    <ExternalLink className="w-3 h-3" />
                    <span>{launchingId === app.id ? "Membuka..." : "Buka"}</span>
                  </button>
                </div>
              </div>

              {/* Status and Category info */}
              <div className="space-y-2 pt-2 border-t border-[#FFFFFF]/05">
                <div className="flex items-center justify-between text-xs">
                  <span className="text-[11px] text-[#71716E] flex items-center gap-1.5">
                    {getCategoryIcon(app.category_label)}
                    <span className="font-medium text-zinc-300">
                      {app.category_label || "Aplikasi Komputer Umum"}
                    </span>
                  </span>

                  {/* Authorization Status Badge */}
                  {app.is_connected ? (
                    <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded text-[10px] font-semibold bg-[#10B981]/15 text-[#10B981] border border-[#10B981]/30">
                      <ShieldCheck className="w-3 h-3" />
                      <span>Diizinkan (Terhubung)</span>
                    </span>
                  ) : (
                    <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded text-[10px] font-medium bg-zinc-800/80 text-zinc-400 border border-white/[0.06]">
                      <ShieldAlert className="w-3 h-3 text-zinc-500" />
                      <span>Belum Diizinkan</span>
                    </span>
                  )}
                </div>

                {/* Connect / Disconnect Action Button */}
                <div className="pt-1 flex items-center justify-between">
                  <span className="text-[10px] text-[#71716E]">
                    {app.is_connected
                      ? "Agen diizinkan mengakses data & automasi aplikasi ini."
                      : "Akses diblokir hingga Anda menghubungkannya secara eksplisit."}
                  </span>

                  <button
                    onClick={() => handleToggleConnection(app)}
                    disabled={connectingId === app.id}
                    className={`px-3 py-1.5 rounded-lg text-xs font-semibold flex items-center gap-1.5 transition-all disabled:opacity-50 ${
                      app.is_connected
                        ? "bg-[#262624] hover:bg-rose-500/15 border border-white/[0.08] hover:border-rose-500/30 text-rose-300"
                        : "bg-[#10B981] hover:bg-[#059669] text-white shadow-sm"
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
                        ? "Putuskan Akses"
                        : "Hubungkan ke AKSA"}
                    </span>
                  </button>
                </div>
              </div>
            </div>
          ))}

          {filteredApps.length === 0 && (
            <div className="col-span-full py-12 text-center text-[#71716E] text-xs border border-dashed border-[#FFFFFF]/10 rounded-xl">
              Tidak ada aplikasi terinstall yang cocok dengan kriteria pencarian "{search}".
            </div>
          )}
        </div>
      </div>
    </div>
  );
};
