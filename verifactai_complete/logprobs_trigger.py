# logprobs_trigger.py
import sqlite3
from difflib import SequenceMatcher


class AdaptiveVerificationTrigger:
    """
    Simple trigger that checks healed KG first
    """

    def should_verify(self, text, claim_type='general'):
        """
        Check healed KG first, then use simple rules
        """
        # FIRST: Check if this is already in healed knowledge graph
        if self._is_in_healed_kg(text):
            return False, 0.95, "Known correct in healed knowledge graph"

        # SECOND: High-risk claims that should always be verified
        high_risk_claims = [
            'capital of france is london',
            'world war ii ended in 1995',
            'body temperature is 35',
            'speed of light is'
        ]

        text_lower = text.lower()
        if any(risk_claim in text_lower for risk_claim in high_risk_claims):
            return True, 0.1, "High-risk claim detected"

        # THIRD: Check for numerical patterns
        import re
        if re.search(r'\b\d+\.?\d*\b', text):
            return True, 0.3, "Numerical claim needs verification"

        # FOURTH: For well-known correct facts, skip verification
        known_correct = [
            'python was created by guido',
            'capital of france is paris',
            'world war ii ended in 1945'
        ]

        if any(correct in text_lower for correct in known_correct):
            return False, 0.9, "Known correct fact"

        # Default: verify most claims for demo purposes
        return True, 0.5, "Standard verification required"

    def _is_in_healed_kg(self, claim):
        """Check if claim exists in healed knowledge graph"""
        try:
            conn = sqlite3.connect('knowledge/verifactai_kg.db')
            cursor = conn.cursor()

            # Check for exact match
            cursor.execute("SELECT claim FROM verified_facts WHERE claim = ?", (claim,))
            exact_match = cursor.fetchone()
            if exact_match:
                conn.close()
                return True

            # Check for similar matches
            cursor.execute("SELECT claim FROM verified_facts")
            all_healed = cursor.fetchall()
            conn.close()

            for healed_claim, in all_healed:
                similarity = SequenceMatcher(None, claim.lower(), healed_claim.lower()).ratio()
                if similarity > 0.8:  # High similarity
                    return True

        except sqlite3.Error:
            pass

        return False