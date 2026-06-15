import { useMemo, useState } from "react";
import { Home } from "lucide-react";
import { drillProduct, identifyItem, type DrillNode } from "../services/ecommerce-api";
import { resolveUrl } from "../services/api";
import OutfitCanvas from "./ecommerce/OutfitCanvas";
import DrillHistory from "./ecommerce/DrillHistory";
import ProductDrawer from "./ecommerce/ProductDrawer";
import UploadSection from "./ecommerce/UploadSection";

function nodeCanvasUrl(node: DrillNode, outfitUrl: string): string {
  return resolveUrl(node.canvasImageUrl ?? outfitUrl);
}

export default function EcommercePage() {
  const [currentImage, setCurrentImage] = useState<{ imageId: string; imageUrl: string } | null>(null);
  const [history, setHistory] = useState<DrillNode[]>([]);
  const [isDrawerOpen, setIsDrawerOpen] = useState(false);
  const [isLoading, setIsLoading] = useState(false);
  const [selectedItem, setSelectedItem] = useState<DrillNode | null>(null);
  const [pendingMarker, setPendingMarker] = useState<{ x: number; y: number } | null>(null);
  const [activeCanvasUrl, setActiveCanvasUrl] = useState<string | null>(null);

  const outfitUrl = currentImage?.imageUrl ?? "";

  const displayCanvasUrl = activeCanvasUrl ?? outfitUrl;

  const canvasMarkers = useMemo(() => {
    const markers = history
      .filter((h) => nodeCanvasUrl(h, outfitUrl) === displayCanvasUrl)
      .map((h) => ({ x: h.x, y: h.y }));
    if (pendingMarker && displayCanvasUrl === (activeCanvasUrl ?? outfitUrl)) {
      markers.push(pendingMarker);
    }
    return markers;
  }, [history, outfitUrl, displayCanvasUrl, activeCanvasUrl, pendingMarker]);

  const handleHome = () => {
    setCurrentImage(null);
    setHistory([]);
    setSelectedItem(null);
    setIsDrawerOpen(false);
    setPendingMarker(null);
    setActiveCanvasUrl(null);
  };

  const handleUploadSuccess = (imageData: { imageId: string; imageUrl: string }) => {
    setCurrentImage(imageData);
    setHistory([]);
    setSelectedItem(null);
    setIsDrawerOpen(false);
    setActiveCanvasUrl(imageData.imageUrl);
  };

  const handleClick = async (x: number, y: number) => {
    if (!currentImage) return;
    setPendingMarker({ x, y });
    setIsLoading(true);
    setIsDrawerOpen(true);
    setSelectedItem(null);
    try {
      const node = await identifyItem(currentImage.imageId, x, y);
      setSelectedItem(node);
      setHistory((prev) => [...prev, node]);
      setActiveCanvasUrl(node.canvasImageUrl ? resolveUrl(node.canvasImageUrl) : currentImage.imageUrl);
      setPendingMarker(null);
    } catch (err) {
      console.error(err);
      setPendingMarker(null);
    } finally {
      setIsLoading(false);
    }
  };

  const handleDrill = async (productId: number, x: number, y: number) => {
    setIsLoading(true);
    try {
      const node = await drillProduct(productId, x, y);
      setSelectedItem(node);
      setHistory((prev) => [...prev, node]);
      setActiveCanvasUrl(resolveUrl(node.canvasImageUrl!));
    } catch (err) {
      console.error(err);
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <div className="flex h-full min-h-[calc(100vh-56px)] bg-luxury-black overflow-hidden relative">
      {currentImage && (
        <button
          type="button"
          onClick={handleHome}
          className="absolute top-4 left-4 z-40 p-2 bg-white/5 hover:bg-white/10 rounded-full border border-white/10 text-luxury-gold"
          title="Back to upload"
        >
          <Home size={22} />
        </button>
      )}
      <main className="flex-1 relative flex flex-col items-center justify-center">
        {!currentImage ? (
          <UploadSection onUploadSuccess={handleUploadSuccess} />
        ) : (
          <>
            <DrillHistory
              history={history}
              onNavigate={(index) => {
                if (index === -1) {
                  setHistory([]);
                  setSelectedItem(null);
                  setIsDrawerOpen(false);
                  setActiveCanvasUrl(outfitUrl);
                  return;
                }
                const slice = history.slice(0, index + 1);
                const node = slice[slice.length - 1];
                setHistory(slice);
                setSelectedItem(node);
                setActiveCanvasUrl(nodeCanvasUrl(node, outfitUrl));
              }}
            />
            <OutfitCanvas imageUrl={displayCanvasUrl} onClick={handleClick} markers={canvasMarkers} />
          </>
        )}
      </main>
      <ProductDrawer
        isOpen={isDrawerOpen}
        onClose={() => setIsDrawerOpen(false)}
        isLoading={isLoading}
        data={selectedItem}
        onDrill={handleDrill}
      />
    </div>
  );
}
