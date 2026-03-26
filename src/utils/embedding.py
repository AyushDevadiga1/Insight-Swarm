"""
src/utils/embedding.py
B2-P12 fix: double-checked locking prevents two threads both calling
SentenceTransformer() when _model_instance is None on startup.
"""
import logging
import threading

logger = logging.getLogger(__name__)

_model_instance = None
_model_lock     = threading.Lock()


def get_embedding_model(local_only: bool = False):
    global _model_instance
    if _model_instance is not None:        # fast path — no lock needed after first load
        return _model_instance

    with _model_lock:
        if _model_instance is None:        # B2-P12 fix: second check inside lock
            try:
                from sentence_transformers import SentenceTransformer
                logger.info("Loading SentenceTransformer (local_only=%s)...", local_only)
                logging.getLogger("transformers").setLevel(logging.ERROR)
                logging.getLogger("sentence_transformers").setLevel(logging.ERROR)
                _model_instance = SentenceTransformer("all-MiniLM-L6-v2",
                                                      local_files_only=local_only)
            except ImportError:
                logger.warning("sentence-transformers not installed.")
                raise RuntimeError("sentence-transformers not installed")
            except Exception as e:
                logger.warning("Failed to load sentence-transformers: %s", e)
                raise

    return _model_instance
