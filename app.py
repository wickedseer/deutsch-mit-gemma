import json, os, re, uuid
from datetime import date
from pathlib import Path

import streamlit as st
from dotenv import load_dotenv
from elevenlabs.client import ElevenLabs
from google import genai
from google.genai import types

load_dotenv()

APP = "Deutsch mit Gemma!"
MODEL = os.getenv("MODEL", "")
API_KEY = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY", "")
EL_KEY = os.getenv("ELEVENLABS_API_KEY", "")
EL_VOICE = os.getenv("ELEVENLABS_VOICE_ID", "JBFqnCBsd6RMkjVDRZzb")
STUDENT = os.getenv("STUDENT_NAME", "Jane")
MEMORY = Path("student_memory.json")

SYSTEM = """You are Gemma, a warm, patient German speaking partner for __STUDENT__, a CEFR A1-A2 learner.
Her weak spots: der/die/das and sentence structure (verb position).

REPLY RULES
- Reply in SIMPLE German: max 2 short sentences, A1-A2 vocabulary, Präsens and Perfekt only.
- End with one easy question, EXCEPT when she says goodbye (Tschüss, Auf Wiedersehen, Bis bald): then give a short
  warm farewell, NO question, and set "end": true. Otherwise "end": false.
- List every noun that appears in her message or in your reply in "nouns" (singular, with its article).

ROLE-PLAY RULES
- You are playing a character in the selected scenario.
- Never describe the scenario from an outside perspective.
- Never say "Ich bin in [location]" simply because that is the scenario.
- Act as the person the student would normally interact with.
- For example:
  - In der Bäckerei → you are the baker, student is the customer.
  - Beim Einkaufen → you are the shop assistant, student is the customer.
  - Beim Arzt → you are the doctor, student is the patient.
  - Im Restaurant → you are the waiter, student is the customer.
  - Freie Unterhaltung → you are a normal conversation partner.

CORRECTION RULES (most important)
- If her message has a grammar, word-order or article error, fill "correction" for the ONE most important error.
  Otherwise "correction": null. Ignore capitalization and punctuation slips (the input comes from speech-to-text).
- Fields:
  "said": her exact words
  "better": the corrected full sentence
  "pattern": the sentence FORMULA of the corrected sentence. Name the sentence type, then show the word order with
             slots (Subjekt, Verb, Objekt, Modalverb, Infinitiv, Partizip II, Zeit, Ort, ...). Mark the verb position.
  "rule_en": 1-2 short English sentences: WHY it is wrong, and any special rule involved.
- Generalize to ANY A1-A2 structure, for example: Aussagesatz (conjugated verb on position 2), Ja/Nein-Frage (verb
  first), W-Frage (W-Wort + Verb + Subjekt), Modalverben (second verb as Infinitiv at the END), Perfekt (haben/sein on
  position 2, Partizip II at the END), trennbare Verben (prefix at the END), Nebensätze with weil/dass (conjugated verb
  at the END), Imperativ, Negation (nicht/kein), Akkusativ/Dativ, Possessivartikel, Zeit-Ort order.

EXAMPLES
said: "kann hier sitzen ich?"
better: "Kann ich hier sitzen?"
pattern: "Ja/Nein-Frage mit Modalverb: Modalverb + Subjekt + Ort + Infinitiv (Ende) ?"
rule_en: "Yes/no questions start with the verb. With a modal verb, the second verb (sitzen) goes to the end in the infinitive."

said: "Ich gehe nach Hause weil ich bin müde."
better: "Ich gehe nach Hause, weil ich müde bin."
pattern: "Hauptsatz + , + weil + Subjekt + Rest + konjugiertes Verb (Ende)"
rule_en: "After weil the conjugated verb (bin) moves to the end of the clause."

said: "Ich gekauft habe ein Brot."
better: "Ich habe ein Brot gekauft."
pattern: "Perfekt: Subjekt + haben/sein (Position 2) + Objekt + Partizip II (Ende)"
rule_en: "In the Perfekt, haben is the verb on position 2 and the Partizip II (gekauft) goes to the end."

said: "Ich habe eine Brot."
better: "Ich habe ein Brot."
pattern: "Akkusativ, neutrum: haben + ein (indefinit) + das-Nomen"
rule_en: "Brot is das-Wort (das Brot), so the indefinite article is ein, not eine."

OUTPUT: return ONLY JSON, no markdown:
{"reply_de": str,
 "correction": {"said": str, "better": str, "pattern": str, "rule_en": str} | null,
 "nouns": [{"article": "der|die|das", "word": str, "en": str}],
 "end": bool}"""

