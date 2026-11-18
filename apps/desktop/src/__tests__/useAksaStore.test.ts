import { describe, it, expect, beforeEach } from "vitest";
import { useAksaStore } from "../stores/useAksaStore";

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
});
