/**
 * Engine Connection Manager for AKSA Desktop & Browser Dev mode.
 * Dynamically resolves host, port, auth token, base URL, and WS URL (P0-2, P1-5).
 */

export interface EngineConnectionConfig {
  baseUrl: string;
  wsUrl: string;
  token: string;
  host: string;
  port: number;
}

let cachedConnection: EngineConnectionConfig | null = null;
let connectionPromise: Promise<EngineConnectionConfig> | null = null;

export async function getEngineConnection(): Promise<EngineConnectionConfig> {
  if (cachedConnection) {
    return cachedConnection;
  }
  if (connectionPromise) {
    return connectionPromise;
  }

  connectionPromise = (async () => {
    // 1. Check if running inside Tauri native runtime
    const isTauri = typeof window !== "undefined" && "__TAURI_INTERNALS__" in window;
    if (isTauri) {
      try {
        const { invoke } = await import("@tauri-apps/api/core");
        const info = await invoke<{
          host: string;
          port: number;
          auth_token: string;
          base_url: string;
          ws_url: string;
        }>("get_engine_connection_info");
        if (info && info.base_url) {
          cachedConnection = {
            baseUrl: info.base_url,
            wsUrl: info.ws_url,
            token: info.auth_token,
            host: info.host,
            port: info.port,
          };
          return cachedConnection;
        }
      } catch (err) {
        console.warn("[AKSA] Gagal invoke get_engine_connection_info dari Tauri, menggunakan fallback:", err);
      }
    }

    // 2. Fallback to Vite environment variables or dev defaults
    const host = (import.meta as any).env?.VITE_AKSA_HOST || "127.0.0.1";
    const port = Number((import.meta as any).env?.VITE_AKSA_PORT || 43120);
    const token = (import.meta as any).env?.VITE_AKSA_TOKEN || "dev-aksa-local-token";
    const baseUrl = (import.meta as any).env?.VITE_AKSA_BASE_URL || `http://${host}:${port}`;
    const wsUrl = (import.meta as any).env?.VITE_AKSA_WS_URL || `ws://${host}:${port}/ws/stream`;

    cachedConnection = {
      baseUrl,
      wsUrl,
      token,
      host,
      port,
    };
    return cachedConnection;
  })();

  return connectionPromise;
}

/**
 * Universal authenticated fetch wrapper for the AKSA Engine Sidecar.
 * Injects X-AKSA-Auth-Token and Content-Type headers automatically.
 */
export async function apiFetch(endpoint: string, init?: RequestInit): Promise<Response> {
  const conn = await getEngineConnection();
  const url = endpoint.startsWith("http")
    ? endpoint
    : `${conn.baseUrl}${endpoint.startsWith("/") ? "" : "/"}${endpoint}`;

  const headers = new Headers(init?.headers || {});
  if (conn.token && !headers.has("X-AKSA-Auth-Token")) {
    headers.set("X-AKSA-Auth-Token", conn.token);
  }
  if (!headers.has("Content-Type") && init?.body && typeof init.body === "string") {
    headers.set("Content-Type", "application/json");
  }

  return fetch(url, {
    ...init,
    headers,
  });
}

