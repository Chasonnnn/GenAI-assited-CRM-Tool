/* global process, require, module, __dirname */
/* eslint-disable @typescript-eslint/no-require-imports */

const withBundleAnalyzer =
  process.env.ANALYZE === "true"
    ? require("@next/bundle-analyzer")({ enabled: true })
    : (config) => config;

module.exports = withBundleAnalyzer({
  async headers() {
    const baseHeaders = [
      { key: "X-Frame-Options", value: "SAMEORIGIN" },
      { key: "X-Content-Type-Options", value: "nosniff" },
      { key: "Referrer-Policy", value: "strict-origin-when-cross-origin" },
      {
        key: "Permissions-Policy",
        value: "camera=(), microphone=(), geolocation=(), browsing-topics=()",
      },
    ];

    // Only enable HSTS for production deploys (avoid affecting preview/dev).
    const isProd = process.env.VERCEL_ENV === "production";
    const headers = isProd
      ? [
          ...baseHeaders,
          {
            key: "Strict-Transport-Security",
            value: "max-age=63072000; includeSubDomains; preload",
          },
        ]
      : baseHeaders;

    return [
      {
        source: "/:path*",
        headers,
      },
    ];
  },
  async rewrites() {
    return [
      {
        source: "/",
        has: [{ type: "header", key: "host", value: "^ops\\." }],
        destination: "/ops",
      },
      {
        source: "/login",
        has: [{ type: "header", key: "host", value: "^ops\\." }],
        destination: "/ops/login",
      },
    ];
  },
  turbopack: {
    root: __dirname, // Explicitly set root to silence multi-lockfile warning
  },
});
