import React, { useRef } from 'react';

interface CanvasProps {
  imageUrl: string;
  onClick: (x: number, y: number) => void;
  markers: { x: number, y: number }[];
}

const Canvas: React.FC<CanvasProps> = ({ imageUrl, onClick, markers }) => {
  const imageRef = useRef<HTMLImageElement>(null);

  const handleImageClick = (e: React.MouseEvent<HTMLImageElement>) => {
    if (!imageRef.current) return;
    
    const rect = imageRef.current.getBoundingClientRect();
    // Calculate coordinates relative to the actual displayed image area
    const x = (e.clientX - rect.left) / rect.width;
    const y = (e.clientY - rect.top) / rect.height;
    
    onClick(x, y);
  };

  return (
    <div className="w-full h-full flex items-center justify-center p-4 overflow-hidden min-h-0">
      <div className="relative inline-block max-w-full max-h-full">
        <img 
          ref={imageRef}
          src={imageUrl} 
          alt="Exploration Canvas" 
          className="block max-w-full max-h-[calc(100vh-120px)] w-auto h-auto object-contain cursor-crosshair rounded-lg shadow-2xl border border-white/10"
          onClick={handleImageClick}
          onDragStart={(e) => e.preventDefault()}
        />
        
        {markers.map((marker, idx) => (
          <div 
            key={idx}
            className="absolute w-4 h-4 -ml-2 -mt-2 bg-red-600 rounded-full border-2 border-white shadow-lg animate-pulse pointer-events-none z-10"
            style={{ 
              left: `${marker.x * 100}%`, 
              top: `${marker.y * 100}%`,
              display: marker.x < 0 || marker.x > 1 ? 'none' : 'block'
            }}
          />
        ))}
      </div>
    </div>
  );
};

export default Canvas;
