import os
from dotenv import load_dotenv

load_dotenv()

PROVIDERS = ("openrouter", "anthropic", "gemini")

OPENROUTER_MODEL = "ling-3.0-flash-vl:free"
ANTHROPIC_MODEL = "claude-sonnet-4-6"
GEMINI_MODEL = "gemini-1.5-flash"

RATE_LIMIT_MESSAGE = "The free model is currently rate-limited. Please try again"
ERROR_MESSAGE = "Something went wrong..."


def default_settings():
    """Provider and key from .env, or None for anything that is not set."""
    provider = (os.getenv("LLM_PROVIDER") or "").strip().lower() or None
    api_key = os.getenv(f"{provider.upper()}_API_KEY") if provider else None
    return provider, api_key


def get_provider_and_key():
    provider, api_key = default_settings()
    if not provider:
        provider = input("Which provider? (openrouter/anthropic/gemini): ").strip().lower()
        api_key = os.getenv(f"{provider.upper()}_API_KEY")
    if not api_key:
        api_key = input(f"Enter your {provider} API key: ").strip()

    return provider, api_key


def _error_text(e):
    if '429' in str(e) or 'rate' in str(e).lower():
        return RATE_LIMIT_MESSAGE
    return ERROR_MESSAGE


def ask_llm(prompt, provider, api_key):
    if provider not in PROVIDERS:
        raise ValueError(f"Unknown provider: {provider}")
    if not api_key:
        raise ValueError(f"No API key set for {provider}")

    if provider == 'openrouter':
        from openai import OpenAI
        client = OpenAI(base_url="https://openrouter.ai/api/v1", api_key=api_key)
        try:
            response = client.chat.completions.create(
                model=OPENROUTER_MODEL,
                messages=[{'role': 'user', 'content': prompt}]
            )
            return response.choices[0].message.content
        except Exception as e:
            return _error_text(e)

    elif provider == "anthropic":
        import anthropic
        client = anthropic.Anthropic(api_key=api_key)
        try:
            response = client.messages.create(
                model=ANTHROPIC_MODEL,
                max_tokens=1000,
                messages=[{"role": "user", "content": prompt}]
            )
            return response.content[0].text
        except Exception as e:
            return _error_text(e)

    elif provider == "gemini":
        import google.generativeai as genai
        try:
            genai.configure(api_key=api_key)
            model = genai.GenerativeModel(GEMINI_MODEL)
            return model.generate_content(prompt).text
        except Exception as e:
            return _error_text(e)
