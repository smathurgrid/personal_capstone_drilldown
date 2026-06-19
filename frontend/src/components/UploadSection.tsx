import React, { useRef, useState } from 'react';
import axios from 'axios';
import { Upload, Loader2 } from 'lucide-react';
import { API_BASE_URL } from '../api';

interface UploadSectionProps {
  onUploadSuccess: (data: any) => void;
}

const UploadSection: React.FC<UploadSectionProps> = ({ onUploadSuccess }) => {
  const [isUploading, setIsUploading] = useState(false);
  const [isDragging, setIsDragging] = useState(false);
  const [uploadError, setUploadError] = useState<string | null>(null);
  const inputRef = useRef<HTMLInputElement>(null);

  const uploadFile = async (file: File) => {
    if (!file.type.startsWith('image/')) {
      setUploadError('Please upload an image file.');
      return;
    }
    setUploadError(null);
    setIsUploading(true);
    const formData = new FormData();
    formData.append('file', file);
    try {
      const response = await axios.post(`${API_BASE_URL}/api/upload`, formData);
      onUploadSuccess(response.data);
    } catch (error) {
      console.error('Upload failed:', error);
      const message = axios.isAxiosError(error)
        ? error.response?.data?.detail || error.message
        : 'Failed to upload image. Make sure the backend is running.';
      setUploadError(message);
    } finally {
      setIsUploading(false);
    }
  };

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (file) uploadFile(file);
  };

  const handleDragOver = (e: React.DragEvent<HTMLDivElement>) => {
    e.preventDefault();
    e.stopPropagation();
    setIsDragging(true);
  };

  const handleDragLeave = (e: React.DragEvent<HTMLDivElement>) => {
    e.preventDefault();
    e.stopPropagation();
    setIsDragging(false);
  };

  const handleDrop = (e: React.DragEvent<HTMLDivElement>) => {
    e.preventDefault();
    e.stopPropagation();
    setIsDragging(false);
    const file = e.dataTransfer.files?.[0];
    if (file) uploadFile(file);
  };

  return (
    <div
      onDragOver={handleDragOver}
      onDragLeave={handleDragLeave}
      onDrop={handleDrop}
      onClick={() => !isUploading && inputRef.current?.click()}
      className={`flex flex-col items-center justify-center space-y-8 max-w-md w-full p-12 border-2 border-dashed rounded-3xl backdrop-blur-sm cursor-pointer transition-all duration-300 ${
        isDragging
          ? 'border-luxury-gold bg-luxury-gold/10 scale-[1.02]'
          : 'border-white/20 bg-white/5 hover:border-white/40 hover:bg-white/8'
      } ${isUploading ? 'cursor-wait' : ''}`}
    >
      <div className={`w-24 h-24 rounded-full flex items-center justify-center transition-colors ${
        isDragging ? 'bg-luxury-gold/30 text-luxury-gold' : 'bg-luxury-gold/20 text-luxury-gold'
      }`}>
        {isUploading ? <Loader2 size={40} className="animate-spin" /> : <Upload size={40} />}
      </div>

      <div className="text-center">
        <h1 className="text-3xl font-bold mb-2">AI Ecommerce DrillDown</h1>
        <p className="text-gray-400">
          {isDragging
            ? 'Drop your image here'
            : 'Drag & drop or click to upload a celebrity photo, runway image, or streetwear shot.'}
        </p>
      </div>

      {uploadError && (
        <div className="w-full rounded-md border border-red-400/50 bg-red-950/70 px-4 py-2 text-sm text-red-100 text-center">
          {uploadError}
        </div>
      )}

      <span className="pointer-events-none bg-luxury-gold hover:bg-luxury-gold/80 text-black font-bold py-4 px-8 rounded-full transition-all">
        {isUploading ? 'Uploading...' : 'Choose Image'}
      </span>

      <input
        ref={inputRef}
        type="file"
        className="hidden"
        onChange={handleFileChange}
        accept="image/*"
        disabled={isUploading}
      />

      <div className="text-[10px] uppercase tracking-widest text-gray-600">
        Powered by Qwen2.5-VL, SerpApi & FashionCLIP
      </div>
    </div>
  );
};

export default UploadSection;
