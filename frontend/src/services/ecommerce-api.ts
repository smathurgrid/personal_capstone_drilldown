import type { DrillNode, UploadResult } from "@shared/types";

import { API_BASE, apiPostForm, resolveUrl } from "./api";

const ECOMMERCE_API = `${API_BASE}/api/ecommerce`;

export async function uploadEcommerceImage(file: File): Promise<UploadResult> {
  const fd = new FormData();
  fd.append("file", file);
  const res = await fetch(`${ECOMMERCE_API}/upload`, { method: "POST", body: fd });
  if (!res.ok) throw new Error(await res.text());
  const data = await res.json();
  return { ...data, imageUrl: resolveUrl(data.imageUrl) };
}

export async function identifyItem(imageId: string, x: number, y: number): Promise<DrillNode> {
  return apiPostForm<DrillNode>(`${ECOMMERCE_API}/identify`, {
    imageId,
    x: x.toString(),
    y: y.toString(),
  });
}

export async function drillProduct(productId: number, x: number, y: number): Promise<DrillNode> {
  return apiPostForm<DrillNode>(`${ECOMMERCE_API}/drill`, {
    productId: productId.toString(),
    x: x.toString(),
    y: y.toString(),
  });
}

export function datasetImageUrl(filename: string): string {
  return resolveUrl(`/dataset/${filename}`);
}

export { ECOMMERCE_API };
export type { DrillNode, UploadResult };
