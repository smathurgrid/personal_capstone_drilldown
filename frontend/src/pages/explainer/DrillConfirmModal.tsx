import { useEffect, useRef, useState } from 'react';
import { AlertTriangle, BookOpen, ChevronDown, ChevronUp, Loader2, MapPin } from 'lucide-react';
import type { ExplainerPage } from '../../services/explainer-api';
import { b64ToDataUrl } from '../../services/explainer-api';

export type AncestryItem = string | { object: string; drill_mode?: string };

export type PendingDrillKb = {
  citation?: string;
  score?: number;
  warning?: string;
  extraHits?: unknown[];
  explainerParagraph?: string;
};

export type PendingDrill = {
  pageId: string;
  parentId: string;
  click: { x: number; y: number };
  objectName: string;
  drillTopic: string;
  cropPreviewB64?: string;
  metadata?: ExplainerPage['metadata'];
  fromCache?: boolean;
  imageUrl?: string;
  expiresAt?: string;
  ancestryChain?: AncestryItem[];
  kb?: PendingDrillKb;
};

type Props = {
  pending: PendingDrill;
  busy: boolean;
  onConfirm: (drillTopic: string) => void;
  onCancel: () => void;
  onRegenerate?: () => void;
};

function formatAncestry(chain: AncestryItem[] | undefined): string {
  if (!chain?.length) return '';
  return chain
    .map((item) => {
      if (typeof item === 'string') return item;
      const mode = item.drill_mode ? ` [${item.drill_mode}]` : '';
      return `${item.object}${mode}`;
    })
    .join(' → ');
}

