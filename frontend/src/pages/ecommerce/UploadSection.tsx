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
    <div className="flex flex-col items-center justify-center space-y-8 max-w-lg w-full p-12 border-2 border-dashed border-[#2d3c5e] rounded-2xl bg-[rgba(19,29,61,0.3)] backdrop-blur-md">
      <div className="w-24 h-24 bg-[rgba(255,107,53,0.15)] rounded-full flex items-center justify-center text-[#ff6b35]">
        {isUploading ? <Loader2 size={40} className="animate-spin" /> : <Upload size={40} strokeWidth={1.5} />}
      </div>
      <div className="text-center">
        <h1 className="text-3xl font-bold mb-2 font-[Playfair Display] text-[#ff6b35]">AI Ecommerce DrillDown</h1>
        <p className="text-[#a8afc4]">Upload an outfit image to find matching products and drill deeper.</p>
      </div>
      <label className="cursor-pointer bg-gradient-to-r from-[#c5a059] to-[#d4af68] hover:from-[#d4af68] hover:to-[#c5a059] text-[#0a0a0a] font-bold py-3 px-8 rounded-lg transition-all shadow-lg hover:shadow-xl">
        {isUploading ? "Uploading…" : "Choose Image"}
        <input type="file" className="hidden" onChange={handleFileChange} accept="image/*" disabled={isUploading} />
      </label>
      <p className="text-[#7a81a0] text-sm">PNG, JPG, JPEG · Up to 50MB</p>
    </div>
  );
}
