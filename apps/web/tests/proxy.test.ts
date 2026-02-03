import { describe, it, expect, vi } from "vitest";
import { proxy } from "../proxy";
import { NextRequest } from "next/server";

// Mock environment variables
vi.stubEnv("PLATFORM_BASE_DOMAIN", "surrogacyforce.com");

describe("Proxy Middleware", () => {
  it("adds security headers to the response", async () => {
    // Create a mock request
    const request = new NextRequest(new URL("http://localhost:3000/"));

    // Call the middleware (proxy)
    const response = await proxy(request);

    // Assert headers are present
    expect(response.headers.get("X-Frame-Options")).toBe("DENY");
    expect(response.headers.get("X-Content-Type-Options")).toBe("nosniff");
    expect(response.headers.get("Referrer-Policy")).toBe("strict-origin-when-cross-origin");
    expect(response.headers.get("Permissions-Policy")).toContain("camera=()");
    expect(response.headers.get("Strict-Transport-Security")).toContain("max-age=31536000");
  });
});
