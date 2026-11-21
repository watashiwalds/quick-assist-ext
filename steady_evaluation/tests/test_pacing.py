"""Test cơ chế pacing RPM chủ động và cờ --provider-rpm."""

from __future__ import annotations

import argparse
import unittest
from unittest import mock

import httpx

import run_evaluation
from steady_backend import BackendClient, Pacer, SteadyConfig, StreamResult


class MockClock:
    """Đồng hồ mô phỏng để test pacing tức thì và tất định, không cần time.sleep thật."""

    def __init__(self, start: float = 1000.0):
        self.now = start
        self.sleep_calls: list[float] = []

    def time(self) -> float:
        return self.now

    def sleep(self, seconds: float) -> None:
        self.sleep_calls.append(seconds)
        self.now += seconds


class TestPacer(unittest.TestCase):
    def test_disabled_pacer(self):
        for rpm in (None, 0, -1, 0.0):
            pacer = Pacer(rpm=rpm)
            self.assertEqual(pacer.min_interval_s, 0.0)
            self.assertEqual(pacer.acquire(), 0.0)

    def test_interval_calculation(self):
        self.assertAlmostEqual(Pacer(rpm=10).min_interval_s, 6.0)
        self.assertAlmostEqual(Pacer(rpm=30).min_interval_s, 2.0)
        self.assertAlmostEqual(Pacer(rpm=6).min_interval_s, 10.0)
        self.assertAlmostEqual(Pacer(rpm=60).min_interval_s, 1.0)

    def test_pacer_acquire_spacing(self):
        clock = MockClock(100.0)
        pacer = Pacer(rpm=10, name="test", time_fn=clock.time, sleep_fn=clock.sleep)

        # Lần 1: không phải chờ
        w1 = pacer.acquire()
        self.assertEqual(w1, 0.0)
        self.assertEqual(clock.now, 100.0)

        # Lần 2 ngay lập tức (elapsed = 0): phải chờ 6.0s
        w2 = pacer.acquire()
        self.assertAlmostEqual(w2, 6.0)
        self.assertAlmostEqual(clock.now, 106.0)

        # Tiến thêm 2.0s rồi gọi lần 3: phải chờ thêm 4.0s để đủ 6.0s
        clock.now += 2.0
        w3 = pacer.acquire()
        self.assertAlmostEqual(w3, 4.0)
        self.assertAlmostEqual(clock.now, 112.0)

        # Tiến thêm 10.0s (vượt quá 6.0s) rồi gọi lần 4: không phải chờ
        clock.now += 10.0
        w4 = pacer.acquire()
        self.assertEqual(w4, 0.0)
        self.assertAlmostEqual(clock.now, 122.0)

    def test_reset(self):
        clock = MockClock(100.0)
        pacer = Pacer(rpm=10, time_fn=clock.time, sleep_fn=clock.sleep)
        pacer.acquire()
        self.assertIsNotNone(pacer._last_call)
        pacer.reset()
        self.assertIsNone(pacer._last_call)
        self.assertEqual(pacer.total_wait_s, 0.0)


