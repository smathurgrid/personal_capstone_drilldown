import {
  uploadExplainerImage,
  streamExplainerPage,
  analyzeExplainerPage,
  confirmExplainerDrill,
  cancelExplainerDrill,
  type ExplainerPage,
} from './explainer-api';

/** Payload shown in confirm modal before Flux generation. */
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
  kb?: {
    citation?: string;
    score?: number;
    warning?: string;
    extraHits?: unknown[];
    explainerParagraph?: string;
  };
};

export type DrillPipelineStage =
  | 'idle'
  | 'grounding'
  | 'vision'
  | 'confirm'
  | 'generating'
  | 'ready'
  | 'error';

export type DrillDownOptions = {
  customTopic?: string;
  cacheBust?: string;
  onProgress?: (message: string) => void;
  onPipelineStage?: (stage: DrillPipelineStage) => void;
  /** Resolve with edited prompt to generate, or null to cancel. */
  onAwaitingConfirm: (pending: PendingDrillPayload) => Promise<string | null>;
  onHistoryUpdate?: (result: DrillResult) => void;
};

// New UI types
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
  id: string;
  title: string;
  description: string;
  x: number;
  y: number;
  width?: number;
  height?: number;
  details: HotspotDetails;
}

export interface HotspotDetails {
  title: string;
  subtitle: string;
  tabs: TabData[];
}

export interface TabData {
  id: string;
  label: string;
  type: 'list' | 'markdown' | 'matches' | 'chart';
  contentJson: string;
}

export interface DrillPathStage {
  id: string;
  label: string;
  imageUrl: string;
}

export interface KeyValueDetail {
  key: string;
  value: string;
}

export class DrillAdapter {
  private drillHistory: ExplainerPage[] = [];
  /** Inside zoom is the primary product path; POV is experimental. */
  private drillMode: string = 'inside';
  private kbId: string | null = null;

  /** Red ring: predictable click marker + tight crop. Best for diagrams and inside drills. */
  private static readonly INSIDE_GROUNDING = 'red_ring' as const;

  setDrillMode(mode: string) {
    const normalized = mode.trim().toLowerCase();
    this.drillMode = normalized === 'pov' || normalized === 'perspective' || normalized === 'outward'
      ? 'pov'
      : 'inside';
  }

  setKbId(kbId: string | null) {
    this.kbId = kbId;
  }
  
  /**
   * Upload and analyze an image - shows image immediately, analyzes in background
   * Progressive labeling: Shows labels as they're discovered
   */
  async exploreImage(file: File, onUpdate?: (result: DrillResult) => void): Promise<DrillResult> {
    // Step 1: Upload the image
    const uploadedPage = await uploadExplainerImage(file);
    
    // Step 2: Return immediate result with image (no hotspots yet)
    this.drillHistory = [uploadedPage];
    const immediateResult = this.mapPageToDrillResult(uploadedPage);
    
    // Step 3: Analyze in background with progressive updates
    console.log('[DrillAdapter] Starting analysis with progressive labeling...');
    
    analyzeExplainerPage(uploadedPage.id, 'qwen3.5', 'global', 0)
      .then(analyzed => {
        const metaAny = analyzed.metadata as any;
        console.log('[DrillAdapter] Analysis response:', {
          hasMetadata: !!analyzed.metadata,
          metadataKeys: Object.keys(analyzed.metadata || {}),
          granularDetails: metaAny?.granular_details?.length || 0,
          metadata: analyzed.metadata
        });
        
        uploadedPage.metadata = analyzed.metadata;
        uploadedPage.rawJson = analyzed.rawJson;
        this.drillHistory[0] = uploadedPage;
        
        console.log('[DrillAdapter] ✅ Analysis complete, found', metaAny?.granular_details?.length || 0, 'labels');
        
        // Log each label for debugging
        if (metaAny?.granular_details?.length > 0) {
          console.log('[DrillAdapter] 📍 Labels found:');
          metaAny.granular_details.slice(0, 3).forEach((detail: any, idx: number) => {
            const point = detail.point || [0.5, 0.5];
            console.log(`  ${idx + 1}. "${detail.label}" at [${point[0]}, ${point[1]}] → [${Math.round(point[0] * 100)}%, ${Math.round(point[1] * 100)}%]`);
          });
          if (metaAny.granular_details.length > 3) {
            console.log(`  ... and ${metaAny.granular_details.length - 3} more`);
          }
        } else {
          console.warn('[DrillAdapter] ⚠️ No labels found in backend response!');
          console.warn('[DrillAdapter] ⚠️ This means the backend vision analysis did not detect any components.');
        }
        
        // Update with all hotspots at once
        const updatedResult = this.mapPageToDrillResult(uploadedPage);
        console.log('[DrillAdapter] 🎯 Updating canvas with', updatedResult.hotspots.length, 'hotspots');
        if (onUpdate) {
          onUpdate(updatedResult);
        }
      })
      .catch(err => {
        console.warn('[DrillAdapter] Analysis failed:', err);
        // Even if analysis fails, keep the image visible
      });
    
    return immediateResult;
  }
  
