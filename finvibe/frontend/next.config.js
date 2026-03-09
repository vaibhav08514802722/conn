/** @type {import('next').NextConfig} */
const nextConfig = {
  async rewrites() {
    const backendUrl =
      process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";
    return [
      {
        source: "/api/:path*",
        destination: `${backendUrl}/api/:path*`,
      },
    ];
  },
  // Output standalone build for production (smaller, self-contained)
  output: process.env.NODE_ENV === "production" ? "standalone" : undefined,
};

module.exports = nextConfig;
