export interface ExplainerPage {
  id: string;
  imageUrl: string;
  parentId?: string | null;
  click?: { x: number; y: number } | null;
  depth?: number;
  metadata?: {
    editorial_headline?: string;
    explainer_paragraph?: string;
    granular_details?: Array<{
      label: string;
      description?: string;
      point?: [number, number];
      positionUncertain?: boolean;
      position_uncertain?: boolean;
    }>;
    object?: string;
    drill_topic?: string;
    style?: string;
    materials?: string | string[];
    spatial_context?: string;
  };
  rawJson?: string;
  isStreaming?: boolean;
  streamStatus?: string;
  context?: string;
  groundingMode?: string;
  samConfidence?: number | null;
  inputPrompt?: string;
  visionModel?: string;
  drillMode?: string;
}

export type GroundingMode = "sam2" | "red_ring";
export type VisionModelKey = "qwen3.5" | "none";
