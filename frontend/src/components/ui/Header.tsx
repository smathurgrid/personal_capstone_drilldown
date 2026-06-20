import React from 'react';
import { User, ChevronRight } from 'lucide-react';

interface HeaderProps {
  breadcrumbs?: string[];
  activeTab: string;
  onNavigate: (tab: string) => void;
  onClearSearch: () => void;
  showTabs?: boolean; // New prop to control tab visibility
}

export default function Header({
  breadcrumbs,
  activeTab,
  onNavigate,
  onClearSearch,
  showTabs = true,
}: HeaderProps) {
  return (
    <header className="fixed top-0 left-0 w-full z-[1000] bg-navy-mid/75 backdrop-blur-[20px] shadow-[0_40px_80px_rgba(0,0,0,0.4)] border-b border-white/5">
      <div className="flex justify-between items-center h-20 px-8 md:px-16 w-full max-w-[1920px] mx-auto">
        <div className="flex items-center gap-8">
          <div 
            onClick={onClearSearch}
            className="flex items-center gap-3 cursor-pointer group"
          >
            <span className="font-serif text-2xl font-black tracking-tighter">
              <span className="text-white group-hover:text-primary transition-colors">Drill</span>
              <span className="text-[#ff6b35] group-hover:text-secondary transition-colors">Down</span>
            </span>
          </div>
          
          {/* Breadcrumbs */}
          {breadcrumbs && breadcrumbs.length > 0 && (
            <nav className="hidden md:flex items-center gap-2 text-on-surface-variant font-mono text-xs tracking-wider">
              {breadcrumbs.map((crumb, idx) => (
                <React.Fragment key={idx}>
                  {idx > 0 && <ChevronRight className="w-3.5 h-3.5 text-outline/50" />}
                  <span 
                    className={`${
                      idx === breadcrumbs.length - 1 
                        ? 'text-secondary font-bold font-mono' 
                        : 'hover:text-primary cursor-pointer transition-colors'
                    }`}
                  >
                    {crumb}
                  </span>
                </React.Fragment>
              ))}
            </nav>
          )}
        </div>

        {/* Center menu links - only show if showTabs is true */}
        {showTabs && (
          <nav className="hidden md:flex items-center gap-6">
            {[
              { id: 'explore', label: 'Explore' },
              { id: 'history', label: 'History' }
            ].map((link) => (
              <button
                key={link.id}
                onClick={() => onNavigate(link.id)}
                className={`font-mono text-xs uppercase tracking-[2px] transition-all py-1.5 px-3 rounded-md cursor-pointer ${
                  activeTab === link.id
                    ? 'text-secondary border-b-2 border-secondary font-bold'
                    : 'text-on-surface-variant hover:text-primary hover:bg-white/5'
                }`}
              >
                {link.label}
              </button>
            ))}
          </nav>
        )}

        {/* Right side actions */}
        <div className="flex items-center gap-4 text-primary">
          <button className="hover:bg-white/5 p-2 rounded-full cursor-pointer transition-colors text-on-surface-variant hover:text-primary">
            <User className="w-5 h-5" />
          </button>
        </div>
      </div>
    </header>
  );
}
