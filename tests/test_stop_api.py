# test_stop_api.py - /api/stop 停止接口安全路径：脚本缺失时返回 500 且绝不执行。
import os
import unittest

from fastapi.testclient import TestClient

from src.main import app


class StopApiTests(unittest.TestCase):
    def setUp(self):
        self.client = TestClient(app)

    def test_stop_returns_500_when_script_missing(self):
        missing = os.path.join("data", "no-such-stop-script.ps1")
        old = os.environ.get("TRAE_STOP_SCRIPT")
        os.environ["TRAE_STOP_SCRIPT"] = missing
        try:
            resp = self.client.post("/api/stop")
        finally:
            if old is None:
                os.environ.pop("TRAE_STOP_SCRIPT", None)
            else:
                os.environ["TRAE_STOP_SCRIPT"] = old
        self.assertEqual(resp.status_code, 500, resp.text)
        body = resp.json()
        self.assertFalse(body.get("ok"))
        self.assertIn("not found", body.get("error", ""))