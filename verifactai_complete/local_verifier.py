# local_verifier.py
import sqlite3
from difflib import SequenceMatcher


class LocalKnowledgeVerifier:
    def __init__(self, db_path="knowledge/local_knowledge.db"):
        self.source_name = "LocalKnowledgeGraph"
        self._init_local_db(db_path)

    def _init_local_db(self, db_path):
        """Initialize local SQLite database with verified facts"""
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()

        cursor.execute('''
            CREATE TABLE IF NOT EXISTS verified_facts (
                id INTEGER PRIMARY KEY,
                claim_pattern TEXT,
                verified_value TEXT,
                category TEXT,
                confidence REAL DEFAULT 0.95
            )
        ''')

        # Pre-populate with demo facts
        demo_facts = [
            ("capital of france is", "Paris", "geographical"),
            ("world war ii ended in", "1945", "temporal"),
            ("average human body temperature is", "37°C (98.6°F)", "statistical"),
            ("python was created by", "Guido van Rossum", "entity"),
            ("speed of light is", "299,792 km/s", "statistical"),
            ("shakespeare wrote", "Hamlet, Romeo and Juliet, etc.", "entity"),
            ("ceo of apple is", "Tim Cook", "entity"),
            ("height of eiffel tower is", "330 meters (1,083 feet)", "statistical")
        ]

        cursor.executemany(
            "INSERT OR IGNORE INTO verified_facts (claim_pattern, verified_value, category) VALUES (?, ?, ?)",
            demo_facts
        )
        conn.commit()
        conn.close()
        self.db_path = db_path

    def verify_claim(self, claim):
        """Verify claim against local knowledge graph - CHECK HEALED KG FIRST"""
        # First check the self-healing knowledge graph (verifactai_kg.db)
        healed_result = self._check_healed_knowledge_graph(claim)
        if healed_result:
            return healed_result

        # Fall back to original local knowledge base
        return self._check_local_knowledge_base(claim)

    def _check_healed_knowledge_graph(self, claim):
        """Check the self-healing knowledge graph for previously verified facts"""
        try:
            conn = sqlite3.connect('knowledge/verifactai_kg.db')
            cursor = conn.cursor()

            # Simple exact match first
            cursor.execute("SELECT claim, verified_value, confidence FROM verified_facts WHERE claim = ?", (claim,))
            result = cursor.fetchone()

            if result:
                conn.close()
                return {
                    "verified": True,
                    "confidence": result[2],
                    "data": [result[1]],
                    "source_name": "HealedKnowledgeGraph",
                    "category": "healed"
                }

            # Fuzzy match for similar claims
            cursor.execute("SELECT claim, verified_value, confidence FROM verified_facts")
            all_facts = cursor.fetchall()
            conn.close()

            best_match = None
            best_score = 0

            for stored_claim, value, confidence in all_facts:
                score = SequenceMatcher(None, claim.lower(), stored_claim.lower()).ratio()
                if score > best_score and score > 0.8:  # High similarity threshold
                    best_score = score
                    best_match = (stored_claim, value, confidence)

            if best_match:
                return {
                    "verified": True,
                    "confidence": best_match[2],
                    "data": [best_match[1]],
                    "source_name": "HealedKnowledgeGraph",
                    "category": "healed_fuzzy"
                }

        except sqlite3.Error:
            pass  # If healed KG doesn't exist or has errors, fall back

        return None

    def _check_local_knowledge_base(self, claim):
        """Original verification against local knowledge base"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        claim_lower = claim.lower()

        # Find best matching fact
        cursor.execute("SELECT claim_pattern, verified_value, category, confidence FROM verified_facts")
        best_match = None
        best_score = 0

        for pattern, value, category, confidence in cursor.fetchall():
            score = SequenceMatcher(None, claim_lower, pattern.lower()).ratio()
            if score > best_score and score > 0.6:  # Similarity threshold
                best_score = score
                best_match = (pattern, value, category, confidence)

        conn.close()

        if best_match:
            return {
                "verified": True,
                "confidence": best_match[3],
                "data": [best_match[1]],
                "source_name": self.source_name,
                "category": best_match[2]
            }
        else:
            # No match found in local knowledge
            return {
                "verified": False,
                "confidence": 0.3,
                "data": ["No match in local knowledge base"],
                "source_name": self.source_name,
                "category": "unknown"
            }