# download_llama33_tokenizer.py
from huggingface_hub import snapshot_download
import os

# set if needed; otherwise relies on login or already-set env var
# os.environ["HF_TOKEN"] = "hf_xxx"

REPO_ID = "meta-llama/Meta-Llama-3.1-70B-Instruct"  # replace with Llama 3.3 70B repo when available
TARGET_DIR = "./llama33-70b-tokenizer"

files = [
    "tokenizer.json",
    "tokenizer.model",
    "tokenizer_config.json",
    "special_tokens_map.json",
    "config.json",
]

snapshot_download(
    repo_id=REPO_ID,
    local_dir=TARGET_DIR,
    allow_patterns=files,
)
print(f"Downloaded tokenizer files to: {TARGET_DIR}")