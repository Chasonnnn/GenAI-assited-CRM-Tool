/* global process, require, module, __dirname */
/* eslint-disable @typescript-eslint/no-require-imports */

const withBundleAnalyzer =
  process.env.ANALYZE === "true"
    ? require("@next/bundle-analyzer")({ enabled: true })
    : (config) => config;

module.exports = withBundleAnalyzer({
  async rewrites() {
    return [
      {
        source: "/",
        has: [{ type: "header", key: "host", value: "^ops\\." }],
        destination: "/ops",
      },
      {
        source:
          "/:path((?!_next|api|favicon\\.ico|robots\\.txt|sitemap\\.xml|ops|mfa|auth\\/duo\\/callback).*)",
        has: [{ type: "header", key: "host", value: "^ops\\." }],
        destination: "/ops/:path",
      },
    ];
  },
  turbopack: {
    root: __dirname, // Explicitly set root to silence multi-lockfile warning
  },
});
