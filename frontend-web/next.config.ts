import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  output: "standalone",
  async rewrites() {
    // Em dev local o Next.js roda sozinho (sem o Caddy na frente) — essa
    // regra faz proxy de /api/* pro backend FastAPI local. Em produção o
    // Caddy já intercepta /api/* antes de chegar aqui, então isso nunca é
    // exercido (ver Caddyfile na raiz do repo).
    return [
      {
        source: "/api/:path*",
        destination: `${process.env.BACKEND_URL ?? "http://localhost:8000"}/api/:path*`,
      },
    ];
  },
};

export default nextConfig;
