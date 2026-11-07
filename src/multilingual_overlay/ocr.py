"""OCR adapter for converting a captured window image into stable text lines."""

from collections import defaultdict

from PIL import Image
import pytesseract
from pytesseract import Output


def recognize_lines(
    image: Image.Image, language: str = "eng+jpn", minimum_confidence: float = 35
) -> tuple[str, ...]:
    """Return readable OCR lines, discarding low-confidence words."""
    data = pytesseract.image_to_data(image, lang=language, output_type=Output.DICT)
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
