"""OCR adapter for converting a captured window image into stable text lines."""

from collections import defaultdict

from PIL import Image
import pytesseract
from pytesseract import Output


class OcrError(RuntimeError):
    """A safe-to-display OCR failure."""


def recognize_lines(
    image: Image.Image,
    language: str = "eng+jpn",
    minimum_confidence: float = 35,
    timeout_seconds: float = 8,
) -> tuple[str, ...]:
    """Return readable OCR lines, discarding low-confidence words."""
    try:
        data = pytesseract.image_to_data(
            image, lang=language, output_type=Output.DICT, timeout=timeout_seconds
        )
    except pytesseract.TesseractNotFoundError:
        raise OcrError("Tesseractが見つかりません。PATHとインストール状態を確認してください。") from None
    except pytesseract.TesseractError:
        raise OcrError("OCRに失敗しました。eng/jpn言語データを確認してください。") from None
    except RuntimeError:
        raise OcrError(f"OCRが{timeout_seconds:g}秒でタイムアウトしました。") from None

    grouped: dict[tuple[int, int, int], list[str]] = defaultdict(list)

    for index, word in enumerate(data["text"]):
        word = word.strip()
        if not word:
            continue
        try:
            confidence = float(data["conf"][index])
        except (ValueError, TypeError):
            continue
        if confidence < minimum_confidence:
            continue
        key = (
            int(data["block_num"][index]),
            int(data["par_num"][index]),
            int(data["line_num"][index]),
        )
        grouped[key].append(word)

    return tuple(" ".join(words) for words in grouped.values())
