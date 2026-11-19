"""Test contract HTTP của BackendClient bằng MockTransport (không cần backend)."""

from __future__ import annotations

import json
import unittest

import httpx

from steady_backend import BackendClient, SteadyConfig

BASE = "http://mock/api/v1"


def _client(handler) -> BackendClient:
    client = BackendClient(SteadyConfig(api_base_url=BASE, access_token="tok"))
    client._client.close()
    client._client = httpx.Client(transport=httpx.MockTransport(handler), base_url=BASE)
    return client


class TestSearchContract(unittest.TestCase):
    def test_search_sends_max_sources_and_parses_grouped_sources(self):
        seen: dict = {}

        def handler(request: httpx.Request) -> httpx.Response:
            seen["path"] = request.url.path
            seen["body"] = json.loads(request.content)
            return httpx.Response(200, json={"sources": [{
                "domain": "example.com", "label": "example.com", "source_rank": 1,
                "note_count": 1,
                "notes": [{"note_id": "n1", "title": "t", "url": None,
                           "summary": None, "snippet": "s", "score": 0.9,
                           "similarity": 0.8}],
            }]})

        client = _client(handler)
        sources, elapsed = client.search("q", 3, "folder-1")
        self.assertEqual(seen["path"], "/api/v1/search")
        self.assertEqual(seen["body"], {"query": "q", "max_sources": 3,
                                        "folder_id": "folder-1"})
        self.assertEqual(sources[0]["notes"][0]["note_id"], "n1")
        self.assertGreaterEqual(elapsed, 0.0)
        client.close()

    def test_list_endpoint_returns_bare_array(self):
        client = _client(lambda request: httpx.Response(
            200, json=[{"id": "f1", "name": "Inbox"}]))
        self.assertEqual(client.list_folders(), [{"id": "f1", "name": "Inbox"}])
        client.close()

    def test_search_rejects_old_items_contract(self):
        client = _client(lambda request: httpx.Response(
            200, json={"items": [{"note_id": "n1"}]}))
        with self.assertRaisesRegex(RuntimeError, "contract cũ"):
            client.search("q")
        client.close()


class TestTokenRefresh(unittest.TestCase):
    def test_retries_once_after_token_expired(self):
        calls: list[str] = []

        def handler(request: httpx.Request) -> httpx.Response:
            if request.url.path.endswith("/auth/refresh"):
                calls.append("refresh")
                return httpx.Response(200, json={"access_token": "new",
                                                 "refresh_token": "r2",
                                                 "expires_in": 900})
            calls.append(request.headers.get("Authorization", ""))
            if request.headers.get("Authorization") == "Bearer new":
                return httpx.Response(200, json={"ok": True})
            return httpx.Response(401, json={
                "error": {"code": "TOKEN_EXPIRED", "message": "expired"}})

        client = _client(handler)
        client.access_token, client.refresh_token = "old", "r1"
        status, body, _ = client.json("GET", "/me")
        self.assertEqual(status, 200)
        self.assertEqual(body, {"ok": True})
        self.assertEqual(calls, ["Bearer old", "refresh", "Bearer new"])
        self.assertEqual(client.refresh_token, "r2")
        client.close()


if __name__ == "__main__":
    unittest.main()
