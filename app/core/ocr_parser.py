import pytesseract
from PIL import Image
import io
import pdf2image
import os
from typing import List, Optional
import logging

logger = logging.getLogger(__name__)

async def extract_text_from_image(file) -> str:
    """
    Extraire le texte d'une image ou PDF en utilisant OCR
    
    Args:
        file: Fichier UploadFile de FastAPI
        
    Returns:
        Texte extrait
    """
    try:
        # Lire le contenu du fichier
        file_content = await file.read()
        
        # Vérifier si c'est un PDF
        if file.filename.lower().endswith('.pdf'):
            return await _extract_text_from_pdf(file_content)
        else:
            return await _extract_text_from_image_bytes(file_content)
            
    except Exception as e:
        logger.error(f"Erreur OCR: {str(e)}")
        raise Exception(f"Erreur d'extraction OCR: {str(e)}")

async def _extract_text_from_pdf(pdf_bytes: bytes) -> str:
    """
    Extraire le texte d'un PDF
    """
    try:
        # Convertir le PDF en images
        images = pdf2image.convert_from_bytes(pdf_bytes)
        
        # Extraire le texte de chaque page
        all_text = []
        
        for i, image in enumerate(images):
            text = pytesseract.image_to_string(
                image,
                lang='fra+eng',  # Français + Anglais
                config='--psm 1 --oem 3'
            )
            all_text.append(f"[Page {i+1}]\n{text}")
        
        return "\n\n".join(all_text)
        
    except Exception as e:
        logger.error(f"Erreur d'extraction PDF: {str(e)}")
        raise

async def _extract_text_from_image_bytes(image_bytes: bytes) -> str:
    """
    Extraire le texte d'une image
    """
    try:
        # Ouvrir l'image
        image = Image.open(io.BytesIO(image_bytes))
        
        # Convertir en RGB si nécessaire
        if image.mode != 'RGB':
            image = image.convert('RGB')
        
        # Extraire le texte avec Tesseract
        text = pytesseract.image_to_string(
            image,
            lang='fra+eng',
            config='--psm 1 --oem 3'
        )
        
        return text
        
    except Exception as e:
        logger.error(f"Erreur d'extraction image: {str(e)}")
        raise

def preprocess_image(image: Image.Image) -> Image.Image:
    """
    Prétraiter une image pour améliorer l'OCR
    
    Args:
        image: Image PIL
        
    Returns:
        Image prétraitée
    """
    # Convertir en niveaux de gris
    image = image.convert('L')
    
    # Augmenter le contraste
    # (Vous pouvez ajouter plus de prétraitements ici)
    
    return image