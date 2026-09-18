from app.nlu.offline_classifier import resolve_offline


def test_high_confidence_exact_phrase_matches_commit_intent():
    result = resolve_offline("commit my changes")
    assert result.matched
    assert result.confidence == "high"
    assert result.intent.intent_id == "git.commit"


def test_extracts_commit_message_param():
    result = resolve_offline("commit everything with the message fix login bug")
    assert result.matched
    assert result.intent.intent_id == "git.commit"
    assert result.params.get("message") == "fix login bug"


def test_undo_last_commit_matches_soft_reset_not_hard_reset():
    result = resolve_offline("undo my last commit")
    assert result.matched
    assert result.intent.intent_id == "git.reset_soft_last_commit"


def test_gibberish_input_is_not_matched():
    result = resolve_offline("purple elephant sandwich quantum")
    assert not result.matched
    assert result.confidence == "none"
    assert result.message is not None


def test_create_branch_extracts_name():
    result = resolve_offline("make a new branch called feature-login")
    assert result.matched
    assert result.intent.intent_id == "git.branch_create"
    assert result.params.get("name") == "feature-login"
