import { describe, expect, it } from "vitest";
import { batches, filterImages, mergeUploadResults, moveItem, uploadSummary } from "./datasets";
import { image } from "@/test/fixtures";

describe("moveItem", () => {
  it("moves items without mutating the input", () => {
    const items = ["a", "b", "c", "d"];
    expect(moveItem(items, 0, 2)).toEqual(["b", "c", "a", "d"]);
    expect(moveItem(items, 3, 0)).toEqual(["d", "a", "b", "c"]);
    expect(items).toEqual(["a", "b", "c", "d"]);
  });

  it("returns the same array for no-op or out-of-range moves", () => {
    const items = ["a", "b"];
    expect(moveItem(items, 1, 1)).toBe(items);
    expect(moveItem(items, 0, 5)).toBe(items);
    expect(moveItem(items, -1, 0)).toBe(items);
  });
});

it("batches files into API-sized requests", () => {
  const files = Array.from({ length: 120 }, (_, i) => i);
  expect(batches(files).map((b) => b.length)).toEqual([50, 50, 20]);
  expect(batches([])).toEqual([]);
});

it("merges and summarises upload results", () => {
  const merged = mergeUploadResults([
    { added: [image(1)], skipped: [] },
    { added: [image(2)], skipped: [{ filename: "x", reason: "duplicate", message: "dup" }] },
  ]);
  expect(merged.added.map((i) => i.id)).toEqual([1, 2]);
  expect(uploadSummary(merged)).toBe("Added 2 images, skipped 1.");
  expect(uploadSummary({ added: [image(1)], skipped: [] })).toBe("Added 1 image.");
});

it("filters flagged and uncaptioned images", () => {
  const images = [
    image(1, { flags: ["possibly_blurry"], caption: "cat" }),
    image(2),
    image(3, { caption: "dog" }),
  ];
  expect(filterImages(images, "all")).toHaveLength(3);
  expect(filterImages(images, "flagged").map((i) => i.id)).toEqual([1]);
  expect(filterImages(images, "uncaptioned").map((i) => i.id)).toEqual([2]);
});
