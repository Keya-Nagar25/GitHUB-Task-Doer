from unittest.mock import MagicMock, patch

import pytest

from app.actions.github_client import GithubApiError, GithubClient


def _mock_client_returning(status_code: int, json_body: dict, text: str = ""):
    mock_response = MagicMock(status_code=status_code)
    mock_response.json.return_value = json_body
    mock_response.text = text or str(json_body)

    mock_http_client = MagicMock()
    mock_http_client.request.return_value = mock_response
    mock_http_client.__enter__.return_value = mock_http_client
    mock_http_client.__exit__.return_value = False
    return mock_http_client


def test_create_pr_returns_parsed_json():
    mock_http_client = _mock_client_returning(201, {"number": 42, "html_url": "https://github.com/o/r/pull/42"})
    with patch("app.actions.github_client.httpx.Client", return_value=mock_http_client):
        client = GithubClient(access_token="fake-token")
        result = client.create_pr("o", "r", title="Add feature", head="feature", base="main")

    assert result["number"] == 42
    call = mock_http_client.request.call_args
    assert call.args[0] == "POST"
    assert call.args[1].endswith("/repos/o/r/pulls")
    assert call.kwargs["json"] == {"title": "Add feature", "head": "feature", "base": "main"}
    assert call.kwargs["headers"]["Authorization"] == "Bearer fake-token"


def test_error_response_raises_github_api_error_with_message():
    mock_http_client = _mock_client_returning(404, {"message": "Not Found"})
    with patch("app.actions.github_client.httpx.Client", return_value=mock_http_client):
        client = GithubClient(access_token="fake-token")
        with pytest.raises(GithubApiError) as exc_info:
            client.open_issue("o", "r", title="bug", body="")

    assert exc_info.value.status_code == 404
    assert "Not Found" in exc_info.value.detail


def test_delete_repo_calls_delete_and_returns_none():
    mock_http_client = _mock_client_returning(204, {})
    with patch("app.actions.github_client.httpx.Client", return_value=mock_http_client):
        client = GithubClient(access_token="fake-token")
        result = client.delete_repo("o", "forked-repo")

    assert result is None
    call = mock_http_client.request.call_args
    assert call.args[0] == "DELETE"
    assert call.args[1].endswith("/repos/o/forked-repo")
