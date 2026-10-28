# AI PDF Chatbot

Ask questions about your PDF files and get answers that show the pages they came from.

Upload one or more PDFs, ask anything about them, and each answer lists the pages it used — hover
a page label to read the exact text the answer was built on. Chats are kept separate, each with its
own documents, and everything is saved on your computer.

The app runs on your own machine and talks to an AI provider of your choice (OpenRouter, Anthropic
or Google Gemini) using **your** API key.

## What you need

- **Python 3.11 or newer** (developed on 3.13). Check with `python3 --version`.
- **An API key** from one provider — see [Getting an API key](#getting-an-api-key).

## Install

```bash
git clone https://github.com/mikh-romanov/AI-pdf-chatbot.git
cd AI-pdf-chatbot
python3 -m venv venv
venv/bin/pip install -r requirements.txt
```

The last step downloads a few hundred megabytes, mostly the search engine, so give it a minute.

## Run

```bash
venv/bin/uvicorn app:app --port 8000
```

Wait for `Application startup complete`, then open **http://127.0.0.1:8000** in your browser.
Keep the terminal window open — the site works only while the server runs. Press `Ctrl+C` to stop it.

Opening `static/index.html` directly does not work: the page needs the server behind it.

## First use

1. In the sidebar, open **Model** and choose a provider.
2. Paste your API key and press **Save key**. It is written to a local `.env` file, so you only do
   this once.
3. Pick a model from the dropdown, which lists what your key can use.
4. Press **Add PDF**, or drop a file onto the page.
5. Ask a question. The answer appears with the pages it came from; hover one to see the source text.

Use **New chat** for a different set of documents. Each chat searches only its own PDFs.

## Getting an API key

| Provider | Where | Notes |
|---|---|---|
| **Google Gemini** | [aistudio.google.com/apikey](https://aistudio.google.com/apikey) | Has a free tier, limited to a few requests per minute |
| **OpenRouter** | [openrouter.ai/keys](https://openrouter.ai/keys) | Offers free models, which are often busy; paid models need credit |
| **Anthropic** | [console.anthropic.com](https://console.anthropic.com/settings/keys) | Paid |

Your key stays on your computer, in `.env`, which git ignores. It is never sent anywhere except to
the provider you chose.

## Where your data lives

| | |
|---|---|
| `.env` | Your provider, API key and chosen model |
| `data/chats.json` | Chats, their questions and answers |
| `data/chroma/` | The searchable text taken from your PDFs |

Both are ignored by git and never leave your machine. The PDF files themselves are not kept — only
their text is indexed — so the app cannot show you the original document. Deleting the `data` folder
resets the app to empty.

## Using it from the terminal

`chatbot.py` runs the same question-answering without the website, against
`ai-pdf-chatbot-test.pdf`:

```bash
venv/bin/python chatbot.py
```

It asks for a provider and key if your `.env` has none, then takes questions until you type `exit`.

## If something goes wrong

**"address already in use"** — another server is already on port 8000:

```bash
pkill -f "uvicorn app:app"
```

Or run yours on a different port with `--port 8001` and open that address instead.

**The page looks stale, or the model dropdown stays empty** — reload with `Cmd+Shift+R`
(`Ctrl+F5` on Windows). If it still fails, check that the server terminal is still running.

**"The free model is currently rate-limited"** — free models are shared and get busy. Wait a moment,
pick a different model in the sidebar, or use a paid one.

**A question fails for another reason** — the terminal running the server prints a line starting
`LLM request failed:` with the provider's own message, which says what actually happened.

**A chosen model returns an error** — provider lists sometimes include models your key cannot use.
Pick another from the dropdown.

## How it works

1. **Reading** — `chatbot.py` pulls the text out of each PDF with PyMuPDF and cuts it into
   800-character pieces, remembering the page each piece came from.
2. **Storing** — the pieces go into a Chroma search index, tagged with their chat, so chats stay
   separate.
3. **Answering** — your question finds the five closest pieces, which are sent to the model as
   context along with the recent questions and answers of that chat, so follow-up questions work.
4. **Showing** — the answer comes back with the file and page of every piece used, which is what the
   page labels and their hover text show.

| File | What it does |
|---|---|
| `app.py` | The web server and its API |
| `chatbot.py` | Reading PDFs, searching them, asking the model |
| `chats.py` | Saving chats to disk |
| `llm.py` | Talking to OpenRouter, Anthropic and Gemini |
| `static/` | The web page: `index.html`, `style.css`, `app.js` |
