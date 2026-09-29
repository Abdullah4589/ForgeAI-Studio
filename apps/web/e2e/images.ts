// Tiny PNG encoder for E2E fixtures, using only Node's zlib (no image dependencies).
import { crc32, deflateSync } from "node:zlib";

type Pixel = (x: number, y: number) => [number, number, number];

function chunk(type: string, data: Buffer): Buffer {
  const length = Buffer.alloc(4);
  length.writeUInt32BE(data.length);
  const body = Buffer.concat([Buffer.from(type, "ascii"), data]);
  const crc = Buffer.alloc(4);
  crc.writeUInt32BE(crc32(body));
  return Buffer.concat([length, body, crc]);
}

export function encodePng(width: number, height: number, pixel: Pixel): Buffer {
  const header = Buffer.alloc(13);
  header.writeUInt32BE(width, 0);
  header.writeUInt32BE(height, 4);
  header.set([8, 2, 0, 0, 0], 8); // 8-bit RGB, no interlace
  const rows = Buffer.alloc(height * (width * 3 + 1));
  let offset = 0;
  for (let y = 0; y < height; y++) {
    rows[offset++] = 0; // filter: none
    for (let x = 0; x < width; x++) {
      const [r, g, b] = pixel(x, y);
      rows[offset++] = r;
      rows[offset++] = g;
      rows[offset++] = b;
    }
  }
  return Buffer.concat([
    Buffer.from([0x89, 0x50, 0x4e, 0x47, 0x0d, 0x0a, 0x1a, 0x0a]),
    chunk("IHDR", header),
    chunk("IDAT", deflateSync(rows)),
    chunk("IEND", Buffer.alloc(0)),
  ]);
}

function random(seed: number): () => number {
  let state = seed;
  return () => {
    state = (state * 1103515245 + 12345) % 2147483648;
    return state / 2147483648;
  };
}

/**
 * Coloured rectangles defined in relative coordinates, so the same seed at different sizes is
 * the "same picture" (a near-duplicate) and different seeds are clearly different pictures.
 */
export function picturePng(seed: number, width = 512, height = width): Buffer {
  const rand = random(seed);
  const colour = (): [number, number, number] => [
    Math.floor(rand() * 256),
    Math.floor(rand() * 256),
    Math.floor(rand() * 256),
  ];
  const background = colour();
  const rects = Array.from({ length: 10 }, () => {
    const x0 = rand() * 0.8;
    const y0 = rand() * 0.8;
    return { x0, y0, x1: x0 + 0.1 + rand() * 0.4, y1: y0 + 0.1 + rand() * 0.4, fill: colour() };
  });
  return encodePng(width, height, (x, y) => {
    const u = x / width;
    const v = y / height;
    let result = background;
    for (const r of rects) if (u >= r.x0 && u < r.x1 && v >= r.y0 && v < r.y1) result = r.fill;
    return result;
  });
}

/** A smooth gradient: almost no edges, so it reads as blurry. */
export function gradientPng(size = 512): Buffer {
  return encodePng(size, size, (x, y) => [
    Math.floor((x / size) * 200),
    Math.floor((y / size) * 200),
    120,
  ]);
}
