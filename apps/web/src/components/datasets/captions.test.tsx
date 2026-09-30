import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import { image } from "@/test/fixtures";
import { CaptionPanel } from "./CaptionPanel";
import { DatasetImageCard } from "./DatasetImageCard";

const empty = image(1);
const manual = image(2, { caption: "my words", caption_source: "manual" });
const ai = image(3, {
  caption: "a lighthouse",
  caption_source: "ai",
  caption_model: "florence-2-base",
});

function renderPanel(images = [empty, manual, ai]) {
  const onStart = vi.fn();
  render(
    <CaptionPanel
      images={images}
      job={null}
      running={false}
      elapsedMs={0}
      onStart={onStart}
      onCancel={vi.fn()}
    />,
  );
  return onStart;
}

describe("CaptionPanel", () => {
  it("captions uncaptioned images by default", async () => {
    const onStart = renderPanel();
    expect(screen.getByText("1 image will be captioned.")).toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: "Generate captions" }));
    expect(onStart).toHaveBeenCalledWith("empty_only");
  });

  it("asks before replacing captions the user wrote", async () => {
    const onStart = renderPanel();
    await userEvent.click(screen.getByRole("radio", { name: /Every image/ }));
    expect(screen.getByText("3 images will be captioned.")).toBeInTheDocument();

    await userEvent.click(screen.getByRole("button", { name: "Generate captions" }));
    expect(onStart).not.toHaveBeenCalled();
    expect(screen.getByRole("alert")).toHaveTextContent("This will replace 1 caption you wrote.");

    await userEvent.click(screen.getByRole("button", { name: "Keep them" }));
    expect(onStart).not.toHaveBeenCalled();

    await userEvent.click(screen.getByRole("button", { name: "Generate captions" }));
    await userEvent.click(screen.getByRole("button", { name: "Replace my captions" }));
    expect(onStart).toHaveBeenCalledWith("everything");
  });

  it("does not ask when only AI captions are refreshed", async () => {
    const onStart = renderPanel();
    await userEvent.click(screen.getByRole("radio", { name: /Uncaptioned \+ AI captions/ }));
    await userEvent.click(screen.getByRole("button", { name: "Generate captions" }));
    expect(onStart).toHaveBeenCalledWith("replace_ai");
  });

  it("is disabled when there is nothing to caption", () => {
    renderPanel([manual]);
    expect(screen.getByRole("button", { name: "Generate captions" })).toBeDisabled();
    expect(screen.getByText("Nothing to caption with this option.")).toBeInTheDocument();
  });
});

function renderCard(img: typeof empty, jobRunning = false) {
  const onSuggest = vi.fn();
  const props = {
    index: 0,
    total: 1,
    canReorder: true,
    nameOf: String,
    onPreview: vi.fn(),
    onMove: vi.fn(),
    onSaveCaption: vi.fn().mockResolvedValue(true),
    onRemove: vi.fn(),
    onSuggest,
    jobRunning,
    dragHandlers: {
      onDragStart: vi.fn(),
      onDragOver: vi.fn(),
      onDrop: vi.fn(),
      onDragEnd: vi.fn(),
    },
  };
  const view = render(<DatasetImageCard image={img} {...props} />);
  return {
    onSuggest,
    rerender: (next: typeof empty) => view.rerender(<DatasetImageCard image={next} {...props} />),
  };
}

describe("DatasetImageCard captions", () => {
  it("labels AI and manual captions", () => {
    renderCard(ai);
    expect(screen.getByTitle("Written by florence-2-base")).toHaveTextContent("AI");
  });

  it("suggests straight away for empty or AI captions", async () => {
    const { onSuggest } = renderCard(ai);
    await userEvent.click(screen.getByRole("button", { name: "Suggest caption" }));
    expect(onSuggest).toHaveBeenCalledWith(ai);
  });

  it("confirms before replacing a manual caption", async () => {
    const { onSuggest } = renderCard(manual);
    expect(screen.getByText("Manual")).toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: "Suggest caption" }));
    expect(onSuggest).not.toHaveBeenCalled();
    await userEvent.click(screen.getByRole("button", { name: "Replace my caption" }));
    expect(onSuggest).toHaveBeenCalledWith(manual);
  });

  it("disables suggestions while a job runs", () => {
    renderCard(empty, true);
    expect(screen.getByRole("button", { name: "Suggest caption" })).toBeDisabled();
  });

  it("shows a caption that arrives from the server", () => {
    const { rerender } = renderCard(empty);
    rerender({ ...empty, caption: "a new ai caption", caption_source: "ai" });
    expect(screen.getByLabelText("Caption")).toHaveValue("a new ai caption");
  });

  it("keeps unsaved typing when a caption arrives", async () => {
    const { rerender } = renderCard(empty);
    await userEvent.type(screen.getByLabelText("Caption"), "typing");
    rerender({ ...empty, caption: "a new ai caption", caption_source: "ai" });
    expect(screen.getByLabelText("Caption")).toHaveValue("typing");
  });
});
