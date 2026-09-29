import { expect, test, type Page } from "@playwright/test";
import { gradientPng, picturePng } from "./images";

type Upload = { name: string; mimeType: string; buffer: Buffer };

function png(name: string, buffer: Buffer): Upload {
  return { name, mimeType: "image/png", buffer };
}

async function createDataset(page: Page, name: string) {
  await page.goto("/datasets");
  await page.getByLabel("Name").fill(name);
  await page.getByRole("button", { name: "Create dataset" }).click();
  await expect(page).toHaveURL(/\/datasets\/\d+$/);
  await expect(page.getByRole("heading", { name, level: 1 })).toBeVisible();
}

async function uploadFiles(page: Page, files: Upload[]) {
  await page.getByLabel("Upload images").setInputFiles(files);
  await expect(page.getByRole("status")).toContainText(/^Added \d+ image/);
}

function images(page: Page) {
  return page.getByRole("list", { name: "Dataset images" }).getByRole("listitem", {
    name: /\.png$/,
  });
}

function summary(page: Page) {
  return page.getByLabel("Dataset summary");
}

test("uploads images, skipping duplicates and invalid files", async ({ page }) => {
  await createDataset(page, "e2e uploads");
  const cat = picturePng(1);
  await uploadFiles(page, [
    png("cat.png", cat),
    png("dog.png", picturePng(2)),
    png("cat-copy.png", cat),
    { name: "notes.png", mimeType: "image/png", buffer: Buffer.from("not really an image") },
  ]);

  await expect(page.getByRole("status")).toHaveText("Added 2 images, skipped 2.");
  const report = page.getByLabel("Upload report");
  await expect(report).toContainText("cat-copy.png: Same file as cat.png.");
  await expect(report).toContainText("notes.png: The file is not a readable image.");
  await expect(images(page)).toHaveCount(2);
  await expect(summary(page)).toContainText("2 images · 0 flagged · 2 uncaptioned");

  // The dataset shows up in the list with its counts.
  await page.getByRole("link", { name: "All datasets" }).click();
  await expect(page.getByRole("link", { name: /e2e uploads/ })).toContainText("2 images");
});

test("edits captions, reorders, previews and removes images", async ({ page }) => {
  await createDataset(page, "e2e editing");
  await uploadFiles(page, [png("first.png", picturePng(11)), png("second.png", picturePng(12))]);

  const first = page.getByRole("listitem", { name: "first.png" });
  await first.getByLabel("Caption").fill("a red square on blue");
  await first.getByRole("button", { name: "Save caption" }).click();
  await expect(first.getByRole("button", { name: "Save caption" })).toBeDisabled();
  await expect(summary(page)).toContainText("1 uncaptioned");

  await page.getByRole("button", { name: "Move second.png up" }).click();
  await expect(images(page).first()).toHaveAccessibleName("second.png");

  // Both survive a reload, so they were saved on the server.
  await page.reload();
  await expect(images(page).first()).toHaveAccessibleName("second.png");
  await expect(page.getByRole("listitem", { name: "first.png" }).getByLabel("Caption")).toHaveValue(
    "a red square on blue",
  );

  await page.getByRole("button", { name: "Preview first.png" }).click();
  const preview = page.getByRole("dialog", { name: "first.png" });
  await expect(preview).toContainText("512×512");
  await expect(preview).toContainText("a red square on blue");
  await preview.getByRole("button", { name: "Close preview" }).click();
  await expect(preview).toBeHidden();

  await page.getByRole("button", { name: "Remove second.png" }).click();
  await page.getByRole("button", { name: "Remove", exact: true }).click();
  await expect(images(page)).toHaveCount(1);
  await expect(summary(page)).toContainText("1 image ·");
});

test("flags low-quality images and near-duplicates, and filters them", async ({ page }) => {
  await createDataset(page, "e2e quality");
  await uploadFiles(page, [
    png("good.png", picturePng(21)),
    png("tiny.png", picturePng(22, 256)),
    png("smooth.png", gradientPng()),
    png("good-bigger.png", picturePng(21, 768)),
  ]);

  const flagsOf = (name: string) =>
    page.getByRole("listitem", { name }).getByRole("list", { name: "Quality flags" });
  await expect(flagsOf("tiny.png")).toContainText("Low resolution");
  await expect(flagsOf("smooth.png")).toContainText("Possibly blurry");
  await expect(flagsOf("good.png")).toContainText("Near-duplicate");
  await expect(page.getByRole("listitem", { name: "good.png" })).toContainText(
    "Similar to good-bigger.png",
  );
  await expect(summary(page)).toContainText("4 flagged");

  await page.getByLabel("Show").selectOption("flagged");
  await expect(images(page)).toHaveCount(4);
  await expect(page.getByText("Show all images to change the order.")).toBeVisible();
  await expect(page.getByRole("button", { name: "Move tiny.png up" })).toBeDisabled();

  // Removing one of the near-identical pair clears the flag on the other.
  await page.getByLabel("Show").selectOption("all");
  await page.getByRole("button", { name: "Remove good-bigger.png" }).click();
  await page.getByRole("button", { name: "Remove", exact: true }).click();
  await expect(page.getByRole("listitem", { name: "good.png" })).not.toContainText(
    "Near-duplicate",
  );

  // Raising the target resolution re-evaluates every image.
  await page.getByText("Dataset settings").click();
  await page.getByLabel("Target resolution").selectOption("768");
  await page.getByRole("button", { name: "Save settings" }).click();
  await expect(flagsOf("good.png")).toContainText("Low resolution");
  await expect(summary(page)).toContainText("target 768 px");
});

test("reorders images by drag and drop", async ({ page }) => {
  await createDataset(page, "e2e drag");
  await uploadFiles(page, [
    png("one.png", picturePng(41)),
    png("two.png", picturePng(42)),
    png("three.png", picturePng(43)),
  ]);

  await page
    .getByRole("listitem", { name: "three.png" })
    .dragTo(page.getByRole("listitem", { name: "one.png" }));
  await expect(images(page).first()).toHaveAccessibleName("three.png");

  await page.reload();
  await expect(images(page)).toHaveCount(3);
  for (const [index, name] of ["three.png", "one.png", "two.png"].entries()) {
    await expect(images(page).nth(index)).toHaveAccessibleName(name);
  }
});

test("renames and deletes a dataset", async ({ page }) => {
  await createDataset(page, "e2e to delete");
  await uploadFiles(page, [png("a.png", picturePng(31))]);

  await page.getByText("Dataset settings").click();
  await page.getByLabel("Name").fill("e2e renamed");
  await page.getByRole("button", { name: "Save settings" }).click();
  await expect(page.getByRole("heading", { name: "e2e renamed", level: 1 })).toBeVisible();

  await page.getByRole("button", { name: "Delete dataset…" }).click();
  await page.getByRole("button", { name: "Delete dataset", exact: true }).click();
  await expect(page).toHaveURL(/\/datasets$/);
  await expect(page.getByRole("link", { name: /e2e renamed/ })).toHaveCount(0);
});

test("validates the new dataset form", async ({ page }) => {
  await page.goto("/datasets");
  await page.getByRole("button", { name: "Create dataset" }).click();
  await expect(page.getByText("Enter a name.")).toBeVisible();
  await expect(page).toHaveURL(/\/datasets$/);
});
