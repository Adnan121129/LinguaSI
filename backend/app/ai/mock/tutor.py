"""Mock SI Tutor: a rule-based teacher built on the grammar knowledge base and learner memory."""

from __future__ import annotations

import re

from app.ai.mock import mock_handler
from app.core.taxonomy import label_for
from app.services.content import kb_entry, scenario

TOPIC_KEYWORDS: list[tuple[str, tuple[str, ...]]] = [
    ("article_usage", ("article", "a or an", "a/an", "when to use the", "a or the", "'the'")),
    ("subject_verb_agreement", ("subject verb", "subject-verb", "agreement", "people is", "people are", "people has")),
    ("preposition", ("preposition", "depend on", "in or on", "at or in", "on or at")),
    ("conditionals", ("conditional", "if clause", "if i would", "if i will")),
    ("passive_voice", ("passive",)),
    ("relative_clauses", ("relative clause", "which or that", "who or which", "whose")),
    ("punctuation", ("punctuation", "comma", "semicolon", "however")),
    ("collocation", ("collocation", "make or do", "do or make", "word partner")),
    ("linking_words", ("linking", "linker", "connector", "cohesive", "transition word")),
    ("plural_forms", ("plural", "uncountable", "countable", "much or many", "fewer or less", "less or fewer")),
    ("comparatives", ("comparative", "superlative")),
    ("modal_verbs", ("modal", "should or must", "must or have to")),
    ("verb_tense", ("tense", "present perfect", "past simple", "past tense", "gerund", "-ing form", "infinitive")),
    ("informal_register", ("formal", "informal", "academic style", "register")),
    ("contractions", ("contraction",)),
    ("word_formation", ("word form", "affect or effect", "effect or affect", "economic or economical")),
    ("overview", ("overview", "task 1")),
    ("idea_development", ("develop my idea", "body paragraph", "support my idea", "develop ideas", "peel")),
    ("position_clarity", ("thesis", "my position", "opinion essay")),
    ("true_false_not_given", ("true false not given", "not given", "tfng")),
    ("matching_headings", ("matching heading", "headings question")),
    ("filler_words", ("filler", "um and uh", "hesitat")),
    ("short_answers", ("extend my answer", "speak longer", "longer answers", "part 1 answer")),
    ("spelling", ("spelling", "spell")),
    ("referencing", ("referencing", "pronoun reference")),
]

REVEAL_PATTERNS = re.compile(
    r"\b(tell me the answer|show me|what is the correct|what's the correct|i don't know|i dont know|give me the answer|correct version|just correct it)\b", re.I
)


def _topic_for(message: str) -> str | None:
    lowered = f" {message.lower()} "
    for key, keywords in TOPIC_KEYWORDS:
        if any(k in lowered for k in keywords):
            return key
    return None


def _teach(key: str, learner: dict) -> str:
    entry = kb_entry(key)
    if not entry:
        return ""
    lines = [f"**{entry['title']}**", "", entry["rule"]]
    if entry.get("examples"):
        lines.append("")
        lines.append("Examples:")
        for wrong, right in entry["examples"][:2]:
            if wrong.startswith("("):
                lines.append(f"- ✓ {right}")
            else:
                lines.append(f"- ✗ {wrong} → ✓ {right}")
    if entry.get("tip"):
        lines += ["", f"Tip: {entry['tip']}"]
    recurring = learner.get("recurring_subcategories", [])
    if key in recurring:
        lines += ["", "This is one of your recurring patterns, so it's worth practising - try a repair challenge from My Mistakes."]
    if entry.get("question"):
        lines += ["", f"Your turn: {entry['question']}"]
    return "\n".join(lines)


