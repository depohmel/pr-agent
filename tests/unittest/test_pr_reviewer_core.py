import pytest
from types import SimpleNamespace
from unittest.mock import MagicMock

from pr_agent.config_loader import get_settings
from pr_agent.tools.pr_reviewer import PRReviewer


def _make_reviewer(git_provider=None):
    reviewer = PRReviewer.__new__(PRReviewer)
    reviewer.git_provider = git_provider or MagicMock()
    reviewer.pr_url = "https://example/pr/1"
    return reviewer


def test_should_publish_review_no_suggestions_respects_config():
    reviewer = _make_reviewer()
    settings = get_settings()
    original_publish_no_suggestions = settings.pr_reviewer.publish_output_no_suggestions

    try:
        settings.pr_reviewer.publish_output_no_suggestions = False
        assert reviewer._should_publish_review_no_suggestions("No major issues detected") is False
        assert reviewer._should_publish_review_no_suggestions("A major issue was detected") is True

        settings.pr_reviewer.publish_output_no_suggestions = True
        assert reviewer._should_publish_review_no_suggestions("No major issues detected") is True
    finally:
        settings.pr_reviewer.publish_output_no_suggestions = original_publish_no_suggestions


def test_can_run_incremental_review_skips_auto_mode_without_new_commit():
    reviewer = _make_reviewer()
    reviewer.is_auto = True
    reviewer.incremental = SimpleNamespace(first_new_commit_sha=None)

    assert reviewer._can_run_incremental_review() is False


def test_set_review_labels_replaces_stale_review_labels_and_keeps_user_labels():
    settings = get_settings()
    original = {
        "publish_output": settings.config.publish_output,
        "require_estimate_effort_to_review": settings.pr_reviewer.require_estimate_effort_to_review,
        "require_security_review": settings.pr_reviewer.require_security_review,
        "enable_review_labels_effort": settings.pr_reviewer.enable_review_labels_effort,
        "enable_review_labels_security": settings.pr_reviewer.enable_review_labels_security,
    }
    settings.config.publish_output = True
    settings.pr_reviewer.require_estimate_effort_to_review = True
    settings.pr_reviewer.require_security_review = True
    settings.pr_reviewer.enable_review_labels_effort = True
    settings.pr_reviewer.enable_review_labels_security = True
    git_provider = MagicMock()
    git_provider.get_pr_labels.return_value = ["Review effort 1/5", "Possible security concern", "keep-me"]
    reviewer = _make_reviewer(git_provider)
    data = {
        "review": {
            "estimated_effort_to_review_[1-5]": "3, moderate",
            "security_concerns": "yes",
        }
    }

    try:
        reviewer.set_review_labels(data)

        git_provider.publish_labels.assert_called_once_with([
            "Review effort 3/5",
            "Possible security concern",
            "keep-me",
        ])
    finally:
        settings.config.publish_output = original["publish_output"]
        settings.pr_reviewer.require_estimate_effort_to_review = original["require_estimate_effort_to_review"]
        settings.pr_reviewer.require_security_review = original["require_security_review"]
        settings.pr_reviewer.enable_review_labels_effort = original["enable_review_labels_effort"]
        settings.pr_reviewer.enable_review_labels_security = original["enable_review_labels_security"]


def test_get_user_answers_collects_question_and_answer_from_issue_comments():
    git_provider = MagicMock()
    git_provider.get_issue_comments.return_value = SimpleNamespace(reversed=[
        SimpleNamespace(body="Unrelated"),
        SimpleNamespace(body="Questions to better understand the PR:\n- Why?"),
        SimpleNamespace(body="/answer Because it fixes production."),
    ])
    reviewer = _make_reviewer(git_provider)
    reviewer.is_answer = True

    question, answer = reviewer._get_user_answers()

    assert question == "Questions to better understand the PR:\n- Why?"
    assert answer == "/answer Because it fixes production."