# SCENARIOS = ["Im Restaurant","Beim Einkaufen","In der Bäckerei", "Beim Arzt", "Anmeldung","Freie Unterhaltung (free chat)"]
SCENARIOS = {
    "Im Restaurant": {
            "role": "You are a waiter or waitress working in a restaurant. The student is the customer.",
            "context": "The student has come to the restaurant to order food and drinks, ask about the menu, and pay the bill."
        },
    "In der Bäckerei": {
        "role": "You are the baker working in a bakery. The student is the customer.",
        "context": "The student has come into the bakery to buy bread, pastries, or drinks."
    },
    "Beim Einkaufen": {
        "role": "You are a shop assistant. The student is the customer.",
        "context": "The student is shopping and may ask about products, prices, sizes, or colors."
    },
    "Beim Arzt": {
        "role": "You are the doctor. The student is the patient.",
        "context": "The student has come to the doctor's office and needs to describe how they feel."
    },
    "Freie Unterhaltung": {
        "role": "You are a friendly German-speaking conversation partner.",
        "context": "Have a casual everyday conversation with the student."
    }
}
BYE = re.compile(r"\b(tsch(ü|u)ss?|tschau|ciao|auf wiedersehen|bis bald|bis später|bis morgen)\b", re.I)

# CSS = """
# <style>
# #MainMenu, footer {visibility: hidden;}
# header[data-testid="stHeader"] {height: 3rem; background: #ffffff;}
# .block-container {max-width: 760px; padding-top: 3rem;}
# [data-testid="stLayoutWrapper"]:has(> .st-key-hdr) {position: sticky; top: 3rem; z-index: 99; background: #ffffff;}
# .st-key-hdr {background: #ffffff; padding: 0.5rem 0 0.9rem 0; border-bottom: 1px solid #ececef;}
# .brand {font-size: 1.7rem; font-weight: 650; letter-spacing: -0.02em; line-height: 1.1;}
# .sub {color: #6b7280; font-size: 0.85rem; margin-top: 0.2rem;}
# [data-testid="stChatMessage"] {background: #f6f7f9; border-radius: 12px;}
# .card {border: 1px solid #ececef; border-radius: 14px; padding: 2.6rem 1rem; text-align: center;
#        background: #fafafb; margin: 0.8rem 0 1rem 0;}
# .card .de {font-size: 2.2rem; font-weight: 600;}
# .card .en {color: #6b7280; margin-top: 0.3rem;}
# .card .hint {color: #9ca3af; font-size: 0.85rem; margin-top: 1.2rem;}
# </style>
# """

CSS = """
<style>
#MainMenu, footer {
    visibility: hidden;
}

header[data-testid="stHeader"] {
    height: 3rem;
    background: var(--background-color);
}

.block-container {
    max-width: 760px;
    padding-top: 3rem;
}

/* Sticky header */
[data-testid="stLayoutWrapper"]:has(> .st-key-hdr) {
    position: sticky;
    top: 3rem;
    z-index: 99;
    background: var(--background-color);
}

.st-key-hdr {
    background: var(--background-color);
    padding: 0.5rem 0 0.9rem 0;
    border-bottom: 1px solid var(--secondary-background-color);
}

/* Brand */
.brand {
    font-size: 1.7rem;
    font-weight: 650;
    letter-spacing: -0.02em;
    line-height: 1.1;
    color: var(--text-color);
}

.sub {
    color: var(--text-color);
    opacity: 0.65;
    font-size: 0.85rem;
    margin-top: 0.2rem;
}

/* Chat */
[data-testid="stChatMessage"] {
    background: var(--secondary-background-color);
    border-radius: 12px;
}

/* Flashcard */
.card {
    border: 1px solid var(--secondary-background-color);
    border-radius: 14px;
    padding: 2.6rem 1rem;
    text-align: center;
    background: var(--secondary-background-color);
    margin: 0.8rem 0 1rem 0;
}

.card .de {
    font-size: 2.2rem;
    font-weight: 600;
    color: var(--text-color);
}

.card .en {
    color: var(--text-color);
    opacity: 0.65;
    margin-top: 0.3rem;
}

.card .hint {
    color: var(--text-color);
    opacity: 0.45;
    font-size: 0.85rem;
    margin-top: 1.2rem;
}

/* Sidebar */
[data-testid="stSidebar"] {
    background: var(--secondary-background-color);
}
</style>
"""

