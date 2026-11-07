"""DeepL translation API adapter."""

from typing import Literal

import requests

ApiPlan = Literal["free", "pro"]
API_HOSTS: dict[ApiPlan, str] = {
    "free": "https://api-free.deepl.com",
    "pro": "https://api.deepl.com",
}


class TranslationError(RuntimeError):
    """A safe-to-display error that never includes request credentials."""


def translate_lines(lines: list[str], api_key: str, plan: ApiPlan) -> list[str]:
    if not lines:
        return []
    if not api_key.strip():
        raise TranslationError("DeepL APIキーを入力するか、DEEPL_AUTH_KEYを設定してください。")
    if plan not in API_HOSTS:
        raise TranslationError("対応しているDeepLプランを選択してください。")

    translated: list[str] = []
    try:
        for offset in range(0, len(lines), 50):
            batch = lines[offset : offset + 50]
            response = requests.post(
                f"{API_HOSTS[plan]}/v2/translate",
                headers={"Authorization": f"DeepL-Auth-Key {api_key.strip()}"},
                json={"text": batch, "target_lang": "JA"},
                timeout=20,
            )
            response.raise_for_status()
            result = response.json()
            results = result.get("translations", [])
            if len(results) != len(batch):
                raise TranslationError("DeepLから不完全な翻訳結果が返されました。")
            translated.extend(str(item["text"]) for item in results)
    except TranslationError:
        raise
    except requests.RequestException as error:
        status = getattr(getattr(error, "response", None), "status_code", None)
        if status:
            raise TranslationError(
                f"DeepLリクエストに失敗しました（HTTP {status}）。APIキー、プラン、ネットワークを確認してください。"
            ) from None
        raise TranslationError("DeepLに接続できません。ネットワーク接続を確認してください。") from None
    except (ValueError, TypeError, KeyError):
        raise TranslationError("DeepLから無効な応答が返されました。") from None
    return translated
