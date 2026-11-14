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


def test_create_branch_called_extracts_name():
    result = resolve_offline("create a branch called login-page")
    assert result.intent.intent_id == "git.branch_create"
    assert result.params.get("name") == "login-page"


def test_branch_name_extracted_from_paraphrase():
    # Not an exact template -- falls back to the anchor-word extraction.
    result = resolve_offline("please create me a new branch called login-page")
    assert result.intent.intent_id == "git.branch_create"
    assert result.params.get("name") == "login-page"


def test_go_back_to_main_is_checkout():
    result = resolve_offline("go back to main")
    assert result.intent.intent_id == "git.checkout"
    assert result.params.get("ref") == "main"


def test_save_changes_as_extracts_commit_message():
    result = resolve_offline("save these changes as login feature")
    assert result.intent.intent_id == "git.commit"
    assert result.params.get("message") == "login feature"


def test_loose_extraction_skips_filler_words():
    # "branch for" must never turn "for" into the branch name.
    from app.nlu.intent_catalog import get_intent
    from app.nlu.offline_classifier import _loose_extract_params

    params = _loose_extract_params("make a branch for the team", get_intent("git.branch_create"))
    assert params.get("name") != "for"
