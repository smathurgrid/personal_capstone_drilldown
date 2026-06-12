import { useRef } from "react";
import { normalizeElementClick } from "../../utils/coords";

interface CanvasProps {
  imageUrl: string;
  onClick: (x: number, y: number) => void;
  markers: { x: number; y: number }[];
}

export default function Canvas({ imageUrl, onClick, markers }: CanvasProps) {
  const imageRef = useRef<HTMLImageElement>(null);

  const handleImageClick = (e: React.MouseEvent<HTMLImageElement>) => {
    if (!imageRef.current) return;
    const { x, y } = normalizeElementClick(e, imageRef.current);
    onClick(x, y);
  };

  return (
    <div className="w-full h-full flex items-center justify-center p-4 overflow-hidden min-h-0">
      <div className="relative inline-block max-w-full max-h-full">
        <img
          ref={imageRef}
          src={imageUrl}
          alt="Exploration canvas"
          className="block max-w-full max-h-[calc(100vh-140px)] w-auto h-auto object-contain cursor-crosshair rounded-lg shadow-2xl border border-white/10"
          onClick={handleImageClick}
          onDragStart={(e) => e.preventDefault()}
        />
        {markers.map((marker, idx) => (
          <div
            key={idx}
            className="absolute w-4 h-4 -ml-2 -mt-2 bg-red-600 rounded-full border-2 border-white shadow-lg animate-pulse pointer-events-none z-10"
            style={{ left: `${marker.x * 100}%`, top: `${marker.y * 100}%` }}
          />
        ))}
      </div>
    </div>
  );
}
