import React from 'react';
import { motion } from 'framer-motion';
import { Loader2, CheckCircle2, AlertCircle } from 'lucide-react';

// ==========================================
// GLASSPANEL COMPONENT
// ==========================================
interface GlassPanelProps extends React.HTMLAttributes<HTMLDivElement> {
  children: React.ReactNode;
  neon?: boolean;
}

export const GlassPanel: React.FC<GlassPanelProps> = ({ children, neon = false, className = '', ...props }) => {
  return (
    <div
      className={`${neon ? 'glass-panel-neon' : 'glass-panel'} rounded-2xl ${className}`}
      {...props}
    >
      {children}
    </div>
  );
};

// ==========================================
// ANIMATEDBUTTON COMPONENT
// ==========================================
interface AnimatedButtonProps extends React.ButtonHTMLAttributes<HTMLButtonElement> {
  children: React.ReactNode;
  glow?: boolean;
}

export const AnimatedButton: React.FC<AnimatedButtonProps> = ({ children, glow = true, className = '', ...props }) => {
  return (
    <motion.button
      whileHover={{ scale: 1.02, y: -1 }}
      whileTap={{ scale: 0.98 }}
      className={`px-4 py-2 font-mono text-[10px] uppercase font-bold tracking-widest rounded-xl cursor-pointer select-none border transition-all ${
        glow 
          ? 'bg-primary/10 border-primary/30 text-primary hover:bg-primary/20 hover:border-primary/50 shadow-[0_0_15px_rgba(0,229,255,0.15)]'
          : 'bg-white/5 border-white/10 text-on-surface hover:bg-white/10 hover:border-white/25'
      } ${className}`}
      {...props}
    >
      {children}
    </motion.button>
  );
};

// ==========================================
// AISTATUSBADGE COMPONENT
// ==========================================
interface AIStatusBadgeProps {
  label: string;
  status: 'online' | 'connected' | 'ready' | 'loading' | 'offline';
}

export const AIStatusBadge: React.FC<AIStatusBadgeProps> = ({ label, status }) => {
  const getColors = () => {
    switch (status) {
      case 'online':
      case 'connected':
      case 'ready':
        return { dot: 'bg-primary animate-pulse shadow-[0_0_8px_#00E5FF]', text: 'text-primary' };
      case 'loading':
        return { dot: 'bg-secondary animate-bounce shadow-[0_0_8px_#9D4EDD]', text: 'text-secondary' };
      default:
        return { dot: 'bg-on-surface-muted/30', text: 'text-on-surface-muted' };
    }
  };

  const { dot, text } = getColors();

  return (
    <div className="flex items-center gap-2 bg-white/2 border border-white/5 px-2.5 py-1.5 rounded-full select-none shrink-0 font-mono text-[9px] uppercase tracking-wider">
      <span className={`w-1.5 h-1.5 rounded-full ${dot}`} />
      <span className="text-on-surface-muted mr-0.5">{label}:</span>
      <span className={`${text} font-bold`}>{status}</span>
    </div>
  );
};

// ==========================================
// GENERATIONLOADER COMPONENT (CHEVRON RENDERER)
// ==========================================
interface GenerationLoaderProps {
  status: string;
}