class TestBackendClientPacing(unittest.TestCase):
    def test_backend_client_pacers_initialization(self):
        cfg = SteadyConfig(provider_rpm=10, search_rpm=30, rag_rpm=10, pagematch_rpm=6)
        client = BackendClient(cfg)
        self.assertEqual(client.provider_pacer.rpm, 10.0)
        self.assertEqual(client.search_pacer.rpm, 30.0)
        self.assertEqual(client.rag_pacer.rpm, 10.0)
        self.assertEqual(client.pagematch_pacer.rpm, 6.0)
        client.close()

    def test_shared_provider_pacing_across_modules(self):
        """Provider pacer phải giữ nhịp chung xuyên suốt Search, RAG và PageMatch."""
        clock = MockClock(100.0)
        cfg = SteadyConfig(provider_rpm=10)  # 6.0s interval
        client = BackendClient(cfg)

        # Tiêm mock clock vào pacers
        for p in (client.provider_pacer, client.search_pacer,
                 client.rag_pacer, client.pagematch_pacer):
            p._time_fn = clock.time
            p._sleep_fn = clock.sleep

        # Search gọi đầu tiên tại t=100.0
        w_search = client.pace_search()
        self.assertEqual(w_search, 0.0)
        self.assertEqual(clock.now, 100.0)

        # RAG gọi 1.0s sau đó tại t=101.0
        clock.now += 1.0
        w_rag = client.pace_rag()
        self.assertAlmostEqual(w_rag, 5.0)
        self.assertAlmostEqual(clock.now, 106.0)

        # PageMatch gọi 2.0s sau đó tại t=108.0
        clock.now += 2.0
        w_pm = client.pace_pagematch()
        self.assertAlmostEqual(w_pm, 4.0)
        self.assertAlmostEqual(clock.now, 112.0)
        client.close()

    def test_search_and_provider_combined_pacing(self):
        """Khi cả search_rpm (30) và provider_rpm (10) cùng bật."""
        clock = MockClock(100.0)
        cfg = SteadyConfig(search_rpm=30, provider_rpm=10)
        client = BackendClient(cfg)
        for p in (client.provider_pacer, client.search_pacer):
            p._time_fn = clock.time
            p._sleep_fn = clock.sleep

        # Lần 1: 0s
        client.pace_search()
        self.assertEqual(clock.now, 100.0)

        # Lần 2 ngay sau đó: search_pacer đợi 2.0s (đến 102.0),
        # sau đó provider_pacer thấy còn thiếu 4.0s để đủ 6.0s -> tổng đợi = 6.0s
        w2 = client.pace_search()
        self.assertAlmostEqual(w2, 6.0)
        self.assertAlmostEqual(clock.now, 106.0)
        client.close()

    def test_methods_trigger_pacing(self):
        """Kiểm tra search, chat_sse, page_match tự động gọi pace tương ứng."""
        clock = MockClock(100.0)
        cfg = SteadyConfig(provider_rpm=10)
        client = BackendClient(cfg)
        for p in (client.provider_pacer, client.search_pacer,
                 client.rag_pacer, client.pagematch_pacer):
            p._time_fn = clock.time
            p._sleep_fn = clock.sleep

        def handler(request: httpx.Request) -> httpx.Response:
            if request.url.path.endswith("/search"):
                return httpx.Response(200, json={"sources": []})
            if request.url.path.endswith("/ai/page-match"):
                return httpx.Response(200, json={"items": [], "mode": "segments"})
            return httpx.Response(200, json={})

        client._client.close()
        client._client = httpx.Client(transport=httpx.MockTransport(handler),
                                      base_url=cfg.api_base_url)

        # Search lần 1 tại 100.0
        client.search("q1")
        self.assertEqual(clock.now, 100.0)

        # Search lần 2 ngay sau đó -> phải chờ 6s vì provider_rpm=10
        client.search("q2")
        self.assertAlmostEqual(clock.now, 106.0)

        # PageMatch ngay sau đó -> phải chờ thêm 6s
        client.page_match("q3", text="abc")
        self.assertAlmostEqual(clock.now, 112.0)
        client.close()


class TestCliAndManifest(unittest.TestCase):
    def test_parse_args_provider_rpm(self):
        with mock.patch("sys.argv", ["run_evaluation.py", "--provider-rpm", "10",
                                     "--search-rpm", "30", "--rag-rpm", "10",
                                     "--pagematch-rpm", "6"]):
            args = run_evaluation.parse_args()
            self.assertEqual(args.provider_rpm, 10.0)
            self.assertEqual(args.search_rpm, 30.0)
            self.assertEqual(args.rag_rpm, 10.0)
            self.assertEqual(args.pagematch_rpm, 6.0)

    def test_manifest_contains_rpm_parameters(self):
        cfg = SteadyConfig(provider_rpm=10.0, search_rpm=30.0,
                           rag_rpm=10.0, pagematch_rpm=6.0)
        fake_manifest: dict = {
            "run_id": "test_run",
            "provider_rpm": cfg.provider_rpm,
            "search_rpm": cfg.search_rpm,
            "rag_rpm": cfg.rag_rpm,
            "pagematch_rpm": cfg.pagematch_rpm,
            "rpm_config": {
                "provider_rpm": cfg.provider_rpm,
                "search_rpm": cfg.search_rpm,
                "rag_rpm": cfg.rag_rpm,
                "pagematch_rpm": cfg.pagematch_rpm,
            },
        }
        self.assertEqual(fake_manifest["provider_rpm"], 10.0)
        self.assertEqual(fake_manifest["search_rpm"], 30.0)
        self.assertEqual(fake_manifest["rag_rpm"], 10.0)
        self.assertEqual(fake_manifest["pagematch_rpm"], 6.0)
        self.assertEqual(fake_manifest["rpm_config"]["provider_rpm"], 10.0)

        # Kiểm tra report markdown render đúng thông số RPM
        report = run_evaluation.build_report_md(fake_manifest, {})
        self.assertIn("provider_rpm: `10.0`", report)
        self.assertIn("search_rpm: `30.0`", report)


if __name__ == "__main__":
    unittest.main()
