"""Утилиты для подсчета токенов и стоимости вызовов LLM."""

from __future__ import annotations

import logging
from typing import Any, Dict, Iterable, List, Optional

import tiktoken

logger = logging.getLogger(__name__)


# Стоимость указана в долларах США за 1000 токенов.
MODEL_PRICING_PER_1K = {
    "gpt-4.1-mini": {"prompt": 0.00015, "completion": 0.00060},
    # Версионные алиасы используют ту же стоимость, что и базовая модель.
    "gpt-4.1-mini-2025-04-14": {"prompt": 0.00015, "completion": 0.00060},
}


def _normalise_model_name(model: str) -> str:
    """Пытается сопоставить модель с известным тарифным планом."""
    if model in MODEL_PRICING_PER_1K:
        return model

    # Некоторые модели имеют постфикс даты. Отбрасываем его и повторяем поиск.
    if "-" in model:
        base = model.split("-", maxsplit=1)[0]
        if base in MODEL_PRICING_PER_1K:
            return base

    return model


def _get_encoding(model: str):
    """Возвращает tiktoken-энкодер для указанной модели."""
    normalised = _normalise_model_name(model)
    try:
        return tiktoken.encoding_for_model(normalised)
    except KeyError:
        # Базовый энкодер подходит для большинства современных моделей OpenAI.
        return tiktoken.get_encoding("cl100k_base")


def _extract_text_parts(message_content: Any) -> Iterable[str]:
    """Извлекает только текстовые фрагменты из контента сообщения."""
    if message_content is None:
        return []

    if isinstance(message_content, str):
        return [message_content]

    if isinstance(message_content, list):
        texts: List[str] = []
        for part in message_content:
            if isinstance(part, dict) and part.get("type") == "text" and part.get("text"):
                texts.append(part["text"])
        return texts

    return []


def count_prompt_tokens(model: str, messages: List[Dict[str, Any]]) -> int:
    """Оценивает количество токенов во входных сообщениях."""
    encoding = _get_encoding(model)
    total_tokens = 0

    for message in messages:
        content_parts = _extract_text_parts(message.get("content"))
        for part in content_parts:
            total_tokens += len(encoding.encode(part))

        # Добавляем небольшую поправку за роль и структуру сообщения.
        total_tokens += 4

    return total_tokens


def count_completion_tokens(model: str, completion_text: Optional[str]) -> int:
    """Подсчитывает токены в ответе LLM."""
    if not completion_text:
        return 0

    encoding = _get_encoding(model)
    return len(encoding.encode(completion_text))


def calculate_cost_usd(model: str, prompt_tokens: int, completion_tokens: int) -> Optional[float]:
    """Вычисляет стоимость запроса на основе количества токенов."""
    normalised = _normalise_model_name(model)
    pricing = MODEL_PRICING_PER_1K.get(normalised)

    if not pricing:
        logger.warning("Не удалось найти тариф для модели %s", model)
        return None

    prompt_cost = (prompt_tokens / 1000) * pricing["prompt"]
    completion_cost = (completion_tokens / 1000) * pricing["completion"]

    return round(prompt_cost + completion_cost, 6)


def log_chat_completion_usage(
    model: str,
    messages: List[Dict[str, Any]],
    completion: Any,
    logger_instance: logging.Logger = logger,
) -> Dict[str, Optional[float]]:
    """Логирует токены и стоимость вызова chat completion."""

    prompt_tokens = count_prompt_tokens(model, messages)
    completion_tokens = None
    total_tokens = None

    usage = getattr(completion, "usage", None)
    if usage:
        prompt_tokens = getattr(usage, "prompt_tokens", prompt_tokens) or prompt_tokens
        completion_tokens = getattr(usage, "completion_tokens", None)
        total_tokens = getattr(usage, "total_tokens", None)

    if completion_tokens is None:
        # Пробуем вычислить по тексту ответа.
        message = completion.choices[0].message if completion.choices else None
        completion_text = getattr(message, "content", None)
        if isinstance(completion_text, list):
            completion_text = "\n".join(
                part.get("text", "") for part in completion_text if isinstance(part, dict)
            )
        completion_tokens = count_completion_tokens(model, completion_text)

    if total_tokens is None and completion_tokens is not None:
        total_tokens = prompt_tokens + completion_tokens

    cost = calculate_cost_usd(model, prompt_tokens, completion_tokens or 0)

    logger_instance.info(
        "LLM вызов %s: prompt_tokens=%s, completion_tokens=%s, total_tokens=%s, cost=%s",
        model,
        prompt_tokens,
        completion_tokens,
        total_tokens,
        f"${cost}" if cost is not None else "n/a",
    )

    return {
        "prompt_tokens": int(prompt_tokens),
        "completion_tokens": int(completion_tokens or 0),
        "total_tokens": int(total_tokens or prompt_tokens),
        "cost_usd": cost,
    }
