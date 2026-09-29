import { expect, test, type Page } from "@playwright/test";

/** Build a minimal, valid SD1.x LoRA safetensors file (header + zeroed fp16 tensors). */
function sd15LoraFile(): Buffer {
  const tensors: Record<string, number[]> = {
    "lora_unet_down_blocks_0_attentions_0_transformer_blocks_0_attn2_to_k.lora_down.weight": [
      4, 768,
    ],
    "lora_unet_down_blocks_0_attentions_0_transformer_blocks_0_attn2_to_k.lora_up.weight": [320, 4],
  };
  const header: Record<string, unknown> = {};
  let offset = 0;
  for (const [name, shape] of Object.entries(tensors)) {
    const size = shape.reduce((a, b) => a * b, 2);
    header[name] = { dtype: "F16", shape, data_offsets: [offset, offset + size] };
    offset += size;
  }
  const json = Buffer.from(JSON.stringify(header));
  const length = Buffer.alloc(8);
  length.writeBigUInt64LE(BigInt(json.length));
  return Buffer.concat([length, json, Buffer.alloc(offset)]);
}

async function openGenerate(page: Page) {
  await page.goto("/generate");
  await expect(page.getByRole("heading", { name: "Generate" })).toBeVisible();
  // The form is ready once the model list has loaded and a model is preselected.
  await expect(page.getByLabel("Base model")).toHaveValue(/\d+/);
}

async function generate(
  page: Page,
  prompt: string,
  options: { images?: number; seed?: string } = {},
) {
  await page.getByLabel("Prompt", { exact: true }).fill(prompt);
  await page.getByLabel("Width").fill("256");
  await page.getByLabel("Height").fill("256");
  await page.getByLabel("Steps").fill("5");
  await page.getByLabel("Images", { exact: true }).fill(String(options.images ?? 1));
  await page.getByLabel("Seed", { exact: true }).fill(options.seed ?? "");
  await page.getByRole("button", { name: "Generate" }).click();
  await expect(page.getByText("Completed", { exact: true })).toBeVisible();
}

test("app loads with navigation and redirects to Generate", async ({ page }) => {
  await page.goto("/");
  await expect(page).toHaveURL(/\/generate$/);
  const nav = page.getByRole("navigation", { name: "Main" });
  for (const name of ["Generate", "Models", "LoRAs", "History", "System", "Settings"]) {
    await expect(nav.getByRole("link", { name })).toBeVisible();
  }
  await expect(nav.getByRole("link", { name: "Generate" })).toHaveAttribute("aria-current", "page");
});

test("selects a model, enters a prompt and generates images", async ({ page }) => {
  await openGenerate(page);
  await expect(page.getByLabel("Base model").locator("option:checked")).toHaveText(
    "tiny sd (SD 1.x)",
  );

  await page.getByLabel("Prompt", { exact: true }).fill("x");
  await expect(page.getByText("1/2000")).toBeVisible();

  await generate(page, "e2e lighthouse at dusk", { images: 2, seed: "777" });

  const results = page.getByRole("list", { name: "Generated images" });
  await expect(results.getByRole("img")).toHaveCount(2);
  await expect(results.getByText("seed 777")).toBeVisible();
  await expect(results.getByText("seed 778")).toBeVisible();

  await page.getByRole("button", { name: "View metadata of image 1" }).click();
  const dialog = page.getByRole("dialog", { name: "Image metadata" });
  await expect(dialog).toContainText("e2e lighthouse at dusk");
  await expect(dialog).toContainText("256 x 256");
  await dialog.getByRole("button", { name: "Close" }).click();
  await expect(dialog).toBeHidden();

  const download = page.waitForEvent("download");
  await page.getByRole("link", { name: "Download image 1" }).click();
  expect((await download).suggestedFilename()).toMatch(/^forge-\d+\.png$/);
});

test("shows validation errors without submitting", async ({ page }) => {
  await openGenerate(page);
  await page.getByLabel("Prompt", { exact: true }).fill("");
  await page.getByLabel("Width").fill("500");
  await page.getByLabel("Steps").fill("0");
  await page.getByRole("button", { name: "Generate" }).click();

  await expect(page.getByText("Enter a prompt.")).toBeVisible();
  await expect(page.getByText("Width must be a multiple of 8.")).toBeVisible();
  await expect(page.getByText("Steps must be between 1 and 150.")).toBeVisible();
  await expect(page.getByLabel("Width")).toHaveAttribute("aria-invalid", "true");
  await expect(page.getByText("Ready. Configure your prompt")).toBeVisible();
});

test("cancels a running generation", async ({ page }) => {
  await openGenerate(page);
  await page.getByLabel("Prompt", { exact: true }).fill("e2e slow generation");
  await page.getByLabel("Width").fill("256");
  await page.getByLabel("Height").fill("256");
  await page.getByLabel("Steps").fill("150");
  await page.getByRole("button", { name: "Generate" }).click();

  await expect(page.getByText(/Step \d+ of 150/)).toBeVisible();
  await page.getByRole("button", { name: "Cancel" }).click();
  await expect(page.getByText("Cancelled", { exact: true })).toBeVisible();
  await expect(page.getByRole("status")).toHaveText("Generation cancelled.");
});

