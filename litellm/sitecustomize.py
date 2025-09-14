import logging

try:
    import rag_callback  # noqa: F401
    logging.getLogger("rag_callback").info("RAG callback loaded via sitecustomize")
except Exception as e:
    logging.getLogger("rag_callback").warning("Failed to load rag_callback: %s", e)
