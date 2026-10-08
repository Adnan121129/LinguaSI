import pytest

from app.ai.client import AIClient, _normalise_history
from app.ai.providers.base import AIMalformedOutputError, AIMessage, AIProviderError, AIRequest, AIResult
from app.ai.schemas import DailyPlanAI
from app.core.config import settings
from app.models import AIInteractionLog


class FlakyProvider:
    """Returns malformed output first, then a valid structured result."""

    name = "flaky"

    def __init__(self) -> None:
        self.requests: list[AIRequest] = []

    def complete(self, request: AIRequest) -> AIResult:
        self.requests.append(request)
        if len(self.requests) == 1:
            raise AIMalformedOutputError("missing field 'summary'")
        plan = DailyPlanAI(title="Focus", summary="Do two things.", focus="grammar", task_notes=[])
        return AIResult(text=plan.model_dump_json(), parsed=plan, model=request.model, provider=self.name, input_tokens=120, output_tokens=40)


PLAN_VARS = {"first_name": "Sam", "goal": "IELTS band 7.0", "learner_context": "(none)", "tasks": "- t1: review 10 words"}


def test_mock_mode_is_default_without_keys():
    assert settings.effective_ai_provider == "mock"
    assert AIClient().is_mock


def test_malformed_output_gets_one_repair_attempt(db):
    client = AIClient()
    provider = FlakyProvider()
    client.set_provider(provider)
    parsed, result = client.generate_model("plan_daily", PLAN_VARS, DailyPlanAI)
    assert parsed.summary == "Do two things."
    assert len(provider.requests) == 2
    repair = provider.requests[1].messages[-1]
    assert repair.role == "user" and "JSON" in repair.content
    log = db.query(AIInteractionLog).order_by(AIInteractionLog.id.desc()).first()
    assert log.success and log.attempts == 2 and log.input_tokens == 120


def test_provider_failure_is_logged_with_category(db):
    class Down:
        name = "down"

        def complete(self, request):
            raise AIProviderError("503 from provider")

    client = AIClient()
    client.set_provider(Down())
    with pytest.raises(AIProviderError):
        client.generate("plan_daily", PLAN_VARS, response_model=DailyPlanAI)
    log = db.query(AIInteractionLog).order_by(AIInteractionLog.id.desc()).first()
    assert not log.success and log.error_category == "provider_error"
    assert log.debug_payload is None, "prompts and learner text are not stored unless AI_LOG_CONTENT is enabled"


def test_history_always_starts_with_a_user_message_and_alternates():
    history = [AIMessage("assistant", "Welcome!"), AIMessage("user", "Hi"), AIMessage("user", "Are you there?")]
    normalised = _normalise_history(history)
    assert normalised[0].role == "user"
    roles = [m.role for m in normalised]
    assert all(a != b for a, b in zip(roles, roles[1:], strict=False))


def test_every_task_has_prompt_templates_and_schema_friendly_tier():
    from app.ai import prompts
    from app.ai.tasks import TASKS

    for name, spec in TASKS.items():
        system, user = prompts.render(spec.prompt, _AnyVariables())
        assert system.strip() and user.strip(), name
        assert spec.tier in ("fast", "strong")


class _AnyVariables(dict):
    """Supplies a placeholder for whatever variable a template asks for."""

    def __contains__(self, key):
        return True

    def __missing__(self, key):
        return f"<{key}>"
