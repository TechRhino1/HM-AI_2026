import time
import unittest
from jarvis.application.timeout_guard import TimeoutGuard, timeout_guarded

class TestTimeoutGuard(unittest.TestCase):
    def test_sync_timeout_success(self):
        def quick_func():
            return "SUCCESS"

        result = TimeoutGuard.run_sync(quick_func, timeout_sec=1.0, default="FALLBACK")
        self.assertEqual(result, "SUCCESS")

    def test_sync_timeout_fallback_on_hang(self):
        def slow_func():
            time.sleep(1.5)
            return "COMPLETED"

        result = TimeoutGuard.run_sync(slow_func, timeout_sec=0.2, default="FALLBACK")
        self.assertEqual(result, "FALLBACK")

    def test_timeout_decorator(self):
        @timeout_guarded(timeout_sec=0.2, default="DECORATED_FALLBACK")
        def slow_decorated():
            time.sleep(1.0)
            return "DONE"

        self.assertEqual(slow_decorated(), "DECORATED_FALLBACK")

if __name__ == "__main__":
    unittest.main()
