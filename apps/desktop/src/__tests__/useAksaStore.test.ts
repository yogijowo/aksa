import { describe, it, expect, beforeEach } from "vitest";
import { useAksaStore } from "../stores/useAksaStore";
import { formatPermissionStatusLabel, TOOL_CATEGORY_LABELS } from "../lib/utils";

describe("useAksaStore state management tests", () => {
  beforeEach(() => {
    // Reset core states before each test
    useAksaStore.setState({
      activeNav: "ruang_kerja",
      selectedAgentId: null,
      activeWorkspaceId: "",
      isExecuting: false,
      emergencyStopActive: false,
    });
  });

  it("initializes with default team and navigation state", () => {
    const state = useAksaStore.getState();

    expect(state.teams).toBeDefined();
    expect(state.teams.length).toBeGreaterThan(0);
    expect(state.teams[0].id).toBe("team_nusantara_default");
    expect(state.activeNav).toBe("ruang_kerja");
    expect(state.isExecuting).toBe(false);
  });

  it("updates navigation item correctly", () => {
    const { setActiveNav } = useAksaStore.getState();

    setActiveNav("tim_agen");
    expect(useAksaStore.getState().activeNav).toBe("tim_agen");

    setActiveNav("pengaturan");
    expect(useAksaStore.getState().activeNav).toBe("pengaturan");

    setActiveNav("pengetahuan_rag");
    expect(useAksaStore.getState().activeNav).toBe("pengetahuan_rag");
  });

  it("switches active workspace", () => {
    const { setActiveWorkspace } = useAksaStore.getState();

    setActiveWorkspace("ws_project_alpha");
    expect(useAksaStore.getState().activeWorkspaceId).toBe("ws_project_alpha");

    setActiveWorkspace("ws_finance_2026");
    expect(useAksaStore.getState().activeWorkspaceId).toBe("ws_finance_2026");
  });

  it("toggles sidebar collapsed state", () => {
    const initial = useAksaStore.getState().isSidebarCollapsed;
    const { toggleSidebar } = useAksaStore.getState();

    toggleSidebar();
    expect(useAksaStore.getState().isSidebarCollapsed).toBe(!initial);

    toggleSidebar();
    expect(useAksaStore.getState().isSidebarCollapsed).toBe(initial);
  });

  it("manages selected agent selection", () => {
    const { selectAgent } = useAksaStore.getState();

    selectAgent("agt_spesialis_office");
    expect(useAksaStore.getState().selectedAgentId).toBe("agt_spesialis_office");

    selectAgent(null);
    expect(useAksaStore.getState().selectedAgentId).toBeNull();
  });

  it("maps technical permission enums to everyday Bahasa Indonesia status labels (Cycle 15 UX)", () => {
    expect(formatPermissionStatusLabel("GRANTED").label).toBe("Izin diberikan");
    expect(formatPermissionStatusLabel("DENIED").label).toBe("Akses ditolak");
    expect(formatPermissionStatusLabel("NEEDS_USER_ACTION").label).toBe("Memerlukan tindakan Anda");
    expect(formatPermissionStatusLabel("automatic_sandbox").label).toBe("Dilindungi otomatis");
    expect(formatPermissionStatusLabel("UNSUPPORTED").label).toBe(
      "Tidak tersedia pada perangkat ini"
    );
    expect(TOOL_CATEGORY_LABELS.rag_search).toBe("Pencarian dalam Dokumen");
  });

  it("updates granular folder permissions without automatically enabling high-risk delete or execute", () => {
    useAksaStore.setState({
      workspaces: [
        {
          id: "ws_test_1",
          name: "Dokumen Kerja",
          folder_path: "/tmp/dokumen",
          allow_read: true,
          allow_write: false,
          allow_execute: false,
          auto_rag_sync: true,
        },
      ],
      activeWorkspaceId: "ws_test_1",
    });

    const { updateWorkspacePermissions, addSubAgent } = useAksaStore.getState();
    updateWorkspacePermissions("ws_test_1", {
      granular_permissions: {
        list_files: true,
        read_content: true,
        create_files: true,
        modify_files: false,
        move_files: false,
        delete_files: false,
        execute_programs: false,
      },
    });

    const ws = useAksaStore.getState().workspaces[0];
    expect(ws.allow_read).toBe(true);
    expect(ws.allow_write).toBe(true);
    expect(ws.allow_execute).toBe(false);
    expect(ws.granular_permissions?.delete_files).toBe(false);
    expect(ws.granular_permissions?.execute_programs).toBe(false);

    // Adding a supporting agent must not automatically inherit high-risk permissions
    const parent = useAksaStore.getState().teams[0].agents[0];
    addSubAgent(parent);
    const created = useAksaStore
      .getState()
      .teams[0].agents.find((a) => a.id === useAksaStore.getState().selectedAgentId);
    expect(created).toBeDefined();
    expect(created?.tool_categories).toEqual(["filesystem"]);
  });
});
