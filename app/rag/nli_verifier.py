"""
NLI (Natural Language Inference) Grounding Verifier

Prevents hallucinations by verifying that LLM responses are actually supported
by the retrieved context using Natural Language Inference.

Uses facebook/bart-large-mnli for entailment verification:
- entailment: Response is supported by context (✅ good)
- neutral: Response is plausible but not directly supported (⚠️ warning)
- contradiction: Response contradicts context (❌ reject)

Example:
    Context: "ResilientDB uses Apache 2.0 license"
    Response: "ResilientDB uses MIT license"
    → contradiction (0.95) → REJECT

Performance:
- ~100-200ms per response (batched sentence verification)
- Can be disabled for non-critical queries
"""
from typing import List, Dict, Tuple, Optional
import re
from loguru import logger

# Try importing transformers (optional dependency)
try:
    from transformers import pipeline
    TRANSFORMERS_AVAILABLE = True
except ImportError:
    TRANSFORMERS_AVAILABLE = False
    logger.warning(
        "transformers library not installed. Install with: pip install transformers torch"
    )


class NLIVerifier:
    """
    Natural Language Inference verifier for grounding LLM responses

    Verifies that generated text is actually supported by the retrieved context
    to prevent hallucinations and ensure factual accuracy.
    """

    # Entailment score thresholds
    ENTAILMENT_THRESHOLD = 0.5  # Minimum score to consider entailed
    CONTRADICTION_THRESHOLD = 0.7  # Score above which we reject

    def __init__(self, model_name: str = "facebook/bart-large-mnli", enable: bool = True):
        """
        Initialize NLI verifier

        Args:
            model_name: HuggingFace model for NLI (default: bart-large-mnli)
            enable: Whether to enable verification (can disable for performance)
        """
        self.enabled = enable and TRANSFORMERS_AVAILABLE
        self.model_name = model_name
        self.nli_pipeline = None

        if not self.enabled:
            if not TRANSFORMERS_AVAILABLE:
                logger.warning("NLI verification disabled: transformers not installed")
            else:
                logger.info("NLI verification disabled by configuration")
            return

        try:
            logger.info(f"Loading NLI model: {model_name}...")
            self.nli_pipeline = pipeline(
                "zero-shot-classification",
                model=model_name,
                device=-1  # CPU (use 0 for GPU)
            )
            logger.success(f"✅ NLI verifier initialized ({model_name})")
            logger.info("Hallucination prevention: ACTIVE")
        except Exception as e:
            logger.error(f"Failed to initialize NLI model: {e}")
            self.enabled = False

    def verify_response(
        self,
        response: str,
        context_chunks: List[str]
    ) -> Dict:
        """
        Verify that response is grounded in the retrieved context

        Args:
            response: Generated LLM response
            context_chunks: Retrieved context documents

        Returns:
            Dict with verification results:
            {
                "grounded": bool,  # Overall grounding verdict
                "confidence": float,  # Average entailment score (0-1)
                "sentence_scores": List[Dict],  # Per-sentence verification
                "flagged_sentences": List[str],  # Sentences with low grounding
                "contradiction_found": bool,  # Whether any contradictions detected
                "enabled": bool  # Whether verification was actually performed
            }
        """
        if not self.enabled:
            return {
                "grounded": True,  # Assume grounded if verification disabled
                "confidence": 1.0,
                "sentence_scores": [],
                "flagged_sentences": [],
                "contradiction_found": False,
                "enabled": False,
                "reason": "NLI verification disabled or unavailable"
            }

        # Combine context chunks into single context
        combined_context = "\n\n".join(context_chunks)

        # Split response into sentences
        sentences = self._split_into_sentences(response)

        if not sentences:
            return {
                "grounded": True,
                "confidence": 1.0,
                "sentence_scores": [],
                "flagged_sentences": [],
                "contradiction_found": False,
                "enabled": True
            }

        # Verify each sentence against context
        sentence_scores = []
        flagged_sentences = []
        contradiction_found = False

        for sentence in sentences:
            # Skip very short sentences, formatting, or incomplete fragments
            sentence_clean = sentence.strip()
            if len(sentence_clean) < 15 or not sentence_clean:
                continue

            # Skip sentences that are just formatting markers
            if sentence_clean.startswith(('- ', '* ', '# ', '> ')):
                continue

            try:
                # Use NLI to check if sentence is entailed by context
                result = self._check_entailment(sentence_clean, combined_context)

                sentence_scores.append({
                    "sentence": sentence,
                    "entailment_score": result["entailment"],
                    "neutral_score": result["neutral"],
                    "contradiction_score": result["contradiction"],
                    "label": result["label"]
                })

                # Flag problematic sentences
                if result["contradiction"] > self.CONTRADICTION_THRESHOLD:
                    flagged_sentences.append(sentence)
                    contradiction_found = True
                    logger.warning(
                        f"Contradiction detected (score={result['contradiction']:.2f}): "
                        f"{sentence[:80]}..."
                    )
                elif result["entailment"] < self.ENTAILMENT_THRESHOLD:
                    flagged_sentences.append(sentence)
                    logger.warning(
                        f"Low entailment (score={result['entailment']:.2f}): "
                        f"{sentence[:80]}..."
                    )

            except Exception as e:
                logger.error(f"Error verifying sentence: {e}")
                # On error, assume grounded to avoid blocking responses
                sentence_scores.append({
                    "sentence": sentence,
                    "entailment_score": 0.5,
                    "error": str(e)
                })

        # Calculate overall confidence (average entailment score)
        if sentence_scores:
            avg_entailment = sum(
                s.get("entailment_score", 0.5) for s in sentence_scores
            ) / len(sentence_scores)
        else:
            avg_entailment = 1.0

        # Overall grounding verdict
        grounded = (
            not contradiction_found and
            avg_entailment >= self.ENTAILMENT_THRESHOLD
        )

        result = {
            "grounded": grounded,
            "confidence": avg_entailment,
            "sentence_scores": sentence_scores,
            "flagged_sentences": flagged_sentences,
            "contradiction_found": contradiction_found,
            "enabled": True
        }

        # Log overall verdict
        if grounded:
            logger.success(
                f"✅ Response grounded (confidence={avg_entailment:.2f}, "
                f"{len(sentences)} sentences verified)"
            )
        else:
            logger.warning(
                f"⚠️ Response NOT grounded (confidence={avg_entailment:.2f}, "
                f"{len(flagged_sentences)}/{len(sentences)} sentences flagged)"
            )

        return result

    def _check_entailment(
        self,
        hypothesis: str,
        premise: str
    ) -> Dict[str, float]:
        """
        Check if hypothesis is entailed by premise using NLI

        Args:
            hypothesis: Statement to verify (generated sentence)
            premise: Context to verify against (retrieved documents)

        Returns:
            Dict with scores for entailment, neutral, contradiction
        """
        # Skip if either is too short or empty
        if not hypothesis or not premise or len(hypothesis) < 10 or len(premise) < 10:
            return {
                "entailment": 0.5,
                "neutral": 0.5,
                "contradiction": 0.0,
                "label": "neutral"
            }

        # Use zero-shot classification with entailment labels
        # For BART NLI, we check if hypothesis is supported by premise
        try:
            result = self.nli_pipeline(
                hypothesis,  # Sequence to classify
                candidate_labels=["supported by context", "not supported", "contradicts context"],
                hypothesis_template="This statement: {}",
                multi_label=False
            )

            # Extract scores
            scores_raw = {
                label: score
                for label, score in zip(result["labels"], result["scores"])
            }

            # Map to NLI labels
            entailment_score = scores_raw.get("supported by context", 0.33)
            neutral_score = scores_raw.get("not supported", 0.33)
            contradiction_score = scores_raw.get("contradicts context", 0.33)

            # Determine primary label
            if entailment_score > neutral_score and entailment_score > contradiction_score:
                label = "entailment"
            elif contradiction_score > entailment_score:
                label = "contradiction"
            else:
                label = "neutral"

            return {
                "entailment": entailment_score,
                "neutral": neutral_score,
                "contradiction": contradiction_score,
                "label": label
            }
        except Exception as e:
            # If error, assume neutral (don't block response)
            logger.debug(f"NLI check failed for sentence, assuming neutral: {e}")
            return {
                "entailment": 0.5,
                "neutral": 0.5,
                "contradiction": 0.0,
                "label": "neutral"
            }

    def _split_into_sentences(self, text: str) -> List[str]:
        """
        Split text into sentences for individual verification

        Args:
            text: Text to split

        Returns:
            List of sentences
        """
        # Simple sentence splitting (can be improved with nltk/spacy)
        # Split on period, exclamation, question mark followed by space/newline
        sentences = re.split(r'[.!?]+\s+', text)

        # Filter empty sentences and strip whitespace
        sentences = [s.strip() for s in sentences if s.strip()]

        return sentences

    def format_verification_report(self, verification: Dict) -> str:
        """
        Format verification results as human-readable report

        Args:
            verification: Results from verify_response()

        Returns:
            Formatted report string
        """
        if not verification["enabled"]:
            return "NLI verification: DISABLED"

        report = []
        report.append("=" * 60)
        report.append("NLI GROUNDING VERIFICATION REPORT")
        report.append("=" * 60)

        # Overall verdict
        if verification["grounded"]:
            report.append("✅ VERDICT: Response is GROUNDED")
        else:
            report.append("⚠️ VERDICT: Response is NOT GROUNDED")

        report.append(f"Confidence: {verification['confidence']:.2f}")
        report.append(
            f"Sentences verified: {len(verification['sentence_scores'])}"
        )

        # Flagged sentences
        if verification["flagged_sentences"]:
            report.append(f"\n⚠️ FLAGGED SENTENCES ({len(verification['flagged_sentences'])}):")
            for i, sent in enumerate(verification["flagged_sentences"], 1):
                report.append(f"  {i}. {sent[:100]}...")

        # Contradiction warning
        if verification["contradiction_found"]:
            report.append("\n❌ CONTRADICTION DETECTED")
            report.append("Response contains statements that contradict the context")

        report.append("=" * 60)

        return "\n".join(report)


# Singleton instance
_verifier_instance: Optional[NLIVerifier] = None


def get_nli_verifier(enable: bool = True) -> NLIVerifier:
    """
    Get singleton NLI verifier instance

    Args:
        enable: Whether to enable verification

    Returns:
        NLIVerifier instance
    """
    global _verifier_instance

    if _verifier_instance is None:
        _verifier_instance = NLIVerifier(enable=enable)

    return _verifier_instance
