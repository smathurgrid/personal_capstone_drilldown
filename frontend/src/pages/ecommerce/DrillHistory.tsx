import { ChevronRight } from "lucide-react";

interface Props {
  history: Array<{ id: string; attributes: { articleType?: string; masterCategory?: string } }>;
  onNavigate: (index: number) => void;
}

export default function DrillHistory({ history, onNavigate }: Props) {
  if (history.length === 0) return null;
  return (
    <div className="absolute top-4 left-4 flex items-center space-x-2 bg-black/40 backdrop-blur-md px-4 py-2 rounded-full border border-white/10 z-40 text-sm">
      <span className="text-gray-500 uppercase text-[10px] tracking-widest font-bold mr-2">History</span>
      {history.map((item, idx) => (
        <span key={item.id} className="flex items-center gap-1">
          {idx > 0 && <ChevronRight size={14} className="text-gray-600" />}
          <button
            type="button"
            onClick={() => onNavigate(idx)}
            className={`truncate max-w-[100px] ${
              idx === history.length - 1 ? "text-luxury-gold font-bold" : "text-gray-400 hover:text-white"
            }`}
          >
            {item.attributes.articleType ?? item.attributes.masterCategory ?? "Item"}
          </button>
        </span>
      ))}
    </div>
  );
}
