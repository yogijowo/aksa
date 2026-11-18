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
  verified?: boolean;
}

/**
 * Compute HMAC-SHA256 in standard browser / Tauri webview environment.
 */
export async function computeHmacSha256(keyStr: string, message: string): Promise<string> {
  if (typeof window !== "undefined" && window.crypto && window.crypto.subtle) {
    try {
      const encoder = new TextEncoder();
      const keyData = encoder.encode(keyStr);
      const msgData = encoder.encode(message);
      const cryptoKey = await window.crypto.subtle.importKey(
        "raw",
        keyData,
        { name: "HMAC", hash: "SHA-256" },
        false,
        ["sign"]
      );
      const signature = await window.crypto.subtle.sign("HMAC", cryptoKey, msgData);
      return Array.from(new Uint8Array(signature))
        .map((b) => b.toString(16).padStart(2, "0"))
        .join("");
    } catch (err) {
      console.warn("[AKSA] Gagal menghitung HMAC:", err);
    }
  }
  return "";
}

/**
 * Verify genuine AKSA engine identity via challenge-response HMAC handshake (P1-5).
 */
export async function verifyEngineIdentity(baseUrl: string, token: string): Promise<boolean> {
  try {
    const nonce = Math.random().toString(36).substring(2) + Date.now().toString(36);
    const res = await fetch(`${baseUrl}/api/v1/health?nonce=${encodeURIComponent(nonce)}`, {
      headers: token ? { "X-AKSA-Auth-Token": token } : {},
    });
    if (!res.ok) return false;
    const data = await res.json();
    if (!data.nonce_hmac || data.engine !== "aksa-engine") return false;
    const expected = await computeHmacSha256(token, nonce);
    return expected.length > 0 && expected === data.nonce_hmac;
  } catch {
    return false;
  }
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
          const isVerified = await verifyEngineIdentity(info.base_url, info.auth_token);
          cachedConnection = {
            baseUrl: info.base_url,
            wsUrl: info.ws_url,
            token: info.auth_token,
            host: info.host,
            port: info.port,
            verified: isVerified,
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

