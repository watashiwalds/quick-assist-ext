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


class TestDocumentContract(unittest.TestCase):
    def test_create_document_sends_parts_and_document_id(self):
        seen: dict = {}

        def handler(request: httpx.Request) -> httpx.Response:
            seen["path"] = request.url.path
            seen["body"] = json.loads(request.content)
            return httpx.Response(201, json={"id": "p0", "part_ids": ["p0", "p1"],
                                             "part_count": 2, "document_id": "doc-1",
                                             "index_status": "PROCESSING"})

        client = _client(handler)
        status, body, _ = client.create_note(parts=["a", "b"], document_id="doc-1",
                                             title="t", folder_id="f1",
                                             idempotency_key="k1")
        self.assertEqual(status, 201)
        self.assertEqual(seen["path"], "/api/v1/notes")
        self.assertEqual(seen["body"], {"title": "t", "parts": ["a", "b"],
                                        "document_id": "doc-1", "folder_id": "f1"})
        self.assertEqual(body["part_ids"], ["p0", "p1"])
        client.close()

    def test_list_document_parts_uses_document_query(self):
        seen: dict = {}

        def handler(request: httpx.Request) -> httpx.Response:
            seen["path"] = request.url.path
            seen["query"] = dict(request.url.params)
            return httpx.Response(200, json={"items": [{"id": "p0"}, {"id": "p1"}],
                                             "next_cursor": None})

        client = _client(handler)
        parts, _ = client.list_document_parts("doc-1")
        self.assertEqual(seen["path"], "/api/v1/notes")
        self.assertEqual(seen["query"], {"document_id": "doc-1", "limit": "200"})
        self.assertEqual([p["id"] for p in parts], ["p0", "p1"])
        client.close()

    def test_list_document_parts_paginates(self):
        calls: list[dict] = []

        def handler(request: httpx.Request) -> httpx.Response:
            calls.append(dict(request.url.params))
            if "cursor" not in request.url.params:
                return httpx.Response(200, json={"items": [{"id": "p0"}],
                                                 "next_cursor": "c2"})
            return httpx.Response(200, json={"items": [{"id": "p1"}],
                                             "next_cursor": None})

        client = _client(handler)
        parts, elapsed = client.list_document_parts("doc-1")
        self.assertEqual([p["id"] for p in parts], ["p0", "p1"])
        self.assertEqual(calls[1]["cursor"], "c2")
        self.assertGreater(elapsed, 0)
        client.close()

    def test_list_notes_paginates(self):
        calls: list[dict] = []

        def handler(request: httpx.Request) -> httpx.Response:
            calls.append(dict(request.url.params))
            if "cursor" not in request.url.params:
                return httpx.Response(200, json={"items": [{"id": "n1"}],
                                                 "next_cursor": "c2"})
            return httpx.Response(200, json={"items": [{"id": "n2"}],
                                             "next_cursor": None})

        client = _client(handler)
        self.assertEqual([n["id"] for n in client.list_notes("f1")], ["n1", "n2"])
        self.assertEqual(calls[0]["limit"], "200")
        self.assertEqual(calls[0]["folder_id"], "f1")
        self.assertEqual(calls[1]["cursor"], "c2")
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
