from unittest.mock import Mock, patch

import pytest
import requests

from multilingual_overlay.deepl import TranslationError, translate_lines


@pytest.mark.parametrize(
    ("plan", "host"),
    [
        ("free", "https://api-free.deepl.com/v2/translate"),
        ("pro", "https://api.deepl.com/v2/translate"),
    ],
)
def test_translate_uses_plan_host_and_sends_only_text(plan: str, host: str) -> None:
    response = Mock()
    response.json.return_value = {"translations": [{"text": "こんにちは"}]}
    with patch("multilingual_overlay.deepl.requests.post", return_value=response) as post:
        result = translate_lines(["Hello"], "local-test-key", plan)

    assert result == ["こんにちは"]
    post.assert_called_once_with(
        host,
        headers={"Authorization": "DeepL-Auth-Key local-test-key"},
        json={"text": ["Hello"], "target_lang": "JA"},
        timeout=20,
    )


def test_translate_does_not_send_empty_text() -> None:
    with patch("multilingual_overlay.deepl.requests.post") as post:
        assert translate_lines([], "key", "free") == []
    post.assert_not_called()


def test_translate_requires_key() -> None:
    with pytest.raises(TranslationError, match="APIキー"):
        translate_lines(["Hello"], "", "free")


def test_translate_error_does_not_expose_key() -> None:
    with patch(
        "multilingual_overlay.deepl.requests.post",
        side_effect=requests.ConnectionError("request failed"),
    ):
        with pytest.raises(TranslationError) as error:
            translate_lines(["Hello"], "secret-key", "free")
    assert "secret-key" not in str(error.value)


def test_translate_splits_large_batches() -> None:
    responses = []
    for batch_size in (50, 1):
        response = Mock()
        response.json.return_value = {
            "translations": [{"text": "ja"} for _ in range(batch_size)]
        }
        responses.append(response)
    with patch("multilingual_overlay.deepl.requests.post", side_effect=responses) as post:
        assert len(translate_lines(["text"] * 51, "key", "free")) == 51
    assert post.call_count == 2
