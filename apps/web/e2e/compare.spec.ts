import { expect, test, type Page } from "@playwright/test";
import { sd15LoraFile } from "./fixtures";

async function openCompare(page: Page) {
  await page.goto("/compare");
  await expect(page.getByRole("heading", { name: "Compare", level: 1 })).toBeVisible();
  // Ready once the models have loaded and a base model is preselected.
  await expect(page.getByLabel("Base model")).toHaveValue(/\d+/);
}

async function fillShared(page: Page, prompt: string, steps = "3") {
  await page.getByLabel("Prompt", { exact: true }).fill(prompt);
  await page.getByLabel("Width").fill("256");
  await page.getByLabel("Height").fill("256");
  await page.getByLabel("Steps").fill(steps);
}

function cells(page: Page) {
  return page.getByRole("list", { name: "Comparison cells" }).getByRole("listitem");
}

test("compares LoRA strengths against a no-LoRA baseline", async ({ page }) => {
  await page.goto("/loras");
  await page.getByLabel("LoRA file (.safetensors)").setInputFiles({
    name: "cmp-style.safetensors",
    mimeType: "application/octet-stream",
    buffer: sd15LoraFile(),
  });
  await page.getByRole("button", { name: "Import" }).click();
  await expect(page.getByRole("status")).toHaveText("Imported cmp-style.safetensors.");

  await openCompare(page);
  await expect(page.getByLabel("Vary")).toHaveValue("lora_strength");
  await fillShared(page, "e2e compare strengths");
  await page.getByLabel("LoRA", { exact: true }).selectOption({ label: "cmp-style" });
  // The strength is what varies, so the single-strength slider is hidden.
  await expect(page.getByLabel("LoRA strength")).toHaveCount(0);
  await page.getByLabel("Strengths").fill("none, 0.4, 0.8");
  await page.getByRole("button", { name: "Compare", exact: true }).click();

  await expect(page.getByText("Completed", { exact: true })).toBeVisible();
  await expect(page).toHaveURL(/\/compare\?id=\d+/);
  await expect(cells(page)).toHaveCount(3);
  await expect(cells(page).nth(0)).toHaveAccessibleName("No LoRA");
  await expect(cells(page).nth(1)).toHaveAccessibleName("LoRA 0.40");
  await expect(cells(page).nth(2)).toHaveAccessibleName("LoRA 0.80");
  for (const index of [0, 1, 2]) {
    await expect(cells(page).nth(index).getByRole("img")).toBeVisible();
  }
  await expect(cells(page).nth(2).getByText("cmp-style @ 0.80")).toBeVisible();

  // Every cell is also a normal history entry.
  await page.goto("/history");
  await page.getByRole("searchbox", { name: "Search prompts" }).fill("e2e compare strengths");
  await expect(page.getByRole("article")).toHaveCount(3);
});

test("compares seeds and reuses one cell's settings", async ({ page }) => {
  await openCompare(page);
  await page.getByLabel("Vary").selectOption("seed");
  await expect(page.getByLabel("Seed", { exact: true })).toHaveCount(0);
  await fillShared(page, "e2e compare seeds");
  await page.getByLabel("Seeds", { exact: true }).fill("11, 22, 33");
  await page.getByRole("button", { name: "Compare", exact: true }).click();

  await expect(page.getByText("Completed", { exact: true })).toBeVisible();
  await expect(cells(page)).toHaveCount(3);
  await expect(cells(page).nth(1)).toHaveAccessibleName("Seed 22");

  await page.getByRole("link", { name: "Reuse settings of Seed 22" }).click();
  await expect(page).toHaveURL(/\/generate\?from=\d+/);
  await expect(page.getByLabel("Prompt", { exact: true })).toHaveValue("e2e compare seeds");
  await expect(page.getByLabel("Seed", { exact: true })).toHaveValue("22");
});

test("compares models", async ({ page }) => {
  await openCompare(page);
  await page.getByLabel("Vary").selectOption("model");
  await expect(page.getByLabel("Base model")).toHaveCount(0);
  await fillShared(page, "e2e compare models");
  await page.getByRole("checkbox", { name: /^tiny sd SD/ }).check();
  await page.getByRole("checkbox", { name: /^tiny sd b/ }).check();
  await page.getByRole("button", { name: "Compare", exact: true }).click();

  await expect(page.getByText("Completed", { exact: true })).toBeVisible();
  await expect(cells(page)).toHaveCount(2);
  await expect(cells(page).nth(0)).toHaveAccessibleName("tiny sd");
  await expect(cells(page).nth(1)).toHaveAccessibleName("tiny sd b");
});

test("shows validation errors without starting", async ({ page }) => {
  await openCompare(page);
  await page.getByLabel("Prompt", { exact: true }).fill("e2e compare invalid");
  await page.getByLabel("Strengths").fill("0.5");
  await page.getByRole("button", { name: "Compare", exact: true }).click();

  await expect(page.getByText("Enter between 2 and 6 strengths.")).toBeVisible();
  await expect(page.getByText("Choose a LoRA to compare its strengths.")).toBeVisible();
  await expect(page.getByText("Ready. Configure your prompt")).toBeVisible();
});

test("cancelling keeps finished cells, and comparisons can be reopened and deleted", async ({
  page,
}) => {
  await openCompare(page);
  await page.getByLabel("Vary").selectOption("seed");
  await fillShared(page, "e2e compare cancel", "40");
  await page.getByLabel("Seeds", { exact: true }).fill("1, 2, 3");
  await page.getByRole("button", { name: "Compare", exact: true }).click();

  // Cancel once the second cell is under way, so the first one is already saved.
  await expect(page.getByText(/Cell 2 of 3/)).toBeVisible();
  await page.getByRole("button", { name: "Cancel" }).click();
  await expect(page.getByText("Cancelled", { exact: true })).toBeVisible();
  await expect(page.getByRole("status")).toHaveText(
    "Comparison cancelled. Finished cells were kept.",
  );
  await expect(cells(page).nth(0).getByRole("img")).toBeVisible();
  await expect(cells(page).nth(2)).toContainText("Not generated");

  // Reopen from the recent list on a fresh page.
  await page.goto("/compare");
  await page.getByRole("link", { name: /e2e compare cancel/ }).click();
  await expect(page).toHaveURL(/\/compare\?id=\d+/);
  await expect(cells(page)).toHaveCount(3);

  await page.getByRole("button", { name: "Delete comparison" }).click();
  await page.getByRole("button", { name: "Confirm delete" }).click();
  await expect(page.getByRole("status")).toHaveText("Comparison deleted.");
  await expect(page.getByRole("link", { name: /e2e compare cancel/ })).toHaveCount(0);
});
