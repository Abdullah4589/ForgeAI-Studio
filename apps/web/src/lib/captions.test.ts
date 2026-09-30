import { describe, expect, it } from "vitest";
import { image } from "@/test/fixtures";
import { captionSummary, previewCaptioning, willCaption } from "./captions";
import type { Job } from "./types";

const empty = image(1);
const ai = image(2, { caption: "a lighthouse", caption_source: "ai" });
const manual = image(3, { caption: "my words", caption_source: "manual" });

describe("willCaption", () => {
  it.each([
    [empty, "empty_only", true],
    [ai, "empty_only", false],
    [ai, "replace_ai", true],
    [manual, "replace_ai", false],
    [manual, "everything", true],
  ] as const)("image %# in %s mode", (img, mode, expected) => {
    expect(willCaption(img, mode)).toBe(expected);
  });
});

it("previews how many captions a run writes and how many are the user's own", () => {
  const images = [empty, ai, manual];
  expect(previewCaptioning(images, "empty_only")).toEqual({ total: 1, manualOverwrites: 0 });
  expect(previewCaptioning(images, "replace_ai")).toEqual({ total: 2, manualOverwrites: 0 });
  expect(previewCaptioning(images, "everything")).toEqual({ total: 3, manualOverwrites: 1 });
});

it("summarises a finished caption job", () => {
  const job = { result: { captioned: 3, skipped: 1, failed: 0 } } as Job;
  expect(captionSummary(job)).toBe("Captioned 3 images, skipped 1 changed meanwhile.");
  expect(captionSummary({ result: { captioned: 1 } } as Job)).toBe("Captioned 1 image.");
});
