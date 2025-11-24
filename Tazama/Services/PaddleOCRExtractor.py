# PaddleOCRExtractor.py - PaddleOCR-based Data Extraction
"""
PaddleOCR-based extractor for extracting financial data from images and PDFs.
Uses PaddleOCR for OCR and then parses the extracted text into structured financial data.
"""

import os
import re
import logging
from typing import Dict, List, Optional, Any, Tuple
import pandas as pd
import numpy as np

# Optional imports with fallbacks
try:
    from PIL import Image
    PIL_AVAILABLE = True
except ImportError:
    PIL_AVAILABLE = False
    logging.warning("PIL/Pillow not installed. Install with: pip install Pillow")

try:
    import pdf2image
    PDF2IMAGE_AVAILABLE = True
except ImportError:
    PDF2IMAGE_AVAILABLE = False
    logging.warning("pdf2image not installed. Install with: pip install pdf2image")

from io import BytesIO

# Try to import PaddleOCR, make it optional
try:
    from paddleocr import PaddleOCR
    PADDLEOCR_AVAILABLE = True
except ImportError:
    PADDLEOCR_AVAILABLE = False
    logging.warning("PaddleOCR not installed. Install with: pip install paddlepaddle paddleocr")

from Tazama.Services.DataNormalizationPipeline import DataNormalizationPipeline

logger = logging.getLogger(__name__)