export const GenerationLoader: React.FC<GenerationLoaderProps> = ({ status }) => {
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-background/80 backdrop-blur-md">
      <GlassPanel neon className="w-full max-w-md p-8 flex flex-col items-center gap-6 text-center shadow-[0_0_50px_rgba(0,229,255,0.1)]">
        {/* Animated Neural Network Orb */}
        <div className="relative w-24 h-24 flex items-center justify-center">
          <motion.div
            animate={{ rotate: 360 }}
            transition={{ repeat: Infinity, duration: 10, ease: "linear" }}
            className="absolute inset-0 border-2 border-dashed border-primary/30 rounded-full"
          />
          <motion.div
            animate={{ rotate: -360 }}
            transition={{ repeat: Infinity, duration: 15, ease: "linear" }}
            className="absolute inset-2 border border-dotted border-secondary/40 rounded-full"
          />
          <motion.div
            animate={{ scale: [1, 1.2, 1] }}
            transition={{ repeat: Infinity, duration: 3, ease: "easeInOut" }}
            className="w-8 h-8 rounded-full bg-gradient-to-r from-primary to-secondary opacity-80 blur-sm shadow-[0_0_20px_#00E5FF]"
          />
          <Loader2 className="absolute w-12 h-12 text-primary animate-spin" />
        </div>

        <div className="space-y-2">
          <h3 className="font-mono text-sm uppercase tracking-widest text-primary font-bold">
            AI Drilling Initiated
          </h3>
          <p className="font-sans text-xs font-light text-on-surface-muted max-w-sm px-4">
            {status || "Synthesizing deep resolution layer..."}
          </p>
        </div>

        {/* Progress Line */}
        <div className="w-full h-[1px] bg-white/5 relative overflow-hidden rounded-full">
          <motion.div
            animate={{ x: ["-100%", "100%"] }}
            transition={{ repeat: Infinity, duration: 1.5, ease: "easeInOut" }}
            className="absolute top-0 bottom-0 left-0 w-1/3 bg-gradient-to-r from-primary to-secondary"
          />
        </div>
      </GlassPanel>
    </div>
  );
};

// ==========================================
// SIMILARITYSCORE COMPONENT
// ==========================================
export const SimilarityScore: React.FC<{ score: number }> = ({ score }) => {
  return (
    <div className="flex items-center gap-2 font-mono">
      <div className="relative flex items-center justify-center">
        {/* Outer Circular Track */}
        <svg className="w-12 h-12 transform -rotate-90">
          <circle
            cx="24"
            cy="24"
            r="18"
            className="stroke-white/5 fill-transparent"
            strokeWidth="2.5"
          />
          <motion.circle
            cx="24"
            cy="24"
            r="18"
            className="stroke-primary fill-transparent"
            strokeWidth="2.5"
            strokeDasharray="113"
            initial={{ strokeDashoffset: 113 }}
            animate={{ strokeDashoffset: 113 - (113 * score) / 100 }}
            transition={{ duration: 1, ease: "easeOut" }}
          />
        </svg>
        <span className="absolute text-[10px] text-primary font-bold">{score}%</span>
      </div>
      <div className="text-left">
        <span className="text-[9px] uppercase tracking-wider text-on-surface-muted block">Match confidence</span>
        <span className="text-[10px] uppercase tracking-widest text-primary font-bold block">HIGH SIMILARITY</span>
      </div>
    </div>
  );
};

// ==========================================
// CANVASTOOLBAR COMPONENT
// ==========================================
interface CanvasToolbarProps {
  onZoomIn: () => void;
  onZoomOut: () => void;
  onReset: () => void;
  onToggleFullscreen?: () => void;
}

export const CanvasToolbar: React.FC<CanvasToolbarProps> = ({ onZoomIn, onZoomOut, onReset, onToggleFullscreen }) => {
  return (
    <div className="absolute bottom-6 left-1/2 -translate-x-1/2 flex items-center gap-1.5 bg-black/60 backdrop-blur-xl border border-white/10 px-3 py-1.5 rounded-full shadow-2xl z-20">
      <button
        onClick={onZoomIn}
        className="p-1.5 hover:bg-white/10 text-on-surface-muted hover:text-primary rounded-lg transition-colors cursor-pointer"
        title="Zoom In"
      >
        <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 4v16m8-8H4" />
        </svg>
      </button>
      <button
        onClick={onZoomOut}
        className="p-1.5 hover:bg-white/10 text-on-surface-muted hover:text-primary rounded-lg transition-colors cursor-pointer"
        title="Zoom Out"
      >
        <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M20 12H4" />
        </svg>
      </button>
      <div className="w-[1px] h-4 bg-white/10 mx-0.5" />
      <button
        onClick={onReset}
        className="px-2.5 py-1 hover:bg-white/10 text-[9px] font-mono uppercase tracking-wider text-on-surface-muted hover:text-primary rounded-lg transition-colors cursor-pointer"
        title="Reset Canvas View"
      >
        RESET
      </button>
    </div>
  );
};
