from unittest.mock import patch

import pytest

from multilingual_overlay.ocr import OcrError, recognize_lines


def test_recognize_lines_filters_low_confidence_words() -> None:
    data = {
        "text": ["Copilot", "noise", "Chat", "window"],
        "conf": ["92", "12", "80", "72"],
        "block_num": [1, 1, 1, 1],
        "par_num": [1, 1, 1, 1],
        "line_num": [1, 1, 2, 2],
    }
    with patch("multilingual_overlay.ocr.pytesseract.image_to_data", return_value=data) as ocr:
        assert recognize_lines(object()) == ("Copilot", "Chat window")
    ocr.assert_called_once_with(
        ocr.call_args.args[0],
        lang="eng+jpn",
        output_type="dict",
        timeout=8,
    )


def test_recognize_lines_reports_tesseract_timeout() -> None:
    with patch(
        "multilingual_overlay.ocr.pytesseract.image_to_data",
        side_effect=RuntimeError("timeout"),
    ), pytest.raises(OcrError, match="8秒"):
        recognize_lines(object())
