import React from 'react';
import { ChevronRight } from 'lucide-react';

interface DrillHistoryProps {
  history: any[];
  onNavigate: (index: number) => void;
}

const DrillHistory: React.FC<DrillHistoryProps> = ({ history, onNavigate }) => {
  if (history.length === 0) return null;

  return (
    <div className="absolute top-8 left-20 flex items-center space-x-2 bg-black/40 backdrop-blur-md px-4 py-2 rounded-full border border-white/10 z-40 text-sm">
      <span className="text-gray-500 uppercase text-[10px] tracking-widest font-bold mr-2">History</span>
      
      {history.map((item, idx) => (
        <React.Fragment key={item.id}>
          {idx > 0 && <ChevronRight size={14} className="text-gray-600" />}
          <button 
            onClick={() => onNavigate(idx)}
            className={`transition-colors truncate max-w-[100px] ${
              idx === history.length - 1 ? 'text-luxury-gold font-bold' : 'text-gray-400 hover:text-white'
            }`}
          >
            {item.attributes.category}
          </button>
        </React.Fragment>
      ))}
    </div>
  );
};

export default DrillHistory;
