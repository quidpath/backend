"""
Advanced label matching engine for financial statement extraction.

Supports exact matching, alias matching, and fuzzy matching with priority ordering.
Handles OCR errors, misspellings, and various accounting formats.
"""

from __future__ import annotations

import logging
from typing import Dict, List, Optional, Tuple

try:
    from rapidfuzz import fuzz, process
    RAPIDFUZZ_AVAILABLE = True
except ImportError:
    RAPIDFUZZ_AVAILABLE = False
    from difflib import SequenceMatcher

from .accounting_aliases import (
    ACCOUNTING_ALIASES,
    FIELD_PRIORITY,
    _normalize_for_matching,
)

logger = logging.getLogger(__name__)

# ✅ BLACKLIST: Generic labels that should never match any field
# These are common column headers or generic terms that appear in financial statements
GENERIC_LABEL_BLACKLIST = {
    # Document structure
    "account", "account code", "account name", "account number",
    "code", "description", "details", "item", "items",
    "particulars", "particular", "narration", "notes",
    "remarks", "comment", "comments", "memo", "reference",
    "ref", "ref no", "reference number", "id", "identifier",
    "date", "period", "year", "month", "quarter",
    "total", "subtotal", "sub total", "grand total",
    "balance", "opening balance", "closing balance",
    "debit", "credit", "dr", "cr",
    "page", "page number", "sheet", "worksheet",
    
    # Document titles (should NEVER match)
    "profit and loss", "profit & loss", "p&l", "p & l",
    "income statement", "statement of income",
    "balance sheet", "statement of financial position",
    "cash flow", "cash flow statement",
    "basis accrual", "basis cash",
    "for the year ended", "for the period ended",
    "as at", "as of",
    
    # ✅ ADD: Intermediate calculation labels (not final totals)
    "operating income before opex", "operating income before expenses",
    "income before opex", "income before expenses",
    "revenue before expenses", "profit before opex",
    
    # Company info
    "limited", "ltd", "llc", "inc", "incorporated",
    "company", "corporation", "corp",
    
    # Common expense items that should NOT match revenue or profit
    "cleaning", "repairs", "maintenance",
    "transport", "transportation", "travel", "travel expenses",
    "travel national", "travel international",
    "telephone", "phone", "mobile",
    "stationery", "supplies", "office supplies",
    "printing", "postage", "courier",
    "subscriptions", "memberships",
    "training", "seminars", "conferences",
    "entertainment", "meals", "refreshments",
    "donations", "contributions", "csr",
    "penalties", "fines", "late fees",
    "bad debts", "write offs", "provisions",
    
    # Specific expense line items (should never match to financial fields)
    "uniforms", "staff uniforms", "workwear",
    "housing levy", "levy", "contributions",
    "nssf", "nhif", "pension", "provident fund",
    "staff welfare", "welfare", "allowances",
    "bond", "performance bond", "security deposit",
    "statutory", "statutory expense", "compliance",
}


