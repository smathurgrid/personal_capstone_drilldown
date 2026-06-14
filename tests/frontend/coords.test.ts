import { describe, expect, it } from "vitest";

import {
  getObjectFitContainRect,
  mapNormalizedToDisplay,
  normalizeClick,
  normalizeContainedImageClick,
} from "../../frontend/src/utils/coords";

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

describe("object-fit contain mapping", () => {
  it("computes letterboxed rect for wide images", () => {
    const fit = getObjectFitContainRect(400, 300, 800, 400);
    expect(fit.width).toBe(400);
    expect(fit.height).toBe(200);
    expect(fit.offsetY).toBe(50);
  });

  it("maps normalized coords to display pixels", () => {
    const fit = getObjectFitContainRect(400, 300, 800, 400);
    const { x, y } = mapNormalizedToDisplay(0.5, 0.5, 400, 300, 800, 400);
    expect(x).toBe(fit.offsetX + fit.width / 2);
    expect(y).toBe(fit.offsetY + fit.height / 2);
  });

  it("maps clicks through contain inset", () => {
    const img = {
      getBoundingClientRect: () => ({ left: 0, top: 0, width: 400, height: 300, right: 400, bottom: 300 }),
      naturalWidth: 800,
      naturalHeight: 400,
    } as HTMLImageElement;
    const fit = getObjectFitContainRect(400, 300, 800, 400);
    const center = normalizeContainedImageClick(
      fit.offsetX + fit.width / 2,
      fit.offsetY + fit.height / 2,
      img,
      { clamp: true }
    );
    expect(center).toEqual({ x: 0.5, y: 0.5 });
  });
});
