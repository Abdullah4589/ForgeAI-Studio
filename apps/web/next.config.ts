import { existsSync } from "node:fs";
import { resolve } from "node:path";
import type { NextConfig } from "next";
import { publicApiToken } from "./src/lib/root-env";

// `next dev` / `next build` run with cwd apps/web. Docker's build stage uses the same layout.
const envCandidates = [resolve(process.cwd(), "../../.env"), resolve(process.cwd(), ".env")].filter(
  existsSync,
);

const nextConfig: NextConfig = {
  // Self-contained server bundle for the Docker image (docker/web.Dockerfile).
  output: "standalone",
  env: {
    // Inlined into the browser bundle. Empty when auth is off.
    NEXT_PUBLIC_API_TOKEN: publicApiToken(process.env, envCandidates),
  },
};

export default nextConfig;