llm = genai.Client(api_key=API_KEY)
el = ElevenLabs(api_key=EL_KEY) if EL_KEY else None


# ---------- helpers ----------
def load_mem():
    m = json.loads(MEMORY.read_text()) if MEMORY.exists() else {}
    m.pop("nouns", None)  # legacy global word list, replaced by per-session records
    m.pop("tips", None)
    m.setdefault("sessions", [])
    return m


def save_mem(m):
    MEMORY.write_text(json.dumps(m, ensure_ascii=False, indent=2))


def session_nouns():
    """Missed-word records of the CURRENT session only (empty before the first message)."""
    sid = st.session_state.get("sid")
    for r in mem["sessions"]:
        if r.get("id") == sid:
            return r.get("nouns", {})
    return {}


def cur():
    """Current session record; created lazily on the first message so page reloads leave no empty sessions."""
    sid = st.session_state.setdefault("sid", uuid.uuid4().hex[:8])
    for r in mem["sessions"]:
        if r.get("id") == sid:
            return r
    r = {"id": sid, "date": date.today().isoformat(), "scenario": scenario, "ended": False,
         "mistakes": 0, "nouns": {}, "corrections": []}
    mem["sessions"].append(r)
    return r


def ask_gemma(history, scenario):
    # Gemma on the Gemini API takes no system role, so the instructions go into the first user turn.
    # first = (SYSTEM.replace("__STUDENT__", STUDENT)
    #          + f"\n\nScenario: {scenario}. Start the role-play with a short greeting and a question.")
    scenario_info = SCENARIOS[scenario]

    first = (
        SYSTEM.replace("__STUDENT__", STUDENT)
        + f"""

    ROLE-PLAY SCENARIO: {scenario}

    YOUR ROLE:
    {scenario_info["role"]}

    CONTEXT:
    {scenario_info["context"]}

    IMPORTANT:
    - Stay in your assigned role throughout the conversation.
    - Do NOT tell the student that you are "at" the location.
    - Do NOT say things like "Ich bin in der Bäckerei."
    - Speak as the person the student would actually interact with.
    - The student is the customer/patient/traveller as described above.
    - Start the role-play naturally with a short greeting and a question.

    Start now.
    """
    )
    turns = [("user", first)] + [("model" if h["role"] == "assistant" else "user", h["content"]) for h in history]
    contents = [types.Content(role=r, parts=[types.Part(text=t)]) for r, t in turns]
    out = llm.models.generate_content(
        model=MODEL, contents=contents, config=types.GenerateContentConfig(temperature=0.4))
    raw = out.text or ""
    try:
        res = json.loads(re.search(r"\{.*\}", raw, re.S).group(0))
    except Exception:
        res = {"reply_de": raw}
    c = res.get("correction")
    if isinstance(c, str):
        c = {"said": "", "better": "", "pattern": "", "rule_en": c}
    if not isinstance(c, dict) or not (c.get("better") or c.get("rule_en")):
        c = None
    res["correction"] = c
    nouns = []
    for n in res.get("nouns") or []:
        if isinstance(n, dict) and n.get("word") and str(n.get("article", "")).lower() in ("der", "die", "das"):
            nouns.append({"article": n["article"].lower(), "word": n["word"], "en": n.get("en", "")})
    res["nouns"] = nouns
    res["reply_de"] = res.get("reply_de") or raw
    res["end"] = bool(res.get("end"))
    return res


