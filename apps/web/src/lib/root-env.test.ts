import { mkdtempSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { describe, expect, it } from "vitest";
import { envFileValue, publicApiToken } from "./root-env";

describe("publicApiToken", () => {
  it("prefers the process environment over a dotenv file", () => {
    const dir = mkdtempSync(join(tmpdir(), "forge-env-"));
    const file = join(dir, ".env");
    writeFileSync(file, "API_TOKEN=from-file\n");
    expect(publicApiToken({ NEXT_PUBLIC_API_TOKEN: "from-env" }, [file])).toBe("from-env");
    expect(publicApiToken({ API_TOKEN: "shared" }, [file])).toBe("shared");
  });

  it("reads a quoted API_TOKEN from a dotenv file", () => {
    const dir = mkdtempSync(join(tmpdir(), "forge-env-"));
    const file = join(dir, ".env");
    writeFileSync(
      file,
      "# comment\nexport API_TOKEN='abc'\nNEXT_PUBLIC_API_URL=http://localhost\n",
    );
    expect(envFileValue(file, "API_TOKEN")).toBe("abc");
    expect(publicApiToken({}, [file])).toBe("abc");
    expect(publicApiToken({}, [join(dir, "missing.env")])).toBe("");
  });
});
