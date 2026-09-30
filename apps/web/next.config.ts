import path from "node:path";

import type { NextConfig } from "next";

// The browser only talks to this origin. /api/* and /auth/* are route handlers (a BFF) that
// hold the session server-side (ADR-018). Page CSP is set per request in src/proxy.ts.
const config: NextConfig = {
  reactStrictMode: true,
  // Self-contained server for the container image (deploy/Dockerfile.web); traced from the
  // workspace root so pnpm's symlinked dependencies are included.
  output: "standalone",
  outputFileTracingRoot: path.join(process.cwd(), "../.."),
  poweredByHeader: false,
  // Do not generate AGENTS.md / CLAUDE.md into the app; project memory lives at the repo root.
  agentRules: false,
  async headers() {
    return [
      {
        source: "/:path*",
        headers: [
          { key: "X-Frame-Options", value: "DENY" },
          { key: "X-Content-Type-Options", value: "nosniff" },
          { key: "Referrer-Policy", value: "no-referrer" },
          { key: "Permissions-Policy", value: "camera=(), microphone=(), geolocation=()" },
        ],
      },
    ];
  },
};

export default config;
