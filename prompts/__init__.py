"""Модуль с промптами для LLM анализа"""

from .system_prompts import (
    EXPERT_DEFECT_ANALYSIS_PROMPT,
    VLM_CLEAN_PROMPT
)

__all__ = [
    "EXPERT_DEFECT_ANALYSIS_PROMPT",
    "VLM_CLEAN_PROMPT"
]