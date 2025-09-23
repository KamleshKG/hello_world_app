# novelty_identifier.py
import re
import sqlite3
from difflib import SequenceMatcher


class NoveltyIdentifier:
    """
    PATENT #1: Main detection system - checks healed KG first
    """

    def __init__(self):
        self.known_errors = {
            'geographical': [
                ('capital of france is london', 'capital of france is paris'),
                ('capital of germany is paris', 'capital of germany is berlin')
            ],
            'temporal': [
                ('world war ii ended in 1995', 'world war ii ended in 1945'),
                ('berlin wall fell in 2000', 'berlin wall fell in 1989')
            ],
            'scientific': [
                ('human body temperature is 35°c', 'human body temperature is 37°c'),
                ('speed of light is 1000 km/s', 'speed of light is 299,792 km/s')
            ]
        }

        self.correct_facts = [
            'python was created by guido van rossum',
            'water boils at 100°c at sea level',
            'earth revolves around the sun'
        ]

    def identify_novelty(self, claim):
        """
        Check healed KG first, then fall back to pattern matching
        """
        # FIRST: Check if this claim is already in healed knowledge graph
        healed_status = self._check_healed_knowledge_graph(claim)
        if healed_status == 'known_correct':
            return 0.1, [('known_fact', "Verified in healed knowledge graph")]
        elif healed_status == 'known_error':
            return 0.9, [('healed_error', "Previously corrected error")]

        # SECOND: Check for known errors
        claim_lower = claim.lower()
        for category, errors in self.known_errors.items():
            for error, correction in errors:
                if error in claim_lower:
                    return 0.9, [(category, f"Known error: {error}")]

        # THIRD: Check for correct facts
        if any(fact in claim_lower for fact in self.correct_facts):
            return 0.1, [('known_fact', "Verified correct fact")]

        # FOURTH: Check for numerical patterns
        numbers = re.findall(r'\b\d+\.?\d*\b', claim)
        if numbers:
            return 0.7, [('numerical', f"Contains numbers: {numbers}")]

        # Default: moderate novelty score
        return 0.5, [('general', "Standard claim requiring verification")]

    def _check_healed_knowledge_graph(self, claim):
        """Check if claim exists in healed knowledge graph"""
        try:
            conn = sqlite3.connect('knowledge/verifactai_kg.db')
            cursor = conn.cursor()

            # Check for exact match
            cursor.execute("SELECT claim FROM verified_facts WHERE claim = ?", (claim,))
            exact_match = cursor.fetchone()
            if exact_match:
                conn.close()
                return 'known_correct'

            # Check for similar matches (healed errors)
            cursor.execute("SELECT claim FROM verified_facts")
            all_healed = cursor.fetchall()
            conn.close()

            for healed_claim, in all_healed:
                # Check if this claim is similar to a healed claim
                similarity = SequenceMatcher(None, claim.lower(), healed_claim.lower()).ratio()
                if similarity > 0.8:  # High similarity
                    return 'known_correct'

        except sqlite3.Error:
            pass  # If healed KG doesn't exist or has errors

        return 'unknown'