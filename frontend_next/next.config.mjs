/** @type {import('next').NextConfig} */
const nextConfig = {
  reactStrictMode: true,
  // Emit a self-contained server bundle (.next/standalone) for a lean Docker image.
  output: "standalone",
  experimental: {
    // neo4j-driver is server-only; keep it out of the client bundle.
    serverComponentsExternalPackages: ["neo4j-driver"],
  },
};

export default nextConfig;
