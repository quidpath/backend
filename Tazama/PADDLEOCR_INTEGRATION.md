# PaddleOCR Integration for Tazama AI

## Overview

PaddleOCR has been integrated into the Tazama AI data extraction pipeline to improve accuracy, especially for:
- Scanned financial documents (images)
- PDF files
- Documents where standard Excel/CSV parsing fails

## Architecture

### Components

1. **PaddleOCRExtractor** (`Tazama/Services/PaddleOCRExtractor.py`)
   - Handles OCR extraction from images and PDFs
   - Parses extracted text into structured financial data
   - Uses the DataNormalizationPipeline to calculate missing values

2. **IntelligentDataExtractor Integration**
   - PaddleOCR is used as:
     - **Primary method** for images (PNG, JPG, BMP, TIFF) and PDFs
     - **Fallback method** when standard Excel/CSV parsing fails
     - **Strategy 5** in the multi-strategy extraction approach

### Extraction Flow

```
File Upload
    ↓
Try Standard Loading (Excel/CSV)
    ↓ (if fails)
Try PaddleOCR
    ↓
Extract Text with OCR
    ↓
Parse Financial Data
    ↓
Normalize & Calculate Missing Values
    ↓
Return Structured Data
```

## Installation

### Required Packages

```bash
# Core OCR
pip install paddlepaddle paddleocr

# Image processing
pip install Pillow

# PDF processing
pip install pdf2image

# System dependency for pdf2image (choose based on OS)
# Ubuntu/Debian:
sudo apt-get install poppler-utils

# macOS:
brew install poppler

# Windows:
# Download from: https://github.com/oschwartz10612/poppler-windows/releases
```

### Verification

```python
from Tazama.Services.PaddleOCRExtractor import PaddleOCRExtractor

extractor = PaddleOCRExtractor()
print("PaddleOCR initialized successfully")
```

## Usage

### Automatic Integration

PaddleOCR is automatically used when:
1. Uploading image files (PNG, JPG, BMP, TIFF)
2. Uploading PDF files
3. Standard Excel/CSV parsing fails

No code changes needed - it's integrated into the existing upload flow.

### Manual Usage

```python
from Tazama.Services.PaddleOCRExtractor import PaddleOCRExtractor

# Initialize extractor
extractor = PaddleOCRExtractor(use_angle_cls=True, lang='en')

# Extract from file
result = extractor.extract_from_file('path/to/document.pdf')

if result['success']:
    normalized_data = result['normalized_data']
    print(f"Revenue: {normalized_data['total_revenue']}")
    print(f"Net Income: {normalized_data['net_income']}")
else:
    print(f"Error: {result['error']}")

# Or get as DataFrame
df = extractor.extract_to_dataframe('path/to/document.pdf')
```

## Features

### 1. Multi-Format Support
- **Images**: PNG, JPG, JPEG, BMP, TIFF
- **PDFs**: Multi-page PDF support
- **Excel/CSV**: Fallback when standard parsing fails

### 2. Intelligent Text Parsing
- Pattern matching for financial metrics:
  - Total Revenue
  - Cost of Revenue / COGS
  - Gross Profit
  - Operating Expenses
  - Operating Income
  - Net Income
  - Interest Income/Expense
  - Tax Expense

### 3. Table Structure Recognition
- Detects Section/Item/Amount table structures
- Aggregates totals from detail lines
- Handles multi-column layouts

### 4. Data Normalization
- Automatically calculates missing values using financial formulas
- Validates data integrity
- Corrects common data issues

## How It Works

### Step 1: OCR Extraction
PaddleOCR extracts text from the document with:
- Bounding box coordinates
- Confidence scores
- Text content

### Step 2: Text Parsing
The extracted text is parsed using:
- **Regex patterns** for financial metrics
- **Table structure detection** for structured data
- **Position-based sorting** (top to bottom)

### Step 3: Data Normalization
The DataNormalizationPipeline:
- Calculates missing values (e.g., Gross Profit = Revenue - Cost)
- Validates data integrity
- Ensures all required fields are present

### Step 4: Structured Output
Returns normalized financial data ready for analysis.

## Example Output

```python
{
    'success': True,
    'extracted_text': 'Total Revenue: 10,850,000\nCost of Goods Sold: 3,640,000\n...',
    'normalized_data': {
        'total_revenue': 10850000.0,
        'cost_of_revenue': 3640000.0,
        'gross_profit': 7210000.0,
        'total_operating_expenses': 3715000.0,
        'operating_income': 3495000.0,
        'net_income': 2432500.0,
        ...
    },
    'confidence': 0.95
}
```

## Performance

- **Speed**: ~2-5 seconds per page (depending on image quality)
- **Accuracy**: High accuracy for clear, well-formatted documents
- **Memory**: Moderate (PaddleOCR models are loaded into memory)

## Limitations

1. **Image Quality**: Requires clear, readable images
2. **Language**: Currently optimized for English (can be extended)
3. **Complex Layouts**: Very complex table layouts may require manual review
4. **Handwritten Text**: Not optimized for handwritten documents

## Troubleshooting

### PaddleOCR Not Available
```
Error: PaddleOCR not available. Install with: pip install paddlepaddle paddleocr
```
**Solution**: Install PaddleOCR as shown in Installation section

### PDF Extraction Fails
```
Error: PDF extraction failed. Make sure poppler is installed
```
**Solution**: Install poppler system dependency (see Installation)

### Low Confidence Scores
- Check image quality (resolution, clarity)
- Ensure document is properly oriented
- Try preprocessing images (contrast, brightness)

## Future Enhancements

1. **Multi-language Support**: Extend to support multiple languages
2. **Layout Analysis**: Better table structure detection
3. **Handwriting Recognition**: Support for handwritten documents
4. **Batch Processing**: Process multiple documents in parallel
5. **Confidence Thresholds**: Configurable confidence levels

## References

- [PaddleOCR GitHub](https://github.com/PaddlePaddle/PaddleOCR)
- [PaddleOCR Documentation](https://paddleocr.readthedocs.io/)
- [PaddlePaddle Framework](https://www.paddlepaddle.org.cn/)





