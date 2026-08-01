import type { NextConfig } from "next";

// Content-Security-Policy is intentionally broad on connect-src/img-src for
// https: because the map tile/style host and the postcode geocoder are both
// environment-configured (NEXT_PUBLIC_MAP_STYLE_URL, POSTCODE_GEOCODER),
// not hardcoded to one vendor. A production deployment that pins to a
// specific tile provider should narrow this to that provider's exact host.
const CONTENT_SECURITY_POLICY = [
  "default-src 'self'",
  "base-uri 'self'",
  "form-action 'self'",
  "frame-ancestors 'none'",
  "object-src 'none'",
  "script-src 'self' 'unsafe-inline'",
  "style-src 'self' 'unsafe-inline'",
  "img-src 'self' data: blob: https:",
  "font-src 'self' data:",
  "connect-src 'self' https:",
  "worker-src 'self' blob:",
  "manifest-src 'self'",
].join("; ");

const SECURITY_HEADERS = [
  { key: "Content-Security-Policy", value: CONTENT_SECURITY_POLICY },
  { key: "X-Content-Type-Options", value: "nosniff" },
  { key: "X-Frame-Options", value: "DENY" },
  { key: "Referrer-Policy", value: "strict-origin-when-cross-origin" },
  {
    key: "Permissions-Policy",
    value: "camera=(), microphone=(), geolocation=(self), interest-cohort=()",
  },
];

const nextConfig: NextConfig = {
  reactStrictMode: true,

  // packages/shared ships TypeScript source directly (no build step), so
  // Next needs to transpile it as part of the app bundle rather than
  // treating it as pre-built library code.
  transpilePackages: ["@schoolscope/shared"],

  eslint: {
    dirs: ["app", "components", "lib", "tests"],
  },

  async headers() {
    return [
      {
        source: "/:path*",
        headers: SECURITY_HEADERS,
      },
    ];
  },
};

export default nextConfig;
