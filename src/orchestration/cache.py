"""
Unified Semantic Caching for InsightSwarm
Consolidates semantic matching, verdict storage, and user feedback into a single SQLite database.
"""
import sqlite3
import json
import logging
import os
from typing import Optional, Dict, Any
from datetime import datetime, timedelta
from pathlib import Path

import numpy as np
try:
    from sentence_transformers import SentenceTransformer
    HAS_SENTENCE_TRANSFORMERS = True
except ImportError:
    HAS_SENTENCE_TRANSFORMERS = False

logger = logging.getLogger(__name__)

# Use a single unified database
CACHE_DB_PATH = Path("insightswarm.db")

# Env toggles to control semantic cache fetch behavior
PYTEST_RUNNING = os.getenv("PYTEST_CURRENT_TEST") is not None
SEMANTIC_CACHE_ENABLED = (
    os.getenv("SEMANTIC_CACHE_ENABLED", "1").strip().lower() not in ("0", "false", "off")
    and not PYTEST_RUNNING
)
HF_LOCAL_ONLY = os.getenv("HF_LOCAL_ONLY", "0").strip().lower() in ("1", "true", "on", "yes")

# Reduce noisy third-party fetch logs
for _name in ("httpx", "huggingface_hub", "sentence_transformers", "transformers"):
    logging.getLogger(_name).setLevel(logging.WARNING)

# Quiet HF Hub progress bars and telemetry by default
os.environ.setdefault("HF_HUB_DISABLE_PROGRESS_BARS", "1")
os.environ.setdefault("HF_HUB_DISABLE_TELEMETRY", "1")

