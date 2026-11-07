from unittest.mock import patch

from multilingual_overlay.ocr import recognize_lines


def test_recognize_lines_filters_low_confidence_words() -> None:
    data = {
        "text": ["Copilot", "noise", "Chat", "window"],
        "conf": ["92", "12", "80", "72"],
        "block_num": [1, 1, 1, 1],
        "par_num": [1, 1, 1, 1],
        "line_num": [1, 1, 2, 2],
    }
    with patch("multilingual_overlay.ocr.pytesseract.image_to_data", return_value=data):
        assert recognize_lines(object()) == ("Copilot", "Chat window")
