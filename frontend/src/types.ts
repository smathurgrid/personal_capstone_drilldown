export type Mode = 'explainer' | 'ecommerce';

export interface TabData {
  id: string;
  label: string;
  type: 'list' | 'markdown' | 'matches' | 'chart';
  contentJson: string; // JSON string representing the tab content
}

export interface HotspotDetails {
  title: string;
  subtitle: string;
  tabs: TabData[];
}

export interface Hotspot {
  id: string;
  title: string;
  description: string;
  x: number; // Percentage (e.g. 45 for 45%)
  y: number; // Percentage (e.g. 35 for 35%)
  width?: number; // Optional bounding box width (for dashed boxes in ecommerce mode)
  height?: number; // Optional bounding box height (for dashed boxes in ecommerce mode)
  details: HotspotDetails;
}

export interface DrillPathStage {
  id: string;
  label: string;
  imageUrl: string;
}

export interface DrillResult {
  id: string;
  mode: Mode;
  title: string;
  subtitle: string;
  category: string;
  breadcrumbs: string[];
  imageUrl: string;
  imageAlt: string;
  hotspots: Hotspot[];
  drillPath?: DrillPathStage[];
  depth?: number;
  parentId?: string;
  metadata?: any; // Full metadata including explainer_paragraph
}

export interface MatchItem {
  brand: string;
  name: string;
  matchPercent: number;
  price: number;
  source: string;
  imageUrl: string;
}

export interface KeyValueDetail {
  key: string;
  value: string;
}

export interface ChartDataPoints {
  xAxisKey: string;
  yAxisKey: string;
  unit?: string;
  data: Array<{ label: string; value: number }>;
}
