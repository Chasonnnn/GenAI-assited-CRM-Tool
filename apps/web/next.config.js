/* global process, require, module, __dirname */
/* eslint-disable @typescript-eslint/no-require-imports */

const withBundleAnalyzer =
  process.env.ANALYZE === "true"
    ? require("@next/bundle-analyzer")({ enabled: true })
    : (config) => config;

module.exports = withBundleAnalyzer({
  // React Compiler (stable in React 19) auto-memoizes components/hooks, letting us retire
  // manual useMemo/useCallback over time. Next runs it via babel-plugin-react-compiler but
  // only on files with JSX/Hooks (SWC pre-filter), so build-time cost stays small.
  reactCompiler: true,
  // Stable in Next 16: compile-time validation of <Link href> / router.push across the
  // multi-tenant route trees. The .next/types/routes.d.ts artifact is already generated
  // and wired into tsconfig; this flag turns on enforcement.
  typedRoutes: true,
  experimental: {
    // Tree-shake heavy barrel-export libs so only the modules actually used are bundled.
    // lucide-react / date-fns / recharts are optimized by Next automatically, so they are
    // intentionally omitted here.
    optimizePackageImports: [
      "@fullcalendar/core",
      "@fullcalendar/react",
      "@fullcalendar/daygrid",
      "@fullcalendar/timegrid",
      "@fullcalendar/interaction",
      "@tiptap/react",
      "@tiptap/starter-kit",
      "@base-ui/react",
      "react-simple-maps",
    ],
  },
  async headers() {
    const sharedHeaders = [
      { key: "X-Content-Type-Options", value: "nosniff" },
      { key: "Referrer-Policy", value: "strict-origin-when-cross-origin" },
      {
        key: "Permissions-Policy",
        value: "camera=(), microphone=(), geolocation=(), browsing-topics=()",
      },
    ];
    const frameProtectionHeaders = [
      { key: "X-Frame-Options", value: "SAMEORIGIN" },
    ];

    // Only enable HSTS for production deploys (avoid affecting preview/dev).
    const isProd = process.env.VERCEL_ENV === "production";
    const headers = isProd
      ? [
          ...sharedHeaders,
          {
            key: "Strict-Transport-Security",
            value: "max-age=63072000; includeSubDomains; preload",
          },
        ]
      : sharedHeaders;

    return [
      {
        source: "/:path*",
        headers,
      },
      {
        source: "/((?!embed/forms).*)",
        headers: frameProtectionHeaders,
      },
      {
        source: "/embed/forms/:slug",
        headers: [{ key: "Cache-Control", value: "no-store" }],
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
