import json
import argparse
from pathlib import Path
from transformers import AutoTokenizer

def load_tokenizer(local_dir: str):
    # Fully offline load from local folder containing the tokenizer files
    tok = AutoTokenizer.from_pretrained(
        local_dir,
        local_files_only=True,
        use_fast=True  # falls back to slow if fast not available
    )
    return tok

def count_text_tokens(tokenizer, text: str) -> int:
    return len(tokenizer.encode(text))

def count_chat_tokens(tokenizer, messages) -> int:
    """
    messages: list of {"role": "user"/"assistant"/"system", "content": "text"}
    Uses chat template if present in tokenizer config (Instruct variants usually have one).
    If no template exists, we fall back to a simple join.
    """
    apply_template = getattr(tokenizer, "apply_chat_template", None)
    if callable(apply_template):
        # tokenize=True returns token IDs directly via template
        token_ids = tokenizer.apply_chat_template(
            messages,
            tokenize=True,
            add_generation_prompt=False  # set True if you also want the assistant prefix
        )
        return len(token_ids)
    else:
        # Fallback: naive join of role/content
        text = "\n".join([f"{m['role']}: {m['content']}" for m in messages])
        return len(tokenizer.encode(text))

def main():
    parser = argparse.ArgumentParser(description="Offline token counter for Llama 3.x")
    parser.add_argument("--tokenizer-dir", required=True, help="Path to local tokenizer folder")
    parser.add_argument("--text", help="Raw text to tokenize")
    parser.add_argument("--messages", help="Path to JSON file with chat messages list")
    args = parser.parse_args()

    if not Path(args.tokenizer_dir).exists():
        raise SystemExit(f"Tokenizer dir not found: {args.tokenizer_dir}")

    tok = load_tokenizer(args.tokenizer_dir)

    if args.text:
        n = count_text_tokens(tok, args.text)
        print(f"Text tokens: {n}")

    if args.messages:
        with open(args.messages, "r", encoding="utf-8") as f:
            msgs = json.load(f)
        n = count_chat_tokens(tok, msgs)
        print(f"Chat tokens: {n}")

    if not args.text and not args.messages:
        print("Provide --text or --messages")

if __name__ == "__main__":
    main()