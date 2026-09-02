import type { NextConfig } from "next";

const API = process.env.NIMBUS_API_URL || "http://127.0.0.1:8080";

const nextConfig: NextConfig = {
  async rewrites() {
    return [
      { source: "/chat", destination: `${API}/chat` },
      { source: "/chat/stream", destination: `${API}/chat/stream` },
      { source: "/api/:path*", destination: `${API}/api/:path*` },
    ];
  },
};

export default nextConfig;
