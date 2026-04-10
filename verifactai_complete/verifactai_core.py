# verifactai_core.py
import sqlite3
from local_verifier import LocalKnowledgeVerifier
from logprobs_trigger import AdaptiveVerificationTrigger
from novelty_identifier import NoveltyIdentifier
from novelty_resolver import NoveltyResolver


class VeriFactAICore:
    def __init__(self, reset_on_start=False):  # Default to not resetting
        self.sources = []
        self.trigger_engine = AdaptiveVerificationTrigger()
        self.novelty_identifier = NoveltyIdentifier()
        self.novelty_resolver = NoveltyResolver()
        self.source_weights = {'LocalKnowledgeGraph': 1.0}

        self.add_source(LocalKnowledgeVerifier())
        self._init_knowledge_graph()

        # Only reset if explicitly requested
        if reset_on_start:
            self._reset_demo_state()

        print("✅ VeriFactAI Engine - Data-Driven Mode")

    def smart_verify(self, claim, claim_type='general', demo_mode=False):
        """
        SIMPLIFIED FLOW for POC:
        1. Use novelty detection as primary (not LLM confidence)
        2. Always verify claims that match known error patterns
        3. Skip verification only for known correct facts
        """
        print(f"\n🔍 [PATENT #1] Analyzing: '{claim}'")

        # STEP 1: Novelty detection (our main patent)
        novelty_score, novelty_types = self.novelty_identifier.identify_novelty(claim)
        novelty_type = novelty_types[0][0] if novelty_types else 'general'

        # High novelty = definitely verify (these are likely wrong)
        if novelty_score >= 0.7:
            print(f"   🚨 HIGH NOVELTY: {novelty_score:.1f} - {novelty_types[0][1]}")
            print("   ⚡ MUST VERIFY: High novelty indicates potential error")
            return self._full_verification(claim, demo_mode, "high_novelty")

        # Low novelty = known correct facts (can skip)
        elif novelty_score <= 0.2:
            print(f"   ✅ LOW NOVELTY: {novelty_score:.1f} - Known correct fact")
            print("   ✅ SKIPPING: Verified correct fact")
            return {
                'verdict': True,
                'confidence': 0.95,
                'sources': [{'source_name': 'KnownFact', 'confidence': 0.95}],
                'verification_skipped': True,
                'reason': 'Known correct fact',
                'claim': claim
            }

        # Medium novelty = use simple trigger rules
        else:
            print(f"   📊 MEDIUM NOVELTY: {novelty_score:.1f}")
            should_verify, confidence, reason = self.trigger_engine.should_verify(claim, claim_type)

            if should_verify:
                print(f"   🔍 Triggering verification: {reason}")
                return self._full_verification(claim, demo_mode, "triggered")
            else:
                print(f"   ✅ Skipping verification: {reason}")
                return {
                    'verdict': True,
                    'confidence': confidence,
                    'sources': [{'source_name': 'LowRisk', 'confidence': confidence}],
                    'verification_skipped': True,
                    'reason': reason,
                    'claim': claim
                }

    def _full_verification(self, claim, demo_mode, reason):
        """Perform full multi-source verification"""
        print(f"   ⚖️ [PATENT #3] Multi-source verification ({reason})...")

        result = self.calculate_consensus(claim)

        # Self-healing for demo purposes
        if demo_mode and result['overall_confidence'] > 0.7:
            print(f"   🔄 [PATENT #4] Self-healing KG update...")
            self._add_to_knowledge_graph(claim, result['sources'])

        result['claim'] = claim
        result['verification_reason'] = reason
        return result

    def calculate_consensus(self, claim: str) -> dict:
        """Patent-pending weighted consensus algorithm"""
        source_results = []
        weighted_sum = 0.0
        total_weight = 0.0

        for source in self.sources:
            source_result = source.verify_claim(claim)
            weight = self.source_weights.get(source.source_name, 0.5)

            if source_result['verified']:
                source_result['weighted_confidence'] = source_result['confidence'] * weight
                weighted_sum += source_result['weighted_confidence']
                total_weight += weight
            else:
                source_result['weighted_confidence'] = 0

            source_result['source_weight'] = weight
            source_results.append(source_result)
            print(f"      📡 {source.source_name}: {source_result['confidence']:.2f}")

        overall_confidence = weighted_sum / total_weight if total_weight > 0 else 0
        is_verified = overall_confidence >= 0.65

        return {
            'claim': claim,
            'verdict': is_verified,
            'overall_confidence': overall_confidence,
            'sources': source_results
        }

    def _add_to_knowledge_graph(self, claim, source_results):
        """Self-healing knowledge graph update"""
        try:
            conn = sqlite3.connect('knowledge/verifactai_kg.db')
            cursor = conn.cursor()

            verified_value = str([s['data'] for s in source_results if s['verified']])
            confidence_val = max(s['confidence'] for s in source_results if s['verified'])

            cursor.execute('''INSERT OR REPLACE INTO verified_facts 
                           (claim, verified_value, confidence) VALUES (?, ?, ?)''',
                           (claim, verified_value, confidence_val))
            conn.commit()
            conn.close()
            print(f"      💾 Knowledge Graph updated: {claim[:50]}...")

        except sqlite3.Error as e:
            print(f"      ❌ KG update failed: {e}")

    def _init_knowledge_graph(self):
        """Initialize self-healing knowledge graph"""
        conn = sqlite3.connect('knowledge/verifactai_kg.db')
        conn.execute('''CREATE TABLE IF NOT EXISTS verified_facts
                     (id INTEGER PRIMARY KEY, claim TEXT UNIQUE, 
                      verified_value TEXT, confidence REAL, 
                      timestamp DATETIME DEFAULT CURRENT_TIMESTAMP)''')
        conn.close()

    def _reset_demo_state(self):
        """Reset knowledge graph to initial demo state"""
        try:
            conn = sqlite3.connect('knowledge/verifactai_kg.db')
            cursor = conn.cursor()
            cursor.execute("DELETE FROM verified_facts")
            conn.commit()
            conn.close()
            print("🔄 Demo state reset - Knowledge graph cleared")
        except sqlite3.Error as e:
            print(f"❌ Reset failed: {e}")

    def add_source(self, source):
        self.sources.append(source)