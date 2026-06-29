import { Check, Loader2 } from 'lucide-react';

export type DrillPipelineStage =
  | 'idle'
  | 'grounding'
  | 'vision'
  | 'confirm'
  | 'generating'
  | 'ready'
  | 'error';

const STAGES: { id: DrillPipelineStage; label: string; estimate: string }[] = [
  { id: 'grounding', label: 'Grounding', estimate: '~5s' },
  { id: 'vision', label: 'Vision', estimate: '~30s' },
  { id: 'confirm', label: 'Confirm', estimate: 'You' },
  { id: 'generating', label: 'Render', estimate: '~90s' },
];

function stageIndex(stage: DrillPipelineStage): number {
  if (stage === 'idle' || stage === 'ready' || stage === 'error') return -1;
  return STAGES.findIndex((s) => s.id === stage);
}

type Props = {
  stage: DrillPipelineStage;
};

export default function DrillPipelineBar({ stage }: Props) {
  if (stage === 'idle' || stage === 'ready') return null;

  const activeIdx = stageIndex(stage);

  return (
    <div
      className="absolute bottom-24 left-1/2 -translate-x-1/2 z-30 bg-[#05070D]/85 backdrop-blur-xl border border-outline px-4 py-2.5 rounded-full shadow-2xl shrink-0 select-none"
      aria-live="polite"
      aria-label="Drill pipeline progress"
    >
      <div className="flex items-center gap-2 max-w-2xl">
        {STAGES.map((s, idx) => {
          const done = activeIdx > idx;
          const active = activeIdx === idx;
          return (
            <div key={s.id} className="flex items-center gap-2 flex-1 min-w-0">
              <div
                className={`flex items-center gap-2 px-3 py-1.5 rounded-full border text-[10px] font-mono uppercase tracking-widest transition-all ${
                  active
                    ? 'border-orange-glow/60 bg-orange-glow/10 text-orange-glow'
                    : done
                      ? 'border-secondary/40 bg-secondary/10 text-secondary'
                      : 'border-white/10 text-on-surface-variant/50'
                }`}
              >
                {done ? (
                  <Check className="w-3 h-3 shrink-0" />
                ) : active ? (
                  <Loader2 className="w-3 h-3 animate-spin shrink-0" />
                ) : (
                  <span className="w-3 h-3 rounded-full border border-current shrink-0" />
                )}
                <span className="truncate">{s.label}</span>
                {active && (
                  <span className="text-[9px] opacity-70 normal-case tracking-normal">{s.estimate}</span>
                )}
              </div>
              {idx < STAGES.length - 1 && (
                <div
                  className={`h-px flex-1 min-w-[12px] ${done ? 'bg-secondary/50' : 'bg-white/10'}`}
                />
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
}
