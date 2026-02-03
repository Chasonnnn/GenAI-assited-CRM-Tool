import { describe, it, expect } from "vitest";
import { middleware } from "../middleware";
import { NextRequest } from "next/server";

describe("Security Middleware", () => {
  it("adds security headers to the response", () => {
    // Create a mock request
    const request = new NextRequest(new URL("http://localhost:3000/"));

    // Call the middleware
    const response = middleware(request);

    // Assert headers are present
    expect(response.headers.get("X-Frame-Options")).toBe("DENY");
    expect(response.headers.get("X-Content-Type-Options")).toBe("nosniff");
    expect(response.headers.get("Referrer-Policy")).toBe("strict-origin-when-cross-origin");
    expect(response.headers.get("Permissions-Policy")).toContain("camera=()");
    expect(response.headers.get("Strict-Transport-Security")).toContain("max-age=31536000");
  });
});