class AdvancedLabelMatcher:
    """
    Advanced label matcher with exact, alias, and fuzzy matching.
    
    Priority order:
    1. Exact match (case-insensitive, normalized)
    2. Alias match (case-insensitive, normalized)
    3. Fuzzy match (token_sort_ratio ≥ 85 or partial_ratio ≥ 90)
    """
    
    def __init__(
        self,
        aliases: Dict[str, List[str]] = None,
        fuzzy_threshold: float = 85.0,
        partial_threshold: float = 90.0,
    ) -> None:
        """
        Initialize the label matcher.
        
        Args:
            aliases: Dictionary mapping canonical fields to alias lists
            fuzzy_threshold: Minimum token_sort_ratio for fuzzy matching (0-100)
            partial_threshold: Minimum partial_ratio for fuzzy matching (0-100)
        """
        self.aliases = aliases or ACCOUNTING_ALIASES
        self.fuzzy_threshold = fuzzy_threshold
        self.partial_threshold = partial_threshold
        
        # Build fast lookup maps
        self._build_lookup_maps()
    
    def _build_lookup_maps(self) -> None:
        """Build fast lookup maps for exact and alias matching."""
        # Map: normalized_alias -> canonical_field
        self.exact_map: Dict[str, str] = {}
        
        # Map: normalized_alias -> (canonical_field, original_alias)
        self.alias_map: Dict[str, Tuple[str, str]] = {}
        
        for field, alias_list in self.aliases.items():
            for alias in alias_list:
                normalized = _normalize_for_matching(alias)
                if normalized:
                    # Exact match map (overwrites if duplicate, but that's OK)
                    self.exact_map[normalized] = field
                    # Alias map (stores original for logging)
                    self.alias_map[normalized] = (field, alias)
    
    def match(self, label: str) -> Optional[str]:
        """
        Match a label to a canonical field.
        
        Args:
            label: The label text from the financial statement
            
        Returns:
            Canonical field name if match found, None otherwise
        """
        if not label or not isinstance(label, str):
            return None
        
        # Normalize the input label
        normalized_label = _normalize_for_matching(label)
        
        if not normalized_label:
            return None
        
        # ✅ FIX: Check blacklist first - skip generic labels
        # Check exact match in blacklist
        if normalized_label in GENERIC_LABEL_BLACKLIST:
            logger.debug("🚫 Label '%s' is in blacklist (generic term), skipping", label)
            return None
        
        # Check if any word in the label is a generic term (for multi-word labels)
        label_words = set(normalized_label.split())
        if label_words & GENERIC_LABEL_BLACKLIST:
            # If the label is ONLY generic words (no financial terms), skip it
            # But allow labels like "Total Revenue" where "Total" is generic but "Revenue" is financial
            if len(label_words) == 1:  # Single generic word
                logger.debug("🚫 Label '%s' is a single generic word, skipping", label)
                return None
            # For multi-word, check if ALL words are generic
            if label_words.issubset(GENERIC_LABEL_BLACKLIST):
                logger.debug("🚫 Label '%s' contains only generic words, skipping", label)
                return None
        
        # ✅ PRIORITY 1: Exact match (case-insensitive, normalized)
        if normalized_label in self.exact_map:
            field = self.exact_map[normalized_label]
            logger.debug("✅ Exact match: '%s' -> %s", label, field)
            return field
        
        # ✅ PRIORITY 2: Alias match (check if normalized label matches any alias)
        if normalized_label in self.alias_map:
            field, original_alias = self.alias_map[normalized_label]
            logger.debug("✅ Alias match: '%s' -> %s (via '%s')", label, field, original_alias)
            return field
        
        # ✅ PRIORITY 2.5: Keyword matching (flexible matching)
        # Check if label contains key terms from any field's aliases
        label_words = set(normalized_label.split())
        for field, alias_list in self.aliases.items():
            for alias in alias_list:
                alias_normalized = _normalize_for_matching(alias)
                if not alias_normalized:
                    continue
                
                alias_words = set(alias_normalized.split())
                # If any significant word from alias is in label, it's a potential match
                # Use words with length > 3 to avoid matching common words
                significant_alias_words = {w for w in alias_words if len(w) > 3}
                if significant_alias_words and significant_alias_words.issubset(label_words):
                    # Calculate confidence based on word overlap
                    overlap_ratio = len(significant_alias_words) / max(len(alias_words), 1)
                    if overlap_ratio >= 0.5:  # At least 50% of significant words match
                        logger.debug("✅ Keyword match: '%s' -> %s (via keywords: %s)", 
                                   label, field, significant_alias_words)
                        return field
        
        # ✅ PRIORITY 3: Fuzzy matching
        fuzzy_match = self._fuzzy_match(normalized_label)
        if fuzzy_match:
            field, score, match_type = fuzzy_match
            logger.debug("✅ Fuzzy match: '%s' -> %s (score=%.1f, type=%s)", 
                        label, field, score, match_type)
            return field
        
        # No match found
        logger.debug("❌ No match found for label: '%s' (normalized: '%s')", label, normalized_label)
        return None
    
    def _fuzzy_match(self, normalized_label: str) -> Optional[Tuple[str, float, str]]:
        """
        Perform fuzzy matching using rapidfuzz or difflib.
        
        Returns:
            Tuple of (field, score, match_type) if match found, None otherwise
        """
        best_match: Optional[Tuple[str, float, str]] = None
        best_score = 0.0
        
        # Try each canonical field and its aliases
        for field, alias_list in self.aliases.items():
            for alias in alias_list:
                normalized_alias = _normalize_for_matching(alias)
                
                if not normalized_alias:
                    continue
                
                # Calculate similarity scores
                if RAPIDFUZZ_AVAILABLE:
                    # Use rapidfuzz (faster and more accurate)
                    token_sort_score = fuzz.token_sort_ratio(normalized_label, normalized_alias)
                    partial_score = fuzz.partial_ratio(normalized_label, normalized_alias)
                    token_set_score = fuzz.token_set_ratio(normalized_label, normalized_alias)
                    
                    # Use the best score
                    score = max(token_sort_score, partial_score, token_set_score)
                    match_type = "token_sort" if token_sort_score == score else \
                                "partial" if partial_score == score else "token_set"
                else:
                    # Fallback to difflib
                    from difflib import SequenceMatcher
                    matcher = SequenceMatcher(None, normalized_label, normalized_alias)
                    score = matcher.ratio() * 100
                    match_type = "sequence"
                
                # Check thresholds
                if RAPIDFUZZ_AVAILABLE:
                    # Use token_sort_ratio ≥ 85 OR partial_ratio ≥ 90
                    token_sort_ok = token_sort_score >= self.fuzzy_threshold
                    partial_ok = partial_score >= self.partial_threshold
                    
                    if not (token_sort_ok or partial_ok):
                        continue
                else:
                    # For difflib, use 85% threshold
                    if score < self.fuzzy_threshold:
                        continue
                
                # Update best match if this is better
                if score > best_score:
                    best_score = score
                    best_match = (field, score, match_type)
                elif score == best_score:
                    # Tie-breaker: use field priority
                    current_priority = FIELD_PRIORITY.get(field, 0)
                    best_priority = FIELD_PRIORITY.get(best_match[0], 0) if best_match else 0
                    if current_priority > best_priority:
                        best_match = (field, score, match_type)
        
        return best_match
    
    def match_with_confidence(self, label: str) -> Optional[Tuple[str, float]]:
        """
        Match a label and return the field with confidence score.
        
        Returns:
            Tuple of (field, confidence_score) where confidence is 0-100
        """
        if not label or not isinstance(label, str):
            return None
        
        normalized_label = _normalize_for_matching(label)
        
        if not normalized_label:
            return None
        
        # Exact match = 100% confidence
        if normalized_label in self.exact_map:
            return (self.exact_map[normalized_label], 100.0)
        
        # Alias match = 95% confidence
        if normalized_label in self.alias_map:
            field, _ = self.alias_map[normalized_label]
            return (field, 95.0)
        
        # Fuzzy match = score as confidence
        fuzzy_match = self._fuzzy_match(normalized_label)
        if fuzzy_match:
            field, score, _ = fuzzy_match
            return (field, score)
        
        return None


def match_label_to_field(label: str, aliases: Dict[str, List[str]] = None) -> Optional[str]:
    """
    Convenience function to match a label to a canonical field.
    
    Args:
        label: The label text from the financial statement
        aliases: Optional custom alias dictionary (uses default if None)
        
    Returns:
        Canonical field name if match found, None otherwise
    """
    matcher = AdvancedLabelMatcher(aliases=aliases)
    return matcher.match(label)