def summarize(turns, scenario):
    lines = []
    for r, d, _ in turns:
        if r == "user":
            lines.append(f"Student: {d}")
        else:
            c = f" | correction: {json.dumps(d['correction'], ensure_ascii=False)}" if d.get("correction") else ""
            lines.append(f"Tutor: {d['reply_de']}{c}")
    log = "\n".join(lines)
    prompt = f"""You are a German teacher reviewing a finished A1-A2 practice chat ({scenario}) with {STUDENT}.
Her weak spots: der/die/das and sentence structure. Be kind, specific, brief. Write explanations in English.
Return ONLY JSON, no markdown, with exactly these keys:
{{"overall_en": "2 sentences",
 "did_well": ["..."],
 "mistakes": [{{"You said": str, "Better": str, "Pattern": "sentence formula", "Why": str}}],
 "articles": [{{"Article": "der|die|das", "Word": str, "English": str}}],
 "tips": ["max 3 concrete tips"],
 "alternatives": [{{"Instead of": str, "Try": str}}]}}
Use only her real mistakes; empty lists are fine.

Chat:
{log}"""
    out = llm.models.generate_content(
        model=MODEL, contents=prompt, config=types.GenerateContentConfig(temperature=0.3))
    raw = out.text or ""
    try:
        return json.loads(re.search(r"\{.*\}", raw, re.S).group(0))
    except Exception:
        return {"overall_en": raw, "did_well": [], "mistakes": [], "articles": [], "tips": [], "alternatives": []}


def speak(text):
    if not el:
        return None
    return b"".join(el.text_to_speech.convert(
        voice_id=EL_VOICE, text=text, model_id="eleven_multilingual_v2",
        output_format="mp3_44100_128"))


def transcribe(audio_bytes):
    # Swap for open-weight Whisper behind any compatible endpoint if preferred.
    r = el.speech_to_text.convert(file=audio_bytes, model_id="scribe_v1", language_code="deu")
    return r.text


def build_deck(turns):
    deck = {}
    for r, d, _ in turns:
        if r == "assistant":
            for n in d.get("nouns", []):
                deck.setdefault(n["word"].lower(), n)
    return list(deck.values())


def cell(s):
    return str(s or "").replace("|", "/").replace("\n", " ")


def show_correction(c):
    st.markdown(f"| You said | Better |\n|---|---|\n| {cell(c.get('said'))} | **{cell(c.get('better'))}** |")
    if c.get("pattern"):
        st.markdown(f"**Pattern:** {c['pattern']}")
    if c.get("rule_en"):
        st.caption(c["rule_en"])


def render_summary(sm):
    st.subheader("Session summary")
    st.write(sm.get("overall_en", ""))
    for title, key in [("What went well", "did_well"), ("Tips", "tips")]:
        if sm.get(key):
            st.table([{title: t} for t in sm[key]])
    for title, key in [("Mistakes and better versions", "mistakes"),
                       ("Articles to review", "articles"),
                       ("Alternative sentences", "alternatives")]:
        if sm.get(key):
            st.markdown(f"**{title}**")
            st.table(sm[key])


def process(text, scenario, audio=None):
    ss = st.session_state
    ss.turns.append(("user", text, audio))
    ss.history.append({"role": "user", "content": text})
    with st.spinner("…"):
        res = ask_gemma(ss.history, scenario)
    res["end"] = res["end"] or bool(BYE.search(text))
    ss.history.append({"role": "assistant", "content": json.dumps(res, ensure_ascii=False)})
    c = res.get("correction")
    rec = cur()
    rec["scenario"] = scenario
    if c:
        rec["corrections"].append(c)
    for n in res["nouns"]:
        e = rec["nouns"].setdefault(n["word"], {"article": n["article"], "en": n["en"], "misses": 0})
        if c and n["word"].lower() in (c.get("said") or "").lower() and re.search(
                r"\b(der|die|das|ein|eine|article)\b", (c.get("rule_en") or "") + (c.get("pattern") or ""), re.I):
            e["misses"] += 1
    ss.turns.append(("assistant", res, speak(res["reply_de"])))
    if res["end"]:
        with st.spinner("Preparing your summary…"):
            sm = summarize(ss.turns, scenario)
        ss.summary, ss.ended = sm, True
        rec["ended"], rec["mistakes"], rec["summary"] = True, len(sm.get("mistakes", [])), sm
    save_mem(mem)
    st.rerun()


# ---------- UI ----------
st.set_page_config(page_title=APP, page_icon="💬")
st.markdown(CSS, unsafe_allow_html=True)
mem = load_mem()
ss = st.session_state

# Sticky header: brand + view switch (stays on screen while the page scrolls)
with st.container(key="hdr"):
    left, right = st.columns([3, 2], vertical_alignment="center")
    left.markdown(f"<div class='brand'>{APP}</div>"
                  f"<div class='sub'>Speaking practice for {STUDENT} · A1-A2 · powered by Gemma</div>",
                  unsafe_allow_html=True)
    with right:
        view = st.segmented_control("View", ["Chat", "Flashcards"], default="Chat", required=True,
                                    key="view", label_visibility="collapsed", width="stretch")

