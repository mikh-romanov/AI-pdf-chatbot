import os
import sys

from dotenv import load_dotenv

ENV_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env")

load_dotenv(ENV_FILE)

PROVIDERS = ("openrouter", "anthropic", "gemini")

# Starting points only: the model is chosen in the browser and saved to .env per provider.
DEFAULT_MODELS = {
    "openrouter": os.getenv("OPENROUTER_MODEL") or "qwen/qwen3.8-27b:free",
    "anthropic": os.getenv("ANTHROPIC_MODEL") or "claude-sonnet-4-6",
    "gemini": os.getenv("GEMINI_MODEL") or "gemini-3.5-flash-lite",
}

# Gemini lists speech and image models alongside text ones, with no flag telling them apart.
NON_TEXT_MODELS = ("-tts", "-image", "embedding", "nano-banana")

RATE_LIMIT_MESSAGE = "The free model is currently rate-limited. Please try again"
ERROR_MESSAGE = "Something went wrong..."


def default_settings():
    """Provider and key from .env, or None for anything that is not set."""
    provider = (os.getenv("LLM_PROVIDER") or "").strip().lower() or None
    api_key = os.getenv(f"{provider.upper()}_API_KEY") if provider else None
    return provider, api_key


def list_models(provider, api_key):
    """Model ids a provider offers, for the dropdown. Raises if the key is refused.

    OpenRouter's catalogue is the same for everyone, so the key is checked separately;
    Anthropic and Gemini answer per account. Gemini's speech and image models are left out
    because they cannot return a text answer.
    """
    if provider == "openrouter":
        from openai import OpenAI
        client = OpenAI(base_url="https://openrouter.ai/api/v1", api_key=api_key)
        client.get("/key", cast_to=object)   # /models is public, so check the key here
        return sorted(m.id for m in client.models.list())

    if provider == "anthropic":
        import anthropic
        return [m.id for m in anthropic.Anthropic(api_key=api_key).models.list(limit=100)]

    if provider == "gemini":
        import google.generativeai as genai
        genai.configure(api_key=api_key)
        names = [m.name.replace("models/", "") for m in genai.list_models()
                 if "generateContent" in m.supported_generation_methods]
        return [n for n in names if not any(kind in n for kind in NON_TEXT_MODELS)]

    raise ValueError(f"Unknown provider: {provider}")


def remember_settings(provider, api_key, model=None):
    """Write the provider and its key to .env, keeping every other line of the file.

    .env is listed in .gitignore, so the key stays on this machine.
    """
    key_name = f"{provider.upper()}_API_KEY"
    wanted = {"LLM_PROVIDER": provider, key_name: api_key}
    if model:
        wanted[f"{provider.upper()}_MODEL"] = model

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
    if model:
        os.environ[f"{provider.upper()}_MODEL"] = model


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


TITLE_PROMPT = (
    "Give this conversation a title of at most 5 words, naming its subject. "
    "Reply with the title alone: no quotation marks, no final period, no explanation.\n\n"
    "Question: {question}\nAnswer: {answer}"
)


def suggest_title(question, answer, provider, api_key, model=None):
    """A short title for a chat, or None if the model can't supply a usable one."""
    prompt = TITLE_PROMPT.format(question=question[:500], answer=answer[:1000])
    title = ask_llm(prompt, provider, api_key, model)
    if not title or title in (RATE_LIMIT_MESSAGE, ERROR_MESSAGE):
        return None
    title = title.strip().strip('"\'').rstrip(".").strip()
    title = " ".join(title.split())          # the model sometimes answers over several lines
    return title[:60] or None


def _error_text(e):
    print(f"LLM request failed: {type(e).__name__}: {e}", file=sys.stderr)
    if '429' in str(e) or 'rate' in str(e).lower():
        return RATE_LIMIT_MESSAGE
    return ERROR_MESSAGE


def ask_llm(prompt, provider, api_key, model=None):
    if provider not in PROVIDERS:
        raise ValueError(f"Unknown provider: {provider}")
    if not api_key:
        raise ValueError(f"No API key set for {provider}")
    model = model or DEFAULT_MODELS[provider]

    if provider == 'openrouter':
        from openai import OpenAI
        client = OpenAI(base_url="https://openrouter.ai/api/v1", api_key=api_key)
        try:
            response = client.chat.completions.create(
                model=model,
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
                model=model,
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
            gemini = genai.GenerativeModel(model)
            return gemini.generate_content(prompt).text
        except Exception as e:
            return _error_text(e)