@mock_handler("tutor_chat")
def chat(ctx: dict) -> str:
    message: str = ctx.get("message", "").strip()
    learner: dict = ctx.get("learner", {})
    name = learner.get("first_name", "")
    check = ctx.get("check")
    vocab = ctx.get("vocab_item")
    lowered = message.lower()

    if check:
        sentence = check["sentence"]
        errors = check.get("errors", [])
        if not errors:
            return (
                f"I couldn't find any grammar or vocabulary errors in:\n\n> {sentence}\n\n"
                "To make it stronger, try adding a precise linking word or a more specific verb. "
                "Can you rewrite it using one word from your vocabulary list?"
            )
        if check.get("reveal"):
            lines = ["Here are the corrections:", ""]
            for err in errors:
                lines.append(f"- **{err['original']}** → **{err['corrected']}** - {err['explanation']}")
            lines += ["", "Now try writing a new sentence that uses the same rule correctly."]
            return "\n".join(lines)
        many = len(errors) > 1
        lines = [f"Good effort! I can see {len(errors)} thing{'s' if many else ''} to fix. Let's work {'them' if many else 'it'} out together:", ""]
        for err in errors:
            entry = kb_entry(err["subcategory"])
            # The rule's own explanation names the principle without giving away the corrected words.
            hint = err["explanation"] or (entry or {}).get("tip", "")
            lines.append(f"- Look at **'{err['original']}'** ({label_for(err['subcategory']).lower()}). {hint}")
        lines += ["", 'Try correcting the sentence yourself and send it back to me. If you\'re stuck, say "show me the answer".']
        return "\n".join(lines)

    if vocab is not None:
        if not vocab:
            word = ctx.get("vocab_query", "that word")
            return (
                f"I don't have '{word}' in the LinguaSI word bank yet. Try using it in a sentence and I'll check "
                "your grammar - or look it up in a learner's dictionary and note one collocation with it."
            )
        lines = [f"**{vocab['word']}** ({vocab['part_of_speech']}) - {vocab['definition']}.", "", f"Example: _{vocab['example']}_"]
        if vocab.get("collocations"):
            lines.append(f"Common collocations: {', '.join(vocab['collocations'][:3])}.")
        if vocab.get("synonyms"):
            lines.append(f"Similar words: {', '.join(vocab['synonyms'][:3])}.")
        lines += ["", f"Your turn: write one sentence about your own life using '{vocab['word']}', and I'll check it."]
        return "\n".join(lines)

    topic = _topic_for(message)
    if topic:
        return _teach(topic, learner)

    if any(w in lowered for w in ("improve", "weak", "focus on", "what should i", "band", "score", "study plan")):
        weak = learner.get("weak_areas", [])
        recurring = learner.get("recurring", [])
        target = learner.get("target_band")
        current = learner.get("estimated_band")
        if not (weak or recurring or (target and current)):
            return (
                f"I don't have enough of your work yet to see patterns{', ' + name if name else ''}. Start with the diagnostic or one "
                "writing task and one speaking practice - after that I can tell you exactly which mistakes and skills to focus on. "
                "Which would you like to try first?"
            )
        lines = [f"Here's what your data shows{', ' + name if name else ''}:", ""]
        if weak:
            lines.append(f"- Weakest areas right now: {', '.join(weak[:3])}.")
        if recurring:
            lines.append(f"- Most frequent mistakes: {', '.join(recurring[:3])}.")
        if target and current:
            lines.append(f"- AI estimated band {current:g} vs target {target:g}.")
        lines += [
            "",
            "My advice: fix one recurring mistake at a time with a 5-minute repair challenge, then use it correctly in your next writing task. "
            "Which skill would you like to work on today?",
        ]
        return "\n".join(lines)

    if any(w in lowered for w in ("hello", "hi ", "hey", "good morning", "good evening")) or lowered in ("hi", "hey"):
        return (
            f"Hello{' ' + name if name else ''}! I'm your SI Tutor. You can ask me about a grammar point (e.g. "
            '"When do I use \'the\'?"), ask what a word means, or paste a sentence and say "check this". What would you like to work on?'
        )
    if any(w in lowered for w in ("thank", "thanks")):
        return "You're welcome! Keep practising - small daily steps add up. Is there anything else you'd like to check?"

    suggestions = learner.get("recurring_subcategories", [])[:2]
    extra = ""
    if suggestions:
        extra = " Based on your recent work, a good place to start would be " + " or ".join(label_for(s).lower() for s in suggestions) + "."
    return (
        "I'm running in offline practice mode, so I work best with focused questions. You can:\n\n"
        '- ask about a grammar point ("How do I use the present perfect?")\n'
        "- ask what a word means (\"What does 'mitigate' mean?\")\n"
        '- paste a sentence and write "check: ..."' + ("\n\n" + extra.strip() if extra else "")
    )


@mock_handler("conversation_chat")
def conversation(ctx: dict) -> str:
    scen = scenario(ctx.get("scenario_id", "")) or {}
    script = scen.get("script", [])
    turn = int(ctx.get("turn_index", 0))
    if turn < len(script):
        return script[turn]
    return "It was really nice talking with you. Have a great day!"