def test_init_maps_user_question_and_answer_to_correct_prompt_vars(monkeypatch):
    """Behavioral regression for the swapped-unpacking bug (#2496).

    The bug lived in ``PRReviewer.__init__``: ``_get_user_answers()`` returns
    ``(question, answer)`` but the tuple was unpacked as ``answer, question``,
    so the review prompt rendered the user's answer under ``{{ question_str }}``
    and the question under ``{{ answer_str }}``. This drives the real ``__init__``
    (external collaborators stubbed) and asserts each value lands in ``self.vars``
    under the correct key — so it fails if the unpack is ever swapped again,
    regardless of how the line is formatted.
    """
    from pr_agent.tools import pr_reviewer as pr_reviewer_module

    provider = MagicMock()
    provider.is_supported.return_value = True
    provider.get_languages.return_value = {}
    provider.get_files.return_value = []
    provider.get_issue_comments.return_value = SimpleNamespace(reversed=[
        SimpleNamespace(body="Questions to better understand the PR:\n- Why?"),
        SimpleNamespace(body="/answer Because it fixes production."),
    ])
    provider.get_pr_description.return_value = ("desc", [])

    monkeypatch.setattr(pr_reviewer_module, "get_git_provider_with_context", lambda pr_url: provider)
    monkeypatch.setattr(pr_reviewer_module, "get_main_pr_language", lambda languages, files: "Python")
    monkeypatch.setattr(pr_reviewer_module, "TokenHandler", MagicMock())

    reviewer = PRReviewer(
        "https://example/pr/1",
        is_answer=True,
        ai_handler=lambda: SimpleNamespace(main_pr_language=None),
    )

    assert reviewer.vars["question_str"] == "Questions to better understand the PR:\n- Why?"
    assert reviewer.vars["answer_str"] == "/answer Because it fixes production."


@pytest.mark.asyncio
async def test_run_removes_placeholder_on_failure(monkeypatch):
    """BUG 1 — when the LLM call raises, the 'Preparing review...' placeholder must
    still be cleaned up (try/finally).  Without the finally block the placeholder
    stays on the PR forever, looking like a hung review.
    """
    from pr_agent.tools import pr_reviewer as pr_reviewer_module

    git_provider = MagicMock()
    reviewer = _make_reviewer(git_provider)
    reviewer.incremental = SimpleNamespace(is_incremental=False)
    reviewer.vars = {}
    reviewer.prediction = None

    async def _noop(*a, **kw):
        return None

    async def _boom(prepare_fn, model_type=None):
        raise RuntimeError("LLM explosion")

    monkeypatch.setattr(pr_reviewer_module, "init_run_details", lambda: None)
    monkeypatch.setattr(pr_reviewer_module, "extract_and_cache_pr_tickets", _noop)
    monkeypatch.setattr(pr_reviewer_module, "retry_with_fallback_models", _boom)

    settings = get_settings()
    original = {
        "publish_output": settings.config.publish_output,
        "is_auto_command": settings.config.get("is_auto_command", False),
    }
    try:
        settings.config.publish_output = True
        settings.config.is_auto_command = False

        await reviewer.run()
    finally:
        settings.config.publish_output = original["publish_output"]
        settings.config.is_auto_command = original["is_auto_command"]

    git_provider.publish_comment.assert_any_call("Preparing review...", is_temporary=True)
    git_provider.remove_initial_comment.assert_called_once()


