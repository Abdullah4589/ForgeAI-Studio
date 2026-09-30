import { expect, test, type Page } from "@playwright/test";
import { picturePng } from "./images";

async function datasetWith(page: Page, name: string, count: number, seed: number) {
  await page.goto("/datasets");
  await page.getByLabel("Name").fill(name);
  await page.getByRole("button", { name: "Create dataset" }).click();
  await expect(page).toHaveURL(/\/datasets\/\d+$/);
  await page.getByLabel("Upload images").setInputFiles(
    Array.from({ length: count }, (_, i) => ({
      name: `img-${i + 1}.png`,
      mimeType: "image/png",
      buffer: picturePng(seed + i),
    })),
  );
  await expect(page.getByLabel("Upload report")).toContainText(`Added ${count} images`);
}

function card(page: Page, index: number) {
  return page.getByRole("listitem", { name: `img-${index}.png` });
}

async function writeCaption(page: Page, index: number, text: string) {
  await card(page, index).getByLabel("Caption").fill(text);
  await card(page, index).getByRole("button", { name: "Save caption" }).click();
  await expect(card(page, index).getByText("Manual")).toBeVisible();
}

test("captions uncaptioned images and keeps the user's own captions", async ({ page }) => {
  await datasetWith(page, "e2e captions", 3, 100);
  await writeCaption(page, 1, "my own description");

  await expect(page.getByText("2 images will be captioned.")).toBeVisible();
  await page.getByRole("button", { name: "Generate captions" }).click();
  await expect(page.getByLabel("Caption status")).toHaveText("Keeping 1 caption you wrote.");
  await expect(page.getByText("Completed", { exact: true })).toBeVisible();
  await expect(page.getByLabel("Caption status")).toHaveText("Captioned 2 images.");

  await expect(card(page, 1).getByLabel("Caption")).toHaveValue("my own description");
  for (const index of [2, 3]) {
    await expect(card(page, index).getByLabel("Caption")).toHaveValue(
      /^a mock caption of a 512x512/,
    );
    await expect(card(page, index).getByText("AI", { exact: true })).toBeVisible();
  }
  await expect(page.getByLabel("Dataset summary")).toContainText("0 uncaptioned");

  // Editing an AI caption makes it the user's own.
  await writeCaption(page, 2, "a clearer description");
});

test("replacing manual captions needs confirmation", async ({ page }) => {
  await datasetWith(page, "e2e caption overwrite", 2, 200);
  await writeCaption(page, 1, "keep me unless I say so");

  await page.getByRole("radio", { name: /Every image/ }).check();
  await page.getByRole("button", { name: "Generate captions" }).click();
  await expect(
    page.getByRole("alert").filter({ hasText: "This will replace 1 caption you wrote." }),
  ).toBeVisible();
  await page.getByRole("button", { name: "Keep them" }).click();
  await expect(card(page, 1).getByLabel("Caption")).toHaveValue("keep me unless I say so");

  await page.getByRole("button", { name: "Generate captions" }).click();
  await page.getByRole("button", { name: "Replace my captions" }).click();
  await expect(page.getByText("Completed", { exact: true })).toBeVisible();
  await expect(card(page, 1).getByLabel("Caption")).toHaveValue(/^a mock caption/);
});

test("suggests a caption for one image", async ({ page }) => {
  await datasetWith(page, "e2e caption single", 2, 300);
  await writeCaption(page, 2, "hand written");

  await card(page, 1).getByRole("button", { name: "Suggest caption" }).click();
  await expect(page.getByText("Completed", { exact: true })).toBeVisible();
  await expect(card(page, 1).getByLabel("Caption")).toHaveValue(/^a mock caption/);
  await expect(card(page, 2).getByLabel("Caption")).toHaveValue("hand written");

  // A manual caption asks first.
  await card(page, 2).getByRole("button", { name: "Suggest caption" }).click();
  await card(page, 2).getByRole("button", { name: "Replace my caption" }).click();
  await expect(card(page, 2).getByText("AI", { exact: true })).toBeVisible();
});

test("shows progress, fills captions as they finish, and cancels", async ({ page }) => {
  await datasetWith(page, "e2e caption cancel", 6, 400);
  await page.getByRole("button", { name: "Generate captions" }).click();

  await expect(page.getByText(/Captioning img-\d\.png|Captioned \d of 6/)).toBeVisible();
  // The first caption appears while the rest are still running.
  await expect(card(page, 1).getByText("AI", { exact: true })).toBeVisible();
  await page.getByRole("button", { name: "Cancel" }).click();

  await expect(page.getByText("Cancelled", { exact: true })).toBeVisible();
  await expect(page.getByLabel("Caption status")).toHaveText(
    "Captioning cancelled. Finished captions were kept.",
  );
  await expect(card(page, 1).getByLabel("Caption")).toHaveValue(/^a mock caption/);
  await expect(card(page, 6).getByLabel("Caption")).toHaveValue("");
});
