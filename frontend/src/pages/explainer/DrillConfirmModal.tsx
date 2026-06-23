import type { ExplainerPage } from "../../services/explainer-api";
import { b64ToDataUrl } from "../../services/explainer-api";

export type PendingDrill = {
  pageId: string;
  parentId: string;
  click: { x: number; y: number };
  objectName: string;
  drillTopic: string;
  cropPreviewB64?: string;
  metadata?: ExplainerPage["metadata"];
};

type Props = {
  pending: PendingDrill;
  busy: boolean;
  onConfirm: (drillTopic: string) => void;
  onCancel: () => void;
};

export default function DrillConfirmModal({ pending, busy, onConfirm, onCancel }: Props) {
  const previewSrc = pending.cropPreviewB64 ? b64ToDataUrl(pending.cropPreviewB64) : null;
  const meta = pending.metadata ?? {};
  const kbCitation = meta.kb_citation as string | undefined;
  const kbScore = meta.kb_score as number | undefined;
  const kbLowConfidence = meta.kb_low_confidence as boolean | undefined;
  const kbBestScore = meta.kb_best_score as number | undefined;

  return (
    <div className="drill-confirm-backdrop" role="presentation">
      <div className="drill-confirm-modal" role="dialog" aria-labelledby="drill-confirm-title">
        <h3 id="drill-confirm-title">Confirm drill target</h3>
        <p className="drill-confirm-object">Drilling into: <strong>{pending.objectName}</strong></p>

        {kbCitation ? (
          <p className="drill-confirm-citation kb-citation-field">
            📄 <strong>Source</strong> {kbCitation}
            {kbScore != null && <span className="kb-score"> · {Math.round(kbScore * 100)}% match</span>}
          </p>
        ) : kbLowConfidence ? (
          <p className="drill-confirm-citation kb-citation-none">
            No strong manual match
            {kbBestScore != null && <span> (best {Math.round(kbBestScore * 100)}%)</span>}
          </p>
        ) : (
          <p className="drill-confirm-citation kb-citation-none">No knowledge-base match for this region</p>
        )}

        {previewSrc && (
          <div className="drill-confirm-preview">
            <img src={previewSrc} alt="Selected region preview" />
          </div>
        )}

        <label className="drill-confirm-label" htmlFor="drill-topic-edit">
          Generation prompt
        </label>
        <textarea
          id="drill-topic-edit"
          className="drill-confirm-topic"
          defaultValue={pending.drillTopic}
          rows={4}
          disabled={busy}
        />

        <div className="drill-confirm-actions">
          <button type="button" className="explainer-btn" onClick={onCancel} disabled={busy}>
            Cancel
          </button>
          <button
            type="button"
            className="explainer-btn primary"
            disabled={busy}
            onClick={() => {
              const el = document.getElementById("drill-topic-edit") as HTMLTextAreaElement | null;
              onConfirm(el?.value.trim() || pending.drillTopic);
            }}
          >
            {busy ? "Generating…" : "Confirm & generate"}
          </button>
        </div>
      </div>
    </div>
  );
}
