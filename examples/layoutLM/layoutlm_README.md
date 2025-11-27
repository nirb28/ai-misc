# LayoutLM Bank Check Processing Example

This example demonstrates how to use Microsoft's LayoutLM (Layout Language Model) to process bank check images and extract structured information.

## Overview

LayoutLM is a multimodal pre-training model that combines:
- **Text**: OCR-extracted words
- **Layout**: Spatial bounding box coordinates
- **Image**: Visual features from the document

This makes it ideal for document understanding tasks like check processing, invoice extraction, form understanding, and more.

## Features

This example shows how to:
1. Create synthetic bank check images for testing
2. Extract text and bounding boxes using Tesseract OCR
3. Process checks with LayoutLM to understand document structure
4. Extract key fields: check number, date, amount, payee, account number
5. Visualize results with annotated images
6. Save structured data to JSON

## Installation

### Prerequisites

1. **Python 3.8+**

2. **Tesseract OCR** (required for text extraction):
   - **Windows**: Download from [UB-Mannheim/tesseract](https://github.com/UB-Mannheim/tesseract/wiki)
   - **Linux**: `sudo apt-get install tesseract-ocr`
   - **Mac**: `brew install tesseract`

3. **Python Dependencies**:
```bash
pip install transformers torch pillow pytesseract requests
```

Or use the requirements file:
```bash
pip install -r layoutlm_requirements.txt
```

## Usage

### Basic Usage

```bash
python layoutlm.py
```

This will:
1. Create 3 sample check images in `sample_checks/` directory
2. Process each check with LayoutLM
3. Extract structured information
4. Save annotated images with extracted data
5. Save results to `sample_checks/check_processing_results.json`

### Using Your Own Check Images

```python
from layoutlm import CheckProcessor

# Initialize processor
processor = CheckProcessor()

# Process a single check
check_info = processor.process_check("path/to/your/check.png")

# Print extracted information
for field, value in check_info.items():
    if value and field != "all_text":
        print(f"{field}: {value}")

# Visualize results
processor.visualize_results("path/to/your/check.png", check_info, "output_annotated.png")
```

## Extracted Fields

The example extracts the following fields from checks:
- **check_number**: Check number (typically 4 digits)
- **date**: Issue date (MM/DD/YYYY format)
- **amount_numeric**: Dollar amount in numeric form ($XXX.XX)
- **amount_written**: Amount written in words
- **payee**: Name of the payee ("Pay to the order of")
- **account_number**: Bank account number (from MICR line)
- **routing_number**: Bank routing number (from MICR line)
- **bank_name**: Name of the issuing bank

## Output

### Console Output
```
================================================================================
LayoutLM Bank Check Processing Example
================================================================================

1. Creating sample check images...
Created: sample_checks/sample_check_1.png
Created: sample_checks/sample_check_2.png
Created: sample_checks/sample_check_3.png

2. Processing checks with LayoutLM...

Processing check: sample_checks/sample_check_1.png
Extracted 45 words from check

Extracted Information:
----------------------------------------
  check_number: 1001
  date: 11/22/2024
  amount_numeric: $100.00
  payee: John Doe #1
  amount_written: One hundred and 00/100
...
```

### JSON Output
```json
[
  {
    "check_number": "1001",
    "date": "11/22/2024",
    "amount_numeric": "$100.00",
    "amount_written": "One hundred and 00/100",
    "payee": "John Doe #1",
    "account_number": "9876543211",
    "routing_number": "123456789",
    "all_text": "SAMPLE BANK 123 Main Street..."
  }
]
```

## Model Information

### Available LayoutLM Models

1. **LayoutLM v1** (`microsoft/layoutlm-base-uncased`)
   - Original model, text + layout only
   - 113M parameters

2. **LayoutLMv2** (`microsoft/layoutlmv2-base-uncased`)
   - Adds visual features from document images
   - Better performance on complex layouts

3. **LayoutLMv3** (`microsoft/layoutlmv3-base`) - **Used in this example**
   - Unified text-image multimodal pre-training
   - Best performance, recommended for production
   - Also available: `microsoft/layoutlmv3-large`

### Changing Models

```python
# Use LayoutLMv2
processor = CheckProcessor(model_name="microsoft/layoutlmv2-base-uncased")

# Use LayoutLMv3 Large
processor = CheckProcessor(model_name="microsoft/layoutlmv3-large")
```

## Fine-Tuning for Production

This example uses heuristic rules for field extraction. For production use, you should:

1. **Collect labeled check dataset** with bounding boxes for each field
2. **Fine-tune LayoutLM** on your specific check format
3. **Use available datasets**:
   - [SSBI Dataset](https://github.com/dfki-av/bank-check-security) - 4,360 annotated checks
   - [IDRBT Cheque Dataset](https://datasetninja.com/cheque-detection) - 112 Indian bank checks
   - [BCSD Dataset](https://paperswithcode.com/dataset/bcsd) - Bank check segmentation

### Fine-Tuning Example

```python
from transformers import LayoutLMv3ForTokenClassification, Trainer, TrainingArguments

# Define your labels
id2label = {
    0: "O",
    1: "CHECK_NUMBER",
    2: "DATE",
    3: "AMOUNT_NUMERIC",
    4: "AMOUNT_WRITTEN",
    5: "PAYEE",
    6: "ACCOUNT_NUMBER",
    7: "SIGNATURE",
    8: "BANK_NAME",
    9: "ROUTING_NUMBER"
}

# Load model
model = LayoutLMv3ForTokenClassification.from_pretrained(
    "microsoft/layoutlmv3-base",
    num_labels=len(id2label),
    id2label=id2label,
    label2id={v: k for k, v in id2label.items()}
)

# Set up training
training_args = TrainingArguments(
    output_dir="./layoutlm-check-finetuned",
    num_train_epochs=10,
    per_device_train_batch_size=4,
    learning_rate=5e-5,
    save_steps=500,
    evaluation_strategy="steps",
    eval_steps=500
)

# Train
trainer = Trainer(
    model=model,
    args=training_args,
    train_dataset=train_dataset,
    eval_dataset=eval_dataset
)

trainer.train()
```

## Use Cases

LayoutLM can be applied to various document understanding tasks:

- ✅ **Check Processing** (this example)
- ✅ **Invoice Extraction** - Extract vendor, amount, date, line items
- ✅ **Receipt Processing** - Parse receipts for expense tracking
- ✅ **Form Understanding** - Extract fields from tax forms, applications
- ✅ **ID Document Processing** - Parse driver's licenses, passports
- ✅ **Contract Analysis** - Extract key terms, dates, parties
- ✅ **Medical Records** - Parse structured medical forms

## Troubleshooting

### Tesseract Not Found
```
Error: pytesseract.pytesseract.TesseractNotFoundError
```
**Solution**: Install Tesseract OCR and add it to your PATH, or specify the path:
```python
import pytesseract
pytesseract.pytesseract.tesseract_cmd = r'C:\Program Files\Tesseract-OCR\tesseract.exe'
```

### CUDA Out of Memory
```
Error: RuntimeError: CUDA out of memory
```
**Solution**: Use CPU or reduce batch size:
```python
# Force CPU
import torch
device = torch.device("cpu")
model = model.to(device)
```

### Poor OCR Quality
**Solution**: Improve image quality:
- Increase resolution (300 DPI minimum)
- Enhance contrast
- Remove noise
- Use image preprocessing (deskewing, binarization)

## References

- [LayoutLM Paper](https://arxiv.org/abs/1912.13318)
- [LayoutLMv2 Paper](https://arxiv.org/abs/2012.14740)
- [LayoutLMv3 Paper](https://arxiv.org/abs/2204.08387)
- [HuggingFace LayoutLM](https://huggingface.co/docs/transformers/model_doc/layoutlm)
- [SSBI Check Dataset](https://github.com/dfki-av/bank-check-security)

## License

This example is provided for educational purposes. When processing real checks, ensure compliance with:
- Banking regulations (PCI DSS, etc.)
- Privacy laws (GDPR, CCPA, etc.)
- Data security requirements

## Contributing

Feel free to improve this example by:
- Adding more sophisticated extraction logic
- Supporting different check formats
- Adding confidence scores
- Implementing signature verification
- Adding fraud detection features