@pytest.mark.asyncio
async def test_run_dismisses_stale_change_requests_on_clean_review(monkeypatch):
    """BUG 2 — a fresh review that finds no key issues and no security concerns
    dismisses the bot's own prior CHANGES_REQUESTED reviews so the gate can clear.
    """
    from pr_agent.tools import pr_reviewer as pr_reviewer_module

    git_provider = MagicMock()
    reviewer = _make_reviewer(git_provider)
    reviewer.incremental = SimpleNamespace(is_incremental=False)
    reviewer.vars = {}
    reviewer.prediction = None
    # A clean review: no key issues, no security concerns
    reviewer.review_data = {"review": {"key_issues_to_review": [], "security_concerns": "No"}}

    async def _noop(*a, **kw):
        return None

    async def _fake_retry(prepare_fn, model_type=None):
        reviewer.prediction = "review: {}"  # noqa: E501

    monkeypatch.setattr(pr_reviewer_module, "init_run_details", lambda: None)
    monkeypatch.setattr(pr_reviewer_module, "extract_and_cache_pr_tickets", _noop)
    monkeypatch.setattr(pr_reviewer_module, "retry_with_fallback_models", _fake_retry)

    review_text = "## PR Reviewer Guide\n\nNo major issues detected"
    reviewer._prepare_pr_review = lambda: review_text

    settings = get_settings()
    original = {
        "publish_output": settings.config.publish_output,
        "is_auto_command": settings.config.get("is_auto_command", False),
        "persistent_comment": settings.pr_reviewer.persistent_comment,
    }
    try:
        settings.config.publish_output = True
        settings.config.is_auto_command = False
        settings.pr_reviewer.persistent_comment = False

        await reviewer.run()
    finally:
        settings.config.publish_output = original["publish_output"]
        settings.config.is_auto_command = original["is_auto_command"]
        settings.pr_reviewer.persistent_comment = original["persistent_comment"]

    git_provider.dismiss_stale_changes_requested_reviews.assert_called_once()


@pytest.mark.asyncio
async def test_run_does_not_dismiss_when_review_has_issues(monkeypatch):
    """When the review has key issues or security concerns, stale CHANGES_REQUESTED
    reviews are NOT dismissed — the gate should stay red until issues are fixed.
    """
    from pr_agent.tools import pr_reviewer as pr_reviewer_module

    git_provider = MagicMock()
    reviewer = _make_reviewer(git_provider)
    reviewer.incremental = SimpleNamespace(is_incremental=False)
    reviewer.vars = {}
    reviewer.prediction = None
    # A review WITH issues: key issues present, security concerns flagged
    reviewer.review_data = {
        "review": {"key_issues_to_review": [{"file": "a.py"}], "security_concerns": "Yes"},
    }

    async def _noop(*a, **kw):
        return None

    async def _fake_retry(prepare_fn, model_type=None):
        reviewer.prediction = "review: {}"  # noqa: E501

    monkeypatch.setattr(pr_reviewer_module, "init_run_details", lambda: None)
    monkeypatch.setattr(pr_reviewer_module, "extract_and_cache_pr_tickets", _noop)
    monkeypatch.setattr(pr_reviewer_module, "retry_with_fallback_models", _fake_retry)

    review_text = "## PR Reviewer Guide\n\nFound a bug"
    reviewer._prepare_pr_review = lambda: review_text

    settings = get_settings()
    original = {
        "publish_output": settings.config.publish_output,
        "is_auto_command": settings.config.get("is_auto_command", False),
        "persistent_comment": settings.pr_reviewer.persistent_comment,
    }
    try:
        settings.config.publish_output = True
        settings.config.is_auto_command = False
        settings.pr_reviewer.persistent_comment = False

        await reviewer.run()
    finally:
        settings.config.publish_output = original["publish_output"]
        settings.config.is_auto_command = original["is_auto_command"]
        settings.pr_reviewer.persistent_comment = original["persistent_comment"]

    git_provider.dismiss_stale_changes_requested_reviews.assert_not_called()


def test_review_has_no_key_issues_or_security_concerns():
    """The helper correctly classifies clean vs. blocking reviews."""
    reviewer = _make_reviewer()

    # Clean: empty key_issues, "No" security concerns
    reviewer.review_data = {"review": {"key_issues_to_review": [], "security_concerns": "No"}}
    assert reviewer._review_has_no_key_issues_or_security_concerns() is True

    # No key issues, security concerns say "yes"
    reviewer.review_data = {"review": {"key_issues_to_review": [], "security_concerns": "Yes, SQL injection"}}
    assert reviewer._review_has_no_key_issues_or_security_concerns() is False

    # Key issues present, no security concerns
    reviewer.review_data = {"review": {"key_issues_to_review": [{"file": "a.py"}], "security_concerns": "No"}}
    assert reviewer._review_has_no_key_issues_or_security_concerns() is False

    # review_data is None (e.g. _prepare_pr_review not called)
    reviewer.review_data = None
    assert reviewer._review_has_no_key_issues_or_security_concerns() is False
