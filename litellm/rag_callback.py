import os, sys
import json
import logging
import re
import yaml
from typing import Any, Dict, List, Optional
import requests
from contextlib import suppress

try:
    import litellm
    sys.path.append("C:\\Program Files\\JetBrains\\PyCharm 2025.1.3.1\\debug-eggs\\pydevd-pycharm.egg")
    import pydevd_pycharm
except ImportError:
    True == True

logger = logging.getLogger("rag_callback")
logger.setLevel(logging.DEBUG)

# Environment-configurable knobs
RAG_API_URL = os.getenv("RAG_API_URL", "").rstrip("/")
RAG_K = int(os.getenv("RAG_K", "4"))
RAG_MAX_CHARS_PER_CHUNK = int(os.getenv("RAG_MAX_CHARS_PER_CHUNK", "1200"))
RAG_MAX_TOTAL_CHARS = int(os.getenv("RAG_MAX_TOTAL_CHARS", "4000"))
RAG_BEARER = os.getenv("RAG_BEARER") or os.getenv("RAG_JWT")
RAG_HEADER = os.getenv("RAG_HEADER", "Use the following retrieved context to help answer the user. Do not mention these chunks explicitly.")
RAG_FOLLOWUP_PROMPT = os.getenv("RAG_FOLLOWUP_PROMPT", "If you don't know the answer, just say that you don't know. Do not try to make up an answer.")

# Configuration file path
RAG_CONFIG_FILE = os.getenv("RAG_CONFIG_FILE", os.path.join(os.path.dirname(__file__), "rag_config.yaml"))


def _rag_endpoint() -> Optional[str]:
    if not RAG_API_URL:
        return None
    # Accept either base or base + /api/v1
    if RAG_API_URL.endswith("/api/v1"):
        return f"{RAG_API_URL}/retrieve"
    return f"{RAG_API_URL}/api/v1/retrieve"


def _load_rag_config() -> Dict[str, Any]:
    """Load RAG configuration from file dynamically each time."""
    try:
        if os.path.exists(RAG_CONFIG_FILE):
            with open(RAG_CONFIG_FILE, 'r', encoding='utf-8') as f:
                config = yaml.safe_load(f) or {}
                logger.debug(f"Loaded RAG config from {RAG_CONFIG_FILE}")
                return config
        else:
            logger.warning(f"RAG config file not found: {RAG_CONFIG_FILE}")
            return {}
    except Exception as e:
        logger.error(f"Failed to load RAG config: {e}")
        return {}


def _parse_rag_directive(message_content: str) -> tuple[Optional[str], str]:
    """
    Parse #ctx(parameter) from message content.
    
    Returns:
        tuple: (parameter_name, cleaned_message_content)
               parameter_name is None if no #ctx directive found
    """
    # Pattern to match #ctx(parameter) with optional whitespace
    pattern = r'#ctx\s*\(\s*([^)]+)\s*\)'
    match = re.search(pattern, message_content, re.IGNORECASE)
    
    if match:
        parameter = match.group(1).strip()
        # Remove the #ctx(parameter) directive from the message
        cleaned_content = re.sub(pattern, '', message_content, flags=re.IGNORECASE).strip()
        return parameter, cleaned_content
    
    return None, message_content


def _get_rag_params_from_config(parameter_name: str) -> Dict[str, Any]:
    """
    Get RAG parameters from configuration based on parameter name.
    
    Args:
        parameter_name: The parameter name from #ctx(parameter_name)
        
    Returns:
        Dict containing RAG parameters, excluding 'query'
    """
    config = _load_rag_config()
    
    # Look for the parameter in the config
    rag_configs = config.get('rag_configurations', {})
    
    if parameter_name in rag_configs:
        params = rag_configs[parameter_name].copy()
        # Remove 'query' if present since it will be set from the message
        params.pop('query', None)
        logger.info(f"Found RAG config for '{parameter_name}': {list(params.keys())}")
        return params
    else:
        logger.warning(f"RAG configuration '{parameter_name}' not found in config file")
        # Return default parameters
        return {
            "k": RAG_K,
            "include_metadata": True,
            "configuration_name": "default",
            "fusion_method": "rrf",
            "similarity_threshold": 0.1,
        }


