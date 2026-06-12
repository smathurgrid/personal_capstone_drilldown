import { describe, expect, it } from "vitest";

import { normalizeClick } from "../../frontend/src/utils/coords";

describe("normalizeClick", () => {
  const rect = { left: 100, top: 50, width: 200, height: 100 } as DOMRect;

  it("returns normalized coordinates", () => {
    const { x, y } = normalizeClick(200, 100, rect);
    expect(x).toBe(0.5);
    expect(y).toBe(0.5);
  });

  it("clamps when requested", () => {
    const { x, y } = normalizeClick(50, 0, rect, { clamp: true });
    expect(x).toBe(0);
    expect(y).toBe(0);
  });
});
