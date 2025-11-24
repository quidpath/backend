# Tazama AI Deployment Checklist

## Python Dependencies

### Core Dependencies
- Django
- pandas
- numpy
- scikit-learn
- torch (PyTorch)
- openpyxl (for Excel files)
- xlrd (for older Excel files)

### Data Processing
- python-dateutil
- fuzzywuzzy
- python-Levenshtein

### OCR and Image Processing (NEW)
- paddlepaddle (PaddlePaddle framework)
- paddleocr (PaddleOCR toolkit)
- Pillow (PIL) - Image processing
- pdf2image - PDF to image conversion
- poppler - System dependency for pdf2image (install via system package manager)

### Installation Commands

**Recommended: Use requirements files**
```bash
# For production
pip install -r requirements/prod.txt

# For development
pip install -r requirements/dev.txt

# Or install all dependencies
pip install -r requirements.txt
```

**Manual Installation (if needed)**
```bash
# Core dependencies
pip install django pandas numpy scikit-learn torch openpyxl xlrd

# Data processing
pip install python-dateutil fuzzywuzzy python-Levenshtein chardet

# OCR and Image Processing
pip install paddlepaddle paddleocr Pillow pdf2image

# PDF Generation
pip install weasyprint fpdf2

# Machine Learning
pip install joblib

# System dependency for pdf2image (Ubuntu/Debian)
sudo apt-get install poppler-utils

# System dependency for pdf2image (macOS)
brew install poppler

# System dependency for pdf2image (Windows)
# Download poppler from: https://github.com/oschwartz10612/poppler-windows/releases
# Add to PATH or place in project directory
```

### PaddleOCR Installation Notes

PaddleOCR requires:
1. PaddlePaddle framework
2. PaddleOCR package
3. Model files (downloaded automatically on first use)

For CPU-only systems:
```bash
pip install paddlepaddle paddleocr
```

For GPU systems (CUDA):
```bash
pip install paddlepaddle-gpu paddleocr
```

### Verification

After installation, verify PaddleOCR:
```python
from paddleocr import PaddleOCR
ocr = PaddleOCR(use_angle_cls=True, lang='en')
print("PaddleOCR initialized successfully")
```

