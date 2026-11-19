/**
 * Engine Connection Manager for AKSA Desktop & Browser Dev mode.
 * Dynamically resolves host, port, auth token, base URL, and WS URL (P0-2, P1-5, P0.3).
 */

export type SidecarLifecycleState = "starting" | "ready" | "failed" | "stopping";

export interface EngineConnectionConfig {
  baseUrl: string;
  wsUrl: string;
  token: string;
  host: string;
  port: number;
  lifecycleState: SidecarLifecycleState;
  verified: boolean;
}

/**
 * Universal Crypto resolution across Browser, Tauri Webview, and Node.js test runtimes.
 */
function getCrypto(): Crypto | null {
  if (typeof window !== "undefined" && window.crypto) {
    return window.crypto;
  }
  if (typeof globalThis !== "undefined" && globalThis.crypto) {
    return globalThis.crypto;
  }
  return null;
}

/**
 * Generate a cryptographically secure random nonce using crypto.getRandomValues.
 */
export function generateCryptographicNonce(): string {
  const cryptoObj = getCrypto();
  if (cryptoObj && cryptoObj.getRandomValues) {
    const bytes = new Uint8Array(16);
    cryptoObj.getRandomValues(bytes);
    return Array.from(bytes, (b) => b.toString(16).padStart(2, "0")).join("");
  }
  return Date.now().toString(16) + Math.random().toString(16).substring(2);
}

/**
 * Compute HMAC-SHA256 in standard browser / Tauri webview / test environment.
 */
export async function computeHmacSha256(keyStr: string, message: string): Promise<string> {
  const cryptoObj = getCrypto();
  if (cryptoObj && cryptoObj.subtle) {
    try {
      const encoder = new TextEncoder();
      const keyData = encoder.encode(keyStr);
      const msgData = encoder.encode(message);
      const cryptoKey = await cryptoObj.subtle.importKey(
        "raw",
        keyData,
        { name: "HMAC", hash: "SHA-256" },
        false,
        ["sign"]
      );
      const signature = await cryptoObj.subtle.sign("HMAC", cryptoKey, msgData);
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
 * Verify genuine AKSA engine identity via challenge-response HMAC handshake (P1-5, P0.3).
 * Retries up to maxRetries before declaring the connection failed.
 */
export async function verifyEngineIdentity(
  baseUrl: string,
  token: string,
  maxRetries: number = 3,
  delayMs: number = 250
): Promise<boolean> {
  for (let attempt = 1; attempt <= maxRetries; attempt++) {
    try {
      const nonce = generateCryptographicNonce();
      // SECURITY (P0-01): NEVER send X-AKSA-Auth-Token before server identity is proven!
      // Challenge the server to prove knowledge of the secret token via HMAC-SHA256 of the random nonce.
      const res = await fetch(`${baseUrl}/api/v1/health?nonce=${encodeURIComponent(nonce)}`);
      if (res.ok) {
        const data = await res.json();
        if (data.engine === "aksa-engine" && data.nonce_hmac) {
          const expected = await computeHmacSha256(token, nonce);
          if (expected.length > 0 && expected === data.nonce_hmac) {
            return true;
          }
        }
      }
    } catch {
      // Retry if server is warming up
    }
    if (attempt < maxRetries) {
      await new Promise((r) => setTimeout(r, delayMs));
    }
  }
  return false;
}

let cachedConnection: EngineConnectionConfig | null = null;
let connectionPromise: Promise<EngineConnectionConfig> | null = null;

export async function getEngineConnection(): Promise<EngineConnectionConfig> {
  if (cachedConnection && cachedConnection.verified) {
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
        let info: {
          host: string;
          port: number;
          auth_token: string;
          base_url: string;
          ws_url: string;
          lifecycle_state?: SidecarLifecycleState;
        } | null = null;

        // Wait up to 10s while Rust completes mandatory manifest + PID + launch_id + HMAC handshake
        for (let attempt = 0; attempt < 40; attempt++) {
          info = await invoke("get_engine_connection_info");
          if (!info) break;
          if (info.lifecycle_state === "failed" || info.lifecycle_state === "stopping") break;
          if (info.lifecycle_state === "ready" && info.port > 0 && info.base_url) break;
          await new Promise((r) => setTimeout(r, 250));
        }

        if (info && info.port > 0 && info.base_url && info.lifecycle_state === "ready") {
          const isVerified = await verifyEngineIdentity(info.base_url, info.auth_token);
          const finalState: SidecarLifecycleState = isVerified ? "ready" : "failed";

          if (!isVerified) {
            try {
              await invoke("update_engine_lifecycle_state", { newState: "failed" });
            } catch {
              // Ignore IPC error if closing
            }
          }

          cachedConnection = {
            baseUrl: info.base_url,
            wsUrl: info.ws_url,
            token: info.auth_token,
            host: info.host,
            port: info.port,
            lifecycleState: finalState,
            verified: isVerified,
          };
          return cachedConnection;
        }
      } catch (err) {
        console.warn("[AKSA] Gagal invoke get_engine_connection_info dari Tauri:", err);
      }
    }

    // SECURITY (P0-01): Fail-closed in production if running without authenticated Tauri runtime
    const isProduction = Boolean((import.meta as any).env?.PROD);
    if (isProduction) {
      console.error("[AKSA Fail-Closed] Mode produksi aktif tanpa token autentikasi valid dari Tauri runtime. Seluruh koneksi diblokir demi keamanan.");
      cachedConnection = {
        baseUrl: "",
        wsUrl: "",
        token: "",
        host: "127.0.0.1",
        port: 0,
        lifecycleState: "failed",
        verified: false,
      };
      return cachedConnection;
    }

    // 2. Development-only Fallback to Vite environment variables or dev defaults
    const host = (import.meta as any).env?.VITE_AKSA_HOST || "127.0.0.1";
    const port = Number((import.meta as any).env?.VITE_AKSA_PORT || 43120);
    const token = (import.meta as any).env?.VITE_AKSA_TOKEN || "dev-aksa-local-token";
    const baseUrl = (import.meta as any).env?.VITE_AKSA_BASE_URL || `http://${host}:${port}`;
    const wsUrl = (import.meta as any).env?.VITE_AKSA_WS_URL || `ws://${host}:${port}/ws/stream`;

    const isVerified = await verifyEngineIdentity(baseUrl, token);
    cachedConnection = {
      baseUrl,
      wsUrl,
      token,
      host,
      port,
      lifecycleState: isVerified ? "ready" : "failed",
      verified: isVerified,
    };
    return cachedConnection;
  })();

  try {
    return await connectionPromise;
  } finally {
    connectionPromise = null;
  }
}

/**
 * Universal authenticated fetch wrapper for the AKSA Engine Sidecar.
 * Injects X-AKSA-Auth-Token and Content-Type headers automatically.
 * Fails closed if the engine identity has not been verified or lifecycle state is not ready (P0.3).
 */
export async function apiFetch(endpoint: string, init?: RequestInit): Promise<Response> {
  const isHealthCheck = endpoint.includes("/api/v1/health");
  const conn = await getEngineConnection();

  if (!isHealthCheck && (!conn.verified || conn.lifecycleState !== "ready")) {
    throw new Error(
      "[AKSA Fail-Closed] Koneksi ke AKSA Engine gagal diverifikasi atau belum siap. Request privat diblokir."
    );
  }

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

