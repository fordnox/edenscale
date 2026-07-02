export type NoiseMode = "lines" | "dots";

export interface NoiseFieldOptions {
  width: number;
  height: number;
  /** Grid cell size in px between marks. */
  res: number;
  mode: NoiseMode;
  color: string;
}

/* Deterministic integer hash → [0, 1). The texture must be stable across
   rebuilds so a window resize doesn't visibly reshuffle the grain. */
function hash(ix: number, iy: number): number {
  let h = Math.imul(ix, 374761393) + Math.imul(iy, 668265263);
  h = Math.imul(h ^ (h >>> 13), 1274126177);
  h ^= h >>> 16;
  return (h >>> 0) / 4294967296;
}

/* Smoothly interpolated value noise — gives the marks a coherent flow
   rather than uncorrelated static. */
function valueNoise(x: number, y: number): number {
  const ix = Math.floor(x);
  const iy = Math.floor(y);
  const fx = x - ix;
  const fy = y - iy;
  const sx = fx * fx * (3 - 2 * fx);
  const sy = fy * fy * (3 - 2 * fy);
  const a = hash(ix, iy);
  const b = hash(ix + 1, iy);
  const c = hash(ix, iy + 1);
  const d = hash(ix + 1, iy + 1);
  return a + (b - a) * sx + (c - a) * sy + (a - b - c + d) * sx * sy;
}

/**
 * Render a field of grain marks as SVG inner markup.
 *
 * Lines are emitted as `<line ... transform="rotate(angle cx cy)"/>` — the
 * reactive controller in GrainField.astro parses that exact transform format
 * to recover each mark's base angle and pivot.
 */
export function renderNoiseField({
  width,
  height,
  res,
  mode,
  color,
}: NoiseFieldOptions): string {
  const cols = Math.ceil(width / res);
  const rows = Math.ceil(height / res);
  const freq = 0.006;
  const parts: string[] = [
    mode === "dots"
      ? `<g fill="${color}">`
      : `<g stroke="${color}" stroke-width="1" stroke-linecap="round">`,
  ];
  for (let gy = 0; gy <= rows; gy++) {
    for (let gx = 0; gx <= cols; gx++) {
      const jx = (hash(gx * 7 + 1, gy * 13 + 5) - 0.5) * res * 0.6;
      const jy = (hash(gx * 11 + 3, gy * 17 + 9) - 0.5) * res * 0.6;
      const cx = +(gx * res + jx).toFixed(1);
      const cy = +(gy * res + jy).toFixed(1);
      const n = valueNoise(cx * freq, cy * freq);
      if (mode === "dots") {
        const r = +(0.6 + n * 0.9).toFixed(2);
        parts.push(`<circle cx="${cx}" cy="${cy}" r="${r}"/>`);
      } else {
        const angle = +(n * 720).toFixed(1);
        const half = res * 0.13;
        parts.push(
          `<line x1="${(cx - half).toFixed(1)}" y1="${cy}" x2="${(cx + half).toFixed(1)}" y2="${cy}" transform="rotate(${angle} ${cx} ${cy})"/>`,
        );
      }
    }
  }
  parts.push("</g>");
  return parts.join("");
}
