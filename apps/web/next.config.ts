import path from "node:path";
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

  // In a monorepo, Next's default file-tracing root detection (walking up
  // to the nearest lockfile) can disagree with Vercel's own root
  // calculation for packaging the deployed function, which silently drops
  // files outputFileTracingIncludes lists even though they appear correctly
  // in the local .next trace manifest. Pinning it explicitly to the actual
  // repo root removes that ambiguity.
  outputFileTracingRoot: path.join(__dirname, "../.."),

  // Prisma's query-engine binary lives in a dot-prefixed sibling package
  // (.prisma/client) several symlink hops deep inside pnpm's nested
  // node_modules/.pnpm/<hash>/node_modules structure, which Vercel's
  // serverless function file tracer does not reliably follow on its own,
  // confirmed by locating the actual .so.node file on disk after every
  // other fix attempt (default output path, hoisting, outputFileTracingRoot
  // alone) still failed at runtime with "could not locate the Query Engine"
  // in the real deployed function logs. The glob covers the version-hashed
  // pnpm folder name without hardcoding it.
  outputFileTracingIncludes: {
    "/**": [
      "../../node_modules/.pnpm/@prisma+client@*/node_modules/.prisma/client/**/*",
    ],
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
