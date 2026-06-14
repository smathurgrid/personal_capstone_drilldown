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

/** Visible image rect for object-fit: contain inside a container. */
export function getObjectFitContainRect(
  containerWidth: number,
  containerHeight: number,
  naturalWidth: number,
  naturalHeight: number
): { offsetX: number; offsetY: number; width: number; height: number } {
  if (!containerWidth || !containerHeight || !naturalWidth || !naturalHeight) {
    return { offsetX: 0, offsetY: 0, width: containerWidth, height: containerHeight };
  }
  const scale = Math.min(containerWidth / naturalWidth, containerHeight / naturalHeight);
  const width = naturalWidth * scale;
  const height = naturalHeight * scale;
  return {
    offsetX: (containerWidth - width) / 2,
    offsetY: (containerHeight - height) / 2,
    width,
    height,
  };
}

/** Map a click on an object-fit: contain image to normalized image coordinates. */
export function normalizeContainedImageClick(
  clientX: number,
  clientY: number,
  img: HTMLImageElement,
  options?: { clamp?: boolean }
): { x: number; y: number } | null {
  const rect = img.getBoundingClientRect();
  const fit = getObjectFitContainRect(rect.width, rect.height, img.naturalWidth, img.naturalHeight);
  const localX = clientX - rect.left - fit.offsetX;
  const localY = clientY - rect.top - fit.offsetY;
  if (
    !options?.clamp &&
    (localX < 0 || localX > fit.width || localY < 0 || localY > fit.height)
  ) {
    return null;
  }
  const x = localX / fit.width;
  const y = localY / fit.height;
  if (!options?.clamp) {
    return { x, y };
  }
  return {
    x: Math.min(1, Math.max(0, x)),
    y: Math.min(1, Math.max(0, y)),
  };
}

/** Map normalized image coordinates to container pixel space (object-fit: contain). */
export function mapNormalizedToDisplay(
  nx: number,
  ny: number,
  containerWidth: number,
  containerHeight: number,
  naturalWidth: number,
  naturalHeight: number
): { x: number; y: number } {
  const fit = getObjectFitContainRect(containerWidth, containerHeight, naturalWidth, naturalHeight);
  return {
    x: fit.offsetX + nx * fit.width,
    y: fit.offsetY + ny * fit.height,
  };
}
