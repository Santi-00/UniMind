# Contributing to UniMind

Thanks for your interest! UniMind is a local-first study assistant, so a few principles guide every change:

1. **Local only.** No cloud AI APIs, no telemetry, no external services. The backend talks only to the user's own Ollama.
2. **Never fake AI.** If Ollama is unavailable, show a clear error. Never return invented results.
3. **Never lose user data.** Database changes must be additive migrations (see `backend/app/database.py`).
4. **Be honest about limits.** If something cannot work, say so in the UI and the docs.

## Setup
Follow the Quick start in the README. Backend API docs are at http://127.0.0.1:8000/docs.

## Good first contributions
- **Translations.** The interface (`frontend/src/pages/*.tsx`) and the AI prompts (`backend/app/lessons.py`, `tutor.py`, `quizzes.py`, `plans.py`, `rag.py`) are currently in Italian. Making the language configurable would open UniMind to many more students.
- Automated tests (backend with pytest, frontend with Vitest).
- Local OCR integration for scanned PDFs, including math.
- Support for more file formats.

## Pull requests
Keep them small and focused, describe what you tested by hand (see `TESTS.md`), and note any limitation.
