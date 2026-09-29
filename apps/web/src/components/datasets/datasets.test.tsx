import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import { image } from "@/test/fixtures";
import { DatasetImageCard } from "./DatasetImageCard";
import { UploadDropzone } from "./UploadDropzone";

const noDrag = {
  onDragStart: vi.fn(),
  onDragOver: vi.fn(),
  onDrop: vi.fn(),
  onDragEnd: vi.fn(),
};

function renderCard(overrides: Partial<Parameters<typeof DatasetImageCard>[0]> = {}) {
  const props = {
    image: image(7, { original_filename: "cat.png", caption: "a cat" }),
    index: 1,
    total: 3,
    canReorder: true,
    nameOf: (id: number) => `img-${id}.png`,
    onPreview: vi.fn(),
    onMove: vi.fn(),
    onSaveCaption: vi.fn().mockResolvedValue(true),
    onRemove: vi.fn(),
    dragHandlers: noDrag,
    ...overrides,
  };
  render(<DatasetImageCard {...props} />);
  return props;
}

describe("DatasetImageCard", () => {
  it("shows image facts, flags and similar images", () => {
    renderCard({
      image: image(7, {
        original_filename: "cat.png",
        width: 320,
        height: 240,
        flags: ["low_resolution", "near_duplicate"],
        near_duplicate_of: [9],
      }),
    });
    expect(screen.getByText(/320×240/)).toBeInTheDocument();
    const flags = within(screen.getByRole("list", { name: "Quality flags" }));
    expect(flags.getByText("Low resolution")).toBeInTheDocument();
    expect(flags.getByText("Near-duplicate")).toBeInTheDocument();
    expect(screen.getByText("Similar to img-9.png")).toBeInTheDocument();
  });

  it("saves an edited caption only when it changed", async () => {
    const props = renderCard();
    const save = screen.getByRole("button", { name: "Save caption" });
    expect(save).toBeDisabled();

    const caption = screen.getByLabelText("Caption");
    await userEvent.clear(caption);
    await userEvent.type(caption, "a tabby cat");
    await userEvent.click(save);
    expect(props.onSaveCaption).toHaveBeenCalledWith(props.image, "a tabby cat");
  });

  it("saves with Ctrl+Enter", async () => {
    const props = renderCard();
    await userEvent.type(screen.getByLabelText("Caption"), " indoors{Control>}{Enter}{/Control}");
    expect(props.onSaveCaption).toHaveBeenCalledWith(props.image, "a cat indoors");
  });

  it("moves and disables arrows at the ends or while filtered", async () => {
    const props = renderCard();
    await userEvent.click(screen.getByRole("button", { name: "Move cat.png up" }));
    expect(props.onMove).toHaveBeenCalledWith(1, 0);

    renderCard({ index: 2 });
    expect(screen.getAllByRole("button", { name: "Move cat.png down" })[1]).toBeDisabled();
  });

  it("disables reordering when filtered", () => {
    renderCard({ canReorder: false });
    expect(screen.getByRole("button", { name: "Move cat.png up" })).toBeDisabled();
    expect(screen.getByRole("listitem", { name: "cat.png" })).toHaveAttribute("draggable", "false");
  });

  it("asks before removing", async () => {
    const props = renderCard();
    await userEvent.click(screen.getByRole("button", { name: "Remove cat.png" }));
    expect(props.onRemove).not.toHaveBeenCalled();
    await userEvent.click(screen.getByRole("button", { name: "Remove" }));
    expect(props.onRemove).toHaveBeenCalledWith(props.image);
  });

  it("opens the preview", async () => {
    const props = renderCard();
    await userEvent.click(screen.getByRole("button", { name: "Preview cat.png" }));
    expect(props.onPreview).toHaveBeenCalledWith(props.image);
  });
});

describe("UploadDropzone", () => {
  it("passes chosen files on", async () => {
    const onFiles = vi.fn();
    render(<UploadDropzone busy={false} onFiles={onFiles} />);
    const files = [
      new File(["a"], "a.png", { type: "image/png" }),
      new File(["b"], "b.jpg", { type: "image/jpeg" }),
    ];
    await userEvent.upload(screen.getByLabelText("Upload images"), files);
    expect(onFiles).toHaveBeenCalledWith(files);
  });

  it("is disabled while uploading", () => {
    render(<UploadDropzone busy onFiles={vi.fn()} />);
    expect(screen.getByLabelText("Upload images")).toBeDisabled();
    expect(screen.getByText(/Uploading/)).toBeInTheDocument();
  });
});
