import type { NextConfig } from "next";

// The browser only talks to this origin; /api/* is proxied to the Travo API so no CORS surface
// is exposed (ADR-017).
const apiUrl = process.env.TRAVO_API_URL ?? "http://localhost:8000";

const config: NextConfig = {
  reactStrictMode: true,
  poweredByHeader: false,
  // Do not generate AGENTS.md / CLAUDE.md into the app; project memory lives at the repo root.
  agentRules: false,
  async rewrites() {
    return [{ source: "/api/:path*", destination: `${apiUrl}/:path*` }];
  },
  async headers() {
    return [
      {
        source: "/:path*",
        headers: [
          { key: "X-Frame-Options", value: "DENY" },
          { key: "X-Content-Type-Options", value: "nosniff" },
          { key: "Referrer-Policy", value: "no-referrer" },
        ],
      },
    ];
  },
};

export default config;