def _retrieve_rag_chunks_with_params(query: str, rag_params: Dict[str, Any]) -> str:
    """Call the RAG service with custom parameters and return a formatted context string.

    Returns an empty string on failure or if no documents found.
    """
    endpoint = _rag_endpoint()
    if not endpoint:
        return ""

    headers = {"Content-Type": "application/json"}
    if RAG_BEARER:
        headers["Authorization"] = f"Bearer {RAG_BEARER}"

    # Build request body with custom parameters
    body = {
        "query": query,
        **rag_params  # Merge in the custom parameters
    }
    
    # Ensure k is within valid range
    if 'k' in body:
        body['k'] = max(1, min(int(body['k']), 10))

    logger.info(f"RAG request body: {json.dumps(body, indent=2)}")

    try:
        resp = requests.post(endpoint, headers=headers, data=json.dumps(body), timeout=10)
        resp.raise_for_status()
        data = resp.json()
        docs = (data or {}).get("documents", [])[: body.get('k', RAG_K)]
        if not docs:
            return ""

        pieces: List[str] = []
        total_chars = 0
        for i, d in enumerate(docs, start=1):
            meta = d.get("metadata") or {}
            content: str = d.get("content") or d.get("text") or ""
            if not content:
                continue
            # Trim per-chunk and respect total cap
            content = content.strip()
            if RAG_MAX_CHARS_PER_CHUNK > 0:
                content = content[: RAG_MAX_CHARS_PER_CHUNK]

            chunk = content
            meta_parts = []
            if isinstance(meta, dict):
                if meta.get("source"):
                    meta_parts.append(f"source: {meta['source']}")
                if meta.get("page") is not None:
                    meta_parts.append(f"page: {meta['page']}")
            meta_line = f" [{', '.join(meta_parts)}]" if meta_parts else ""
            block = f"({i}){meta_line}\n{chunk}"

            new_total = total_chars + len(block)
            if RAG_MAX_TOTAL_CHARS > 0 and new_total > RAG_MAX_TOTAL_CHARS:
                break
            total_chars = new_total
            pieces.append(block)

        return "\n\n-----\n\n".join(pieces)
    except Exception as e:
        logger.warning("RAG retrieval failed: %s", e)
        return ""


def _retrieve_rag_chunks(query: str) -> str:
    """Call the RAG service and return a formatted context string.

    Returns an empty string on failure or if no documents found.
    """
    endpoint = _rag_endpoint()
    if not endpoint:
        return ""

    headers = {"Content-Type": "application/json"}
    if RAG_BEARER:
        headers["Authorization"] = f"Bearer {RAG_BEARER}"

    body = {
        "query": query,
        "k": max(1, min(RAG_K, 10)),
        "include_metadata": True,
        "configuration_name": "batch_ml_ai_basics_test",
        "fusion_method": "rrf",
        "similarity_threshold": 0.1,
    }

    try:
        resp = requests.post(endpoint, headers=headers, data=json.dumps(body), timeout=10)
        resp.raise_for_status()
        data = resp.json()
        docs = (data or {}).get("documents", [])[: RAG_K]
        if not docs:
            return ""

        pieces: List[str] = []
        total_chars = 0
        for i, d in enumerate(docs, start=1):
            meta = d.get("metadata") or {}
            content: str = d.get("content") or d.get("text") or ""
            if not content:
                continue
            # Trim per-chunk and respect total cap
            content = content.strip()
            if RAG_MAX_CHARS_PER_CHUNK > 0:
                content = content[: RAG_MAX_CHARS_PER_CHUNK]

            chunk = content
            meta_parts = []
            if isinstance(meta, dict):
                if meta.get("source"):
                    meta_parts.append(f"source: {meta['source']}")
                if meta.get("page") is not None:
                    meta_parts.append(f"page: {meta['page']}")
            meta_line = f" [{', '.join(meta_parts)}]" if meta_parts else ""
            block = f"({i}){meta_line}\n{chunk}"

            new_total = total_chars + len(block)
            if RAG_MAX_TOTAL_CHARS > 0 and new_total > RAG_MAX_TOTAL_CHARS:
                break
            total_chars = new_total
            pieces.append(block)

        return "\n\n-----\n\n".join(pieces)
    except Exception as e:
        logger.warning("RAG retrieval failed: %s", e)
        return ""


