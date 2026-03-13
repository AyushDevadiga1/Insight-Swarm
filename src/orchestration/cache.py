"""
Unified Semantic Caching for InsightSwarm
Consolidates semantic matching, verdict storage, and user feedback into a single SQLite database.
"""
import sqlite3
import json
import logging
import numpy as np
import os
from typing import Optional, Dict, Any
from datetime import datetime, timedelta
from pathlib import Path
from sentence_transformers import SentenceTransformer

logger = logging.getLogger(__name__)

# Use a single unified database
CACHE_DB_PATH = Path("insightswarm.db")

class SemanticCache:
    """
    Handles semantic caching of debate verdicts and user feedback.
    """
    def __init__(self, db_path: Path = CACHE_DB_PATH, ttl_days: int = 7):
        self.db_path = db_path
        self.ttl_days = ttl_days
        # Lazy loading of model to avoid overhead if cache is hit directly by text match (optional optimization)
        self._model = None
        self._init_db()

    @property
    def model(self):
        if self._model is None:
            logger.info("Loading SentenceTransformer model for semantic cache...")
            self._model = SentenceTransformer('all-MiniLM-L6-v2')
        return self._model

    def _init_db(self):
        """Initializes the SQLite unified database"""
        try:
            conn = sqlite3.connect(self.db_path)
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
        finally:
            if 'conn' in locals():
                conn.close()

    def get_verdict(self, claim: str, similarity_threshold: float = 0.92) -> Optional[Dict[str, Any]]:
        """Retrieves a cached verdict using semantic similarity"""
        try:
            query_embedding = self.model.encode([claim])[0]
            conn = sqlite3.connect(self.db_path)
            c = conn.cursor()
            
            now = datetime.now().isoformat()
            c.execute('''
                SELECT claim_text, claim_embedding, verdict_data, created_at 
                FROM claim_cache 
                WHERE expires_at > ?
            ''', (now,))
            
            rows = c.fetchall()
            conn.close()
            
            best_match = None
            best_similarity = 0.0
            
            for row in rows:
                cached_claim, embedding_bytes, verdict_json, created_at = row
                cached_embedding = np.frombuffer(embedding_bytes, dtype=np.float32)
                
                # Cosine similarity
                similarity = np.dot(query_embedding, cached_embedding) / (
                    np.linalg.norm(query_embedding) * np.linalg.norm(cached_embedding)
                )
                
                if similarity > best_similarity and similarity >= similarity_threshold:
                    best_similarity = similarity
                    data = json.loads(verdict_json)
                    data['is_cached'] = True
                    data['cache_similarity'] = float(similarity)
                    data['cached_at'] = created_at
                    best_match = data
                    
            if best_match:
                logger.info(f"💾 SEMANTIC CACHE HIT (sim: {best_similarity:.2f}) for: '{claim}'")
            return best_match
            
        except Exception as e:
            logger.error(f"Cache read error: {e}")
            return None

    def set_verdict(self, claim: str, verdict_data: Dict[str, Any]):
        """Saves a verdict with its embedding to the cache"""
        try:
            embedding = self.model.encode([claim])[0]
            embedding_bytes = embedding.tobytes()
            
            created_at = datetime.now()
            expires_at = created_at + timedelta(days=self.ttl_days)
            
            conn = sqlite3.connect(self.db_path)
            c = conn.cursor()
            c.execute('''
                INSERT INTO claim_cache (claim_text, claim_embedding, verdict_data, created_at, expires_at)
                VALUES (?, ?, ?, ?, ?)
            ''', (claim, embedding_bytes, json.dumps(verdict_data), created_at.isoformat(), expires_at.isoformat()))
            conn.commit()
            conn.close()
        except Exception as e:
            logger.error(f"Cache write error: {e}")

    def record_user_feedback(self, claim: str, verdict: str, feedback_type: str):
        """Records user thumbs up/down"""
        try:
            conn = sqlite3.connect(self.db_path)
            c = conn.cursor()
            c.execute('''
                INSERT INTO user_feedback (claim_text, verdict, feedback_type)
                VALUES (?, ?, ?)
            ''', (claim, verdict, feedback_type))
            conn.commit()
            conn.close()
        except Exception as e:
            logger.error(f"Feedback record error: {e}")

# Global singleton or helper functions
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
    get_cache() # Triggers init 
