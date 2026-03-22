"""
embedding.py - Shared embedding model loader.
"""
import logging
import threading

logger = logging.getLogger(__name__)

_model_instance = None
_model_lock = threading.Lock()

def get_embedding_model(local_only: bool = False):
    """
    Returns a shared singleton instance of the SentenceTransformer model.
    """
    global _model_instance
    if _model_instance is not None:
        return _model_instance
        
    with _model_lock:
        if _model_instance is None:
            try:
                from sentence_transformers import SentenceTransformer
                logger.info(f"Loading SentenceTransformer model (local_only={local_only})...")
                # Suppress noisy expected architecture warnings from transformers
                logging.getLogger("transformers").setLevel(logging.ERROR)
                logging.getLogger("sentence_transformers").setLevel(logging.ERROR)
                _model_instance = SentenceTransformer('all-MiniLM-L6-v2', local_files_only=local_only)
            except ImportError:
                logger.warning("sentence-transformers not installed.")
                raise RuntimeError("sentence-transformers not installed")
            except Exception as e:
                logger.warning(f"Failed to load sentence-transformers: {e}")
                raise
                
    return _model_instance