def _update_message_content_inplace(msg: Dict[str, Any], user_query: str, context: str) -> None:
    """Prepend context to a message's content.

    Supports string content or OpenAI-style list-of-parts with type='text'.
    """
    updated = f"## DOCUMENT: \n {context} \n\n ## QUESTION: \n {user_query}"
    updated += f"\n\n {RAG_FOLLOWUP_PROMPT}"

    content = msg.get("content")
    if isinstance(content, str):
        msg["content"] = updated
        return

    if isinstance(content, list):
        # Find first text part, otherwise append
        for part in content:
            if isinstance(part, dict) and part.get("type") == "text" and isinstance(part.get("text"), str):
                part["text"] = updated
                return
        content.append({"type": "text", "text": updated})
        return

    # Fallback: overwrite as string
    msg["content"] = updated


def _update_message_content_with_no_context(msg: Dict[str, Any], message: str) -> None:
    """Update message content when no RAG context is available.

    Supports string content or OpenAI-style list-of-parts with type='text'.
    """
    content = msg.get("content")
    if isinstance(content, str):
        msg["content"] = message
        return

    if isinstance(content, list):
        # Find first text part, otherwise append
        for part in content:
            if isinstance(part, dict) and part.get("type") == "text" and isinstance(part.get("text"), str):
                part["text"] = message
                return
        content.append({"type": "text", "text": message})
        return

    # Fallback: overwrite as string
    msg["content"] = message


def _convert_json_to_string_in_content(content: Any) -> Any:
    """Convert JSON objects to strings in message content.
    
    Args:
        content: The content to process (can be string, list, or dict)
        
    Returns:
        The processed content with JSON objects converted to strings
    """
    if isinstance(content, str):
        # Try to parse as JSON and convert back to formatted string
        try:
            parsed = json.loads(content)
            return json.dumps(parsed, indent=2, ensure_ascii=False)
        except (json.JSONDecodeError, TypeError):
            # Not JSON, return as-is
            return content
    
    elif isinstance(content, list):
        # Process each item in the list
        processed_content = []
        for item in content:
            if isinstance(item, dict):
                # Handle OpenAI-style message parts
                if item.get("type") == "text" and "text" in item:
                    # Check if the text is JSON
                    text_content = item["text"]
                    if isinstance(text_content, (dict, list)):
                        # Convert dict/list to JSON string
                        item = item.copy()
                        item["text"] = json.dumps(text_content, indent=2, ensure_ascii=False)
                    elif isinstance(text_content, str):
                        # Try to parse and reformat JSON string
                        try:
                            parsed = json.loads(text_content)
                            item = item.copy()
                            item["text"] = json.dumps(parsed, indent=2, ensure_ascii=False)
                        except (json.JSONDecodeError, TypeError):
                            # Not JSON, keep as-is
                            pass
                else:
                    # Convert the entire dict to JSON string if it's not a standard message part
                    item = json.dumps(item, indent=2, ensure_ascii=False)
            elif isinstance(item, (dict, list)):
                # Convert dict/list directly to JSON string
                item = json.dumps(item, indent=2, ensure_ascii=False)
            processed_content.append(item)
        return processed_content
    
    elif isinstance(content, dict):
        # Convert dict to JSON string
        return json.dumps(content, indent=2, ensure_ascii=False)
    
    else:
        # For other types, try to convert to JSON string if possible
        try:
            return json.dumps(content, indent=2, ensure_ascii=False)
        except (TypeError, ValueError):
            # Can't convert to JSON, return as string
            return str(content)

