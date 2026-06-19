import React from 'react';
import { X, ExternalLink, Sparkles, Loader2 } from 'lucide-react';
import { motion, AnimatePresence } from 'framer-motion';

interface ProductDrawerProps {
  isOpen: boolean;
  onClose: () => void;
  loadingState: string | null;
  garmentDetails?: any;
  products?: any[];
  pipelineError?: string | null;
}

const ProductDrawer: React.FC<ProductDrawerProps> = ({
  isOpen,
  onClose,
  loadingState,
  garmentDetails,
  products = [],
  pipelineError,
}) => {
  return (
    <AnimatePresence>
      {isOpen && (
        <>
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            onClick={onClose}
            className="fixed inset-0 bg-black/40 backdrop-blur-sm z-40"
          />
          <motion.div
            initial={{ x: '100%' }}
            animate={{ x: 0 }}
            exit={{ x: '100%' }}
            transition={{ type: 'spring', damping: 25, stiffness: 200 }}
            className="fixed right-0 top-0 z-50 flex h-full w-full max-w-[440px] flex-col overflow-y-auto border-l border-white/10 bg-[#121212] shadow-2xl"
          >
            <div className="sticky top-0 z-10 bg-[#121212]/90 backdrop-blur-md px-6 py-4 flex justify-between items-center border-b border-white/10">
              <h2 className="text-lg font-medium text-white tracking-wide flex items-center gap-2">
                <Sparkles size={18} className="text-luxury-gold" />
                Analysis Results
              </h2>
              <button 
                onClick={onClose}
                className="p-2 hover:bg-white/10 rounded-full transition-colors text-white/60 hover:text-white"
              >
                <X size={20} />
              </button>
            </div>

            <div className="p-6 flex-1 flex flex-col gap-8">
              {/* Loading State */}
              {loadingState && (
                <div className="flex flex-col items-center justify-center py-12 gap-4 text-luxury-gold">
                  <Loader2 size={32} className="animate-spin" />
                  <p className="text-sm font-medium tracking-wide animate-pulse">{loadingState}</p>
                </div>
              )}

              {/* Pipeline Error */}
              {!loadingState && pipelineError && (
                <div className="rounded-md border border-red-400/50 bg-red-950/70 px-4 py-3 text-sm text-red-50 backdrop-blur-md">
                  <div className="font-semibold uppercase tracking-widest text-red-300 text-xs mb-1">Analysis failed</div>
                  <div className="leading-relaxed text-red-100/80">{pipelineError}</div>
                </div>
              )}

              {/* Garment Details */}
              {!loadingState && garmentDetails && (
                <div className="space-y-4">
                  <div className="bg-white/5 rounded-xl p-5 border border-white/10">
                    <h3 className="text-luxury-gold text-sm font-semibold tracking-widest uppercase mb-4 border-b border-white/10 pb-2">Identified Attributes</h3>
                    
                    <div className="grid grid-cols-2 gap-y-4 gap-x-2 text-sm">
                      <div>
                        <span className="text-white/40 block text-xs uppercase tracking-wider mb-1">Category</span>
                        <span className="text-white/90 font-medium">{garmentDetails.category || 'N/A'}</span>
                      </div>
                      <div>
                        <span className="text-white/40 block text-xs uppercase tracking-wider mb-1">Style</span>
                        <span className="text-white/90 font-medium">{garmentDetails.style || 'N/A'}</span>
                      </div>
                      <div>
                        <span className="text-white/40 block text-xs uppercase tracking-wider mb-1">Color</span>
                        <span className="text-white/90 font-medium">{garmentDetails.color || 'N/A'}</span>
                      </div>
                      <div>
                        <span className="text-white/40 block text-xs uppercase tracking-wider mb-1">Material</span>
                        <span className="text-white/90 font-medium">{garmentDetails.material || 'N/A'}</span>
                      </div>
                      <div>
                        <span className="text-white/40 block text-xs uppercase tracking-wider mb-1">Fit</span>
                        <span className="text-white/90 font-medium">{garmentDetails.fit || 'N/A'}</span>
                      </div>
                      <div>
                        <span className="text-white/40 block text-xs uppercase tracking-wider mb-1">Pattern</span>
                        <span className="text-white/90 font-medium">{garmentDetails.pattern || 'N/A'}</span>
                      </div>
                      <div>
                        <span className="text-white/40 block text-xs uppercase tracking-wider mb-1">Gender</span>
                        <span className="text-white/90 font-medium">{garmentDetails.gender || 'N/A'}</span>
                      </div>
                      <div>
                        <span className="text-white/40 block text-xs uppercase tracking-wider mb-1">Confidence</span>
                        <span className="text-white/90 font-medium">{garmentDetails.confidence || 'N/A'}</span>
                      </div>
                      <div className="col-span-2 mt-2">
                         <span className="text-white/40 block text-xs uppercase tracking-wider mb-1">Description</span>
                         <p className="text-white/80 leading-relaxed">{garmentDetails.description}</p>
                      </div>
                    </div>
                  </div>
                </div>
              )}

              {/* Products List */}
              {!loadingState && products.length > 0 && (
                <div className="space-y-4">
                  <h3 className="text-luxury-gold text-sm font-semibold tracking-widest uppercase flex justify-between items-end border-b border-white/10 pb-2">
                    Similar Products
                    <span className="text-white/40 text-xs font-normal lowercase">{products.length} found</span>
                  </h3>
                  
                  <div className="flex flex-col gap-4">
                    {products.map((product) => (
                      <a 
                        key={product.id}
                        href={product.product_url}
                        target="_blank"
                        rel="noopener noreferrer"
                        className="group flex gap-4 bg-white/5 rounded-xl p-3 border border-white/5 hover:border-luxury-gold/50 transition-all duration-300 hover:bg-white/10 relative overflow-hidden"
                      >
                        <div className="w-24 h-32 flex-shrink-0 bg-black/40 rounded-lg overflow-hidden relative">
                          <img 
                            src={product.image_url} 
                            alt={product.title}
                            className="w-full h-full object-cover group-hover:scale-105 transition-transform duration-500"
                            loading="lazy"
                          />
                          <div className="absolute top-0 right-0 bg-black/80 text-luxury-gold text-[10px] font-bold px-2 py-1 rounded-bl-lg backdrop-blur-md">
                            {product.visual_match_pct}% Match
                          </div>
                        </div>
                        
                        <div className="flex flex-col justify-between py-1 flex-1 min-w-0">
                          <div>
                            <p className="text-white/60 text-xs mb-1 truncate">{product.retailer}</p>
                            <h4 className="text-white font-medium text-sm leading-snug line-clamp-2 group-hover:text-luxury-gold transition-colors">{product.title}</h4>
                            {product.description && (
                              <p className="mt-2 line-clamp-2 text-xs leading-snug text-white/45">
                                {product.description}
                              </p>
                            )}
                          </div>
                          
                          <div className="flex justify-between items-end mt-2">
                            <span className="text-white font-semibold">{product.price}</span>
                            <div className="flex items-center gap-1 text-luxury-gold opacity-0 group-hover:opacity-100 transition-opacity translate-x-2 group-hover:translate-x-0">
                               <span className="text-xs font-medium">Buy</span>
                               <ExternalLink size={14} />
                            </div>
                          </div>
                          <div className="mt-2 flex items-center justify-between gap-2 text-[10px] text-white/35">
                            <span>Source: {product.source}</span>
                            {product.visual_similarity !== undefined && (
                              <span>Visual: {Math.round(product.visual_similarity * 100)}%</span>
                            )}
                          </div>
                        </div>
                      </a>
                    ))}
                  </div>
                </div>
              )}

              {!loadingState && garmentDetails && products.length === 0 && (
                <div className="text-center py-12 text-white/40">
                  <p>No visually similar products found currently.</p>
                </div>
              )}
            </div>
          </motion.div>
        </>
      )}
    </AnimatePresence>
  );
};

export default ProductDrawer;
