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

# Respect env var so CI / tests can redirect to :memory: or a temp path
_db_file = os.getenv("INSIGHTSWARM_DB", "insightswarm.db")
CACHE_DB_PATH = Path(_db_file)

PYTEST_RUNNING = os.getenv("PYTEST_CURRENT_TEST") is not None
SEMANTIC_CACHE_ENABLED = (
    os.getenv("SEMANTIC_CACHE_ENABLED", "1").strip().lower() not in ("0", "false", "off")
    and not PYTEST_RUNNING
)
HF_LOCAL_ONLY = os.getenv("HF_LOCAL_ONLY", "0").strip().lower() in ("1", "true", "on", "yes")

for _name in ("httpx", "huggingface_hub", "sentence_transformers", "transformers"):
    logging.getLogger(_name).setLevel(logging.WARNING)

os.environ.setdefault("HF_HUB_DISABLE_PROGRESS_BARS", "1")
os.environ.setdefault("HF_HUB_DISABLE_TELEMETRY", "1")


class SemanticCache:
    """Semantic caching of debate verdicts and user feedback."""

    def __init__(self, db_path: Path = CACHE_DB_PATH, ttl_days: int = 7):
        self.db_path   = db_path
        self.ttl_days  = ttl_days
        self.enabled   = SEMANTIC_CACHE_ENABLED
        self.local_only = HF_LOCAL_ONLY
        if os.getenv("PYTEST_CURRENT_TEST") is not None:
            self.enabled = False
        self._model        = None
        self._model_failed = False
        self._init_db()

    # ── Model lazy-load ───────────────────────────────────────────────────────

    @property
    def model(self):
        if not self.enabled:
            raise RuntimeError("Semantic cache disabled by SEMANTIC_CACHE_ENABLED")
        if self._model_failed:
            raise RuntimeError("Semantic cache model previously failed to load")
        if self._model is None:
            if not HAS_SENTENCE_TRANSFORMERS:
                self._model_failed = True
                raise RuntimeError("sentence-transformers not installed")
            logger.info("Loading SentenceTransformer model for semantic cache...")
            try:
                self._model = SentenceTransformer("all-MiniLM-L6-v2",
                                                  local_files_only=self.local_only)
            except Exception:
                self._model_failed = True
                raise
        return self._model

    def _encode(self, text: str) -> Optional[np.ndarray]:
        try:
            return self.model.encode([text])[0]
        except Exception as e:
            logger.warning(f"Semantic cache disabled (model load failed): {e}")
            self.enabled = False
            return None

    def _has_live_rows(self) -> bool:
        try:
            with sqlite3.connect(self.db_path) as conn:
                c = conn.cursor()
                c.execute("SELECT 1 FROM claim_cache WHERE expires_at > ? LIMIT 1",
                          (datetime.now().isoformat(),))
                return c.fetchone() is not None
        except Exception:
            return False

    # ── Schema init ───────────────────────────────────────────────────────────

    def _init_db(self):
        """Initialise SQLite schema with WAL mode for concurrent write safety."""
        try:
            with sqlite3.connect(self.db_path) as conn:
                # WAL mode: allows concurrent reads + one writer; prevents
                # "database is locked" under multi-user Streamlit sessions.
                conn.execute("PRAGMA journal_mode=WAL")
                conn.execute("PRAGMA synchronous=NORMAL")

                c = conn.cursor()
                c.execute("""
                    CREATE TABLE IF NOT EXISTS claim_cache (
                        id              INTEGER PRIMARY KEY AUTOINCREMENT,
                        claim_text      TEXT    NOT NULL,
                        claim_embedding BLOB    NOT NULL,
                        verdict_data    TEXT    NOT NULL,
                        created_at      DATETIME DEFAULT CURRENT_TIMESTAMP,
                        expires_at      DATETIME NOT NULL
                    )
                """)
                c.execute("""
                    CREATE TABLE IF NOT EXISTS user_feedback (
                        id            INTEGER PRIMARY KEY AUTOINCREMENT,
                        claim_text    TEXT    NOT NULL,
                        verdict       TEXT    NOT NULL,
                        feedback_type TEXT    NOT NULL,
                        timestamp     DATETIME DEFAULT CURRENT_TIMESTAMP
                    )
                """)
                c.execute("""
                    CREATE TABLE IF NOT EXISTS debate_history (
                        id         INTEGER PRIMARY KEY AUTOINCREMENT,
                        claim_text TEXT    NOT NULL,
                        verdict    TEXT,
                        confidence REAL,
                        timestamp  DATETIME DEFAULT CURRENT_TIMESTAMP
                    )
                """)
                c.execute("CREATE INDEX IF NOT EXISTS idx_cache_expires  ON claim_cache(expires_at)")
                c.execute("CREATE INDEX IF NOT EXISTS idx_feedback_claim ON user_feedback(claim_text)")
                c.execute("CREATE INDEX IF NOT EXISTS idx_history_ts     ON debate_history(timestamp)")
                conn.commit()
        except Exception as e:
            logger.error(f"Failed to initialise cache DB: {e}")

    # ── Verdict cache ─────────────────────────────────────────────────────────

    def get_verdict(self, claim: str, similarity_threshold: float = 0.85) -> Optional[Dict[str, Any]]:
        """Retrieve a cached verdict using cosine similarity (threshold lowered to 0.85)."""
        try:
            if not self.enabled:
                return None
            if not self._has_live_rows():
                return None
            query_embedding = self._encode(claim)
            if query_embedding is None:
                return None

            with sqlite3.connect(self.db_path) as conn:
                c = conn.cursor()
                c.execute("""
                    SELECT claim_text, claim_embedding, verdict_data, created_at
                    FROM   claim_cache
                    WHERE  expires_at > ?
                """, (datetime.now().isoformat(),))
                rows = c.fetchall()

            best_match, best_sim = None, 0.0
            for cached_claim, embedding_bytes, verdict_json, created_at in rows:
                cached_emb = np.frombuffer(embedding_bytes, dtype=np.float32)
                denom = np.linalg.norm(query_embedding) * np.linalg.norm(cached_emb)
                if denom == 0:
                    continue
                sim = np.dot(query_embedding, cached_emb) / denom
                if sim > best_sim and sim >= similarity_threshold:
                    best_sim   = sim
                    data       = json.loads(verdict_json)
                    data["is_cached"]        = True
                    data["cache_similarity"] = float(sim)
                    data["cached_at"]        = created_at
                    best_match = data

            if best_match:
                logger.info(f"💾 CACHE HIT (sim={best_sim:.2f}): '{claim}'")
            return best_match

        except Exception as e:
            logger.error(f"Cache read error: {e}")
            return None

    def set_verdict(self, claim: str, verdict_data: Dict[str, Any]):
        """Save a verdict with its embedding."""
        try:
            if not self.enabled:
                return
            embedding = self._encode(claim)
            if embedding is None:
                return

            created_at = datetime.now()
            expires_at = created_at + timedelta(days=self.ttl_days)

            with sqlite3.connect(self.db_path) as conn:
                conn.execute("PRAGMA journal_mode=WAL")
                conn.execute("""
                    INSERT INTO claim_cache
                        (claim_text, claim_embedding, verdict_data, created_at, expires_at)
                    VALUES (?, ?, ?, ?, ?)
                """, (claim, embedding.tobytes(), json.dumps(verdict_data),
                      created_at.isoformat(), expires_at.isoformat()))
                conn.commit()
        except Exception as e:
            logger.error(f"Cache write error: {e}")

    # ── Debate history ────────────────────────────────────────────────────────

    def record_debate(self, claim: str, verdict: str, confidence: float):
        """Persist a completed debate to the history table (FR-24)."""
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.execute("PRAGMA journal_mode=WAL")
                conn.execute(
                    "INSERT INTO debate_history (claim_text, verdict, confidence) VALUES (?,?,?)",
                    (claim, verdict, float(confidence)),
                )
                conn.commit()
        except Exception as e:
            logger.error(f"History record error: {e}")

    def get_history(self, limit: int = 50):
        """Return the last `limit` debate records, newest first (FR-19 / US-07)."""
        try:
            with sqlite3.connect(self.db_path) as conn:
                rows = conn.execute(
                    "SELECT claim_text, verdict, confidence, timestamp "
                    "FROM debate_history ORDER BY timestamp DESC LIMIT ?",
                    (limit,),
                ).fetchall()
            return [{"claim": r[0], "verdict": r[1],
                     "confidence": r[2], "timestamp": r[3]} for r in rows]
        except Exception:
            return []

    # ── User feedback ─────────────────────────────────────────────────────────

    def record_user_feedback(self, claim: str, verdict: str, feedback_type: str):
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.execute(
                    "INSERT INTO user_feedback (claim_text, verdict, feedback_type) VALUES (?,?,?)",
                    (claim, verdict, feedback_type),
                )
                conn.commit()
        except Exception as e:
            logger.error(f"Feedback record error: {e}")


# ── Module-level helpers ──────────────────────────────────────────────────────

_cache_instance = None


def get_cache() -> SemanticCache:
    global _cache_instance
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
    get_cache()  # Triggers _init_db via __init__
