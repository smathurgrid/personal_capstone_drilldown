import { ChevronRight } from "lucide-react";

interface Props {
  history: Array<{ id: string; attributes: { articleType?: string; masterCategory?: string } }>;
  onNavigate: (index: number) => void;
}

export default function DrillHistory({ history, onNavigate }: Props) {
  if (history.length === 0) return null;
  return (
    <div className="absolute top-6 left-6 flex items-center space-x-2 bg-[rgba(13,17,42,0.8)] backdrop-blur-md px-4 py-2.5 rounded-lg border border-[#2d3c5e] z-40 text-sm">
      <span className="text-[#7a81a0] uppercase text-[10px] tracking-widest font-bold mr-2 font-[JetBrains Mono]">Path</span>
      {history.map((item, idx) => (
        <span key={item.id} className="flex items-center gap-1">
          {idx > 0 && <ChevronRight size={14} className="text-[#2d3c5e]" strokeWidth={2} />}
          <button
            type="button"
            onClick={() => onNavigate(idx)}
            className={`truncate max-w-[120px] text-xs font-medium transition-all ${
              idx === history.length - 1 
                ? "text-[#ff6b35] font-semibold" 
                : "text-[#a8afc4] hover:text-[#e8eef7] hover:text-[#ff6b35]"
            }`}
          >
            {item.attributes.articleType ?? item.attributes.masterCategory ?? "Item"}
          </button>
        </span>
      ))}
    </div>
  );
}
