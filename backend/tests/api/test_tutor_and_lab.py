from app.models import PracticeSet


def test_tutor_gives_hints_before_revealing_corrections(onboarded):
    conv = onboarded.post("/tutor/conversations", json={"mode": "tutor"})
    assert conv.status_code == 201
    cid = conv.json()["id"]
    assert conv.json()["messages"][0]["role"] == "assistant"
    first = onboarded.post(f"/tutor/conversations/{cid}/messages", json={"content": "check: She go to school every days."}).json()
    assert first["reply"]["meta"]["intent"] == "sentence_check"
    assert "She goes" not in first["reply"]["content"], "the first reply hints instead of correcting"
    reveal = onboarded.post(f"/tutor/conversations/{cid}/messages", json={"content": "show me the answer"}).json()
    assert reveal["reply"]["meta"]["intent"] == "reveal"
    assert "She goes" in reveal["reply"]["content"] and "every day" in reveal["reply"]["content"]
    full = onboarded.get(f"/tutor/conversations/{cid}").json()
    assert len(full["messages"]) == 5 and full["title"].startswith("check:")


def test_tutor_uses_word_bank_and_handles_outage(onboarded, ai_outage):
    from app.ai.client import ai_client

    ai_client.set_provider(None)
    cid = onboarded.post("/tutor/conversations", json={"mode": "tutor"}).json()["id"]
    reply = onboarded.post(f"/tutor/conversations/{cid}/messages", json={"content": 'What does "mitigate" mean?'}).json()["reply"]
    assert reply["meta"]["intent"] == "vocabulary" and "mitigate" in reply["content"].lower()
    ai_client.set_provider(ai_outage)
    r = onboarded.post(f"/tutor/conversations/{cid}/messages", json={"content": "Another question"})
    assert r.status_code == 503
    assert len(onboarded.get(f"/tutor/conversations/{cid}").json()["messages"]) == 3, "failed turns are not half-saved"


def test_role_play_conversation_counts_as_a_lab_session(onboarded):
    scenarios = onboarded.get("/lab/scenarios").json()
    assert scenarios and {"id", "title", "goal", "phrases"} <= set(scenarios[0])
    conv = onboarded.post("/tutor/conversations", json={"mode": "conversation", "scenario_id": scenarios[0]["id"]}).json()
    assert conv["scenario_info"]["title"] == scenarios[0]["title"]
    outcomes = []
    for msg in ["Hello!", "Could I have a coffee, please?", "Hot, please.", "For here, thanks.", "Yes, by card."]:
        outcomes.append(onboarded.post(f"/tutor/conversations/{conv['id']}/messages", json={"content": msg}).json()["outcome"])
    rewarded = [o for o in outcomes if o]
    assert len(rewarded) == 1 and rewarded[0]["xp_gained"] >= 10
    assert onboarded.post("/tutor/conversations", json={"mode": "conversation", "scenario_id": "nope"}).status_code == 422


def test_conversations_are_private_and_deletable(onboarded, make_learner):
    cid = onboarded.post("/tutor/conversations", json={"mode": "tutor"}).json()["id"]
    other = make_learner()
    assert other.get(f"/tutor/conversations/{cid}").status_code == 404
    assert onboarded.get("/tutor/conversations").json()["total"] == 1
    assert onboarded.delete(f"/tutor/conversations/{cid}").status_code == 200
    assert onboarded.get(f"/tutor/conversations/{cid}").status_code == 404


def test_lab_overview_daily_phrase_and_quiz(onboarded, db):
    overview = onboarded.get("/lab").json()
    assert {s["key"] for s in overview["sections"]} >= {"grammar", "pronunciation", "conversation", "sentence_building", "daily"}
    assert overview["daily_phrase"]["phrase"] == onboarded.get("/lab/daily").json()["phrase"]
    quiz = onboarded.post("/lab/daily/quiz").json()
    assert quiz["kind"] == "daily_english" and len(quiz["items"]) == 3
    answers = {i["id"]: i["answer"] for i in db.get(PracticeSet, quiz["id"]).items}
    result = onboarded.post(f"/practice/sets/{quiz['id']}/submit", json={"answers": answers}).json()
    assert result["practice"]["accuracy"] == 100.0 and result["outcome"]["xp_gained"] > 0


def test_sentence_building_hides_capitalisation_clue(onboarded, db):
    ps = onboarded.post("/lab/sentence-building").json()
    assert ps["kind"] == "sentence_building" and ps["items"]
    for item in ps["items"]:
        shuffled = item["prompt"].split(": ", 1)[1].split(" / ")
        answer_first = db.get(PracticeSet, ps["id"]).items[int(item["id"][1:]) - 1]["answer"].split()[0]
        if answer_first != "I":
            assert answer_first not in shuffled or not answer_first[0].isupper()


def test_pronunciation_check_is_honest_about_what_it_measures(onboarded):
    sets = onboarded.get("/lab/pronunciation").json()
    sentence = sets[0]["sentences"][0]
    r = onboarded.post("/lab/pronunciation/check", json={"sentence": sentence, "transcript": sentence.replace("think", "sink"), "duration_seconds": 4})
    body = r.json()
    assert r.status_code == 200 and body["match"] < 100
    assert "think" in body["missing_words"] and "sink" in body["unexpected_words"]
    assert "not a phonetic pronunciation score" in body["note"]
