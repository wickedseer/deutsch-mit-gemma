# Deutsch mit Gemma!

A German speaking partner for A1-A2 learners, built on the open-weight **Gemma** model.

The app starts a short role-play, listens to the student speak, and corrects their German with the exact sentence pattern they got wrong.

Built for the DEV Hacktoberfest "Build for a Friend" challenge, for one real student who wants speaking practice and keeps forgetting sentence structure and der/die/das.

## What it does

| Feature | Details |
|---|---|
| Spoken role-play | Bakery, doctor, Anmeldung, restaurant, or free chat. Replies are short, in A1-A2 German, and end with an easy question |
| Voice in and out | Tutor replies are read aloud (ElevenLabs TTS). The student speaks through the mic button in the chat box (ElevenLabs speech-to-text). Students' own recording is playable in the chat |
| Corrections with the formula | Every correction shows what she said, the better sentence, the **sentence pattern**, and the rule |
| Flashcards | A separate tab turns every noun used in the chat into a der/die/das card |
| Word table | Sidebar lists the session's nouns with articles, English meaning and miss count |
| Goodbye and summary | Saying Tschüss or Auf Wiedersehen ends the chat and shows a summary: what went well, mistakes, articles, tips, alternative sentences |
| Sessions | Each conversation is stored as its own record, so old words never leak into a new session |
| UI | Light, minimal theme. Header and chat box stay pinned while the conversation scrolls |

### Example correction

| You said | Better |
|---|---|
| kann hier sitzen ich? | **Kann ich hier sitzen?** |

**Pattern:** Ja/Nein-Frage mit Modalverb: Modalverb + Subjekt + Ort + Infinitiv (Ende) ?

*Yes/no questions start with the verb. With a modal verb, the second verb (sitzen) goes to the end in the infinitive.*

The prompt covers main clauses, yes/no and W-questions, modal verbs, Perfekt, separable verbs, weil/dass clauses, imperatives, negation, Akkusativ/Dativ and time-place order, using four worked examples.

## Tech stack

| Layer | Choice |
|---|---|
| Language model | Gemma (`gemma-4-26b-a4b-it` by default) through the Google Gemini API (`google-genai`) |
| Voice | ElevenLabs text-to-speech and speech-to-text |
| UI | Streamlit |
| Config | `python-dotenv` |
| Storage | One local JSON file, `student_memory.json` |

## Quick start

Requires Python 3.10+.

```bash
git clone https://github.com/wickedseer/deutsch-mit-gemma.git
cd deutsch-mit-gemma
pip install -r requirements.txt
cp .env.example .env      # then add your keys
streamlit run app.py
```

### Environment variables (`.env`)

| Variable | Required | Notes |
|---|---|---|
| `GEMINI_API_KEY` | Yes | From Google AI Studio. `GOOGLE_API_KEY` also works |
| `ELEVENLABS_API_KEY` | No | Without it the app runs text-only (no tutor voice, no mic) |
| `MODEL` | No | Defaults to `gemma-4-26b-a4b-it`. Use the exact ID your API lists |
| `ELEVENLABS_VOICE_ID` | No | Defaults to a built-in voice |
| `STUDENT_NAME` | No | Defaults to `Jane` |

Streamlit 1.47 or newer is needed for the mic button in the chat box.

## How it works

| Step | What happens |
|---|---|
| 1 | The student types or speaks. Speech goes to ElevenLabs Scribe and comes back as German text |
| 2 | The full chat plus the system prompt goes to Gemma, which must return JSON: reply, correction (said, better, pattern, rule), nouns with articles, and an `end` flag |
| 3 | The reply is shown and read aloud. Nouns feed the sidebar table and the flashcard deck |
| 4 | On goodbye (model flag or regex backup), a second Gemma call writes the session summary |
| 5 | The session record (nouns, corrections, summary) is saved to `student_memory.json` |

Notes on Gemma through the Gemini API: it takes no system instruction and has no JSON mode, so the rules are placed in the first user turn and the reply is parsed from the text, with a plain-text fallback if parsing fails.

## Project structure

| Path | Purpose |
|---|---|
| `app.py` | The whole app: prompt, Gemma calls, voice, UI, sessions |
| `requirements.txt` | Python dependencies |
| `.env.example` | Template for your keys |
| `.streamlit/config.toml` | Light theme |
| `student_memory.json` | Created at runtime. Ignored by git |


## Known limitations

| Limitation | Detail |
|---|---|
| Correction quality | Depends on Gemma following the JSON and pattern format. Add more examples to the prompt for structures it misses |
| Noun list | Flashcards only include nouns the model lists |
| Miss counts | The article-error count is a simple heuristic plus flashcard answers |
| Audio storage | Recordings stay in memory for the current session and are not saved |
| Pronunciation | Speech-to-text gives text only. There is no pronunciation scoring yet |

## Roadmap

| Idea | Why |
|---|---|
| Teacher view across sessions | Recurring patterns and weak nouns per student |
| Slow-repeat audio | Helps A1 learners catch words |
| Verb-position drills | Rebuild scrambled sentences |
| Self-hosted option | Run Gemma on Ollama and Whisper for speech 

## Acknowledgements

Gemma by Google DeepMind. Voice by ElevenLabs. UI by Streamlit.