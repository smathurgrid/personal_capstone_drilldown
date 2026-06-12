export type ProductResult = {
  product_id: number;
  visual_score: number;
  payload: { filename?: string; productDisplayName?: string; articleType?: string };
};

export type DrillNode = {
  id: string;
  x: number;
  y: number;
  attributes: Record<string, string>;
  results: ProductResult[];
  imageId?: string;
  productId?: number;
};

export type UploadResult = {
  imageId: string;
  imageUrl: string;
  imageHash?: string;
};
