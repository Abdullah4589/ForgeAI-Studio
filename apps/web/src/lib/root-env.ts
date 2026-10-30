import { existsSync, readFileSync } from "node:fs";

/** Read one variable from a dotenv file. Missing file or key yields undefined. */
export function envFileValue(filePath: string, name: string): string | undefined {
  if (!existsSync(filePath)) return undefined;
  for (const rawLine of readFileSync(filePath, "utf8").split("\n")) {
    let line = rawLine.trim();
    if (!line || line.startsWith("#")) continue;
    if (line.startsWith("export ")) line = line.slice("export ".length).trim();
    const eq = line.indexOf("=");
    if (eq === -1 || line.slice(0, eq).trim() !== name) continue;
    let value = line.slice(eq + 1).trim();
    if (
      (value.startsWith('"') && value.endsWith('"')) ||
      (value.startsWith("'") && value.endsWith("'"))
    ) {
      value = value.slice(1, -1);
    }
    return value;
  }
  return undefined;
}

/**
 * Token the browser should send. Prefers the process environment (including a value baked in at
 * image build), then the repo-root `.env`, so one `API_TOKEN` configures the API and the UI.
 */
export function publicApiToken(env: NodeJS.Dict<string>, envFiles: string[] = []): string {
  const fromProcess = env.NEXT_PUBLIC_API_TOKEN || env.API_TOKEN;
  if (fromProcess) return fromProcess;
  for (const file of envFiles) {
    const named = envFileValue(file, "NEXT_PUBLIC_API_TOKEN") || envFileValue(file, "API_TOKEN");
    if (named) return named;
  }
  return "";
}
