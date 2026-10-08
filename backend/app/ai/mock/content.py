"""Mock handlers for content tasks: vocabulary explanations, error classification and practice items."""

from __future__ import annotations

import random

from app.ai.mock import mock_handler
from app.ai.schemas import (
    ErrorClassificationAI,
    ErrorClassificationItemAI,
    PracticeItemAI,
    PracticeSetAI,
    VocabularyExplanationAI,
)
from app.core.taxonomy import category_for, label_for, normalize_subcategory
from app.services.content import kb_entry


@mock_handler("vocab_explain")
def explain(ctx: dict) -> VocabularyExplanationAI:
    item = ctx["item"]
    word = item["word"]
    examples = [item["example"]]
    for coll in item.get("collocations", [])[:2]:
        examples.append(f"Common pattern: '{coll}'.")
    pos = item.get("part_of_speech", "")
    if pos == "verb":
        mistake = f"Check the verb pattern: learners often add an unnecessary preposition after '{word}'. Learn it with its typical object."
    elif pos == "adjective":
        mistake = f"Don't confuse '{word}' with its noun or adverb forms - use the adjective before a noun or after 'be'."
    elif pos == "noun":
        mistake = (
            f"Check whether '{word}' is countable, and learn the verbs that go with it ({', '.join(item.get('collocations', [])[:2]) or 'see collocations'})."
        )
    else:
        mistake = f"Use '{word}' as a fixed chunk - changing its words usually makes it sound unnatural."
    register = "formal/academic" if item.get("is_academic") else "neutral"
    return VocabularyExplanationAI(
        explanation=f"'{word}' ({pos}, {register}): {item['definition']}.",
        examples=examples[:3],
        common_mistake=mistake,
        usage_tip=(
            f"In IELTS Writing, '{word}' helps you paraphrase and sound precise. Try using it in your next essay."
            if item.get("is_academic")
            else f"'{word}' is great in IELTS Speaking to describe personal experiences naturally."
        ),
    )


@mock_handler("error_classify")
def classify(ctx: dict) -> ErrorClassificationAI:
    out = []
    for i, err in enumerate(ctx.get("errors", [])):
        sub = normalize_subcategory(err.get("subcategory"), err.get("category"))
        out.append(ErrorClassificationItemAI(index=i, category=category_for(sub), subcategory=sub))
    return ErrorClassificationAI(items=out)


@mock_handler("practice_generate")
def practice(ctx: dict) -> PracticeSetAI:
    """Builds error-correction items from the knowledge base and the learner's own mistakes."""
    rng = random.Random(ctx.get("seed", 0))
    focus = ctx["focus"]
    count = int(ctx.get("item_count", 5))
    items: list[PracticeItemAI] = []
    for mistake in ctx.get("mistake_items", [])[:2]:
        items.append(
            PracticeItemAI(
                qtype="error_correction",
                prompt=f"Correct this sentence from your own work: {mistake['context'] or mistake['original']}",
                answer=mistake["corrected_context"] or mistake["corrected"],
                accepted_answers=[mistake["corrected"]],
                explanation=mistake.get("explanation") or f"Rule: {label_for(focus)}.",
            )
        )
    entry = kb_entry(focus)
    if entry:
        pairs = list(entry.get("examples", []))
        rng.shuffle(pairs)
        for wrong, right in pairs:
            if len(items) >= count:
                break
            if wrong.startswith("("):
                continue
            items.append(
                PracticeItemAI(
                    qtype="error_correction",
                    prompt=f"Correct the error: {wrong}",
                    answer=right,
                    accepted_answers=[],
                    explanation=entry["rule"],
                )
            )
    return PracticeSetAI(title=f"{label_for(focus)} practice", items=items[:count])
