"""Query understanding — intent classification and keyword extraction."""
import re
from dataclasses import dataclass, field
from enum import Enum


class QueryIntent(Enum):
    CODE_LOOKUP = "code_lookup"
    DECISION_RECALL = "decision_recall"
    ARCHITECTURE = "architecture"
    GENERAL = "general"


_DECISION_PATTERNS = [
    r"what did we decide",
    r"decision about",
    r"why did we",
    r"last session",
    r"previous discussion",
    r"agreed on",
]
_ARCHITECTURE_PATTERNS = [
    r"how is .+ structured",
    r"architecture",
    r"module.+structure",
    r"component.+design",
    r"how does .+ work",
    r"overview of",
    r"explain the .+ system",
]
_CODE_PATTERNS = [
    r"find .+ function",
    r"show me .+ class",
    r"where is .+ defined",
    r"implementation of",
    r"\.py|\.js|\.ts",
    r"function|class|method|def |import ",
]
_FILE_PATH_RE = re.compile(r"[a-zA-Z0-9_./-]+\.[a-zA-Z]{1,10}")
# Natural-language stop words we always strip.
_STOP_WORDS = {
    "the", "a", "an", "is", "are", "was", "were", "do", "does", "did",
    "what", "how", "why", "where", "when", "who", "which",
    "in", "on", "at", "to", "for", "of", "with", "about",
    "me", "my", "we", "our", "it", "its", "i", "you",
    "tell", "give",
}
# Code-flavoured words that look like stop words in prose ("show me get
# functions") but are critical naming prefixes in code. Strip them when the
# intent is conversational, keep them when the intent is code lookup so
# `getUser` / `set_config` / `find_by_id` matches survive keyword extraction.
_CODE_PREFIX_WORDS = {"show", "find", "get", "set", "fetch", "save", "validate", "create", "update", "delete"}


@dataclass
class ParsedQuery:
    original: str
    intent: QueryIntent
    keywords: list[str] = field(default_factory=list)
    file_hints: list[str] = field(default_factory=list)


class QueryParser:
    def parse(self, query: str) -> ParsedQuery:
        lower = query.lower()
        intent = self._classify_intent(lower)
        keywords = self._extract_keywords(query, intent=intent)
        file_hints = _FILE_PATH_RE.findall(query)
        return ParsedQuery(
            original=query, intent=intent, keywords=keywords, file_hints=file_hints
        )

    def _classify_intent(self, query: str) -> QueryIntent:
        for p in _DECISION_PATTERNS:
            if re.search(p, query):
                return QueryIntent.DECISION_RECALL
        for p in _ARCHITECTURE_PATTERNS:
            if re.search(p, query):
                return QueryIntent.ARCHITECTURE
        for p in _CODE_PATTERNS:
            if re.search(p, query):
                return QueryIntent.CODE_LOOKUP
        return QueryIntent.GENERAL

    def _extract_keywords(
        self, query: str, intent: QueryIntent = QueryIntent.GENERAL
    ) -> list[str]:
        identifiers = re.findall(r"[A-Z][a-zA-Z0-9]+", query)
        words = re.findall(r"[a-zA-Z_][a-zA-Z0-9_]*", query)
        # For code-lookup intent, keep prefix words like `get`/`find`/`save`
        # so the user's literal verb survives into FTS keyword scoring.
        stop_words = (
            _STOP_WORDS if intent == QueryIntent.CODE_LOOKUP
            else _STOP_WORDS | _CODE_PREFIX_WORDS
        )
        meaningful = [
            w for w in words if w.lower() not in stop_words and len(w) > 2
        ]
        seen = set()
        result = []
        for kw in identifiers + meaningful:
            if kw not in seen:
                seen.add(kw)
                result.append(kw)
        return result