export default function DrillConfirmModal({
  pending,
  busy,
  onConfirm,
  onCancel,
  onRegenerate,
}: Props) {
  const [topic, setTopic] = useState(pending.drillTopic);
  const [excerptOpen, setExcerptOpen] = useState(false);
  const textareaRef = useRef<HTMLTextAreaElement>(null);
  const previewSrc = pending.cropPreviewB64
    ? b64ToDataUrl(pending.cropPreviewB64)
    : pending.imageUrl || null;

  const kb = pending.kb;
  const ancestryLine = formatAncestry(pending.ancestryChain);
  const charCount = topic.length;

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (busy) return;
      if (e.key === 'Escape') onCancel();
      if (e.key === 'Enter' && (e.metaKey || e.ctrlKey)) onConfirm(topic.trim() || pending.drillTopic);
    };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, [busy, onCancel, onConfirm, pending.drillTopic, topic]);

  return (
    <div
      className="fixed inset-0 z-[600] flex items-center justify-center p-4 bg-black/70 backdrop-blur-sm"
      role="presentation"
      onClick={(e) => {
        if (e.target === e.currentTarget && !busy) onCancel();
      }}
    >
      <div
        className="w-full max-w-3xl rounded-2xl border border-white/10 bg-[#0c1014]/95 backdrop-blur-xl shadow-2xl overflow-hidden animate-fade-in"
        role="dialog"
        aria-labelledby="drill-confirm-title"
        aria-modal="true"
      >
        <div className="px-6 py-4 border-b border-white/10 flex items-start justify-between gap-4">
          <div className="min-w-0 text-left">
            <p className="font-mono text-[9px] uppercase tracking-widest text-secondary mb-1">
              {busy ? 'Generating inside view' : 'Review drill target'}
            </p>
            <h3 id="drill-confirm-title" className="font-serif text-xl font-bold text-on-surface">
              {pending.objectName}
            </h3>
            {ancestryLine && (
              <p className="font-mono text-[10px] text-on-surface-variant mt-1 truncate flex items-center gap-1">
                <MapPin className="w-3 h-3 text-orange-glow shrink-0" />
                {ancestryLine}
              </p>
            )}
          </div>
          {pending.fromCache && (
            <span className="shrink-0 px-2 py-1 rounded-full bg-secondary/15 border border-secondary/30 font-mono text-[9px] uppercase tracking-widest text-secondary">
              Cached result
            </span>
          )}
        </div>

        {busy ? (
          <div className="px-6 py-12 flex flex-col items-center gap-4 text-center">
            <Loader2 className="w-10 h-10 text-orange-glow animate-spin" />
            <p className="font-mono text-sm text-orange-glow tracking-wide">
              Generating image (1–2 min)…
            </p>
            <p className="text-xs text-on-surface-variant max-w-sm">
              AI is painting from your prompt. The panel stays readable while you wait.
            </p>
          </div>
        ) : (
          <div className="grid md:grid-cols-2 gap-0 md:gap-6 p-6">
            <div className="mb-4 md:mb-0">
              {previewSrc ? (
                <div className="relative rounded-xl overflow-hidden border-2 border-orange-glow/40 bg-black/40">
                  <img
                    src={previewSrc}
                    alt="Selected region preview"
                    className="w-full h-auto max-h-56 object-contain"
                  />
                  <div className="absolute inset-0 pointer-events-none ring-2 ring-orange-glow/30 ring-inset rounded-xl" />
                </div>
              ) : (
                <div className="h-40 rounded-xl border border-dashed border-white/20 flex items-center justify-center text-on-surface-variant text-xs">
                  No preview available
                </div>
              )}
            </div>

            <div className="space-y-4 text-left">
              {kb?.warning && (
                <div className="flex gap-2 p-3 rounded-lg bg-amber-500/10 border border-amber-500/30 text-amber-200 text-xs">
                  <AlertTriangle className="w-4 h-4 shrink-0 mt-0.5" />
                  <span>{kb.warning}</span>
                </div>
              )}

              {kb?.citation && (
                <div className="rounded-lg border border-white/10 bg-white/5 p-3 space-y-2">
                  <div className="flex items-center gap-2 text-secondary">
                    <BookOpen className="w-4 h-4" />
                    <span className="font-mono text-[9px] uppercase tracking-widest">Manual excerpt</span>
                    {typeof kb.score === 'number' && (
                      <span className="ml-auto font-mono text-[9px] text-on-surface-variant">
                        {Math.round(kb.score * 100)}% match
                      </span>
                    )}
                  </div>
                  <p className="text-[11px] text-on-surface-variant">{kb.citation}</p>
                  {kb.explainerParagraph && (
                    <>
                      <button
                        type="button"
                        className="flex items-center gap-1 text-[10px] font-mono text-orange-glow/90"
                        onClick={() => setExcerptOpen((o) => !o)}
                      >
                        {excerptOpen ? <ChevronUp className="w-3 h-3" /> : <ChevronDown className="w-3 h-3" />}
                        {excerptOpen ? 'Hide excerpt' : 'Show excerpt'}
                      </button>
                      {excerptOpen && (
                        <p className="text-[11px] text-on-surface leading-relaxed line-clamp-3">
                          {kb.explainerParagraph}
                        </p>
                      )}
                    </>
                  )}
                  <p className="text-[10px] text-on-surface-variant/80 italic">
                    Manual informs the explanation; image follows your prompt.
                  </p>
                </div>
              )}

              <div>
                <label
                  className="font-mono text-[9px] uppercase tracking-widest text-on-surface-variant block mb-2"
                  htmlFor="drill-topic-edit"
                >
                  Generation prompt
                </label>
                <textarea
                  ref={textareaRef}
                  id="drill-topic-edit"
                  className="w-full rounded-lg border border-white/15 bg-black/30 px-3 py-2 text-sm text-on-surface resize-y min-h-[100px] focus:outline-none focus:border-orange-glow/50"
                  value={topic}
                  onChange={(e) => setTopic(e.target.value)}
                  rows={4}
                />
                <p
                  className={`mt-1 font-mono text-[9px] ${charCount > 400 ? 'text-amber-400' : 'text-on-surface-variant'}`}
                >
                  {charCount} chars{charCount > 400 ? ' — consider shortening' : ''}
                </p>
              </div>
            </div>
          </div>
        )}

        <div className="px-6 py-4 border-t border-white/10 flex flex-wrap gap-3 justify-end">
          {!busy && (
            <>
              <button
                type="button"
                className="px-4 py-2 rounded-lg border border-white/15 font-mono text-[10px] uppercase tracking-widest text-on-surface-variant hover:bg-white/5 transition-colors"
                onClick={onCancel}
              >
                Cancel
              </button>
              {pending.fromCache && onRegenerate && (
                <button
                  type="button"
                  className="px-4 py-2 rounded-lg border border-secondary/40 font-mono text-[10px] uppercase tracking-widest text-secondary hover:bg-secondary/10 transition-colors"
                  onClick={onRegenerate}
                >
                  Regenerate
                </button>
              )}
              <button
                type="button"
                className="px-5 py-2 rounded-lg bg-orange-glow text-black font-mono text-[10px] uppercase tracking-widest font-bold hover:opacity-90 transition-opacity"
                onClick={() => onConfirm(topic.trim() || pending.drillTopic)}
              >
                {pending.fromCache ? 'Use cached image' : 'Generate inside view'}
              </button>
            </>
          )}
        </div>
      </div>
    </div>
  );
}
