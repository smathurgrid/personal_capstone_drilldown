import React, { useState } from 'react';
import axios from 'axios';
import { Home } from 'lucide-react';
import Canvas from './components/Canvas';
import ProductDrawer from './components/ProductDrawer';
import DrillHistory from './components/DrillHistory';
import UploadSection from './components/UploadSection';

const API_BASE_URL = 'http://localhost:8000';

function App() {
  const [currentImage, setCurrentImage] = useState<any>(null);
  const [history, setHistory] = useState<any[]>([]);
  const [isDrawerOpen, setIsDrawerOpen] = useState(false);
  const [isLoading, setIsLoading] = useState(false);
  const [selectedItem, setSelectedItem] = useState<any>(null);
  const [pendingMarker, setPendingMarker] = useState<{x: number, y: number} | null>(null);

  const handleUploadSuccess = (imageData: any) => {
    console.log('Upload Success:', imageData);
    setCurrentImage(imageData);
    setHistory([]);
  };

  const handleHome = () => {
    setCurrentImage(null);
    setHistory([]);
    setSelectedItem(null);
    setIsDrawerOpen(false);
    setPendingMarker(null);
  };

  const handleClick = async (x: number, y: number) => {
    if (!currentImage) return;

    console.log(`\n--- NEW CLICK DETECTED ---`);
    console.log(`Coordinates: x=${x.toFixed(4)}, y=${y.toFixed(4)}`);
    
    // Immediate feedback: Show the marker optimistically
    setPendingMarker({ x, y });
    setIsLoading(true);
    setIsDrawerOpen(true);
    setSelectedItem(null); // Clear previous results while loading
    
    try {
      const formData = new FormData();
      formData.append('imageId', currentImage.imageId);
      formData.append('x', x.toString());
      formData.append('y', y.toString());

      console.log('Sending /api/identify request...');
      const response = await axios.post(`${API_BASE_URL}/api/identify`, formData);
      console.log('Response received:', response.data);
      
      setSelectedItem(response.data);
      setHistory(prev => [...prev, response.data]);
      setPendingMarker(null); // Remove pending marker as it's now in history
    } catch (error) {
      console.error('Error identifying item:', error);
      setPendingMarker(null);
    } finally {
      setIsLoading(false);
    }
  };

  const handleDrill = async (productId: number, x: number, y: number) => {
    console.log(`\n--- DRILL DOWN DETECTED ---`);
    console.log(`Product ID: ${productId}, x=${x.toFixed(4)}, y=${y.toFixed(4)}`);
    
    setIsLoading(true);
    try {
      const formData = new FormData();
      formData.append('productId', productId.toString());
      formData.append('x', x.toString());
      formData.append('y', y.toString());

      const response = await axios.post(`${API_BASE_URL}/api/drill`, formData);
      console.log('Drill response:', response.data);
      
      setSelectedItem(response.data);
      setHistory(prev => [...prev, response.data]);
    } catch (error) {
      console.error('Error drilling down:', error);
    } finally {
      setIsLoading(false);
    }
  };

  // Combine history markers with any pending optimistic marker
  const allMarkers = history.map(h => ({ x: h.x, y: h.y }));
  if (pendingMarker) {
    allMarkers.push(pendingMarker);
  }

  return (
    <div className="flex h-screen bg-luxury-black overflow-hidden font-sans relative">
      {/* Home Button */}
      <button 
        onClick={handleHome}
        className="absolute top-6 left-6 z-40 p-2 bg-white/5 hover:bg-white/10 rounded-full border border-white/10 text-luxury-gold transition-all duration-300 group"
        title="Go to Upload"
      >
        <Home size={24} className="group-hover:scale-110 transition-transform" />
      </button>

      <main className="flex-1 relative flex flex-col items-center justify-center p-4">
        {!currentImage ? (
          <UploadSection onUploadSuccess={handleUploadSuccess} />
        ) : (
          <>
            <DrillHistory history={history} onNavigate={(index) => {
              if (index === -1) {
                setHistory([]);
                setSelectedItem(null);
                setIsDrawerOpen(false);
                return;
              }
              const newHistory = history.slice(0, index + 1);
              setHistory(newHistory);
              setSelectedItem(newHistory[newHistory.length - 1]);
            }} />
            <Canvas 
              imageUrl={`${API_BASE_URL}${currentImage.imageUrl}`} 
              onClick={handleClick}
              markers={allMarkers}
            />
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

export default App;