  /**
   * Generate from text topic
   */
  async exploreTopic(query: string, _mode: 'explainer' | 'ecommerce' = 'explainer'): Promise<DrillResult> {
    return new Promise((resolve, reject) => {
      let finalPage: any = null;
      
      streamExplainerPage({ query }, (eventType, data) => {
        if (eventType === 'complete') {
          finalPage = data;
          this.drillHistory = [finalPage];
          resolve(this.mapPageToDrillResult(finalPage));
        } else if (eventType === 'error') {
          reject(new Error((data.message as string) || 'Exploration failed'));
        }
      });
    });
  }
  
  /**
   * Drill down into a specific point
   */
  async drillDown(
    parentId: string,
    x: number,
    y: number,
    options: DrillDownOptions,
  ): Promise<DrillResult> {
    const normX = x / 100;
    const normY = y / 100;
    const { customTopic, cacheBust, onProgress, onPipelineStage, onAwaitingConfirm, onHistoryUpdate } = options;

    return new Promise((resolve, reject) => {
      let settled = false;
      let awaitingConfirm = false;
      const finish = (fn: () => void) => {
        if (settled) return;
        settled = true;
        fn();
      };

      onPipelineStage?.('grounding');
      onProgress?.(
        this.kbId
          ? 'Isolating region and retrieving manual context (30–90s)…'
          : 'Isolating selected region…',
      );

      streamExplainerPage(
        {
          parentId,
          x: normX,
          y: normY,
          customTopic,
          cacheBust,
          visionModel: 'qwen3.5',
          groundingMode: DrillAdapter.INSIDE_GROUNDING,
          drillMode: this.drillMode,
          kbId: this.kbId,
        },
        async (eventType, data) => {
          if (eventType === 'grounding') {
            onPipelineStage?.('grounding');
            onProgress?.((data.message as string) || 'Isolating object…');
            return;
          }
          if (eventType === 'vision') {
            onPipelineStage?.('vision');
            onProgress?.(
              this.kbId
                ? 'Vision analysis with KB context (Ollama, ~30–60s)…'
                : (data.message as string) || 'Analyzing component…',
            );
            return;
          }

          if (eventType === 'complete') {
            const page = data as unknown as ExplainerPage;
            this.drillHistory.push(page);
            onPipelineStage?.('ready');
            finish(() => resolve(this.mapPageToDrillResult(page)));
            return;
          }

          if (eventType === 'confirm') {
            awaitingConfirm = true;
            onPipelineStage?.('confirm');
            onProgress?.('Review the drill target before generating…');
            const meta = (data.metadata as Record<string, unknown>) || {};
            const pending: PendingDrillPayload = {
              pageId: data.pageId as string,
              parentId: data.parentId as string,
              click: data.click as { x: number; y: number },
              objectName: (data.objectName as string) || 'Selected region',
              drillTopic: (data.drillTopic as string) || '',
              cropPreviewB64: data.cropPreviewB64 as string | undefined,
              metadata: meta,
              fromCache: Boolean(data.fromCache),
              imageUrl: data.imageUrl as string | undefined,
              expiresAt: data.expiresAt as string | undefined,
              ancestryChain: data.ancestryChain as PendingDrillPayload['ancestryChain'],
              kb: {
                citation: (data.kbCitation as string) || (meta.kb_citation as string),
                score: (data.kbScore as number) ?? (meta.kb_score as number),
                warning: (data.kbWarning as string) || (meta.kb_warning as string),
                extraHits: (data.kbExtraHits as unknown[]) || (meta.kb_extra_hits as unknown[]),
                explainerParagraph:
                  (data.explainerParagraph as string) || (meta.explainer_paragraph as string),
              },
            };

            let topic: string | null;
            try {
              topic = await onAwaitingConfirm(pending);
            } catch (err) {
              finish(() => reject(err));
              return;
            }

            if (!topic) {
              try {
                await cancelExplainerDrill(pending.pageId);
              } catch {
                /* best-effort */
              }
              onPipelineStage?.('idle');
              finish(() => reject(new Error('Drill cancelled')));
              return;
            }

            onPipelineStage?.('generating');
            onProgress?.('Generating drill image (may take 1–2 minutes)…');
            try {
              const confirmedPage = await confirmExplainerDrill(pending.pageId, topic);
              this.drillHistory.push(confirmedPage);
              onPipelineStage?.('ready');
              const result = this.mapPageToDrillResult(confirmedPage);
              finish(() => resolve(result));

              if (this.drillMode === 'inside') {
                this.scheduleFocusScan(confirmedPage, onHistoryUpdate);
              }
            } catch (err) {
              onPipelineStage?.('error');
              finish(() => reject(new Error('Image generation failed: ' + (err as Error).message)));
            }
            return;
          }

          if (eventType === 'error') {
            onPipelineStage?.('error');
            finish(() => reject(new Error((data.message as string) || 'Drill failed')));
          }
        },
      )
        .then(() => {
          if (!settled && !awaitingConfirm) {
            finish(() =>
              reject(
                new Error(
                  'Drill stream ended unexpectedly. Check that Ollama is running (ollama serve) and retry.',
                ),
              ),
            );
          }
        })
        .catch((err) => {
          onPipelineStage?.('error');
          finish(() => reject(err));
        });
    });
  }

