"""
User feedback collection and storage.
"""

import sqlite3
from datetime import datetime
from typing import Dict

class FeedbackDB:
    """Store user feedback on verdicts"""
    def __init__(self, db_path: str = "feedback.db"):
        self.db_path = db_path
        self._init_db()
    def _init_db(self):
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()
        c.execute('''
            CREATE TABLE IF NOT EXISTS feedback (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                claim TEXT NOT NULL,
                verdict TEXT NOT NULL,
                confidence REAL NOT NULL,
                user_feedback TEXT NOT NULL,
                timestamp TEXT NOT NULL
            )
        ''')
        conn.commit()
        conn.close()
    def add_feedback(self, claim: str, verdict: str, confidence: float, user_feedback: str):
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()
        c.execute('''
            INSERT INTO feedback (claim, verdict, confidence, user_feedback, timestamp)
            VALUES (?, ?, ?, ?, ?)
        ''', (claim, verdict, confidence, user_feedback, datetime.now().isoformat()))
        conn.commit()
        conn.close()
    def get_accuracy_stats(self) -> Dict:
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()
        c.execute('''
            SELECT COUNT(*) as total, SUM(CASE WHEN user_feedback = 'thumbs_up' THEN 1 ELSE 0 END) as positive
            FROM feedback
        ''')
        row = c.fetchone()
        conn.close()
        total, positive = row
        if total == 0:
            return {'total': 0, 'positive': 0, 'accuracy': 0.0}
        return {'total': total, 'positive': positive, 'accuracy': positive / total}
