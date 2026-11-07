"""OCR stability, line-level change detection, and bounded translation memory."""

from collections import OrderedDict
from collections.abc import Callable


class RetryBackoff:
    def __init__(self, initial_seconds: float = 2, maximum_seconds: float = 30) -> None:
        self.initial_seconds = initial_seconds
        self.maximum_seconds = maximum_seconds
        self._delay = initial_seconds
        self._retry_at = 0.0

    def ready(self, now: float) -> bool:
        return now >= self._retry_at

    def failed(self, now: float) -> None:
        self._retry_at = now + self._delay
        self._delay = min(self._delay * 2, self.maximum_seconds)

    def succeeded(self) -> None:
        self._delay = self.initial_seconds
        self._retry_at = 0.0


class TranslationMemory:
    def __init__(self, capacity: int = 512) -> None:
        self.capacity = capacity
        self._translations: OrderedDict[str, str] = OrderedDict()

    def translate(
        self, lines: tuple[str, ...], translate_missing: Callable[[list[str]], list[str]]
    ) -> tuple[str, ...]:
        missing = list(dict.fromkeys(line for line in lines if line not in self._translations))
        current: dict[str, str] = {}
        for line in lines:
            if line in self._translations:
                current[line] = self._translations[line]
                self._translations.move_to_end(line)

        if missing:
            results = translate_missing(missing)
            if len(results) != len(missing):
                raise RuntimeError("Translation service returned an unexpected result count.")
            for source, translated in zip(missing, results):
                current[source] = translated
                self._translations[source] = translated
                self._translations.move_to_end(source)
            while len(self._translations) > self.capacity:
                self._translations.popitem(last=False)

        return tuple(current[line] for line in lines)


class StableText:
    """Require repeated identical OCR and a quiet period before translation."""

    def __init__(self, debounce_seconds: float = 0.8) -> None:
        self.debounce_seconds = debounce_seconds
        self._candidate: tuple[str, ...] | None = None
        self._first_seen = 0.0
        self._samples = 0

    def observe(self, lines: tuple[str, ...], now: float) -> bool:
        if lines != self._candidate:
            self._candidate = lines
            self._first_seen = now
            self._samples = 1
            return False
        self._samples += 1
        return self._samples >= 2 and now - self._first_seen >= self.debounce_seconds

    @property
    def candidate(self) -> tuple[str, ...]:
        return self._candidate or ()
