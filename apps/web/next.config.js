const bundleAnalyzer = require("@next/bundle-analyzer");

const withBundleAnalyzer = bundleAnalyzer({
  enabled: process.env.ANALYZE === "true",
});

module.exports = withBundleAnalyzer({
  turbopack: {
    root: __dirname, // Explicitly set root to silence multi-lockfile warning
  },
});
