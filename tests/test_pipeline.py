from multilingual_overlay.pipeline import RetryBackoff, StableText, TranslationMemory


def test_retry_backoff_grows_and_resets() -> None:
    retry = RetryBackoff(initial_seconds=2, maximum_seconds=8)
    assert retry.ready(0)
    retry.failed(0)
    assert not retry.ready(1.9)
    assert retry.ready(2)
    retry.failed(2)
    assert not retry.ready(5.9)
    assert retry.ready(6)
    retry.failed(6)
    retry.failed(14)
    assert not retry.ready(21.9)
    assert retry.ready(22)
    retry.succeeded()
    assert retry.ready(0)


def test_stable_text_requires_repeat_and_debounce() -> None:
    state = StableText(debounce_seconds=1.0)
    assert not state.observe(("Hello",), 0.0)
    assert not state.observe(("Hello",), 0.5)
    assert state.observe(("Hello",), 1.0)
    assert state.candidate == ("Hello",)


def test_stable_text_restarts_when_ocr_changes() -> None:
    state = StableText(debounce_seconds=0.0)
    assert not state.observe(("Hello",), 0.0)
    assert not state.observe(("Hello", "World"), 0.1)
    assert state.observe(("Hello", "World"), 0.2)


def test_translation_memory_sends_only_new_lines_and_reuses_cache() -> None:
    memory = TranslationMemory()
    sent: list[list[str]] = []

    def translate(lines: list[str]) -> list[str]:
        sent.append(lines)
        return [f"ja:{line}" for line in lines]

    assert memory.translate(("Hello", "World"), translate) == ("ja:Hello", "ja:World")
    assert memory.translate(("Hello", "There"), translate) == ("ja:Hello", "ja:There")
    assert sent == [["Hello", "World"], ["There"]]


def test_translation_memory_is_bounded() -> None:
    memory = TranslationMemory(capacity=2)
    memory.translate(("one", "two", "three"), lambda lines: [line.upper() for line in lines])
    sent: list[list[str]] = []
    memory.translate(("one",), lambda lines: sent.append(lines) or [line.upper() for line in lines])
    assert sent == [["one"]]