test("history search, filters and reuse settings", async ({ page }) => {
  await openGenerate(page);
  await generate(page, "e2e history castle", { seed: "4242" });

  await page
    .getByRole("navigation", { name: "Main" })
    .getByRole("link", { name: "History" })
    .click();
  await expect(page.getByRole("heading", { name: "History" })).toBeVisible();

  await page.getByRole("searchbox", { name: "Search prompts" }).fill("history castle");
  const entry = page.getByRole("article").filter({ hasText: "e2e history castle" });
  await expect(entry).toHaveCount(1);
  await expect(entry.getByText("seed 4242")).toBeVisible();

  await page.getByRole("searchbox", { name: "Search prompts" }).fill("no such prompt zzz");
  await expect(page.getByText("No generations found")).toBeVisible();
  await page.getByRole("searchbox", { name: "Search prompts" }).fill("history castle");

  await page.getByLabel("Filter by model").selectOption({ label: "tiny sd" });
  await expect(entry).toHaveCount(1);

  await entry.getByRole("link", { name: "Reuse settings" }).click();
  await expect(page).toHaveURL(/\/generate\?from=\d+/);
  await expect(page.getByLabel("Prompt", { exact: true })).toHaveValue("e2e history castle");
  await expect(page.getByLabel("Seed", { exact: true })).toHaveValue("4242");
  await expect(page.getByLabel("Width")).toHaveValue("256");
  await expect(page.getByLabel("Steps")).toHaveValue("5");
  await expect(page.getByRole("status")).toHaveText("Settings restored from history.");
});

test("reuse settings from a result restores that image's seed", async ({ page }) => {
  await openGenerate(page);
  await generate(page, "e2e reuse result", { images: 2, seed: "900" });
  await page.getByLabel("Prompt", { exact: true }).fill("something else");

  await page.getByRole("button", { name: "Reuse settings of image 2" }).click();
  await expect(page.getByLabel("Prompt", { exact: true })).toHaveValue("e2e reuse result");
  await expect(page.getByLabel("Seed", { exact: true })).toHaveValue("901");
  await expect(page.getByLabel("Images", { exact: true })).toHaveValue("1");
});

test("imports a LoRA and uses it for generation", async ({ page }) => {
  await page.goto("/loras");
  await page.getByLabel("LoRA file (.safetensors)").setInputFiles({
    name: "e2e-style.safetensors",
    mimeType: "application/octet-stream",
    buffer: sd15LoraFile(),
  });
  await page.getByRole("button", { name: "Import" }).click();
  await expect(page.getByRole("status")).toHaveText("Imported e2e-style.safetensors.");
  const card = page.getByRole("article", { name: "LoRA e2e-style" });
  await expect(card.getByText("For SD 1.x")).toBeVisible();

  await card.getByLabel("Trigger words").fill("e2estyle");
  await card.getByRole("button", { name: "Save" }).click();
  await expect(card.getByRole("button", { name: "Save" })).toBeDisabled();

  await openGenerate(page);
  await page.getByLabel("LoRA", { exact: true }).selectOption({ label: "e2e-style" });
  await expect(page.getByText("e2estyle")).toBeVisible();
  await expect(page.getByLabel("LoRA strength")).toBeEnabled();
  await generate(page, "e2e with lora");

  await page.getByRole("button", { name: "View metadata of image 1" }).click();
  await expect(page.getByRole("dialog", { name: "Image metadata" })).toContainText(
    "e2e-style @ 1.00",
  );
});

test("rejects an invalid LoRA upload with a clear message", async ({ page }) => {
  await page.goto("/loras");
  await page.getByLabel("LoRA file (.safetensors)").setInputFiles({
    name: "broken.safetensors",
    mimeType: "application/octet-stream",
    buffer: Buffer.from("definitely not a safetensors file"),
  });
  await page.getByRole("button", { name: "Import" }).click();
  await expect(
    page.getByRole("alert").filter({ hasText: "invalid safetensors header" }),
  ).toBeVisible();
});

test("system page reports hardware without a GPU requirement", async ({ page }) => {
  await page.goto("/system");
  await expect(page.getByRole("heading", { name: "System" })).toBeVisible();
  await expect(page.getByText("CUDA available")).toBeVisible();
  await expect(page.getByText("Generation backend")).toBeVisible();
  await expect(page.getByText("mock", { exact: true })).toBeVisible();
  await expect(page.getByRole("meter", { name: "RAM usage" })).toBeVisible();
});

test("settings page saves generation defaults", async ({ page }) => {
  await page.goto("/settings");
  await page.getByLabel("Default steps").fill("12");
  await page.getByRole("button", { name: "Save defaults" }).click();
  await expect(page.getByRole("status")).toHaveText("Defaults saved.");

  await openGenerate(page);
  await expect(page.getByLabel("Steps")).toHaveValue("12");

  // Restore so test order doesn't matter.
  await page.goto("/settings");
  await page.getByLabel("Default steps").fill("25");
  await page.getByRole("button", { name: "Save defaults" }).click();
  await expect(page.getByRole("status")).toHaveText("Defaults saved.");
});
