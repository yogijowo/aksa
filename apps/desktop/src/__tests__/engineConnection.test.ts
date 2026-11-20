import { describe, it, expect, vi, beforeEach } from "vitest";
import {
  generateCryptographicNonce,
  computeHmacSha256,
  verifyEngineIdentity,
} from "../services/engineConnection";

describe("engineConnection security & identity tests", () => {
  beforeEach(() => {
    vi.restoreAllMocks();
  });

  it("generateCryptographicNonce generates 32-character hex nonce", () => {
    const nonce1 = generateCryptographicNonce();
    const nonce2 = generateCryptographicNonce();

    expect(nonce1).toBeDefined();
    expect(nonce1.length).toBe(32);
    expect(nonce1).toMatch(/^[0-9a-f]{32}$/);
    expect(nonce2).toBeDefined();
    expect(nonce1).not.toBe(nonce2);
  });

  it("computeHmacSha256 computes expected HMAC-SHA256 signature", async () => {
    const key = "test-secret-key-aksa";
    const message = "random-challenge-nonce-12345678";
    const hmac = await computeHmacSha256(key, message);

    expect(hmac).toBeDefined();
    expect(hmac.length).toBe(64);
    expect(hmac).toMatch(/^[0-9a-f]{64}$/);

    // Deterministic: same key and message must produce identical HMAC
    const hmac2 = await computeHmacSha256(key, message);
    expect(hmac).toBe(hmac2);

    // Different message must produce different HMAC
    const hmacDiff = await computeHmacSha256(key, "different-nonce");
    expect(hmac).not.toBe(hmacDiff);
  });

  it("verifyEngineIdentity passes when server returns genuine HMAC for challenge nonce", async () => {
    const baseUrl = "http://127.0.0.1:43120";
    const token = "aksa-valid-token-1234567890";

    // Mock global fetch to intercept health check challenge
    vi.stubGlobal(
      "fetch",
      vi.fn().mockImplementation(async (url: string) => {
        const u = new URL(url);
        const nonce = u.searchParams.get("nonce") || "";
        const expectedHmac = await computeHmacSha256(token, nonce);
        return {
          ok: true,
          json: async () => ({
            status: "ok",
            engine: "aksa-engine",
            version: "0.0.2",
            nonce_hmac: expectedHmac,
          }),
        };
      })
    );

    const isVerified = await verifyEngineIdentity(baseUrl, token, 1, 10);
    expect(isVerified).toBe(true);
  });

  it("verifyEngineIdentity fails closed when server returns invalid HMAC or engine mismatch", async () => {
    const baseUrl = "http://127.0.0.1:43120";
    const token = "aksa-valid-token-1234567890";

    // Mock global fetch returning mismatched hmac
    vi.stubGlobal(
      "fetch",
      vi.fn().mockImplementation(async () => {
        return {
          ok: true,
          json: async () => ({
            status: "ok",
            engine: "aksa-engine",
            version: "0.0.2",
            nonce_hmac: "tampered_fake_hmac_hex",
          }),
        };
      })
    );

    const isVerified = await verifyEngineIdentity(baseUrl, token, 1, 10);
    expect(isVerified).toBe(false);
  });
});

