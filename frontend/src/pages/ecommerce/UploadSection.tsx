import { useState } from "react";
import { Upload, Loader2 } from "lucide-react";
import { uploadEcommerceImage } from "../../services/ecommerce-api";
import { getErrorMessage } from "../../utils/errors";

interface Props {
  onUploadSuccess: (data: { imageId: string; imageUrl: string }) => void;
}

export default function UploadSection({ onUploadSuccess }: Props) {
  const [isUploading, setIsUploading] = useState(false);

  const handleFileChange = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;
    setIsUploading(true);
    try {
      const data = await uploadEcommerceImage(file);
      onUploadSuccess(data);
    } catch (err) {
      alert(getErrorMessage(err, "Upload failed. Check backend and GOOGLE_API_KEY / Qdrant for identify."));
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
        <p className="text-gray-400">Upload an outfit image to find matching products.</p>
      </div>
      <label className="cursor-pointer bg-luxury-gold hover:bg-luxury-gold/80 text-black font-bold py-4 px-8 rounded-full transition-all">
        {isUploading ? "Uploading…" : "Choose Image"}
        <input type="file" className="hidden" onChange={handleFileChange} accept="image/*" disabled={isUploading} />
      </label>
    </div>
  );
}
