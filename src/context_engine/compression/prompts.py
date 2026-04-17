"""Summarization prompt templates for different chunk types."""

CODE_PROMPT: str = "Summarize this code. Include: function/class name, purpose, inputs/outputs, key side effects. Be concise (2-3 sentences max).\n\nCode:\n{content}"

DECISION_PROMPT: str = "Summarize this decision. Include: what was decided, why, and what the outcome/action was. One paragraph max.\n\nDecision:\n{content}"

ARCHITECTURE_PROMPT: str = "Summarize this component. Include: what it does, its role in the system, and its key dependencies. Be concise (2-3 sentences).\n\nComponent:\n{content}"

DOC_PROMPT: str = "Summarize this documentation. Keep the key information, remove boilerplate. Be concise.\n\nDocumentation:\n{content}"
