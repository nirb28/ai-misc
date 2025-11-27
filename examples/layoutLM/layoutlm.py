"""
LayoutLM Example: Bank Check Processing

This example demonstrates how to use LayoutLM (Layout Language Model) to process
bank check images and extract structured information like:
- Check number
- Date
- Amount (numeric and written)
- Payee name
- Account number
- Signature location

LayoutLM is a multimodal pre-training model that combines text, layout, and image
information for document understanding tasks.

Requirements:
    pip install transformers torch pillow pytesseract requests
    
    Also install Tesseract OCR:
    - Windows: https://github.com/UB-Mannheim/tesseract/wiki
    - Linux: sudo apt-get install tesseract-ocr
    - Mac: brew install tesseract
"""

import os
import requests
from PIL import Image, ImageDraw, ImageFont
import torch
from transformers import LayoutLMv3Processor, LayoutLMv3ForTokenClassification
import pytesseract
from typing import List, Dict, Tuple
import json


class CheckProcessor:
    """Process bank check images using LayoutLM"""
    
    def __init__(self, model_name: str = "microsoft/layoutlmv3-base"):
        """
        Initialize the check processor with LayoutLM model
        
        Args:
            model_name: HuggingFace model name for LayoutLM
        """
        print(f"Loading LayoutLM model: {model_name}")
        self.processor = LayoutLMv3Processor.from_pretrained(model_name)
        self.processor.image_processor.apply_ocr = False
        self.model = LayoutLMv3ForTokenClassification.from_pretrained(model_name)
        self.model.eval()
        
        # Define check field labels (these would be trained for specific check layouts)
        self.label_map = {
            0: "O",  # Outside
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
        
    def download_sample_checks(self, output_dir: str = "sample_checks") -> List[str]:
        """
        Download sample check images for demonstration
        
        Args:
            output_dir: Directory to save sample checks
            
        Returns:
            List of paths to downloaded check images
        """
        os.makedirs(output_dir, exist_ok=True)
        
        # Sample check image URLs (public domain or creative commons)
        sample_urls = [
            # These are placeholder URLs - in practice, you'd use real sample check images
            "https://raw.githubusercontent.com/tesseract-ocr/tessdata/main/doc/sample_check.png",
        ]
        
        # For this example, we'll create synthetic check images
        print("Creating sample check images...")
        check_paths = []
        
        for i in range(3):
            check_path = os.path.join(output_dir, f"sample_check_{i+1}.png")
            self._create_sample_check(check_path, i+1)
            check_paths.append(check_path)
            print(f"Created: {check_path}")
            
        return check_paths
    
    def _create_sample_check(self, output_path: str, check_num: int):
        """Create a synthetic sample check for demonstration"""
        # Create a blank check image
        width, height = 800, 350
        img = Image.new('RGB', (width, height), color='white')
        draw = ImageDraw.Draw(img)
        
        # Try to use a nice font, fallback to default
        try:
            font_large = ImageFont.truetype("arial.ttf", 16)
            font_medium = ImageFont.truetype("arial.ttf", 14)
            font_small = ImageFont.truetype("arial.ttf", 12)
        except:
            font_large = ImageFont.load_default()
            font_medium = ImageFont.load_default()
            font_small = ImageFont.load_default()
        
        # Draw check border
        draw.rectangle([10, 10, width-10, height-10], outline='black', width=2)
        
        # Bank name and logo area
        draw.text((30, 30), "SAMPLE BANK", fill='blue', font=font_large)
        draw.text((30, 55), "123 Main Street, City, ST 12345", fill='black', font=font_small)
        
        # Check number (top right)
        draw.text((width-150, 30), f"Check #: {1000 + check_num}", fill='black', font=font_medium)
        
        # Date field
        draw.text((width-200, 80), f"Date: 11/22/202{3+check_num}", fill='black', font=font_medium)
        
        # Pay to the order of
        draw.text((30, 120), "Pay to the", fill='black', font=font_small)
        draw.text((30, 140), "order of:", fill='black', font=font_small)
        draw.text((120, 135), f"John Doe #{check_num}", fill='black', font=font_medium)
        draw.line([(120, 155), (width-150, 155)], fill='black', width=1)
        
        # Amount box
        draw.rectangle([width-140, 125, width-30, 155], outline='black', width=2)
        draw.text((width-130, 133), f"${100 * check_num}.00", fill='black', font=font_medium)
        
        # Amount in words
        amounts = ["One hundred", "Two hundred", "Three hundred"]
        draw.text((30, 180), f"{amounts[check_num-1]} and 00/100", fill='black', font=font_medium)
        draw.line([(30, 200), (width-30, 200)], fill='black', width=1)
        draw.text((width-100, 185), "Dollars", fill='black', font=font_small)
        
        # Bank info at bottom
        draw.text((30, 250), "SAMPLE BANK", fill='black', font=font_small)
        draw.text((30, 270), "Memo: _______________", fill='black', font=font_small)
        
        # Routing and account numbers (MICR line)
        draw.text((30, 310), f"⑈123456789⑈ ⑆987654321{check_num}⑆ {1000+check_num}", 
                 fill='black', font=font_small)
        
        # Signature line
        draw.line([(width-250, 280), (width-30, 280)], fill='black', width=1)
        draw.text((width-200, 285), "Authorized Signature", fill='gray', font=font_small)
        
        img.save(output_path)
    
    def extract_text_and_boxes(self, image_path: str) -> Tuple[List[str], List[List[int]]]:
        """
        Extract text and bounding boxes using OCR
        
        Args:
            image_path: Path to check image
            
        Returns:
            Tuple of (words, boxes) where boxes are [x0, y0, x1, y1]
        """
        image = Image.open(image_path).convert("RGB")
        width, height = image.size
        
        # Use Tesseract to get word-level OCR with bounding boxes
        ocr_data = pytesseract.image_to_data(image, output_type=pytesseract.Output.DICT)
        
        words = []
        boxes = []
        
        for i in range(len(ocr_data['text'])):
            if int(ocr_data['conf'][i]) > 0:  # Filter out low confidence
                word = ocr_data['text'][i].strip()
                if word:
                    words.append(word)
                    
                    # Normalize coordinates to 0-1000 scale (LayoutLM expects this)
                    x0 = int((ocr_data['left'][i] / width) * 1000)
                    y0 = int((ocr_data['top'][i] / height) * 1000)
                    x1 = int(((ocr_data['left'][i] + ocr_data['width'][i]) / width) * 1000)
                    y1 = int(((ocr_data['top'][i] + ocr_data['height'][i]) / height) * 1000)
                    
                    boxes.append([x0, y0, x1, y1])
        
        return words, boxes
    
    def process_check(self, image_path: str) -> Dict:
        """
        Process a check image and extract structured information
        
        Args:
            image_path: Path to check image
            
        Returns:
            Dictionary with extracted check information
        """
        print(f"\nProcessing check: {image_path}")
        
        # Load image
        image = Image.open(image_path).convert("RGB")
        
        # Extract text and bounding boxes
        words, boxes = self.extract_text_and_boxes(image_path)
        
        print(f"Extracted {len(words)} words from check")
        
        # Prepare inputs for LayoutLM
        encoding = self.processor(
            image,
            words,
            boxes=boxes,
            return_tensors="pt",
            padding="max_length",
            truncation=True
        )
        
        # Run inference
        with torch.no_grad():
            outputs = self.model(**encoding)
            predictions = outputs.logits.argmax(-1).squeeze().tolist()
        
        # Map predictions back to words
        # Note: LayoutLM uses subword tokenization, so we need to align
        word_ids = encoding.word_ids()
        
        # Extract structured information
        check_info = {
            "check_number": [],
            "date": [],
            "amount_numeric": [],
            "amount_written": [],
            "payee": [],
            "account_number": [],
            "bank_name": [],
            "routing_number": [],
            "all_text": " ".join(words)
        }
        
        # For demonstration, we'll use simple heuristics since we don't have a trained model
        # In practice, you'd use a fine-tuned LayoutLM model
        check_info.update(self._extract_check_fields_heuristic(words, boxes))
        
        return check_info
    
    def _extract_check_fields_heuristic(self, words: List[str], boxes: List[List[int]]) -> Dict:
        """
        Extract check fields using heuristic rules (for demonstration)
        In practice, use a fine-tuned LayoutLM model
        """
        result = {
            "check_number": None,
            "date": None,
            "amount_numeric": None,
            "amount_written": None,
            "payee": None,
            "account_number": None,
            "routing_number": None
        }
        
        # Simple pattern matching
        for i, word in enumerate(words):
            # Check number (usually after "Check #" or just a 4-digit number in top right)
            if word.startswith("#") or (word.isdigit() and len(word) == 4 and i < 10):
                if not result["check_number"]:
                    result["check_number"] = word.replace("#", "").replace(":", "")
            
            # Date (MM/DD/YYYY pattern)
            if "/" in word and len(word) >= 8:
                if not result["date"]:
                    result["date"] = word
            
            # Amount (starts with $)
            if word.startswith("$"):
                if not result["amount_numeric"]:
                    result["amount_numeric"] = word
            
            # Payee (after "order of:")
            if i > 0 and words[i-1].lower() == "of:" and not result["payee"]:
                payee_words = []
                for j in range(i, min(i+5, len(words))):
                    if not words[j].startswith("$"):
                        payee_words.append(words[j])
                    else:
                        break
                result["payee"] = " ".join(payee_words)
            
            # Amount in words (hundred, thousand, etc.)
            if word.lower() in ["hundred", "thousand", "million"] and not result["amount_written"]:
                amount_words = []
                for j in range(max(0, i-3), min(i+3, len(words))):
                    amount_words.append(words[j])
                result["amount_written"] = " ".join(amount_words)
        
        return result
    
    def visualize_results(self, image_path: str, check_info: Dict, output_path: str = None):
        """
        Visualize extracted information on the check image
        
        Args:
            image_path: Path to original check image
            check_info: Extracted check information
            output_path: Path to save annotated image (optional)
        """
        image = Image.open(image_path).convert("RGB")
        draw = ImageDraw.Draw(image)
        
        try:
            font = ImageFont.truetype("arial.ttf", 12)
        except:
            font = ImageFont.load_default()
        
        # Draw extracted information
        y_offset = 10
        for field, value in check_info.items():
            if value and field != "all_text":
                text = f"{field}: {value}"
                draw.text((10, y_offset), text, fill='red', font=font)
                y_offset += 20
        
        if output_path:
            image.save(output_path)
            print(f"Saved annotated image to: {output_path}")
        else:
            image.show()


def main():
    """Main demonstration function"""
    print("=" * 80)
    print("LayoutLM Bank Check Processing Example")
    print("=" * 80)
    
    # Initialize processor
    processor = CheckProcessor()
    
    # Download/create sample checks
    print("\n1. Creating sample check images...")
    check_paths = processor.download_sample_checks()
    
    # Process each check
    print("\n2. Processing checks with LayoutLM...")
    results = []
    
    for check_path in check_paths:
        check_info = processor.process_check(check_path)
        results.append(check_info)
        
        # Print results
        print("\nExtracted Information:")
        print("-" * 40)
        for field, value in check_info.items():
            if field != "all_text" and value:
                print(f"  {field}: {value}")
        
        # Visualize results
        output_path = check_path.replace(".png", "_annotated.png")
        processor.visualize_results(check_path, check_info, output_path)
    
    # Save results to JSON
    output_json = "sample_checks/check_processing_results.json"
    with open(output_json, 'w') as f:
        json.dump(results, f, indent=2)
    print(f"\n3. Saved results to: {output_json}")
    
    print("\n" + "=" * 80)
    print("Processing Complete!")
    print("=" * 80)
    print("\nNote: This example uses heuristic extraction for demonstration.")
    print("For production use, fine-tune LayoutLM on labeled check datasets like:")
    print("  - SSBI Dataset: https://github.com/dfki-av/bank-check-security")
    print("  - IDRBT Cheque Dataset: https://datasetninja.com/cheque-detection")
    print("\nLayoutLM models available:")
    print("  - microsoft/layoutlm-base-uncased")
    print("  - microsoft/layoutlmv2-base-uncased")
    print("  - microsoft/layoutlmv3-base")
    print("  - microsoft/layoutlmv3-large")


if __name__ == "__main__":
    main()
