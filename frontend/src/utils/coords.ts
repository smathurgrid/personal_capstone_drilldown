import type { MouseEvent } from "react";

/** Normalized (0–1) click coordinates relative to an element's bounding box. */

export function normalizeClick(
  clientX: number,
  clientY: number,
  rect: DOMRect,
  options?: { clamp?: boolean }
): { x: number; y: number } {
  const x = (clientX - rect.left) / rect.width;
  const y = (clientY - rect.top) / rect.height;
  if (!options?.clamp) {
    return { x, y };
  }
  return {
    x: Math.min(1, Math.max(0, x)),
    y: Math.min(1, Math.max(0, y)),
  };
}

export function normalizeElementClick(
  event: MouseEvent<HTMLElement>,
  element: HTMLElement,
  options?: { clamp?: boolean }
): { x: number; y: number } {
  return normalizeClick(event.clientX, event.clientY, element.getBoundingClientRect(), options);
}
