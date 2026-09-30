import { expect, test, type Page } from "@playwright/test";
import { picturePng } from "./images";

async function datasetWithImages(page: Page, name: string) {
  await page.goto("/datasets");
  await page.getByLabel("Name").fill(name);
  await page.getByRole("button", { name: "Create dataset" }).click();
  await expect(page).toHaveURL(/\/datasets\/\d+$/);
  await page.getByLabel("Upload images").setInputFiles([
    { name: "one.png", mimeType: "image/png", buffer: picturePng(501) },
    { name: "two.png", mimeType: "image/png", buffer: picturePng(502) },
  ]);
  await expect(page.getByLabel("Upload report")).toContainText("Added 2 images");
  const card = page.getByRole("listitem", { name: "one.png" });
  await card.getByLabel("Caption").fill("a red and blue pattern");
  await card.getByRole("button", { name: "Save caption" }).click();
  await expect(card.getByText("Manual")).toBeVisible();
}

async function openTraining(page: Page, dataset: string, lora: string, steps: string) {
  await page.goto("/training");
  await expect(page.getByRole("heading", { name: "Training", level: 1 })).toBeVisible();
  await page.getByLabel("Dataset").selectOption({ label: `${dataset} (2 images)` });
  await expect(page.getByText("1 image has no caption")).toBeVisible();
  await page.getByLabel("Base model").selectOption({ label: "tiny sd" });
  await page.getByLabel("LoRA name").fill(lora);
  await page.getByLabel("Trigger word").fill("fgx");
  await page.getByRole("button", { name: "Quick test" }).click();
  await page.getByLabel("Training steps").fill(steps);
}

function runCard(page: Page, name: string) {
  return page.getByRole("listitem", { name: `Training run ${name}` });
}

test("trains a LoRA and makes it available for generation", async ({ page }) => {
  await datasetWithImages(page, "e2e train set");
  await openTraining(page, "e2e train set", "e2e-lora", "30");
  await page.getByLabel("Save every (steps)").fill("10");
  await page.getByRole("button", { name: "Start training" }).click();

  const progress = page.getByLabel("Training progress");
  await expect(progress).toBeVisible();
  await expect(progress).toContainText(/\d+ \/ 30/);
  await expect(page.getByLabel("Training status")).toHaveText(
    'Training finished. The LoRA "e2e-lora" is ready on the Generate page.',
  );

  const card = runCard(page, "e2e-lora");
  await expect(card.getByText("completed", { exact: true })).toBeVisible();
  await expect(card.getByRole("img", { name: /Sample \d from e2e-lora/ })).toHaveCount(2);
  await expect(card.getByRole("figure", { name: "Training loss chart" })).toBeVisible();
  // A finished run gives the next one a time estimate.
  await expect(page.getByText(/Estimated ~.* of training on this machine/)).toBeVisible();

  await card.getByRole("link", { name: "View LoRA" }).click();
  const lora = page.getByRole("article", { name: "LoRA e2e-lora" });
  await expect(lora.getByLabel("Trigger words")).toHaveValue("fgx");
  await expect(lora.getByText("For SD 1.x")).toBeVisible();

  await page.goto("/generate");
  await expect(page.getByLabel("Base model")).toHaveValue(/\d+/);
  await expect(
    page.getByLabel("LoRA", { exact: true }).locator("option", { hasText: "e2e-lora" }),
  ).toHaveCount(1);
});

test("validates the form and reports a failed run", async ({ page }) => {
  await datasetWithImages(page, "e2e train fail");
  await openTraining(page, "e2e train fail", "", "10");
  await page.getByLabel("Rank").fill("0");
  await page.getByRole("button", { name: "Start training" }).click();
  await expect(page.getByText("Name the LoRA.")).toBeVisible();
  await expect(page.getByText("Rank must be between 1 and 128.")).toBeVisible();

  await page.getByLabel("Rank").fill("8");
  // The mock trainer fails on purpose for this name.
  await page.getByLabel("LoRA name").fill("mock-fail");
  await page.getByRole("button", { name: "Start training" }).click();
  await expect(
    page.getByRole("alert").filter({ hasText: "Mock training failed on purpose." }),
  ).toBeVisible();
  await expect(runCard(page, "mock-fail").getByText("failed", { exact: true })).toBeVisible();
});

test("cancels a run, and reattaches to a running run after reload", async ({ page }) => {
  await datasetWithImages(page, "e2e train cancel");
  await openTraining(page, "e2e train cancel", "e2e-cancel", "2000");
  await page.getByRole("button", { name: "Start training" }).click();
  await expect(page.getByLabel("Training progress")).toContainText(/[1-9]\d* \/ 2000/);

  // The run keeps going in its own process; a reload picks it up again.
  await page.reload();
  await expect(page.getByLabel("Training progress")).toBeVisible();
  await expect(page.getByRole("button", { name: "Start training" })).toBeDisabled();

  await page.getByRole("button", { name: "Cancel training" }).click();
  await expect(page.getByLabel("Training status")).toHaveText("Training cancelled.");
  await expect(runCard(page, "e2e-cancel").getByText("cancelled", { exact: true })).toBeVisible();
  await expect(page.getByRole("button", { name: "Start training" })).toBeEnabled();
});
