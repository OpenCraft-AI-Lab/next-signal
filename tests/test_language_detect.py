"""Coverage for the deterministic, non-LLM source-language detector.

No mocks, no fixtures beyond plain strings — this is a pure function, and the
whole point of it being deterministic is that a real call is as cheap and
repeatable as a mocked one.
"""

from __future__ import annotations

from next_signal.core.language_detect import detect_language


def test_chinese_dominant_text_detects_zh() -> None:
    assert detect_language("这是一篇关于人工智能的中文文章,介绍了最新的技术进展。") == "zh"


def test_english_dominant_text_detects_en() -> None:
    assert detect_language(
        "This is an English-language article about recent progress in AI systems."
    ) == "en"


def test_empty_string_falls_back_to_en() -> None:
    assert detect_language("") == "en"


def test_pure_code_or_punctuation_falls_back_to_en() -> None:
    assert detect_language("```{}[]();,.<>/\\1234567890```") == "en"


def test_a_few_chinese_proper_nouns_in_english_text_stays_en() -> None:
    """A handful of CJK proper nouns shouldn't flip an otherwise-English text."""
    text = (
        "OpenAI and 百度 both announced new models this week, alongside "
        "DeepSeek and 阿里巴巴, in a fast-moving week for the industry overall "
        "with many English sentences describing the announcements in detail."
    )
    assert detect_language(text) == "en"


def test_a_few_english_proper_nouns_in_chinese_text_stays_zh() -> None:
    text = (
        "OpenAI 和百度本周都发布了新模型,同时 DeepSeek 和阿里巴巴也有动作,"
        "这是行业内非常忙碌的一周,中文媒体对此进行了详细的报道和分析。"
    )
    assert detect_language(text) == "zh"


def test_deterministic_across_repeated_calls() -> None:
    text = "混合 mixed 内容 content 测试 test"
    results = {detect_language(text) for _ in range(20)}
    assert len(results) == 1


def test_title_only_input_is_enough_signal() -> None:
    """Detection is designed to run primarily against short titles."""
    assert detect_language("深度学习模型的最新突破") == "zh"
    assert detect_language("Breakthrough in Deep Learning Models") == "en"
