import { useState } from "react";
import type { ExplainerPage } from "../../services/explainer-api";

type Tab = "detected" | "prompt" | "raw";

type Props = {
  page: ExplainerPage;
  groundingLabel: string;
};

export default function MetadataPanel({ page, groundingLabel }: Props) {
  const [tab, setTab] = useState<Tab>("detected");
  const meta = page.metadata ?? {};
  const hasContent =
    meta.editorial_headline ||
    meta.object ||
    page.context ||
    page.rawJson ||
    page.inputPrompt;

  if (!hasContent) return null;

  const materials = Array.isArray(meta.materials)
    ? meta.materials.join(", ")
    : typeof meta.materials === "string"
      ? meta.materials
      : null;

  return (
    <div className="metadata-panel">
      <div className="metadata-tabs">
        {(
          [
            ["detected", "Detected"],
            ["prompt", "Prompt"],
            ["raw", "Raw JSON"],
          ] as const
        ).map(([id, label]) => (
          <button
            key={id}
            type="button"
            className={tab === id ? "active" : ""}
            onClick={() => setTab(id)}
          >
            {label}
          </button>
        ))}
      </div>

      <div className="metadata-body">
        {tab === "detected" && (
          <div className="metadata-detected">
            <p className="meta-kicker">
              {groundingLabel}
              {page.samConfidence != null && (
                <span> · {(page.samConfidence * 100).toFixed(0)}% mask</span>
              )}
            </p>
            <h3>{meta.editorial_headline ?? meta.object ?? "Component"}</h3>
            {meta.object && <p className="meta-object">{meta.object}</p>}
            {meta.style && (
              <p className="meta-field">
                <strong>Style</strong> {meta.style}
              </p>
            )}
            {materials && (
              <p className="meta-field">
                <strong>Materials</strong> {materials}
              </p>
            )}
            {meta.spatial_context && (
              <p className="meta-field">
                <strong>Spatial</strong> {meta.spatial_context}
              </p>
            )}
            {meta.explainer_paragraph && <p className="meta-paragraph">{meta.explainer_paragraph}</p>}
            {page.context && <p className="meta-context">Drill: {page.context}</p>}
            {meta.drill_topic && (
              <p className="meta-field">
                <strong>Next layer prompt</strong> {meta.drill_topic}
              </p>
            )}
          </div>
        )}

        {tab === "prompt" && (
          <div className="metadata-prompt">
            <p className="meta-field">
              <strong>Vision input</strong>
            </p>
            <pre>{page.inputPrompt || "—"}</pre>
            {meta.drill_topic && (
              <>
                <p className="meta-field">
                  <strong>drill_topic</strong>
                </p>
                <pre>{meta.drill_topic}</pre>
              </>
            )}
          </div>
        )}

        {tab === "raw" && (
          <pre className="metadata-raw">{page.rawJson || JSON.stringify(meta, null, 2)}</pre>
        )}
      </div>
    </div>
  );
}
