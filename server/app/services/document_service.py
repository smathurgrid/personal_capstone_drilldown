import os
import fitz  # PyMuPDF
import hashlib
import json
from typing import Dict, Any, List

STATIC_DIR = "static"
DOCUMENTS_DIR = os.path.join(STATIC_DIR, "documents")

class DocumentService:
    @staticmethod
    def get_hash(content: bytes) -> str:
        return hashlib.sha256(content).hexdigest()

    @classmethod
    async def process_pdf(cls, file_name: str, file_content: bytes) -> Dict[str, Any]:
        """
        Processes an uploaded PDF:
        1. Computes document hash to use as document_id (enables caching).
        2. Saves PDF pages as PNG images in static/documents/{document_id}/
        3. Generates metadata.json mapping pages to image URLs.
        """
        # Ensure directories exist
        os.makedirs(DOCUMENTS_DIR, exist_ok=True)
        
        document_id = cls.get_hash(file_content)
        doc_dir = os.path.join(DOCUMENTS_DIR, document_id)
        os.makedirs(doc_dir, exist_ok=True)

        pdf_path = os.path.join(doc_dir, "document.pdf")
        metadata_path = os.path.join(doc_dir, "metadata.json")

        # If already cached, return existing metadata
        if os.path.exists(metadata_path):
            try:
                with open(metadata_path, "r") as f:
                    return json.load(f)
            except Exception as e:
                print(f"Error reading cached metadata: {e}. Re-processing...")

        # Save the uploaded PDF file
        with open(pdf_path, "wb") as f:
            f.write(file_content)

        # Open and extract PDF pages
        doc = fitz.open(pdf_path)
        page_count = len(doc)
        pages_list: List[Dict[str, Any]] = []

        # We will restrict extraction to the first 50 pages for safety and performance
        max_pages = min(page_count, 50)

        for i in range(max_pages):
            page_num = i + 1
            page = doc.load_page(i)
            # 150 DPI provides a perfect balance of text readability and image size
            pix = page.get_pixmap(dpi=150)
            page_filename = f"page_{page_num}.png"
            page_img_path = os.path.join(doc_dir, page_filename)
            pix.save(page_img_path)

            pages_list.append({
                "page_num": page_num,
                "imageUrl": f"/static/documents/{document_id}/{page_filename}",
                "pageId": f"doc_{document_id}_p{page_num}"
            })

        # Generate metadata dict
        metadata = {
            "id": document_id,
            "filename": file_name,
            "pageCount": page_count,
            "extractedCount": max_pages,
            "pages": pages_list
        }

        # Write metadata.json
        with open(metadata_path, "w") as f:
            json.dump(metadata, f, indent=2)

        return metadata

    @classmethod
    def get_document(cls, document_id: str) -> Dict[str, Any]:
        """Retrieves document pages metadata if document exists."""
        metadata_path = os.path.join(DOCUMENTS_DIR, document_id, "metadata.json")
        if not os.path.exists(metadata_path):
            raise FileNotFoundError(f"Document with ID {document_id} not found.")
        
        with open(metadata_path, "r") as f:
            return json.load(f)