  /** Labels on uploaded roots only — skip synthetic AI layers to avoid bad drill memory. */
  private scheduleFocusScan(
    page: ExplainerPage,
    onHistoryUpdate?: (result: DrillResult) => void,
  ): void {
    const depth = typeof page.depth === 'number' ? page.depth : undefined;
    if (depth !== undefined && depth > 1) {
      console.log('[DrillAdapter] Skipping focus scan on synthetic drill layer (depth > 1)');
      return;
    }
    analyzeExplainerPage(page.id, 'qwen3.5', 'focus', depth)
      .then((analyzed) => {
        const idx = this.drillHistory.findIndex((p) => p.id === page.id);
        if (idx >= 0) {
          this.drillHistory[idx] = {
            ...this.drillHistory[idx],
            metadata: analyzed.metadata,
            rawJson: analyzed.rawJson,
          };
          if (onHistoryUpdate) {
            onHistoryUpdate(this.mapPageToDrillResult(this.drillHistory[idx]));
          }
        }
      })
      .catch((err) => console.warn('[DrillAdapter] Focus scan failed:', err));
  }
  
  /**
   * Get drill path timeline
   */
  getDrillPath(): DrillPathStage[] {
    return this.drillHistory.map((page, idx) => ({
      id: page.id || `stage-${idx}`,
      label: this.extractTitle(page) || `Stage ${idx + 1}`,
      imageUrl: page.imageUrl || ''
    }));
  }
  
  /**
   * Navigate to a specific stage in history
   */
  getStageResult(stageId: string): DrillResult | null {
    const page = this.drillHistory.find(p => p.id === stageId);
    if (!page) return null;
    return this.mapPageToDrillResult(page);
  }
  
  /**
   * Map backend ExplainerPage to new UI DrillResult
   */
  private mapPageToDrillResult(page: any): DrillResult {
    const metadata = page.metadata || {};
    const title = this.extractTitle(page);
    const subtitle = this.extractSubtitle(page);
    const category = this.extractCategory(metadata);
    
    console.log('[DrillAdapter] Mapping page to result:', {
      pageId: page.id,
      hasMetadata: !!metadata,
      componentCards: metadata.component_cards?.length || 0,
      title,
      subtitle
    });
    
    const result = {
      id: page.id || 'unknown',
      mode: 'explainer' as const,
      title,
      subtitle,
      category,
      breadcrumbs: this.generateBreadcrumbs(page),
      imageUrl: page.imageUrl || '',
      imageAlt: title,
      hotspots: this.mapHotspots(metadata, page),
      drillPath: this.getDrillPath(),
      depth: page.depth,
      parentId: page.parentId,
      metadata: metadata // Include full metadata for ProductPanel
    };
    
    console.log('[DrillAdapter] Mapped result:', {
      id: result.id,
      hotspots: result.hotspots.length,
      imageUrl: result.imageUrl
    });
    
    return result;
  }
  
