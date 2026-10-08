"""Answer checking for reading, listening, diagnostic and practice items."""

from __future__ import annotations

import re
import unicodedata

NUMBER_WORDS = {
    "zero": "0",
    "one": "1",
    "two": "2",
    "three": "3",
    "four": "4",
    "five": "5",
    "six": "6",
    "seven": "7",
    "eight": "8",
    "nine": "9",
    "ten": "10",
    "eleven": "11",
    "twelve": "12",
    "thirteen": "13",
    "fourteen": "14",
    "fifteen": "15",
    "sixteen": "16",
    "seventeen": "17",
    "eighteen": "18",
    "nineteen": "19",
    "twenty": "20",
    "thirty": "30",
    "forty": "40",
    "fifty": "50",
    "hundred": "100",
}
TFNG = {"t": "TRUE", "true": "TRUE", "f": "FALSE", "false": "FALSE", "ng": "NOT GIVEN", "not given": "NOT GIVEN", "notgiven": "NOT GIVEN"}
YNNG = {"y": "YES", "yes": "YES", "n": "NO", "no": "NO", "ng": "NOT GIVEN", "not given": "NOT GIVEN", "notgiven": "NOT GIVEN"}

CHOICE_TYPES = {"multiple_choice", "matching_headings", "matching_information", "matching"}
COMPLETION_TYPES = {
    "sentence_completion",
    "summary_completion",
    "short_answer",
    "form_completion",
    "note_completion",
    "gap_fill",
    "table_completion",
}


def normalize_text(value: str | None) -> str:
    text = unicodedata.normalize("NFKC", value or "").lower().strip()
    text = text.replace("’", "'").replace("‘", "'").replace("“", '"').replace("”", '"')
    text = re.sub(r"[£$€%]", "", text)
    text = re.sub(r"[^\w\s'\-/:.]", " ", text)
    text = re.sub(r"(?<!\d)\.|\.(?!\d)", " ", text)  # keep decimal points only
    text = re.sub(r"\s+", " ", text).strip()
    return text


def normalize_completion(value: str | None) -> str:
    text = normalize_text(value)
    tokens = [NUMBER_WORDS.get(tok, tok) for tok in text.split()]
    while tokens and tokens[0] in ("a", "an", "the"):
        tokens = tokens[1:]
    text = " ".join(tokens)
    return text.replace(" - ", "-").replace(",", "")


def option_letter(index: int) -> str:
    return chr(ord("A") + index)


def _strip_option_prefix(option: str) -> str:
    return re.sub(r"^\s*[A-Za-z0-9ivx]{1,4}[.)]\s+", "", option or "").strip()


def check_answer(
    user_answer: str | None,
    answer: str,
    *,
    qtype: str,
    accepted: list[str] | None = None,
    options: list[str] | None = None,
    word_limit: int | None = None,
) -> tuple[bool, str | None]:
    """Return (is_correct, feedback_note)."""
    raw = (user_answer or "").strip()
    if not raw:
        return False, "No answer given."
    if qtype == "true_false_not_given":
        return TFNG.get(normalize_text(raw)) == TFNG.get(normalize_text(answer), answer.upper()), None
    if qtype == "yes_no_not_given":
        return YNNG.get(normalize_text(raw)) == YNNG.get(normalize_text(answer), answer.upper()), None
    if qtype in CHOICE_TYPES:
        candidates = {normalize_text(answer)}
        for alt in accepted or []:
            candidates.add(normalize_text(alt))
        if options:
            for i, opt in enumerate(options):
                stripped = _strip_option_prefix(opt)
                if normalize_text(stripped) in candidates or normalize_text(opt) in candidates or normalize_text(option_letter(i)) in candidates:
                    candidates.update({normalize_text(option_letter(i)), normalize_text(stripped), normalize_text(opt)})
        user = normalize_text(raw)
        return user in candidates or normalize_text(_strip_option_prefix(raw)) in candidates, None

    # completion / short answer / gap fill
    if word_limit and len(normalize_text(raw).split()) > word_limit:
        return False, f"Your answer uses more than {word_limit} word(s), so it would be marked wrong."
    user = normalize_completion(raw)
    candidates = {normalize_completion(answer)} | {normalize_completion(a) for a in accepted or []}
    if user in candidates:
        return True, None
    # tolerate a missing plural 's' only when the stem matches exactly (spelling still matters in IELTS)
    for cand in candidates:
        if cand and (user == cand.rstrip("s") or cand == user.rstrip("s")) and len(cand) > 3:
            return False, "Check the singular/plural form - the exact form matters in the test."
    return False, None


def accuracy(correct: int, total: int) -> float:
    return round(correct / total * 100, 1) if total else 0.0
