"""Mock Learning Planner and Progress Analyst: templated narratives over real learner data."""

from __future__ import annotations

from app.ai.mock import mock_handler
from app.ai.schemas import DailyPlanAI, ProgressInsightsAI, TaskNoteAI


@mock_handler("plan_daily")
def daily_plan(ctx: dict) -> DailyPlanAI:
    name = ctx.get("first_name") or "there"
    tasks = ctx.get("tasks", [])
    focus = ctx.get("focus") or "balanced practice"
    minutes = sum(int(t.get("minutes", 5)) for t in tasks)
    goal = ctx.get("goal_label") or "your goal"
    main_task = next((t for t in tasks if t.get("metric") != "vocab_reviews"), tasks[0] if tasks else None)
    main = main_task["title"] if main_task else "a short practice session"
    summary = (
        f'Hi {name}, today\'s mission focuses on {focus}. Start with "{main}" - it targets the area where your '
        f"recent results show the most room to grow. The whole mission takes about {minutes} minutes and moves you closer to {goal}."
    )
    return DailyPlanAI(
        title=f"Today's focus: {focus}"[:60],
        summary=summary,
        focus=focus,
        task_notes=[TaskNoteAI(task_id=t["id"], why=t.get("why", "")) for t in tasks],
    )


@mock_handler("progress_insights")
def insights(ctx: dict) -> ProgressInsightsAI:
    skills = ctx.get("skills", [])
    trends = ctx.get("mistake_trends", [])
    target = ctx.get("target_band")
    improvements, regressions, gaps = [], [], []
    for s in skills:
        now, before = s.get("score"), s.get("score_before")
        label = s["skill"].capitalize()
        if now is not None and before is not None:
            delta = now - before
            if delta >= 3:
                improvements.append(f"{label} improved from {before:.0f} to {now:.0f} (out of 100) over the last two weeks.")
            elif delta <= -3:
                regressions.append(f"{label} dropped from {before:.0f} to {now:.0f} - review recent mistakes in this skill.")
        band = s.get("band")
        if target and band is not None and band < target:
            gaps.append((target - band, f"{label}: AI estimated band {band:g}, {target - band:g} below your target of {target:g}."))
    gaps = [text for _, text in sorted(gaps, key=lambda g: -g[0])]  # biggest gap first
    recurring = []
    for t in trends:
        if t["recent"] >= 2:
            change = t["recent"] - t["previous"]
            direction = "down" if change < 0 else "up" if change > 0 else "unchanged"
            recurring.append(f"{t['label']}: {t['recent']} in the last 14 days ({direction} from {t['previous']}).")
            if change < 0:
                improvements.append(f"Fewer {t['label'].lower()} mistakes than in the previous fortnight ({t['previous']} → {t['recent']}).")
    if improvements:
        headline = improvements[0]
    elif regressions:
        headline = regressions[0]
    else:
        headline = "Keep practising regularly - SI needs a few more sessions to measure clear trends."
    if gaps:
        next_focus = f"Prioritise {gaps[0].split(':')[0].lower()}, your biggest gap to target, with two focused sessions this week."
    elif recurring:
        next_focus = f"Run a repair challenge on {recurring[0].split(':')[0].lower()} and apply it in your next writing task."
    else:
        next_focus = "Keep a balanced routine: one writing, one speaking and three short vocabulary sessions this week."
    return ProgressInsightsAI(
        headline=headline,
        improvements=improvements[:4],
        regressions=regressions[:3],
        recurring_weaknesses=recurring[:4],
        skill_gaps=gaps[:4],
        next_focus=next_focus,
    )