class PaddleOCRExtractor:
    """
    Extract financial data from images and PDFs using PaddleOCR
    """
    
    def __init__(self, use_angle_cls=True, lang='en'):
        """
        Initialize PaddleOCR extractor
        
        Args:
            use_angle_cls: Whether to use angle classification
            lang: Language code ('en', 'ch', 'fr', etc.)
        """
        self.use_angle_cls = use_angle_cls
        self.lang = lang
        self.ocr = None
        self.normalization_pipeline = DataNormalizationPipeline()
        
        if PADDLEOCR_AVAILABLE:
            try:
                # Initialize PaddleOCR
                self.ocr = PaddleOCR(
                    use_angle_cls=use_angle_cls,
                    lang=lang,
                    show_log=False
                )
                logger.info("✅ PaddleOCR initialized successfully")
            except Exception as e:
                logger.error(f"Failed to initialize PaddleOCR: {e}")
                self.ocr = None
        else:
            logger.warning("⚠️ PaddleOCR not available. Install with: pip install paddlepaddle paddleocr")
    
    def extract_from_file(self, file_path: str) -> Dict[str, Any]:
        """
        Extract financial data from a file (image or PDF)
        
        Args:
            file_path: Path to the file
            
        Returns:
            Dictionary with extracted data
        """
        if not self.ocr:
            return {
                'success': False,
                'error': 'PaddleOCR not available. Please install: pip install paddlepaddle paddleocr'
            }
        
        try:
            file_ext = os.path.splitext(file_path)[1].lower()
            
            if file_ext in ['.pdf']:
                return self._extract_from_pdf(file_path)
            elif file_ext in ['.png', '.jpg', '.jpeg', '.bmp', '.tiff', '.tif']:
                return self._extract_from_image(file_path)
            else:
                return {
                    'success': False,
                    'error': f'Unsupported file format: {file_ext}'
                }
        except Exception as e:
            logger.error(f"Error extracting from file {file_path}: {e}", exc_info=True)
            return {
                'success': False,
                'error': str(e)
            }
    
    def _extract_from_pdf(self, pdf_path: str) -> Dict[str, Any]:
        """Extract text from PDF using PaddleOCR"""
        if not PDF2IMAGE_AVAILABLE:
            return {
                'success': False,
                'error': 'pdf2image not available. Install with: pip install pdf2image. Also install poppler system dependency.'
            }
        
        try:
            # Convert PDF to images
            images = pdf2image.convert_from_path(pdf_path)
            
            all_results = []
            for i, image in enumerate(images):
                logger.info(f"Processing PDF page {i+1}/{len(images)}")
                result = self.ocr.ocr(np.array(image), cls=self.use_angle_cls)
                if result and result[0]:
                    all_results.extend(result[0])
            
            return self._parse_ocr_results(all_results, source='pdf')
        except Exception as e:
            logger.error(f"Error extracting from PDF: {e}", exc_info=True)
            return {
                'success': False,
                'error': f'PDF extraction failed: {str(e)}. Make sure poppler is installed (system dependency).'
            }
    
    def _extract_from_image(self, image_path: str) -> Dict[str, Any]:
        """Extract text from image using PaddleOCR"""
        if not PIL_AVAILABLE:
            return {
                'success': False,
                'error': 'PIL/Pillow not available. Install with: pip install Pillow'
            }
        
        try:
            # Read image
            image = Image.open(image_path)
            image_array = np.array(image)
            
            # Run OCR
            result = self.ocr.ocr(image_array, cls=self.use_angle_cls)
            
            if not result or not result[0]:
                return {
                    'success': False,
                    'error': 'No text detected in image'
                }
            
            return self._parse_ocr_results(result[0], source='image')
        except Exception as e:
            logger.error(f"Error extracting from image: {e}", exc_info=True)
            return {
                'success': False,
                'error': f'Image extraction failed: {str(e)}'
            }
    
    def _parse_ocr_results(self, ocr_results: List, source: str = 'unknown') -> Dict[str, Any]:
        """
        Parse OCR results into structured financial data
        
        Args:
            ocr_results: List of OCR results from PaddleOCR
            source: Source type ('pdf', 'image', etc.)
            
        Returns:
            Dictionary with parsed financial data
        """
        try:
            # Extract all text with positions
            text_lines = []
            for line in ocr_results:
                if line and len(line) >= 2:
                    bbox = line[0]  # Bounding box
                    text_info = line[1]  # (text, confidence)
                    if isinstance(text_info, tuple) and len(text_info) >= 1:
                        text = text_info[0]
                        confidence = text_info[1] if len(text_info) > 1 else 1.0
                        # Calculate approximate y-position for sorting
                        y_avg = sum([point[1] for point in bbox]) / len(bbox) if bbox else 0
                        text_lines.append({
                            'text': text,
                            'confidence': confidence,
                            'y_position': y_avg,
                            'bbox': bbox
                        })
            
            # Sort by y-position (top to bottom)
            text_lines.sort(key=lambda x: x['y_position'])
            
            # Extract text content
            full_text = '\n'.join([line['text'] for line in text_lines])
            
            # Parse into structured data
            parsed_data = self._parse_financial_text(full_text, text_lines)
            
            # Normalize the data
            normalized = self.normalization_pipeline.normalize_and_calculate(parsed_data)
            
            return {
                'success': True,
                'extracted_text': full_text,
                'text_lines': text_lines,
                'parsed_data': parsed_data,
                'normalized_data': normalized,
                'source': source,
                'confidence': sum([line['confidence'] for line in text_lines]) / len(text_lines) if text_lines else 0.0
            }
        except Exception as e:
            logger.error(f"Error parsing OCR results: {e}", exc_info=True)
            return {
                'success': False,
                'error': f'Parsing failed: {str(e)}'
            }
    
    def _parse_financial_text(self, text: str, text_lines: List[Dict]) -> Dict[str, float]:
        """
        Parse financial text into structured data
        
        This method uses pattern matching to extract financial metrics from text
        """
        parsed = {
            'total_revenue': 0.0,
            'cost_of_revenue': 0.0,
            'gross_profit': 0.0,
            'total_operating_expenses': 0.0,
            'operating_income': 0.0,
            'net_income': 0.0,
            'interest_income': 0.0,
            'interest_expense': 0.0,
            'income_tax_expense': 0.0,
        }
        
        # Normalize text for matching
        text_lower = text.lower()
        
        # Financial patterns with variations
        patterns = {
            'total_revenue': [
                r'total\s+revenue[:\s]+([\d,]+\.?\d*)',
                r'revenue[:\s]+([\d,]+\.?\d*)',
                r'total\s+sales[:\s]+([\d,]+\.?\d*)',
                r'sales\s+revenue[:\s]+([\d,]+\.?\d*)',
            ],
            'cost_of_revenue': [
                r'cost\s+of\s+(?:goods\s+)?sold[:\s]+([\d,]+\.?\d*)',
                r'cost\s+of\s+revenue[:\s]+([\d,]+\.?\d*)',
                r'cogs[:\s]+([\d,]+\.?\d*)',
                r'cost\s+of\s+sales[:\s]+([\d,]+\.?\d*)',
            ],
            'gross_profit': [
                r'gross\s+profit[:\s]+([\d,]+\.?\d*)',
                r'gross\s+income[:\s]+([\d,]+\.?\d*)',
            ],
            'total_operating_expenses': [
                r'total\s+operating\s+expenses[:\s]+([\d,]+\.?\d*)',
                r'operating\s+expenses[:\s]+([\d,]+\.?\d*)',
                r'opex[:\s]+([\d,]+\.?\d*)',
            ],
            'operating_income': [
                r'operating\s+income[:\s]+([\d,]+\.?\d*)',
                r'operating\s+profit[:\s]+([\d,]+\.?\d*)',
            ],
            'net_income': [
                r'net\s+income[:\s]+([\d,]+\.?\d*)',
                r'net\s+profit[:\s]+([\d,]+\.?\d*)',
                r'profit\s+after\s+tax[:\s]+([\d,]+\.?\d*)',
            ],
            'interest_income': [
                r'interest\s+income[:\s]+([\d,]+\.?\d*)',
            ],
            'interest_expense': [
                r'interest\s+expense[:\s]+([\d,]+\.?\d*)',
            ],
            'income_tax_expense': [
                r'income\s+tax[:\s]+([\d,]+\.?\d*)',
                r'tax\s+expense[:\s]+([\d,]+\.?\d*)',
            ],
        }
        
        # Extract values using patterns
        for field, pattern_list in patterns.items():
            for pattern in pattern_list:
                matches = re.finditer(pattern, text_lower, re.IGNORECASE)
                for match in matches:
                    value_str = match.group(1).replace(',', '')
                    try:
                        value = float(value_str)
                        if value > parsed[field]:  # Take the largest value (likely the total)
                            parsed[field] = value
                    except ValueError:
                        continue
        
        # Try to parse table structure (Section/Item/Amount format)
        table_data = self._parse_table_structure(text_lines)
        if table_data:
            # Merge table data with pattern-matched data
            for key, value in table_data.items():
                if value > 0:
                    parsed[key] = value
        
        return parsed
    
    def _parse_table_structure(self, text_lines: List[Dict]) -> Dict[str, float]:
        """
        Parse table structure from OCR results
        Looks for Section/Item/Amount patterns
        """
        table_data = {}
        current_section = None
        
        # Section keywords
        section_keywords = {
            'revenue': ['revenue', 'sales', 'income'],
            'cost': ['cost of goods sold', 'cost of sales', 'cogs'],
            'expenses': ['operating expenses', 'expenses', 'opex'],
            'profit': ['gross profit', 'operating income', 'net income'],
        }
        
        for line in text_lines:
            text = line['text'].lower()
            
            # Detect section headers
            for section_type, keywords in section_keywords.items():
                if any(keyword in text for keyword in keywords) and 'total' in text:
                    current_section = section_type
                    # Try to extract amount from the same line
                    amount = self._extract_amount_from_text(line['text'])
                    if amount > 0:
                        if section_type == 'revenue':
                            table_data['total_revenue'] = amount
                        elif section_type == 'cost':
                            table_data['cost_of_revenue'] = amount
                        elif section_type == 'expenses':
                            table_data['total_operating_expenses'] = amount
                    break
            
            # If we're in a section, try to extract amounts
            if current_section:
                amount = self._extract_amount_from_text(line['text'])
                if amount > 0:
                    # Check if this is a total line
                    if 'total' in text:
                        if current_section == 'revenue':
                            table_data['total_revenue'] = amount
                        elif current_section == 'cost':
                            table_data['cost_of_revenue'] = amount
                        elif current_section == 'expenses':
                            table_data['total_operating_expenses'] = amount
                    else:
                        # Sum individual items
                        if current_section == 'expenses':
                            table_data['total_operating_expenses'] = table_data.get('total_operating_expenses', 0) + amount
        
        return table_data
    
    def _extract_amount_from_text(self, text: str) -> float:
        """Extract numeric amount from text"""
        # Remove currency symbols and extract numbers
        # Pattern: number with optional commas and decimal
        patterns = [
            r'([\d,]+\.?\d*)',  # Standard number
            r'\(([\d,]+\.?\d*)\)',  # Negative in parentheses
        ]
        
        for pattern in patterns:
            matches = re.findall(pattern, text.replace(',', ''))
            if matches:
                try:
                    # Take the largest number (likely the amount)
                    amounts = [float(m.replace(',', '')) for m in matches]
                    return max(amounts) if amounts else 0.0
                except ValueError:
                    continue
        
        return 0.0
    
    def extract_to_dataframe(self, file_path: str) -> Optional[pd.DataFrame]:
        """
        Extract data and convert to DataFrame format
        
        Args:
            file_path: Path to the file
            
        Returns:
            DataFrame with extracted data, or None if extraction fails
        """
        result = self.extract_from_file(file_path)
        
        if not result.get('success'):
            return None
        
        normalized_data = result.get('normalized_data', {})
        
        # Convert to DataFrame
        df_data = {
            'total_revenue': [normalized_data.get('total_revenue', 0)],
            'cost_of_revenue': [normalized_data.get('cost_of_revenue', 0)],
            'gross_profit': [normalized_data.get('gross_profit', 0)],
            'total_operating_expenses': [normalized_data.get('total_operating_expenses', 0)],
            'operating_income': [normalized_data.get('operating_income', 0)],
            'net_income': [normalized_data.get('net_income', 0)],
            'interest_income': [normalized_data.get('interest_income', 0)],
            'interest_expense': [normalized_data.get('interest_expense', 0)],
            'income_tax_expense': [normalized_data.get('income_tax_expense', 0)],
        }
        
        return pd.DataFrame(df_data)

