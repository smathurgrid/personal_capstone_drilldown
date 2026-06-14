import { ChevronRight } from "lucide-react";
import type { ExplainerPage } from "../../services/explainer-api";

type Props = {
  pages: ExplainerPage[];
  currentIndex: number;
  onNavigate: (index: number) => void;
};

function layerLabel(page: ExplainerPage, index: number): string {
  return (
    page.metadata?.object ||
    page.metadata?.editorial_headline ||
    page.context?.slice(0, 32) ||
    `Layer ${index + 1}`
  );
}

export default function DrillBreadcrumb({ pages, currentIndex, onNavigate }: Props) {
  if (pages.length === 0) return null;

  return (
    <nav className="drill-breadcrumb" aria-label="Drill path">
      {pages.map((page, idx) => (
        <span key={page.id + idx} className="drill-crumb-wrap">
          {idx > 0 && <ChevronRight size={14} className="drill-crumb-sep" />}
          <button
            type="button"
            className={`drill-crumb${idx === currentIndex ? " active" : ""}`}
            onClick={() => onNavigate(idx)}
            title={layerLabel(page, idx)}
          >
            {layerLabel(page, idx)}
          </button>
        </span>
      ))}
    </nav>
  );
}
