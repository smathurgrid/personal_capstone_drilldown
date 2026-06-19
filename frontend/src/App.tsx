import { useRef, useState } from 'react';
import axios from 'axios';
import { Home } from 'lucide-react';
import Canvas from './components/Canvas';
import ProductDrawer from './components/ProductDrawer';
import UploadSection from './components/UploadSection';
import { API_BASE_URL } from './api';

function App() {
  const [currentImage, setCurrentImage] = useState<any>(null);
  const [garments, setGarments] = useState<any[]>([]);
  const [selectedGarment, setSelectedGarment] = useState<any>(null);
  const [garmentDetails, setGarmentDetails] = useState<any>(null);
  const [products, setProducts] = useState<any[]>([]);

  const [isDetecting, setIsDetecting] = useState(false);
  const [isDrawerOpen, setIsDrawerOpen] = useState(false);
  const [loadingState, setLoadingState] = useState<string | null>(null);
  const [detectionError, setDetectionError] = useState<string | null>(null);
  const [pipelineError, setPipelineError] = useState<string | null>(null);

  // Incremented on every new detection; lets stale in-flight responses know to discard themselves
  const detectionGenRef = useRef(0);

  const detectGarments = async (imageData: any) => {
    // Claim this generation; any older in-flight call that resolves later will be a no-op
    const gen = ++detectionGenRef.current;
    setGarments([]);
    setDetectionError(null);
    setIsDetecting(true);
    try {
      const formData = new FormData();
      formData.append('filename', imageData.filename);
      const response = await axios.post(`${API_BASE_URL}/api/detect-garments`, formData);
      if (gen !== detectionGenRef.current) return; // superseded by a newer upload
      setGarments(response.data.garments || []);
    } catch (error) {
      if (gen !== detectionGenRef.current) return;
      console.error('Error detecting garments:', error);
      const message = axios.isAxiosError(error)
        ? error.response?.data?.detail || error.message
        : 'Unable to detect garments.';
      setDetectionError(message);
    } finally {
      if (gen === detectionGenRef.current) setIsDetecting(false);
    }
  };

  const handleUploadSuccess = async (imageData: any) => {
    console.log('Upload Success:', imageData);
    setCurrentImage(imageData);
    await detectGarments(imageData);
  };

  const handleHome = () => {
    detectionGenRef.current++; // discard any in-flight Qwen detection
    setCurrentImage(null);
    setGarments([]);
    setSelectedGarment(null);
    setGarmentDetails(null);
    setProducts([]);
    setDetectionError(null);
    setPipelineError(null);
    setIsDrawerOpen(false);
  };

  const handleLabelClick = async (garment: any) => {
    setSelectedGarment(garment);
    setIsDrawerOpen(true);
    setGarmentDetails(null);
    setProducts([]);
    setPipelineError(null);

    // Step 1: Get Details & Search Query
    setLoadingState('Analyzing garment...');
    try {
      const detailsForm = new FormData();
      detailsForm.append('filename', currentImage.filename);
      detailsForm.append('bbox', JSON.stringify(garment.boundingBox));

      const detailsRes = await axios.post(`${API_BASE_URL}/api/get-details`, detailsForm);
      const details = detailsRes.data;
      setGarmentDetails(details.attributes);

      // Step 2: Search Products (SerpApi)
      setLoadingState('Searching live products...');
      const searchForm = new FormData();
      searchForm.append('query', details.shopping_query);
      const searchRes = await axios.post(`${API_BASE_URL}/api/search-products`, searchForm);
      const initialProducts = searchRes.data.products;

      if (!initialProducts || initialProducts.length === 0) {
        setLoadingState(null);
        return;
      }

      // Step 3: Rerank Products (FashionCLIP)
      setLoadingState('Visually reranking results...');
      const rerankForm = new FormData();
      rerankForm.append('filename', currentImage.filename);
      rerankForm.append('bbox', JSON.stringify(garment.boundingBox));
      rerankForm.append('products', JSON.stringify(initialProducts));
      rerankForm.append('attributes', JSON.stringify(details.attributes));

      const rerankRes = await axios.post(`${API_BASE_URL}/api/rerank`, rerankForm);
      setProducts(rerankRes.data.products);

    } catch (error) {
      console.error('Error in pipeline:', error);
      const message = axios.isAxiosError(error)
        ? error.response?.data?.detail || error.message
        : 'Something went wrong. Please try again.';
      setPipelineError(message);
    } finally {
      setLoadingState(null);
    }
  };

  return (
    <div className="flex h-screen bg-luxury-black overflow-hidden font-sans relative">
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
          <Canvas 
            imageUrl={`${API_BASE_URL}${currentImage.imageUrl}`} 
            garments={garments}
            isDetecting={isDetecting}
            detectionError={detectionError}
            onRetryDetection={() => currentImage && detectGarments(currentImage)}
            onLabelClick={handleLabelClick}
            selectedGarmentId={selectedGarment?.id}
          />
        )}
      </main>

      <ProductDrawer
        isOpen={isDrawerOpen}
        onClose={() => setIsDrawerOpen(false)}
        loadingState={loadingState}
        garmentDetails={garmentDetails}
        products={products}
        pipelineError={pipelineError}
      />
    </div>
  );
}

export default App;
