const withBundleAnalyzer =
  process.env.ANALYZE === "true"
    ? require("@next/bundle-analyzer")({ enabled: true })
    : (config) => config;

module.exports = withBundleAnalyzer({
  turbopack: {
    root: __dirname, // Explicitly set root to silence multi-lockfile warning
  },
});
