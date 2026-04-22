from deep_translator import DeeplTranslator, GoogleTranslator, LibreTranslator
import httpx
from .utils import get_config
from openrouter import OpenRouter


def _call_google(text: str, src: str, tgt: str) -> dict:
    try:
        res = GoogleTranslator(source=src, target=tgt).translate(text)
        return {"api": "Google", "translation": res, "error": None}
    except Exception as exc:
        return {"api": "Google", "translation": None, "error": str(exc)}


def _call_deepl(text: str, src: str, tgt: str) -> dict:
    DEEPL_API_KEY = get_config("DEEPL_API_KEY", "")
    try:
        if not DEEPL_API_KEY:
            return {
                "api": "DeepL",
                "translation": None,
                "error": "No DeepL API key configured",
            }
        res = DeeplTranslator(
            api_key=DEEPL_API_KEY, source=src, target=tgt, use_free_api=True
        ).translate(text)
        return {"api": "DeepL", "translation": res, "error": None}
    except Exception as exc:
        return {"api": "DeepL", "translation": None, "error": str(exc)}


def _call_libre(text: str, src: str, tgt: str) -> dict:
    LIBRE_API_KEY = get_config("LIBRE_API_KEY", "")
    try:
        kwargs = {"source": src, "target": tgt}
        if LIBRE_API_KEY:
            kwargs["api_key"] = LIBRE_API_KEY
        else:
            kwargs["api_key"] = "none"
            kwargs["use_free_api"] = True
        if libre_url := get_config("LIBRE_URL", ""):
            kwargs["custom_url"] = libre_url

        res = LibreTranslator(**kwargs).translate(text)
        return {"api": "LibreTranslate", "translation": res, "error": None}
    except Exception as exc:
        return {"api": "LibreTranslate", "translation": None, "error": str(exc)}


def _call_mymemory(text: str, src: str, tgt: str) -> dict:
    try:
        resp = httpx.get(
            "https://api.mymemory.translated.net/get",
            params={"q": text, "langpair": f"{src}|{tgt}"},
            timeout=10,
        )
        data = resp.json()
        if data.get("responseStatus") == 200:
            return {
                "api": "MyMemory",
                "translation": data["responseData"]["translatedText"],
                "error": None,
            }
        return {
            "api": "MyMemory",
            "translation": None,
            "error": "API returned an error",
        }
    except Exception as exc:
        return {"api": "MyMemory", "translation": None, "error": str(exc)}


def _call_llm(prompt: str) -> bool:
    # use openrouter api
    client = OpenRouter(api_key=get_config("OPENROUTER_API_KEY", ""))
    response = client.chat.completions.create(
        model="google/gemini-2.5-flash-lite",
        messages=[
            {
                "role": "user",
                "content": prompt + "\n\nOutput only pass or fail and nothing else",
            }
        ],
    )
    text = response.choices[0].message.content.lower()
    if "pass" in text and "fail" in text:
        raise ValueError(f"Invalid LLM response: {text}")
    else:
        return "pass" in text
