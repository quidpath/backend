# Requirements Update Summary

## Overview
All dependencies have been added to the requirements files to ensure complete functionality of the Tazama AI system, including the new PaddleOCR integration and data normalization pipeline.

## Files Updated

### 1. `requirements/base.txt`
Added the following dependencies:

#### Date and Time Utilities
- `python-dateutil` - For date parsing and relative date calculations (used in `EnhancedFinancialDataService.py` and `views.py`)

#### OCR and Image Processing (PaddleOCR)
- `paddlepaddle` - PaddlePaddle deep learning framework
- `paddleocr` - PaddleOCR toolkit for OCR extraction
- `pdf2image` - PDF to image conversion (requires poppler system dependency)

#### PDF Generation
- `weasyprint` - Professional PDF generation from HTML (used in `report_generator.py`)

#### Data Processing and ML
- `joblib` - Model serialization and parallel processing (used in `TazamaService.py`)
- `chardet` - Character encoding detection (used in `financial_data_pipeline.py` and `TazamaService.py`)

### 2. `requirements.txt` (Root Level)
Created a comprehensive root-level requirements file that includes all dependencies for easy installation.

### 3. `DEPLOYMENT_CHECKLIST.md`
Updated installation instructions to reference the requirements files.

## Complete Dependency List

### Core Framework
- Django>=3.2,<4.0
- djangorestframework
- django-cors-headers
- djangorestframework-simplejwt

### Database
- psycopg2-binary

### Server
- gunicorn
- whitenoise

### Machine Learning
- torch
- torchvision
- scikit-learn
- joblib

### Data Processing
- pandas
- numpy
- python-dateutil
- chardet

### File Processing
- openpyxl (Excel)
- xlrd (Excel)
- Pillow (Images)
- pdf2image (PDF conversion)
- fpdf2 (PDF generation)
- weasyprint (PDF generation from HTML)

### OCR
- paddlepaddle
- paddleocr

### String Matching
- fuzzywuzzy
- python-Levenshtein

### Visualization
- plotly
- matplotlib

### Utilities
- python-dotenv
- dj-database-url
- requests
- boto3>=1.34.0

## System Dependencies

### Required for pdf2image
- **Ubuntu/Debian**: `sudo apt-get install poppler-utils`
- **macOS**: `brew install poppler`
- **Windows**: Download from [poppler-windows](https://github.com/oschwartz10612/poppler-windows/releases)

## Installation

### Quick Install
```bash
# Install all dependencies
pip install -r requirements.txt

# Or use environment-specific files
pip install -r requirements/prod.txt  # Production
pip install -r requirements/dev.txt  # Development
```

### Verify Installation
```python
# Test PaddleOCR
from paddleocr import PaddleOCR
ocr = PaddleOCR(use_angle_cls=True, lang='en')
print("✅ PaddleOCR installed successfully")

# Test dateutil
from dateutil.relativedelta import relativedelta
print("✅ python-dateutil installed successfully")

# Test WeasyPrint
try:
    from weasyprint import HTML, CSS
    print("✅ WeasyPrint installed successfully")
except ImportError:
    print("⚠️ WeasyPrint not installed (optional)")

# Test chardet
import chardet
print("✅ chardet installed successfully")

# Test joblib
import joblib
print("✅ joblib installed successfully")
```

## Notes

1. **PaddleOCR**: First run will download model files automatically (~100MB)
2. **WeasyPrint**: Optional but recommended for professional PDF reports
3. **poppler**: System dependency required for PDF processing - must be installed separately
4. **GPU Support**: For GPU acceleration with PaddleOCR, use `paddlepaddle-gpu` instead of `paddlepaddle`

## Version Compatibility

All packages are compatible with Python 3.8+ and Django 3.2-4.0.

## Troubleshooting

### PaddleOCR Installation Issues
```bash
# If installation fails, try:
pip install paddlepaddle -i https://pypi.tuna.tsinghua.edu.cn/simple
pip install paddleocr -i https://pypi.tuna.tsinghua.edu.cn/simple
```

### WeasyPrint Installation Issues
```bash
# On Ubuntu/Debian, may need:
sudo apt-get install python3-cffi python3-brotli libpango-1.0-0 libpangoft2-1.0-0

# On macOS:
brew install pango
```

### pdf2image Issues
Ensure poppler is installed and accessible in PATH.





