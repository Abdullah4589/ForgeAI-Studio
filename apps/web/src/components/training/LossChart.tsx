import { lossPath } from "@/lib/training";

const WIDTH = 320;
const HEIGHT = 80;

/** Training loss over steps. Loss is noisy per step; the overall trend is what matters. */
export function LossChart({ points }: { points: [number, number][] }) {
  if (points.length < 2) {
    return <p className="text-faint text-xs">The loss chart appears after a few steps.</p>;
  }
  const losses = points.map(([, loss]) => loss);
  const last = points[points.length - 1];
  return (
    <figure aria-label="Training loss chart">
      <svg
        viewBox={`0 0 ${WIDTH} ${HEIGHT}`}
        preserveAspectRatio="none"
        className="bg-canvas border-line h-20 w-full rounded border"
        role="img"
        aria-label={`Loss over ${points.length} recorded steps, latest ${last[1].toFixed(4)}`}
      >
        <path
          d={lossPath(points, WIDTH, HEIGHT)}
          fill="none"
          stroke="var(--color-accent)"
          strokeWidth="1.5"
          vectorEffect="non-scaling-stroke"
        />
      </svg>
      <figcaption className="text-faint mt-1 flex justify-between font-mono text-xs tabular-nums">
        <span>min {Math.min(...losses).toFixed(4)}</span>
        <span>max {Math.max(...losses).toFixed(4)}</span>
      </figcaption>
    </figure>
  );
}
