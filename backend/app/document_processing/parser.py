import os
import fitz  # PyMuPDF
import pdfplumber
from docx import Document as DocxDocument
from pptx import Presentation as PptxPresentation
from PIL import Image


class DocumentParser:
    """
    Core parsing engine supporting multiple formats (PDF, DOCX, PPTX, Images).
    """

    def parse_pdf(self, file_path: str) -> list[dict]:
        """
        Extract text from PDF pages using PyMuPDF (fast path) 
        and pdfplumber (table/fallback path).
        """
        pages_content = []
        
        # Open PDF via PyMuPDF
        with fitz.open(file_path) as doc:
            for page_idx, page in enumerate(doc):
                text = page.get_text()
                
                # If text extraction is completely empty, it might be a scanned PDF page.
                # We save placeholders or layout metrics.
                if not text.strip():
                    text = "[Scanned Page / Unparsed Content]"
                
                pages_content.append({
                    "page": page_idx + 1,
                    "text": text,
                    "tables": []
                })
        
        # Use pdfplumber to extract table objects and append them to pages
        try:
            with pdfplumber.open(file_path) as pdf:
                for idx, page in enumerate(pdf.pages):
                    if idx < len(pages_content):
                        tables = page.extract_tables()
                        if tables:
                            pages_content[idx]["tables"] = tables
        except Exception as e:
            # Table extraction failure shouldn't crash the text parsing
            print(f"Warning during PDF table extraction: {e}")

        return pages_content

    def parse_docx(self, file_path: str) -> list[dict]:
        """
        Extract structural paragraphs from MS Word files.
        """
        doc = DocxDocument(file_path)
        paragraphs = []
        for p_idx, para in enumerate(doc.paragraphs):
            if para.text.strip():
                paragraphs.append(para.text)
                
        # Group docx contents by logical page approximations (e.g. every 10 paragraphs)
        pages_content = []
        temp_text = []
        page_num = 1
        
        for idx, text in enumerate(paragraphs):
            temp_text.append(text)
            if (idx + 1) % 10 == 0 or (idx + 1) == len(paragraphs):
                pages_content.append({
                    "page": page_num,
                    "text": "\n".join(temp_text),
                    "tables": []
                })
                temp_text = []
                page_num += 1
                
        return pages_content

    def parse_pptx(self, file_path: str) -> list[dict]:
        """
        Extract text coordinates and slide text from PowerPoint presentation files.
        """
        prs = PptxPresentation(file_path)
        pages_content = []
        
        for slide_idx, slide in enumerate(prs.slides):
            slide_text = []
            for shape in slide.shapes:
                if hasattr(shape, "text_frame") and shape.text_frame:
                    for paragraph in shape.text_frame.paragraphs:
                        if paragraph.text.strip():
                            slide_text.append(paragraph.text)
                            
            pages_content.append({
                "page": slide_idx + 1,
                "text": "\n".join(slide_text),
                "tables": []
            })
            
        return pages_content

    def parse_image(self, file_path: str) -> list[dict]:
        """
        OCR fallback check for image formats.
        Note: Supports Tesseract OCR if installed and configured,
        otherwise logs a placeholder.
        """
        # If pytesseract is installed and on system path, we run it.
        try:
            import pytesseract
            img = Image.open(file_path)
            text = pytesseract.image_to_string(img)
        except ImportError:
            text = "[OCR library pytesseract not installed. Local image parsing is disabled.]"
        except Exception as e:
            text = f"[OCR image parsing failed: {e}]"
            
        return [{
            "page": 1,
            "text": text,
            "tables": []
        }]

    def extract_text(self, file_path: str, file_type: str) -> list[dict]:
        """
        Route file path to matching format extractor based on file extension.
        """
        ftype = file_type.lower().strip(".")
        if ftype == "pdf":
            return self.parse_pdf(file_path)
        elif ftype in {"docx", "doc"}:
            return self.parse_docx(file_path)
        elif ftype in {"pptx", "ppt"}:
            return self.parse_pptx(file_path)
        elif ftype in {"png", "jpg", "jpeg"}:
            return self.parse_image(file_path)
        elif ftype == "zip":
            # ZIP extraction is handled at the archive service layer,
            # this routes to single files.
            raise ValueError("ZIP files must be extracted before parsing single files.")
        else:
            raise ValueError(f"No parsing handler registered for format: .{file_ext}")


# Singleton instance
document_parser = DocumentParser()
