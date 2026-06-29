// Drill adapter — now powered by the speculative OVERLAPPED engine.
// Public API (exploreImage / exploreTopic / drillDown / getDrillPath / getStageResult)
// is unchanged so App.tsx and the UI stay the same. Internally it drives the
// /spec-drill/* session: predict 2 hotspots, generate child (main) + 2 hotspots
// (2 workers) in parallel, every loop. Clicking a hotspot is instant (cached).
import { startSpec, clickSpec, clickPointSpec, endSpec, b64ToDataUrl } from './spec-drill-api';

export type PendingDrillPayload = {
  pageId: string;
  parentId: string;
  click: { x: number; y: number };
  objectName: string;
  drillTopic: string;
  cropPreviewB64?: string;
  metadata?: Record<string, unknown>;
  fromCache?: boolean;
  imageUrl?: string;
  expiresAt?: string;
  ancestryChain?: Array<string | { object: string; drill_mode?: string }>;
  kb?: { citation?: string; score?: number; warning?: string; extraHits?: unknown[]; explainerParagraph?: string };
};

export type DrillPipelineStage =
  | 'idle' | 'grounding' | 'vision' | 'confirm' | 'generating' | 'ready' | 'error';

export type DrillDownOptions = {
  customTopic?: string;
  cacheBust?: string;
  onProgress?: (message: string) => void;
  onPipelineStage?: (stage: DrillPipelineStage) => void;
  onAwaitingConfirm?: (pending: PendingDrillPayload) => Promise<string | null>;
  onHistoryUpdate?: (result: DrillResult) => void;
};

export interface DrillResult {
  id: string;
  mode: 'explainer' | 'ecommerce';
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
}
export interface Hotspot {
  id: string; title: string; description: string; x: number; y: number;
  width?: number; height?: number; details: HotspotDetails;
}
export interface HotspotDetails { title: string; subtitle: string; tabs: TabData[]; }
export interface TabData { id: string; label: string; type: 'list' | 'markdown' | 'matches' | 'chart'; contentJson: string; }
export interface DrillPathStage { id: string; label: string; imageUrl: string; }
export interface KeyValueDetail { key: string; value: string; }

/** Number of hotspots predicted per layer (= number of worker Macs for full parallelism). */
const HOTSPOTS_PER_LAYER = 2;

export class DrillAdapter {
  private sessionId: string | null = null;
  private depth = 0;
  private results: DrillResult[] = [];
  private drillMode = 'inside';
  private kbId: string | null = null;

  setDrillMode(mode: string) {
    const n = mode.trim().toLowerCase();
    this.drillMode = n === 'pov' || n === 'perspective' || n === 'outward' ? 'pov' : 'inside';
  }
  setKbId(kbId: string | null) { this.kbId = kbId; }

  private fileToB64(file: File): Promise<string> {
    return new Promise((resolve, reject) => {
      const r = new FileReader();
      r.onload = () => resolve((r.result as string).split(',')[1] || '');
      r.onerror = () => reject(new Error('Could not read file'));
      r.readAsDataURL(file);
    });
  }

  private buildResult(image: string, regions: any[], title: string, depth: number): DrillResult {
    const imageUrl = image.startsWith('http') || image.startsWith('data:') || image.startsWith('blob:')
      ? image : b64ToDataUrl(image);
    const hotspots: Hotspot[] = (regions || []).map((r: any, idx: number) => {
      const label = r.label || `Region ${idx + 1}`;
      return {
        id: r.hotspot_id || `hotspot-${idx}`,
        title: label,
        description: 'Predicted drill region',
        x: (typeof r.x === 'number' ? r.x : 0.5) * 100,
        y: (typeof r.y === 'number' ? r.y : 0.5) * 100,
        details: { title: label, subtitle: 'Component', tabs: [] },
      };
    });
    const id = `${this.sessionId || 'spec'}#${depth}`;
    const result: DrillResult = {
      id, mode: 'explainer', title: title || 'Diagram', subtitle: '',
      category: 'TECH', breadcrumbs: ['Explainer', title].filter(Boolean) as string[],
      imageUrl, imageAlt: title || 'Diagram', hotspots, depth,
    };
    // Maintain the drill-path timeline (truncate forward history on a new branch).
    const existing = this.results.findIndex((r) => r.depth === depth);
    if (existing >= 0) this.results = this.results.slice(0, existing);
    this.results.push(result);
    result.drillPath = this.getDrillPath();
    return result;
  }

