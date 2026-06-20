import { motion, AnimatePresence } from "framer-motion";
import { X, Loader2 } from "lucide-react";
import { datasetImageUrl, type DrillNode } from "../../services/ecommerce-api";
import { normalizeElementClick } from "../../utils/coords";

interface Props {
  isOpen: boolean;
  onClose: () => void;
  isLoading: boolean;
  data: DrillNode | null;
  onDrill: (productId: number, x: number, y: number) => void;
}

export default function ProductDrawer({ isOpen, onClose, isLoading, data, onDrill }: Props) {
  const handleProductClick = (productId: number, e: React.MouseEvent<HTMLDivElement>) => {
    const { x, y } = normalizeElementClick(e, e.currentTarget);
    onDrill(productId, x, y);
  };

  return (
    <AnimatePresence>
      {isOpen && (
        <motion.div
          initial={{ x: "100%" }}
          animate={{ x: 0 }}
          exit={{ x: "100%" }}
          transition={{ type: "spring", damping: 25, stiffness: 200 }}
          className="fixed right-0 top-0 h-full w-[420px] bg-[#131d3d] border-l border-[#2d3c5e] shadow-2xl z-50 flex flex-col"
        >
          <div className="p-6 border-b border-[#2d3c5e] flex items-center justify-between bg-[rgba(19,29,61,0.6)]">
            <h2 className="text-lg font-bold text-[#ff6b35] uppercase tracking-wider font-[Playfair Display]">Identified Item</h2>
            <button type="button" onClick={onClose} className="p-1.5 hover:bg-white/10 rounded-lg transition-all" title="Close drawer">
              <X size={20} strokeWidth={2} />
            </button>
          </div>
          <div className="flex-1 overflow-y-auto p-6">
            {isLoading ? (
              <div className="h-full flex flex-col items-center justify-center text-[#7a81a0]">
                <Loader2 size={48} className="animate-spin mb-4" strokeWidth={1.5} />
                <p className="text-sm font-medium">Analyzing with Gemini…</p>
              </div>
            ) : data ? (
              <div className="space-y-6">
                <div className="bg-[rgba(255,107,53,0.08)] p-4 rounded-lg border border-[#2d3c5e]">
                  <h3 className="text-xs font-bold text-[#7a81a0] uppercase mb-3 tracking-wide font-[JetBrains Mono]">Attributes</h3>
                  <div className="grid grid-cols-2 gap-y-2.5 text-sm">
                    <div className="text-[#7a81a0]">Type</div>
                    <div className="text-[#ff6b35] font-semibold">{data.attributes.articleType}</div>
                    <div className="text-[#7a81a0]">Category</div>
                    <div className="text-[#e8eef7]">{data.attributes.masterCategory}</div>
                    <div className="text-[#7a81a0]">Color</div>
                    <div className="text-[#e8eef7]">{data.attributes.color}</div>
                  </div>
                  <p className="mt-4 text-xs text-[#a8afc4] italic border-t border-[#2d3c5e] pt-3">
                    &ldquo;{data.attributes.description}&rdquo;
                  </p>
                </div>
                <div>
                  <h3 className="text-xs font-bold text-[#7a81a0] uppercase mb-3 tracking-wide font-[JetBrains Mono]">Similar Products</h3>
                  <div className="grid grid-cols-1 gap-3">
                    {data.results.map((product) => (
                      <div
                        key={product.product_id}
                        role="button"
                        tabIndex={0}
                        className="flex gap-3 p-2.5 hover:bg-[rgba(255,107,53,0.08)] rounded-lg cursor-crosshair border border-transparent hover:border-[#2d3c5e] transition-all"
                        onClick={(e) => handleProductClick(product.product_id, e)}
                        onKeyDown={() => {}}
                      >
                        <div className="w-20 h-24 bg-[#0a0a0a] rounded overflow-hidden border border-[#2d3c5e]">
                          <img
                            src={datasetImageUrl(product.payload.filename ?? `${product.product_id}.jpg`)}
                            alt={product.payload.productDisplayName}
                            className="w-full h-full object-cover"
                          />
                        </div>
                        <div className="flex-1 min-w-0">
                          <p className="text-sm font-medium text-[#e8eef7] truncate">{product.payload.productDisplayName}</p>
                          <p className="text-xs text-[#7a81a0]">{product.payload.articleType}</p>
                          <span className="text-[10px] text-[#ff6b35] font-semibold font-[JetBrains Mono]">
                            {(product.visual_score * 100).toFixed(0)}% match
                          </span>
                        </div>
                      </div>
                    ))}
                  </div>
                </div>
              </div>
            ) : (
              <p className="text-center text-[#7a81a0] mt-10">Click an item to see details</p>
            )}
          </div>
        </motion.div>
      )}
    </AnimatePresence>
  );
}
