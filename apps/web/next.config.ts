import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  // The Next.js server proxies `/backend/*` to FastAPI so the browser only
  // ever talks to same-origin URLs — auth cookies (httpOnly, set by FastAPI)
  // stay first-party and survive in browsers that block third-party cookies.
  async rewrites() {
    const apiBaseUrl = process.env.BACKEND_API_URL ?? "http://localhost:8000";
    return [{ source: "/backend/:path*", destination: `${apiBaseUrl}/:path*` }];
  },
};

export default nextConfig;
