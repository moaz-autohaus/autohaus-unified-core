"""
AutoHaus CIL — OCR & Text Extraction Engine
Phase 1, Step 4 & Phase 2, Step 6 Integration

Converts various file formats into plain text for the Extraction Engine.
"""

import os
import logging
import json
from typing import Optional, Dict, Any

logger = logging.getLogger("autohaus.ocr_engine")

async def extract_text_from_file(file_path: str, detected_format: str) -> Optional[str]:
    """
    Dispatcher for text extraction based on format.
    """
    if detected_format == "TEXT_PDF":
        return _extract_from_text_pdf(file_path)
    
    elif detected_format in ("SCANNED_PDF", "IMAGE"):
        return await _extract_via_gemini_vision(file_path)
    
    elif detected_format == "TEXT_FILE":
        return _extract_from_plain_text(file_path)
    
    elif detected_format == "WORD_DOC":
        return _extract_from_docx(file_path)
    
    else:
        logger.warning(f"[OCR] Unsupported format for direct text extraction: {detected_format}")
        return None


def _extract_from_text_pdf(file_path: str) -> Optional[str]:
    """Extract text from a searchable PDF using PyMuPDF."""
    try:
        import fitz
        doc = fitz.open(file_path)
        text = ""
        for page in doc:
            text += page.get_text()
        doc.close()
        return text.strip()
    except Exception as e:
        logger.error(f"[OCR] PyMuPDF extraction failed: {e}")
        return None


async def _extract_via_gemini_vision(file_path: str) -> Optional[str]:
    """Uses Gemini Flash Vision to perform OCR on images or scanned PDFs."""
    try:
        import google.generativeai as genai
        
        api_key = os.environ.get("GEMINI_API_KEY")
        if not api_key:
            logger.error("[OCR] No GEMINI_API_KEY for Vision OCR.")
            return None
            
        genai.configure(api_key=api_key)
        model = genai.GenerativeModel("gemini-1.5-flash")
        
        # Determine if PDF or Image
        mime_type = "application/pdf" if file_path.lower().endswith(".pdf") else "image/jpeg"
        
        # Upload to Gemini File API (Optimized for large files/PDFs)
        # Note: For simple images, we could just send the bytes. 
        # But for PDFs, the File API is better.
        
        # For MVP, let's try direct bytes if it's an image
        if mime_type == "image/jpeg":
            with open(file_path, "rb") as f:
                img_data = f.read()
            
            prompt = "You are an OCR engine. Extract ALL text from this image as accurately as possible. Output ONLY the text content, no commentary."
            response = model.generate_content([prompt, {"mime_type": "image/jpeg", "data": img_data}])
            return response.text.strip()
        
        # For PDF, use the File API
        myfile = genai.upload_file(file_path, mime_type=mime_type)
        prompt = "You are an OCR engine. Extract ALL text from this document as accurately as possible. Output ONLY the text content, no commentary."
        response = model.generate_content([prompt, myfile])
        
        # Cleanup
        genai.delete_file(myfile.name)
        
        return response.text.strip()
        
    except Exception as e:
        logger.error(f"[OCR] Gemini Vision extraction failed: {e}")
        return None


def _extract_from_plain_text(file_path: str) -> Optional[str]:
    """Read plain text files."""
    try:
        with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
            return f.read().strip()
    except Exception as e:
        logger.error(f"[OCR] Plain text read failed: {e}")
        return None


def _extract_from_docx(file_path: str) -> Optional[str]:
    """Extract text from Word documents."""
    try:
        import docx
        doc = docx.Document(file_path)
        return "\n".join([p.text for p in doc.paragraphs]).strip()
    except Exception as e:
        logger.error(f"[OCR] Docx extraction failed: {e}")
        return None