  /**
   * Extract title from various metadata formats
   */
  private extractTitle(page: any): string {
    const metadata = page.metadata || {};
    return metadata.editorial_headline 
      || metadata.object
      || metadata.title
      || metadata.name
      || 'Untitled Diagram';
  }
  
  /**
   * Extract subtitle/description
   */
  private extractSubtitle(page: any): string {
    const metadata = page.metadata || {};
    return metadata.explainer_paragraph
      || metadata.editorial_context
      || metadata.description
      || metadata.summary
      || '';
  }
  
  /**
   * Extract category
   */
  private extractCategory(metadata: any): string {
    if (metadata.category) return metadata.category.toUpperCase();
    if (metadata.domain) return metadata.domain.toUpperCase();
    
    // Guess from title
    const title = (metadata.editorial_headline || '').toLowerCase();
    if (title.includes('volcano') || title.includes('geology')) return 'GEOLOGY';
    if (title.includes('mechanical') || title.includes('watch')) return 'TECH';
    if (title.includes('fashion') || title.includes('blazer')) return 'LOOK';
    
    return 'TECH';
  }
  
  /**
   * Generate breadcrumbs from drill path
   */
  private generateBreadcrumbs(page: any): string[] {
    const chain: string[] = ['Explainer'];
    const ancestry = page?.metadata?.ancestry_chain;
    if (Array.isArray(ancestry)) {
      for (const item of ancestry) {
        const label =
          typeof item === 'string' ? item : (item as { object?: string })?.object;
        if (typeof label === 'string' && label.trim()) {
          const trimmed = label.trim();
          if (!chain.includes(trimmed)) chain.push(trimmed);
        }
      }
    }
    const title = this.extractTitle(page);
    const last = chain[chain.length - 1];
    if (title && title !== 'Untitled Diagram' && title !== last) {
      chain.push(title);
    }
    return chain;
  }
  
  /**
   * Map component cards to hotspots - supports both formats
   */
  private mapHotspots(metadata: any, page: any): Hotspot[] {
    // Backend uses 'granular_details' with 'point' [x, y] format
    const granularDetails = metadata.granular_details || [];
    const componentCards = metadata.component_cards || [];
    
    console.log('[DrillAdapter] Mapping hotspots:', {
      granularDetails: granularDetails.length,
      componentCards: componentCards.length,
      metadata: Object.keys(metadata)
    });
    
    // Try granular_details first (backend format)
    if (granularDetails.length > 0) {
      console.log('[DrillAdapter] 📍 Processing granular_details:');
      granularDetails.forEach((detail: any, idx: number) => {
        console.log(`  ${idx + 1}. "${detail.label}" - Raw point:`, detail.point);
      });
      
      return granularDetails.map((detail: any, idx: number) => {
        // Backend returns normalized coordinates [x, y] between 0-1
        // Convert to percentage (0-100)
        const point = detail.point || [0.5, 0.5];
        const x = point[0] * 100;
        const y = point[1] * 100;
        
        console.log(`[DrillAdapter] Mapped "${detail.label}": [${point[0]}, ${point[1]}] → [${x.toFixed(1)}%, ${y.toFixed(1)}%]`);
        
        return {
          id: `hotspot-${idx}`,
          title: detail.label || detail.title || `Component ${idx + 1}`,
          description: detail.description || 'Component details',
          x,
          y,
          details: {
            title: detail.label || detail.title || `Component ${idx + 1}`,
            subtitle: 'Component Details',
            tabs: this.generateTabs(detail, metadata)
          }
        };
      });
    }
    
    // Fallback to component_cards format
    if (componentCards.length > 0) {
      return componentCards.map((card: any, idx: number) => ({
        id: `hotspot-${idx}`,
        title: card.title || card.name || `Component ${idx + 1}`,
        description: card.description || card.summary || 'Component details',
        x: card.x || 50,
        y: card.y || 50,
        width: card.width,
        height: card.height,
        details: {
          title: card.title || `Component ${idx + 1}`,
          subtitle: card.subtitle || 'Component Details',
          tabs: this.generateTabs(card, metadata)
        }
      }));
    }
    
    // Create default hotspots if neither format exists
    return this.generateDefaultHotspots(metadata, page);
  }
  
