import os
from dotenv import load_dotenv

load_dotenv()

def get_provider_and_key():
    provider = os.getenv("LLM_PROVIDER")
    if not provider:
        provider = input("Which provider? (openrouter/anthropic/gemini): ").strip().lower()

    key_var_name = f"{provider.upper()}_API_KEY"
    api_key = os.getenv(key_var_name)
    if not api_key:
        api_key = input(f"Enter your {provider} API key: ").strip()

    return provider, api_key


PROVIDER, API_KEY = get_provider_and_key()

def ask_llm(prompt):
    if PROVIDER == 'openrouter':
        from openai import OpenAI
        client = OpenAI(base_url="https://openrouter.ai/api/v1", api_key=API_KEY)
        try:
            response = client.chat.completions.create(
                model="ling-3.0-flash-vl:free",
                messages=[{'role': 'user', 'content': prompt}]
            )
            return response.choices[0].message.content
        except Exception as e:
            if '429' in str(e) or 'rate' in str(e).lower():
                return "The free model is currently rate-limited. Please try again"
            else:
                return "Something went wrong..."

    elif PROVIDER == "anthropic":
        import anthropic
        client = anthropic.Anthropic(api_key=API_KEY)
        try:
            response = client.messages.create(
                model="claude-sonnet-4-6",
                max_tokens=1000,
                messages=[{"role": "user", "content": prompt}]
            )
            return response.content[0].text
        except Exception as e:
            if '429' in str(e) or 'rate' in str(e).lower():
                return "The free model is currently rate-limited. Please try again"
            else:
                return "Something went wrong..."

    elif PROVIDER == "gemini":
        import google.generativeai as genai
        genai.configure(api_key=API_KEY)
        model = genai.GenerativeModel("gemini-1.5-flash")
        return model.generate_content(prompt).text

    else:
        raise ValueError(f"Unknown provider: {PROVIDER}")