with st.sidebar:
    scenario = st.selectbox("Scenario", SCENARIOS)
    if st.button("New conversation", use_container_width=True):
        ss.clear()
        st.rerun()

if "history" not in ss:
    ss.history, ss.turns = [], []
    with st.spinner("…"):
        first = ask_gemma([], scenario)
    ss.history.append({"role": "assistant", "content": json.dumps(first, ensure_ascii=False)})
    ss.turns.append(("assistant", first, speak(first["reply_de"])))

with st.sidebar:
    if view == "Chat":  # word table is hidden on the Flashcards view
        missed = session_nouns()
        rows = [{"Word": f"{n['article']} {n['word']}", "English": n["en"],
                 "Missed": missed.get(n["word"], {}).get("misses", 0)} for n in build_deck(ss.turns)]
        rows.sort(key=lambda r: -r["Missed"])  # stable: most-missed first, rest in order of appearance
        if rows:
            st.markdown("**Words this session**")
            st.table(rows[:20])

if view == "Chat":
    for role, data, audio in ss.turns:
        with st.chat_message(role):
            if role == "assistant":
                st.write(data["reply_de"])
                if audio:
                    st.audio(audio, format="audio/mp3")
                if data.get("correction"):
                    show_correction(data["correction"])
                if data.get("nouns"):
                    st.caption(" · ".join(f"{n['article']} {n['word']} ({n['en']})" for n in data["nouns"]))
            else:
                st.write(data)
                if audio:
                    st.audio(audio, format="audio/wav")

    if ss.get("ended"):
        st.divider()
        render_summary(ss.summary)
    else:
        # top-level chat_input is pinned to the bottom of the screen; the mic button records German speech
        val = st.chat_input("Schreib oder sprich Deutsch…", accept_audio=bool(el))
        text, clip = None, None
        if val:
            if isinstance(val, str):
                text = val.strip()
            else:
                text = (val.text or "").strip()
                if val.audio:
                    clip = val.audio.getvalue()  # keep the student's recording to play back in the chat
                    if not text:
                        with st.spinner("Listening…"):
                            text = transcribe(clip)
        if text:
            process(text, scenario, clip)

else:
    deck = build_deck(ss.turns)
    fc = ss.setdefault("fc", {"i": 0, "score": 0, "picked": None})
    if not deck:
        st.info("Nouns from your chat will show up here as flashcards.")
    elif fc["i"] >= len(deck):
        st.subheader("Done")
        st.write(f"Score: {fc['score']} / {len(deck)}")
        if st.button("Restart"):
            ss.fc = {"i": 0, "score": 0, "picked": None}
            st.rerun()
    else:
        card = deck[fc["i"]]
        st.progress(fc["i"] / len(deck))
        st.caption(f"Card {fc['i'] + 1} of {len(deck)} · {len(deck)} nouns from this chat")
        shown = f"{card['article']} {card['word']}" if fc["picked"] else f"___ {card['word']}"
        st.markdown(f"<div class='card'><div class='de'>{shown}</div>"
                    f"<div class='en'>{card['en']}</div>"
                    f"<div class='hint'>der, die or das?</div></div>", unsafe_allow_html=True)
        if fc["picked"] is None:
            for col, art in zip(st.columns(3), ["der", "die", "das"]):
                if col.button(art, use_container_width=True, key=f"art_{art}_{fc['i']}"):
                    fc["picked"] = art
                    if art == card["article"]:
                        fc["score"] += 1
                    else:
                        e = cur()["nouns"].setdefault(card["word"], {"article": card["article"], "en": card["en"], "misses": 0})
                        e["misses"] += 1
                        save_mem(mem)
                    st.rerun()
        else:
            ok = fc["picked"] == card["article"]
            st.markdown(f"**{'Richtig' if ok else 'Nicht ganz'}** · {card['article']} {card['word']}"
                        + ("" if ok else f" (you chose {fc['picked']})"))
            if st.button("Next", key=f"next_{fc['i']}"):
                fc["i"] += 1
                fc["picked"] = None
                st.rerun()