  /**
   * Generate default hotspots when none exist
   */
  private generateDefaultHotspots(metadata: any, _page: any): Hotspot[] {
    // Create a center hotspot with metadata
    return [{
      id: 'center-spot',
      title: metadata.object || 'Main Component',
      description: metadata.description || 'Click for details',
      x: 50,
      y: 50,
      details: {
        title: metadata.object || 'Component',
        subtitle: 'Details',
        tabs: this.generateTabs(metadata, metadata)
      }
    }];
  }
  
  /**
   * Generate tabs for hotspot details
   */
  private generateTabs(card: any, metadata: any): TabData[] {
    const tabs: TabData[] = [];
    
    // Specifications tab
    const specs = this.extractSpecifications(card, metadata);
    if (specs.length > 0) {
      tabs.push({
        id: 'specs',
        label: 'SPECIFICATIONS',
        type: 'list',
        contentJson: JSON.stringify(specs)
      });
    }
    
    // Description tab
    const descriptionText =
      metadata.explainer_paragraph
      || card.description
      || metadata.editorial_context
      || metadata.description
      || metadata.summary;
    if (descriptionText) {
      tabs.push({
        id: 'description',
        label: 'DESCRIPTION',
        type: 'markdown',
        contentJson: JSON.stringify({
          content: descriptionText
        })
      });
    }
    
    // Technical data tab
    const technical = this.extractTechnicalData(card, metadata);
    if (technical.length > 0) {
      tabs.push({
        id: 'technical',
        label: 'TECHNICAL DATA',
        type: 'list',
        contentJson: JSON.stringify(technical)
      });
    }
    
    return tabs;
  }
  
  /**
   * Extract specifications from metadata
   */
  private extractSpecifications(card: any, metadata: any): KeyValueDetail[] {
    const specs: KeyValueDetail[] = [];
    
    // Common fields
    if (card.type || metadata.type) {
      specs.push({ key: 'Type', value: card.type || metadata.type });
    }
    if (card.material || metadata.material) {
      specs.push({ key: 'Material', value: card.material || metadata.material });
    }
    if (card.size || metadata.size) {
      specs.push({ key: 'Size', value: card.size || metadata.size });
    }
    if (card.weight || metadata.weight) {
      specs.push({ key: 'Weight', value: card.weight || metadata.weight });
    }
    if (card.dimensions || metadata.dimensions) {
      specs.push({ key: 'Dimensions', value: card.dimensions || metadata.dimensions });
    }
    
    // Add any other metadata fields
    for (const [key, value] of Object.entries(card)) {
      if (typeof value === 'string' && !['title', 'description', 'name', 'x', 'y'].includes(key)) {
        specs.push({ key: this.formatKey(key), value });
      }
    }
    
    return specs;
  }
  
  /**
   * Extract technical data
   */
  private extractTechnicalData(_card: any, metadata: any): KeyValueDetail[] {
    const technical: KeyValueDetail[] = [];
    
    if (metadata.temperature) {
      technical.push({ key: 'Temperature', value: metadata.temperature });
    }
    if (metadata.pressure) {
      technical.push({ key: 'Pressure', value: metadata.pressure });
    }
    if (metadata.depth) {
      technical.push({ key: 'Depth', value: metadata.depth });
    }
    if (metadata.viscosity) {
      technical.push({ key: 'Viscosity', value: metadata.viscosity });
    }
    
    return technical;
  }
  
  /**
   * Format key for display
   */
  private formatKey(key: string): string {
    return key
      .replace(/_/g, ' ')
      .replace(/([A-Z])/g, ' $1')
      .split(' ')
      .map(word => word.charAt(0).toUpperCase() + word.slice(1))
      .join(' ')
      .trim();
  }
}

// Singleton instance
export const drillAdapter = new DrillAdapter();