class SemanticCache:
    """
    Handles semantic caching of debate verdicts and user feedback.
    """
    def __init__(self, db_path: Path = CACHE_DB_PATH, ttl_days: int = 7):
        self.db_path = db_path
        self.ttl_days = ttl_days
        self.enabled = SEMANTIC_CACHE_ENABLED
        self.local_only = HF_LOCAL_ONLY
        if os.getenv("PYTEST_CURRENT_TEST") is not None:
            self.enabled = False
        # Lazy loading of model to avoid overhead if cache is hit directly by text match (optional optimization)
        self._model = None
        self._model_failed = False
        self._model_fail_count = 0
        
        self._l1_cache = None
        if self.enabled:
            try:
                from src.orchestration.bounded_cache import BoundedCache
                self._l1_cache = BoundedCache(maxsize=100)
            except ImportError:
                pass

        self._embedding_index = None   # numpy matrix shape (N, embedding_dim)
        self._index_data = []          # list of verdict dicts, aligned with matrix rows
        self._index_dirty = True       # True = rebuild needed on next lookup

        self._init_db()

    @property
    def model(self):
        if not self.enabled:
            raise RuntimeError("Semantic cache disabled by SEMANTIC_CACHE_ENABLED")
        if self._model_failed:
            raise RuntimeError("Semantic cache model previously failed to load")
        if self._model is None:
            try:
                from src.utils.embedding import get_embedding_model
                self._model = get_embedding_model(local_only=self.local_only)
            except Exception as e:
                self._model_fail_count = getattr(self, '_model_fail_count', 0) + 1
                if self._model_fail_count >= 3:
                    self._model_failed = True   # Only permanently fail after 3 consecutive failures
                raise RuntimeError(f"Failed to load embedding model: {e}")
        return self._model

    def _encode(self, text: str) -> Optional[np.ndarray]:
        try:
            return self.model.encode([text])[0]
        except Exception as e:
            # Return None for this call only — do NOT permanently disable the cache
            # The next call will try again; transient errors should not kill caching
            logger.warning(f"Embedding encode failed (cache miss for this call only): {e}")
            return None

    def _rebuild_index(self):
        """Load all live embeddings into a numpy matrix for fast vectorised similarity."""
        try:
            with sqlite3.connect(self.db_path) as conn:
                c = conn.cursor()
                now = datetime.now().isoformat()
                c.execute(
                    'SELECT id, claim_embedding, verdict_data, created_at '
                    'FROM claim_cache WHERE expires_at > ?',
                    (now,)
                )
                rows = c.fetchall()

            if not rows:
                self._embedding_index = None
                self._index_data = []
                self._index_dirty = False
                return

            embeddings, data = [], []
            for _, emb_bytes, verdict_json, created_at in rows:
                emb = np.frombuffer(emb_bytes, dtype=np.float32).copy()
                embeddings.append(emb)
                d = json.loads(verdict_json)
                d['cached_at'] = created_at
                data.append(d)

            matrix = np.stack(embeddings)                                # (N, D)
            norms = np.linalg.norm(matrix, axis=1, keepdims=True)
            norms[norms == 0] = 1.0
            self._embedding_index = matrix / norms                       # pre-normalised
            self._index_data = data
            self._index_dirty = False
            logger.debug(f"Rebuilt embedding index: {len(rows)} entries")

        except Exception as e:
            logger.error(f"Index rebuild failed: {e}")
            self._embedding_index = None

    def _has_live_rows(self) -> bool:
        try:
            with sqlite3.connect(self.db_path) as conn:
                c = conn.cursor()
                now = datetime.now().isoformat()
                c.execute('SELECT 1 FROM claim_cache WHERE expires_at > ? LIMIT 1', (now,))
                row = c.fetchone()
                return row is not None
        except Exception:
            return False
    def _init_db(self):
        """Initializes the SQLite unified database"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                c = conn.cursor()
                
                # Table for verdicts with embeddings
                c.execute('''
                    CREATE TABLE IF NOT EXISTS claim_cache (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        claim_text TEXT NOT NULL,
                        claim_embedding BLOB NOT NULL,
                        verdict_data TEXT NOT NULL,
                        created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                        expires_at DATETIME NOT NULL
                    )
                ''')
                
                # Table for user feedback
                c.execute('''
                    CREATE TABLE IF NOT EXISTS user_feedback (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        claim_text TEXT NOT NULL,
                        verdict TEXT NOT NULL,
                        feedback_type TEXT NOT NULL,
                        timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
                    )
                ''')
                
                # Indexes
                c.execute('CREATE INDEX IF NOT EXISTS idx_cache_expires ON claim_cache(expires_at)')
                c.execute('CREATE INDEX IF NOT EXISTS idx_feedback_claim ON user_feedback(claim_text)')
                
                conn.commit()
        except Exception as e:
            logger.error(f"Failed to initialize unified cache DB: {e}")

    def get_verdict(self, claim: str, similarity_threshold: float = 0.92) -> Optional[Dict[str, Any]]:
        """Retrieves a cached verdict using semantic similarity"""
        if self._l1_cache:
            hit = self._l1_cache.get(claim)
            if hit:
                logger.info(f"🧠 L1 MEMORY CACHE HIT for: '{claim}'")
                return hit
                
        try:
            if not self.enabled:
                return None
            if not self._has_live_rows():
                return None
            query_embedding = self._encode(claim)
            if query_embedding is None:
                return None
            
            if self._index_dirty or self._embedding_index is None:
                self._rebuild_index()

            if self._embedding_index is None or len(self._index_data) == 0:
                return None

            # Vectorised cosine similarity — O(N) numpy vs O(N) Python loop, 10-50x faster
            q_norm = np.linalg.norm(query_embedding)
            if q_norm == 0:
                return None
            q = query_embedding / q_norm
            similarities = self._embedding_index @ q              # dot product, shape (N,)
            best_idx = int(np.argmax(similarities))
            best_similarity = float(similarities[best_idx])
            
            best_match = None
            if best_similarity >= similarity_threshold:
                best_match = dict(self._index_data[best_idx])
                best_match['is_cached'] = True
                best_match['cache_similarity'] = best_similarity
                    
            if best_match:
                if self._l1_cache:
                    self._l1_cache.put(claim, best_match)
                logger.info(f"💾 SEMANTIC CACHE HIT (sim: {best_similarity:.2f}) for: '{claim}'")
            return best_match
            
        except Exception as e:
            logger.error(f"Cache read error: {e}")
            return None

    def set_verdict(self, claim: str, verdict_data: Dict[str, Any]):
        """Saves a verdict with its embedding to the cache"""
        if self._l1_cache:
            self._l1_cache.put(claim, verdict_data)
            
        try:
            if not self.enabled:
                return
            embedding = self._encode(claim)
            if embedding is None:
                return
            embedding_bytes = embedding.tobytes()
            
            created_at = datetime.now()
            expires_at = created_at + timedelta(days=self.ttl_days)
            
            with sqlite3.connect(self.db_path) as conn:
                c = conn.cursor()
                c.execute('''
                    INSERT INTO claim_cache (claim_text, claim_embedding, verdict_data, created_at, expires_at)
                    VALUES (?, ?, ?, ?, ?)
                ''', (claim, embedding_bytes, json.dumps(verdict_data), created_at.isoformat(), expires_at.isoformat()))
                conn.commit()
                self._index_dirty = True
        except Exception as e:
            logger.error(f"Cache write error: {e}")

    def record_user_feedback(self, claim: str, verdict: str, feedback_type: str):
        """Records user thumbs up/down"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                c = conn.cursor()
                c.execute('''
                    INSERT INTO user_feedback (claim_text, verdict, feedback_type)
                    VALUES (?, ?, ?)
                ''', (claim, verdict, feedback_type))
                conn.commit()
        except Exception as e:
            logger.error(f"Feedback record error: {e}")

import threading

# Global singleton or helper functions
_cache_instance = None
_cache_lock = threading.Lock()

def get_cache() -> SemanticCache:
    global _cache_instance
    if _cache_instance is None:
        with _cache_lock:
            if _cache_instance is None:
                _cache_instance = SemanticCache()
    return _cache_instance

def get_cached_verdict(claim: str) -> Optional[Dict[str, Any]]:
    return get_cache().get_verdict(claim)

def set_cached_verdict(claim: str, verdict_data: Dict[str, Any]):
    return get_cache().set_verdict(claim, verdict_data)

def record_feedback(claim: str, verdict: str, feedback_type: str):
    return get_cache().record_user_feedback(claim, verdict, feedback_type)

def init_db():
    get_cache() # Triggers init 