  /** Start from a topic — parent image + 2 hotspots (workers warm them). */
  async exploreTopic(query: string, _mode: 'explainer' | 'ecommerce' = 'explainer'): Promise<DrillResult> {
    void _mode;
    if (this.sessionId) endSpec(this.sessionId);
    this.results = []; this.depth = 0;
    return new Promise((resolve, reject) => {
      let settled = false; let parentImg = ''; let regions: any[] = [];
      const done = (r: DrillResult) => { if (!settled) { settled = true; resolve(r); } };
      startSpec({ topic: query, hotspots: HOTSPOTS_PER_LAYER, max_depth: 8 }, (type, d) => {
        if (type === 'session') { this.sessionId = d.session_id as string; parentImg = (d.parent_image_b64 as string) || ''; }
        else if (type === 'hotspots') { regions = (d.regions as any[]) || []; done(this.buildResult(parentImg, regions, query, 0)); }
        else if (type === 'depth_ready') { done(this.buildResult(parentImg, regions, query, 0)); }
        else if (type === 'error' && !settled) { settled = true; reject(new Error((d.message as string) || 'Exploration failed')); }
      }).then(() => { if (!settled && parentImg) done(this.buildResult(parentImg, regions, query, 0)); })
        .catch((e) => { if (!settled) { settled = true; reject(e); } });
    });
  }

  /** Start from an uploaded image — shows it immediately, then 2 hotspots appear. */
  async exploreImage(file: File, onUpdate?: (r: DrillResult) => void): Promise<DrillResult> {
    if (this.sessionId) endSpec(this.sessionId);
    this.results = []; this.depth = 0;
    const previewUrl = URL.createObjectURL(file);
    const b64 = await this.fileToB64(file);
    return new Promise((resolve) => {
      let settled = false;
      const resolveOnce = (r: DrillResult) => { if (!settled) { settled = true; resolve(r); } };
      startSpec({ parent_image_b64: b64, predict: true, hotspots: HOTSPOTS_PER_LAYER, max_depth: 8 }, (type, d) => {
        if (type === 'session') {
          this.sessionId = d.session_id as string;
          resolveOnce(this.buildResult(previewUrl, [], '', 0)); // image now, hotspots soon
        } else if (type === 'hotspots') {
          const regions = (d.regions as any[]) || [];
          onUpdate?.(this.buildResult(previewUrl, regions, '', 0));
        }
      }).catch(() => resolveOnce(this.buildResult(previewUrl, [], '', 0)));
    });
  }

  /**
   * Drill down. If (x,y) matches a predicted hotspot → instant (cached child).
   * Otherwise free-click → child on main + 2 new hotspots on workers in parallel.
   */
  async drillDown(_parentId: string, x: number, y: number, options: DrillDownOptions): Promise<DrillResult> {
    const { onPipelineStage, onProgress } = options;
    if (!this.sessionId) throw new Error('No active session — start a drill first.');
    onPipelineStage?.('generating');
    onProgress?.('Drilling (child on main + hotspots on workers)…');
    console.debug('[drill] mode=%s kb=%s', this.drillMode, this.kbId);

    const current = this.results[this.results.length - 1];
    const hs = current?.hotspots.find((h) => Math.abs(h.x - x) < 1.5 && Math.abs(h.y - y) < 1.5);

    return new Promise((resolve, reject) => {
      let settled = false; let childImg = ''; let label = ''; let regions: any[] = []; let childDepth = this.depth + 1;
      const finish = () => {
        if (settled || !childImg) return;
        settled = true;
        this.depth = childDepth;
        onPipelineStage?.('ready');
        resolve(this.buildResult(childImg, regions, label, childDepth));
      };
      const handler = (type: string, d: Record<string, unknown>) => {
        if (type === 'status') onProgress?.('Generating on the fly…');
        else if (type === 'chosen') { childImg = (d.image_b64 as string) || ''; label = (d.label as string) || ''; childDepth = (d.depth as number) ?? childDepth; }
        else if (type === 'hotspots') regions = (d.regions as any[]) || [];
        else if (type === 'depth_ready' || type === 'complete') finish();
        else if (type === 'error' && !settled) { settled = true; onPipelineStage?.('error'); reject(new Error((d.message as string) || 'Drill failed')); }
      };
      const stream = hs
        ? clickSpec(this.sessionId!, hs.id, handler)
        : clickPointSpec(this.sessionId!, x / 100, y / 100, handler);
      stream.then(finish).catch((e) => { if (!settled) { settled = true; onPipelineStage?.('error'); reject(e); } });
    });
  }

  getDrillPath(): DrillPathStage[] {
    return this.results.map((r) => ({ id: r.id, label: r.title || 'Stage', imageUrl: r.imageUrl }));
  }
  getStageResult(stageId: string): DrillResult | null {
    return this.results.find((r) => r.id === stageId) || null;
  }
}

export const drillAdapter = new DrillAdapter();