def add_rag_context_to_payload(kwargs: Dict[str, Any]) -> Dict[str, Any]:
    """LiteLLM input_callback-compatible function.

    Receives the kwargs that will be passed into the provider call.
    We mutate kwargs["messages"] in-place to inject RAG context for the last user message.
    Must return kwargs.
    """
    try:
        messages = kwargs.get("messages")
        print("**** Before Messages: ", messages)
        if not isinstance(messages, list) or not messages:
            return kwargs

        # Find last user message
        user_idx = None
        for i in range(len(messages) - 1, -1, -1):
            m = messages[i]
            if isinstance(m, dict) and m.get("role") == "user":
                user_idx = i
                break
        if user_idx is None:
            return kwargs

        user_msg = messages[user_idx]
        # Extract query text from the user message
        user_query: Optional[str] = None
        content = user_msg.get("content")
        if isinstance(content, str):
            user_query = content.strip()
        elif isinstance(content, list):
            # Find first text part
            for part in content:
                if isinstance(part, dict) and part.get("type") == "text" and isinstance(part.get("text"), str):
                    user_query = part["text"].strip()
                    break

        if not user_query:
            return kwargs
                
        # Parse #ctx directive
        rag_parameter, cleaned_query = _parse_rag_directive(user_query)
        print("**** User query: ", user_query, rag_parameter, cleaned_query)

        # TODO: Remove Debugging
        #with suppress(Error): pydevd_pycharm.settrace('localhost', port=25000)
        if rag_parameter is not None:
            # #ctx directive found, use parameter-based lookup
            logger.info(f"Found #ctx directive with parameter: '{rag_parameter}'")
            
            # Get RAG parameters from configuration
            rag_params = _get_rag_params_from_config(rag_parameter)
            
            # Retrieve RAG chunks with custom parameters
            context = _retrieve_rag_chunks_with_params(cleaned_query, rag_params)
            if not context:
                logger.warning(f"No RAG context retrieved for parameter '{rag_parameter}'")
                # Update message with no-context notification instead of returning
                no_context_msg = f"No additional context available. Proceeding with my built-in knowledge.\n\n{cleaned_query}"
                _update_message_content_with_no_context(user_msg, no_context_msg)
                logger.info(f"No RAG context available for '{rag_parameter}', proceeding without additional context")
            else:
                # Update message content with RAG context
                _update_message_content_inplace(user_msg, cleaned_query, context)
                logger.info(f"Injected RAG context for '{rag_parameter}' into LiteLLM payload")
        else:
            # No #ctx directive found, check if we should apply default RAG
            if not RAG_API_URL:
                return kwargs
            # Apply default RAG behavior (existing logic)
            context = _retrieve_rag_chunks(cleaned_query)
            if not context:
                # No default RAG context available, proceed with cleaned query only
                no_context_msg = f"No additional context available. Proceeding with my built-in knowledge.\n\n{cleaned_query}"
                _update_message_content_with_no_context(user_msg, no_context_msg)
                logger.info("No default RAG context available, proceeding without additional context")
            else:
                _update_message_content_inplace(user_msg, cleaned_query, context)
                logger.info("Injected default RAG context into LiteLLM payload (k=%s)", RAG_K)

        print("**** After Messages: ", kwargs.get("messages"))
        return kwargs
    except Exception as e:
        logger.warning("input_callback error: %s", e)
        return kwargs


def convert_json_content_to_string(kwargs: Dict[str, Any]) -> Dict[str, Any]:
    """LiteLLM input_callback-compatible function for converting JSON content to strings.

    Receives the kwargs that will be passed into the provider call.
    We mutate kwargs["messages"] in-place to convert any JSON content to formatted strings.
    Must return kwargs.
    """
    try:
        messages = kwargs.get("messages")
        if not messages or not isinstance(messages, list):
            return kwargs

        print("**** Processing messages for JSON content conversion")

        # Process each message
        for msg in messages:
            if not isinstance(msg, dict):
                continue
            content = msg.get("content")
            if content is None or str(content).strip() == "":
                msg["content"] = "I'll use the available tools to help you."
            print(msg)
        return kwargs

    except Exception as e:
        logger.warning("JSON content conversion error: %s", e)
        return kwargs


# Register the input callbacks with litellm, preserving any existing callbacks
try:
    print(f"************************* Registering Callbacks")
    existing = getattr(litellm, "input_callback", None)
    callbacks_to_register = [] #add_rag_context_to_payload convert_json_content_to_string

    if existing is None:
        litellm.input_callback = callbacks_to_register
    elif isinstance(existing, list):
        # Avoid duplicate registration
        for callback in callbacks_to_register:
            if callback not in existing:
                existing.append(callback)
    else:
        # Wrap existing single callback into a list
        litellm.input_callback = [existing] + callbacks_to_register
    
    logger.info("Registered JSON conversion and RAG input_callbacks with LiteLLM")
except Exception as e:
    logger.warning("Failed to register input_callbacks: %s", e)

# if __name__ == "__main__":
#     add_rag_context_to_payload(None)
