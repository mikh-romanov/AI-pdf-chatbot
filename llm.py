import os
import sys

from dotenv import load_dotenv

ENV_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env")

load_dotenv(ENV_FILE)

PROVIDERS = ("openrouter", "anthropic", "gemini")

OPENROUTER_MODEL = "qwen/qwen3.8-27b:free"  # free tier; "inclusionai/ling-3.0-flash-vl" is the paid model used before
ANTHROPIC_MODEL = "claude-sonnet-4-6"
GEMINI_MODEL = "gemini-1.5-flash"

RATE_LIMIT_MESSAGE = "The free model is currently rate-limited. Please try again"
ERROR_MESSAGE = "Something went wrong..."


def default_settings():
    """Provider and key from .env, or None for anything that is not set."""
    provider = (os.getenv("LLM_PROVIDER") or "").strip().lower() or None
    api_key = os.getenv(f"{provider.upper()}_API_KEY") if provider else None
    return provider, api_key

#check this function for logic errors

def remember_settings(provider, api_key):
    """Write the provider and its key to .env, keeping every other line of the file.

    .env is listed in .gitignore, so the key stays on this machine.
    """
    key_name = f"{provider.upper()}_API_KEY"
    wanted = {"LLM_PROVIDER": provider, key_name: api_key}

    try:
        with open(ENV_FILE, encoding="utf-8") as f:
            lines = f.read().splitlines()
    except FileNotFoundError:
        lines = []

    kept = []
    for line in lines:
        name = line.split("=", 1)[0].strip()
        if name in wanted:
            kept.append(f"{name}={wanted.pop(name)}")   # replace in place
        else:
            kept.append(line)
    kept += [f"{name}={value}" for name, value in wanted.items()]   # whatever was not in the file

    with open(ENV_FILE, "w", encoding="utf-8") as f:
        f.write("\n".join(kept).strip() + "\n")

    os.environ.update({"LLM_PROVIDER": provider, key_name: api_key})


def _prompt(question):
    """Ask in the terminal. Quit cleanly if there is nothing to read (Ctrl+D, or piped input)."""
    try:
        return input(question).strip()
    except EOFError:
        raise SystemExit("\nNo answer given, quitting.")


def get_provider_and_key():
    """Provider and key for the terminal version, asking until both are usable."""
    provider, api_key = default_settings()

    if provider and provider not in PROVIDERS:
        print(f"LLM_PROVIDER in .env is {provider!r}, which is not supported.")
        provider, api_key = None, None

    while provider not in PROVIDERS:
        provider = _prompt(f"Which provider? ({'/'.join(PROVIDERS)}): ").lower()
        if provider not in PROVIDERS:
            print(f"Please type one of: {', '.join(PROVIDERS)}")
            continue
        api_key = os.getenv(f"{provider.upper()}_API_KEY")

    while not api_key:
        api_key = _prompt(f"Enter your {provider} API key: ")
        if not api_key:
            print("The key can't be empty. Press Ctrl+C to quit.")

    return provider, api_key


def _error_text(e):
    print(f"LLM request failed: {type(e).__name__}: {e}", file=sys.stderr)
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
