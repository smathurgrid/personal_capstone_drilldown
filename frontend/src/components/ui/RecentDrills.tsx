import { ExternalLink, ArrowRight, Sparkles } from 'lucide-react';

interface RecentDrill {
  id: string;
  title: string;
  subtitle: string;
  badge: string;
  badgeClass: string;
  imageUrl: string;
  mode: 'explainer' | 'ecommerce';
}

interface RecentDrillsProps {
  onSelectDrill: (drill: RecentDrill) => void;
  drills?: RecentDrill[];
}

export default function RecentDrills({ onSelectDrill, drills }: RecentDrillsProps) {
  // Show message if no drills available
  if (!drills || drills.length === 0) {
    return (
      <section className="w-full max-w-7xl mx-auto px-8 md:px-16 mt-20 mb-32 relative z-10">
        <div className="flex justify-between items-end mb-8 border-b border-white/5 pb-4">
          <h2 className="font-serif text-3xl font-black text-on-surface">
            Recent Drills
          </h2>
        </div>
        <div className="glass-card rounded-2xl p-16 text-center border border-white/5 flex flex-col items-center gap-4">
          <Sparkles className="w-12 h-12 text-secondary animate-pulse" />
          <p className="font-mono text-xs tracking-wider text-on-surface-variant uppercase font-bold">
            No recent drills yet. Start your first exploration above.
          </p>
        </div>
      </section>
    );
  }

  return (
    <section className="w-full max-w-7xl mx-auto px-8 md:px-16 mt-20 mb-32 relative z-10">
      <div className="flex justify-between items-end mb-8 border-b border-white/5 pb-4">
        <h2 className="font-serif text-3xl font-black text-on-surface">
          Recent Drills
        </h2>
        <button 
          onClick={() => drills.length > 0 && onSelectDrill(drills[0])}
          className="text-secondary font-mono text-xs uppercase tracking-widest hover:underline flex items-center gap-2 cursor-pointer group"
        >
          VIEW ALL
          <ArrowRight className="w-4 h-4 group-hover:translate-x-1 transition-transform" />
        </button>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-8">
        {drills.map((drill) => (
          <div
            key={drill.id}
            onClick={() => onSelectDrill(drill)}
            className="group relative overflow-hidden rounded-xl bg-navy-mid/40 border border-outline-variant/20 hover:border-secondary/40 transition-all duration-300 hover:shadow-[0_20px_40px_rgba(0,0,0,0.3)] cursor-pointer flex flex-col h-full"
          >
            <div className="aspect-[16/10] relative overflow-hidden w-full bg-[#0a1628]">
              <img 
                src={drill.imageUrl} 
                alt={drill.title}
                className="w-full h-full object-cover group-hover:scale-105 transition-transform duration-700 brightness-[0.95] group-hover:brightness-100"
                onError={(e) => {
                  // Fallback if image fails to load
                  (e.target as HTMLImageElement).style.display = 'none';
                }}
              />
              <div className="absolute top-4 left-4">
                <span className={`px-3 py-1 rounded-full font-mono text-[10px] uppercase font-bold tracking-widest border ${drill.badgeClass}`}>
                  {drill.badge}
                </span>
              </div>
              <div className="absolute top-4 right-4 bg-black/60 backdrop-blur-md p-1.5 rounded-full border border-white/10 group-hover:bg-secondary/20 transition-colors">
                <ExternalLink className="w-3.5 h-3.5 text-on-surface group-hover:text-secondary transition-colors" />
              </div>
            </div>

            <div className="p-6 flex flex-col flex-grow">
              <h3 className="font-serif text-xl text-on-surface font-bold mb-2 group-hover:text-primary transition-colors">
                {drill.title}
              </h3>
              <p className="text-on-surface-variant text-sm font-light leading-relaxed flex-grow">
                {drill.subtitle}
              </p>
            </div>
          </div>
        ))}
      </div>
    </section>
  );
}
