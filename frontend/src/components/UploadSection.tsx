import React, { useState } from 'react';
import axios from 'axios';
import { Upload, Loader2 } from 'lucide-react';

interface UploadSectionProps {
  onUploadSuccess: (data: any) => void;
}

const UploadSection: React.FC<UploadSectionProps> = ({ onUploadSuccess }) => {
  const [isUploading, setIsUploading] = useState(false);

  const handleFileChange = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;

    setIsUploading(true);
    const formData = new FormData();
    formData.append('file', file);

    try {
      const response = await axios.post('http://localhost:8000/api/upload', formData);
      onUploadSuccess(response.data);
    } catch (error) {
      console.error('Upload failed:', error);
      alert('Failed to upload image. Make sure the backend is running.');
    } finally {
      setIsUploading(false);
    }
  };

  return (
    <div className="flex flex-col items-center justify-center space-y-8 max-w-md w-full p-12 border-2 border-dashed border-white/20 rounded-3xl bg-white/5 backdrop-blur-sm">
      <div className="w-24 h-24 bg-luxury-gold/20 rounded-full flex items-center justify-center text-luxury-gold">
        {isUploading ? <Loader2 size={40} className="animate-spin" /> : <Upload size={40} />}
      </div>
      
      <div className="text-center">
        <h1 className="text-3xl font-bold mb-2">AI Ecommerce DrillDown</h1>
        <p className="text-gray-400">Upload a celebrity photo, runway image, or streetwear shot to begin exploration.</p>
      </div>

      <label className="cursor-pointer bg-luxury-gold hover:bg-luxury-gold/80 text-black font-bold py-4 px-8 rounded-full transition-all transform hover:scale-105 active:scale-95 disabled:opacity-50">
        {isUploading ? 'Uploading...' : 'Choose Image'}
        <input type="file" className="hidden" onChange={handleFileChange} accept="image/*" disabled={isUploading} />
      </label>
      
      <div className="text-[10px] uppercase tracking-widest text-gray-600">
        Powered by Gemini 2.5 Flash & FashionCLIP
      </div>
    </div>
  );
};

export default UploadSection;
