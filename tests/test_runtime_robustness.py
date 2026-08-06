from __future__ import annotations

import gc
import json
import tempfile
import time
import tracemalloc
import unittest
from pathlib import Path
from unittest import mock

from trajectory_ledger.cli import run_fixture
from trajectory_ledger.core import verify_ledger
from trajectory_ledger.replay import prove_isolation


ROOT = Path(__file__).resolve().parents[1]
FIXTURES = ROOT / "fixtures"


class RuntimeRobustnessTests(unittest.TestCase):
    def test_isolation_probe_closes_listener_and_removes_workspace_on_error(self):
        listeners = []

        class TrackedListener:
            closed = False

            def bind(self, address):
                self.address = address

            def listen(self, backlog):
                self.backlog = backlog

            def settimeout(self, timeout):
                self.timeout = timeout

            def getsockname(self):
                return ("127.0.0.1", 49152)

            def close(self):
                self.closed = True

        def tracked_socket():
            listener = TrackedListener()
            listeners.append(listener)
            return listener

        with tempfile.TemporaryDirectory() as directory, mock.patch(
            "trajectory_ledger.replay.tempfile.tempdir", directory
        ), mock.patch(
            "trajectory_ledger.replay.sandbox_available", return_value=True
        ), mock.patch(
            "trajectory_ledger.replay.socket.socket", side_effect=tracked_socket
        ), mock.patch(
            "trajectory_ledger.replay._invoke", side_effect=TimeoutError("probe timeout")
        ):
            with self.assertRaisesRegex(TimeoutError, "probe timeout"):
                prove_isolation()
            self.assertEqual(list(Path(directory).glob("tl-proof-*")), [])

        self.assertEqual(len(listeners), 1)
        self.assertTrue(listeners[0].closed)

    def test_repeated_clean_runs_are_bounded_and_leave_no_open_descriptors(self):
        # /dev/fd is a macOS process-level view that includes descriptors held
        # by the interpreter and test runner. Compare the same process before
        # and after repeated complete lifecycles rather than assuming a fixed
        # baseline descriptor count.
        descriptor_root = Path("/dev/fd")
        if not descriptor_root.is_dir():
            self.skipTest("process descriptor view unavailable")

        gc.collect()
        before = len(list(descriptor_root.iterdir()))
        durations: list[float] = []
        packet_sizes: list[int] = []
        tracemalloc.start()
        try:
            with tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                for index in range(20):
                    output = root / f"packet-{index}"
                    started = time.perf_counter()
                    run_fixture(FIXTURES / "clean.json", output)
                    durations.append(time.perf_counter() - started)
                    packet_sizes.append(
                        sum(path.stat().st_size for path in output.iterdir())
                    )
                    self.assertEqual(verify_ledger(output / "ledger.jsonl")[0], True)
                self.assertEqual(
                    list(root.glob(".trajectory-ledger-incomplete-*")), []
                )
            _, peak_bytes = tracemalloc.get_traced_memory()
        finally:
            tracemalloc.stop()

        gc.collect()
        after = len(list(descriptor_root.iterdir()))
        self.assertLessEqual(after, before)
        self.assertLess(max(durations), 1.0)
        self.assertLess(peak_bytes, 8 * 1024 * 1024)
        self.assertLess(max(packet_sizes), 64 * 1024)

    def test_packet_size_is_stable_and_outputs_are_closed_after_commit(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            outputs = [root / "first", root / "second"]
            for output in outputs:
                run_fixture(FIXTURES / "clean.json", output)

            first_sizes = {
                path.name: path.stat().st_size for path in outputs[0].iterdir()
            }
            second_sizes = {
                path.name: path.stat().st_size for path in outputs[1].iterdir()
            }
            self.assertEqual(first_sizes, second_sizes)

            # Exercise the post-commit filesystem lifecycle independently of
            # the descriptor-count assertion above.
            for path in outputs[0].iterdir():
                moved = path.with_suffix(path.suffix + ".checked")
                path.rename(moved)
                moved.rename(path)

            diagnostic = json.loads(
                (outputs[0] / "diagnostic.json").read_text(encoding="ascii")
            )
            self.assertEqual(
                diagnostic["authority"], "human_review_only_no_external_action"
            )


if __name__ == "__main__":
    unittest.main()
