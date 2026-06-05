import React from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { X, Loader2 } from 'lucide-react';

interface ProductDrawerProps {
  isOpen: boolean;
  onClose: () => void;
  isLoading: boolean;
  data: any;
  onDrill: (productId: number, x: number, y: number) => void;
}

const ProductDrawer: React.FC<ProductDrawerProps> = ({ isOpen, onClose, isLoading, data, onDrill }) => {
  const handleProductClick = (productId: number, e: React.MouseEvent<HTMLDivElement>) => {
    const rect = e.currentTarget.getBoundingClientRect();
    const x = (e.clientX - rect.left) / rect.width;
    const y = (e.clientY - rect.top) / rect.height;
    onDrill(productId, x, y);
  };

  return (
    <AnimatePresence>
      {isOpen && (
        <motion.div
          initial={{ x: '100%' }}
          animate={{ x: 0 }}
          exit={{ x: '100%' }}
          transition={{ type: 'spring', damping: 25, stiffness: 200 }}
          className="fixed right-0 top-0 h-full w-[400px] bg-[#121212] border-l border-white/10 shadow-2xl z-50 flex flex-col"
        >
          <div className="p-4 border-b border-white/10 flex items-center justify-between">
            <h2 className="text-xl font-bold text-luxury-gold uppercase tracking-widest">
              Identified Item
            </h2>
            <button onClick={onClose} className="p-1 hover:bg-white/10 rounded-full transition-colors">
              <X size={24} />
            </button>
          </div>

          <div className="flex-1 overflow-y-auto p-4">
            {isLoading ? (
              <div className="h-full flex flex-col items-center justify-center text-gray-400">
                <Loader2 size={48} className="animate-spin mb-4" />
                <p>Analyzing with Gemini...</p>
              </div>
            ) : data ? (
              <div className="space-y-6">
                {/* Attributes Section */}
                <div className="bg-white/5 p-4 rounded-lg border border-white/5">
                  <h3 className="text-sm font-semibold text-gray-400 uppercase mb-3">Attributes</h3>
                  <div className="grid grid-cols-2 gap-y-2 text-sm">
                    <div className="text-gray-500">Type</div>
                    <div className="text-luxury-gold font-bold">{data.attributes.articleType}</div>
                    <div className="text-gray-500">Category</div>
                    <div>{data.attributes.masterCategory}</div>
                    <div className="text-gray-500">Color</div>
                    <div>{data.attributes.color}</div>
                    <div className="text-gray-500">Gender</div>
                    <div>{data.attributes.gender}</div>
                  </div>
                  <p className="mt-4 text-xs text-gray-400 italic border-t border-white/5 pt-3">
                    "{data.attributes.description}"
                  </p>
                </div>

                {/* Similar Products */}
                <div>
                  <h3 className="text-sm font-semibold text-gray-400 uppercase mb-3">Similar Products</h3>
                  <div className="grid grid-cols-1 gap-4">
                    {data.results.map((product: any) => (
                      <div 
                        key={product.product_id} 
                        className="flex gap-4 p-2 hover:bg-white/5 rounded-lg transition-colors group border border-transparent hover:border-white/10 cursor-crosshair"
                        onClick={(e) => handleProductClick(product.product_id, e)}
                      >
                        <div className="w-20 h-24 bg-gray-800 rounded overflow-hidden">
                          <img 
                            src={`http://localhost:8000/dataset/${product.payload.filename}`} 
                            alt={product.payload.productDisplayName}
                            className="w-full h-full object-cover"
                          />
                        </div>
                        <div className="flex-1 min-w-0">
                          <p className="text-sm font-medium text-white truncate">{product.payload.productDisplayName}</p>
                          <p className="text-xs text-gray-500">{product.payload.articleType}</p>
                          <div className="mt-2 flex items-center gap-2">
                            <div className="h-1 flex-1 bg-gray-800 rounded-full overflow-hidden">
                              <div 
                                className="h-full bg-luxury-gold" 
                                style={{ width: `${product.visual_score * 100}%` }}
                              />
                            </div>
                            <span className="text-[10px] text-luxury-gold font-mono">
                              {(product.visual_score * 100).toFixed(0)}%
                            </span>
                          </div>
                        </div>
                      </div>
                    ))}
                  </div>
                </div>
              </div>
            ) : (
              <p className="text-center text-gray-500 mt-10">Click an item to see details</p>
            )}
          </div>
        </motion.div>
      )}
    </AnimatePresence>
  );
};

export default ProductDrawer;
