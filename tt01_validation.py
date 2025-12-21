"""
TT-01: Truth Team Protocol
Independent AI verification with anti-shortcut validation
"""

from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass
from enum import Enum
import re

class ValidationStatus(Enum):
    APPROVED = "approved"
    BLOCKED = "blocked"
    REQUIRES_REVISION = "requires_revision"
    ESCALATE = "escalate"

@dataclass
class ValidationResult:
    status: ValidationStatus
    confidence: str  # low, medium, high
    issues: List[str]
    corrections: List[str]
    assumptions_identified: List[str]
    shortcuts_detected: List[str]

class TT01Validator:
    """
    Truth Team Protocol Validator
    Catches: hallucinations, contradictions, shortcuts, assumptions
    """
    
    def __init__(self):
        self.shortcut_patterns = [
            r"probably",
            r"likely",
            r"seems like",
            r"appears to",
            r"I assume",
            r"presumably",
            r"I think",
            r"maybe",
            r"could be",
            r"might be"
        ]
        
        self.certainty_without_evidence = [
            r"definitely",
            r"certainly",
            r"obviously",
            r"clearly",
            r"without a doubt"
        ]
    
    def validate_response(
        self, 
        response: str, 
        original_query: str,
        context: Optional[str] = None
    ) -> ValidationResult:
        """
        Validate AI response for truth, shortcuts, and assumptions
        """
        issues = []
        corrections = []
        assumptions = []
        shortcuts = []
        
        # Check for shortcuts (AI making assumptions)
        for pattern in self.shortcut_patterns:
            matches = re.findall(pattern, response, re.IGNORECASE)
            if matches:
                shortcuts.append(f"Found assumption language: '{matches[0]}'")
        
        # Check for false certainty
        for pattern in self.certainty_without_evidence:
            if re.search(pattern, response, re.IGNORECASE):
                if not context or "evidence" not in context.lower():
                    issues.append(f"Claims certainty without evidence: '{pattern}'")
        
        # Check for contradictions
        if self._check_contradictions(response):
            issues.append("Response contains internal contradictions")
        
        # Check response actually answers the query
        if not self._addresses_query(response, original_query):
            issues.append("Response doesn't directly address the query")
            corrections.append("Refocus response on the specific question asked")
        
        # Identify stated assumptions
        assumption_markers = ["assuming", "if we assume", "given that"]
        for marker in assumption_markers:
            if marker in response.lower():
                # Extract the assumption
                start_idx = response.lower().find(marker)
                assumption_text = response[start_idx:start_idx+100]
                assumptions.append(assumption_text)
        
        # Determine status
        if len(issues) > 3 or any("contradiction" in i.lower() for i in issues):
            status = ValidationStatus.BLOCKED
            confidence = "low"
        elif len(issues) > 0 or len(shortcuts) > 2:
            status = ValidationStatus.REQUIRES_REVISION
            confidence = "medium"
        elif len(shortcuts) > 0:
            status = ValidationStatus.APPROVED
            confidence = "medium"
        else:
            status = ValidationStatus.APPROVED
            confidence = "high"
        
        return ValidationResult(
            status=status,
            confidence=confidence,
            issues=issues,
            corrections=corrections,
            assumptions_identified=assumptions,
            shortcuts_detected=shortcuts
        )
    
    def _check_contradictions(self, text: str) -> bool:
        """Simple contradiction detection"""
        # Look for "but" followed by opposite claim
        sentences = text.split('.')
        for i, sent in enumerate(sentences[:-1]):
            if 'but' in sent.lower() or 'however' in sent.lower():
                # Simple heuristic: check if next sentence contradicts
                if self._likely_contradiction(sent, sentences[i+1]):
                    return True
        return False
    
    def _likely_contradiction(self, sent1: str, sent2: str) -> bool:
        """Check if two sentences likely contradict"""
        negation_words = ['not', 'no', 'never', 'cannot', 'won\'t', 'don\'t']
        
        # Very simple: if one has negation and other doesn't
        has_neg_1 = any(neg in sent1.lower() for neg in negation_words)
        has_neg_2 = any(neg in sent2.lower() for neg in negation_words)
        
        return has_neg_1 != has_neg_2
    
    def _addresses_query(self, response: str, query: str) -> bool:
        """Check if response actually answers the question"""
        # Extract key terms from query
        query_words = set(query.lower().split())
        response_words = set(response.lower().split())
        
        # Remove common words
        stop_words = {'the', 'a', 'an', 'is', 'are', 'was', 'were', 'what', 'how', 'when', 'where', 'why'}
        query_words -= stop_words
        response_words -= stop_words
        
        # Check overlap
        overlap = query_words & response_words
        
        # At least 30% of query words should appear in response
        if len(query_words) == 0:
            return True
        
        overlap_ratio = len(overlap) / len(query_words)
        return overlap_ratio >= 0.3
    
    def format_validation_message(self, result: ValidationResult) -> str:
        """Format validation result for user"""
        if result.status == ValidationStatus.APPROVED and result.confidence == "high":
            return ""  # No message needed
        
        msg = []
        
        if result.shortcuts_detected:
            msg.append("⚠️ TT-01 detected assumption language:")
            for shortcut in result.shortcuts_detected[:3]:
                msg.append(f"  • {shortcut}")
        
        if result.issues:
            msg.append("\n🚫 TT-01 Issues:")
            for issue in result.issues[:3]:
                msg.append(f"  • {issue}")
        
        if result.assumptions_identified:
            msg.append("\n📋 Stated Assumptions:")
            for assumption in result.assumptions_identified[:2]:
                msg.append(f"  • {assumption}")
        
        if result.status == ValidationStatus.BLOCKED:
            msg.append("\n❌ Response blocked by TT-01 - requires correction")
        elif result.status == ValidationStatus.REQUIRES_REVISION:
            msg.append("\n⚠️ TT-01 recommends revision before use")
        
        return "\n".join(msg)


# Quick test
if __name__ == "__main__":
    validator = TT01Validator()
    
    # Test with shortcut language
    test_response = "I think the API probably works fine. It seems like the issue might be with your configuration."
    test_query = "Why is the API failing?"
    
    result = validator.validate_response(test_response, test_query)
    
    print(f"Status: {result.status.value}")
    print(f"Confidence: {result.confidence}")
    print(f"Shortcuts detected: {result.shortcuts_detected}")
    print(f"Issues: {result.issues}")
