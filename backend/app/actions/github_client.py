import httpx

from app.config import get_settings


class GithubApiError(Exception):
    def __init__(self, status_code: int, detail: str):
        self.status_code = status_code
        self.detail = detail
        super().__init__(f"GitHub API error {status_code}: {detail}")


class GithubClient:
    """Thin, typed wrapper around the exact GitHub REST endpoints this app
    uses. Deliberately not a general-purpose GitHub SDK: every method maps
    1:1 to one whitelisted action, so there is no path from a resolved
    action to an arbitrary GitHub API call.
    """

    def __init__(self, access_token: str):
        self._access_token = access_token
        self._base_url = get_settings().github_api_base_url

    def _headers(self) -> dict:
        return {
            "Authorization": f"Bearer {self._access_token}",
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
        }

    def _request(self, method: str, path: str, **kwargs) -> httpx.Response:
        with httpx.Client(timeout=15.0) as client:
            response = client.request(method, f"{self._base_url}{path}", headers=self._headers(), **kwargs)
        if response.status_code >= 400:
            detail = response.text
            try:
                detail = response.json().get("message", detail)
            except ValueError:
                pass
            raise GithubApiError(response.status_code, detail)
        return response

    def create_pr(self, owner: str, repo: str, title: str, head: str, base: str) -> dict:
        response = self._request(
            "POST", f"/repos/{owner}/{repo}/pulls", json={"title": title, "head": head, "base": base}
        )
        return response.json()

    def close_pr(self, owner: str, repo: str, number: int) -> dict:
        response = self._request("PATCH", f"/repos/{owner}/{repo}/pulls/{number}", json={"state": "closed"})
        return response.json()

    def open_issue(self, owner: str, repo: str, title: str, body: str) -> dict:
        response = self._request("POST", f"/repos/{owner}/{repo}/issues", json={"title": title, "body": body})
        return response.json()

    def close_issue(self, owner: str, repo: str, number: int) -> dict:
        response = self._request("PATCH", f"/repos/{owner}/{repo}/issues/{number}", json={"state": "closed"})
        return response.json()

    def fork(self, owner: str, repo: str) -> dict:
        response = self._request("POST", f"/repos/{owner}/{repo}/forks")
        return response.json()

    def delete_repo(self, owner: str, repo: str) -> None:
        self._request("DELETE", f"/repos/{owner}/{repo}")

    def list_commits(self, owner: str, repo: str, limit: int = 20) -> list[dict]:
        response = self._request("GET", f"/repos/{owner}/{repo}/commits", params={"per_page": limit})
        return response.json()
