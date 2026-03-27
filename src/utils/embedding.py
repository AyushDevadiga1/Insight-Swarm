"""
src/utils/embedding.py — Final production version.
"""
import logging, threading

logger      = logging.getLogger(__name__)
_instance   = None
_lock       = threading.Lock()


def get_embedding_model(local_only: bool = False):
    global _instance
    if _instance is not None:
        return _instance
    with _lock:
        if _instance is None:
            try:
                from sentence_transformers import SentenceTransformer
                logger.info("Loading SentenceTransformer (local_only=%s)...", local_only)
                logging.getLogger("transformers").setLevel(logging.ERROR)
                logging.getLogger("sentence_transformers").setLevel(logging.ERROR)
                _instance = SentenceTransformer("all-MiniLM-L6-v2", local_files_only=local_only)
            except ImportError:
                raise RuntimeError("sentence-transformers not installed")
            except Exception as e:
                logger.warning("Failed to load sentence-transformers: %s", e)
                raise
    return _instance
