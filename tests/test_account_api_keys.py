# test_account_api_keys.py - per-account API keys (key -> account binding).
#
# Behaviour under test:
#   * a bound key pins requests to its account and never rotates or falls back
#   * an unusable bound account raises a terminal error instead of borrowing
#     another account's credential
#   * unbound (.env) keys keep the legacy behaviour (active account / polling)
#   * an account's key is stored with the account, so removing the account
#     takes the key with it
from __future__ import annotations

import unittest

from src import auth
from src import main as main_module


def _credential(suffix: str) -> str:
    # Shaped like a JWT so _account_id_from_token does not try to parse it as
    # one that resolves to a different account.
    return f"eyJhbGciOiJSUzI1NiJ9.{suffix}.{suffix}"


class AccountApiKeyStoreTests(unittest.TestCase):
    def setUp(self):
        self._saved_accounts = dict(auth._accounts)
        self._saved_active = auth._active_account
        self._saved_poll = auth._poll_enabled
        auth._accounts = {
            "acct-a": {"token": _credential("aaa"), "user_id": "acct-a", "label": "alpha"},
            "acct-b": {"token": _credential("bbb"), "user_id": "acct-b", "label": "beta"},
        }
        auth._active_account = "acct-a"
        auth._poll_enabled = False
        auth._save_accounts()

    def tearDown(self):
        auth._accounts = self._saved_accounts
        auth._active_account = self._saved_active
        auth._poll_enabled = self._saved_poll
        auth._save_accounts()

    def test_bind_and_resolve(self):
        self.assertEqual(auth.account_for_api_key("sk-alpha"), "")
        self.assertTrue(auth.set_account_api_key("acct-a", "sk-alpha"))
        self.assertTrue(auth.set_account_api_key("acct-b", "sk-beta"))
        self.assertEqual(auth.account_for_api_key("sk-alpha"), "acct-a")
        self.assertEqual(auth.account_for_api_key("sk-beta"), "acct-b")
        self.assertEqual(auth.account_for_api_key("sk-unknown"), "")
        self.assertEqual(auth.known_api_keys(), {"sk-alpha", "sk-beta"})

    def test_clear_key(self):
        auth.set_account_api_key("acct-a", "sk-alpha")
        auth.set_account_api_key("acct-a", "")
        self.assertEqual(auth.get_account_api_key("acct-a"), "")
        self.assertEqual(auth.account_for_api_key("sk-alpha"), "")

    def test_unknown_account_is_rejected(self):
        self.assertFalse(auth.set_account_api_key("nope", "sk-x"))
        self.assertEqual(auth.account_for_api_key("sk-x"), "")

    def test_key_survives_reload_and_dies_with_account(self):
        auth.set_account_api_key("acct-a", "sk-alpha")
        auth._accounts = {}
        auth._bootstrap_account_store()
        self.assertEqual(auth.account_for_api_key("sk-alpha"), "acct-a")

        auth.remove_account("acct-a")
        self.assertEqual(auth.account_for_api_key("sk-alpha"), "")


class PinnedRoutingTests(unittest.TestCase):
    MESSAGES = [{"role": "user", "content": "hello"}]

    def setUp(self):
        self._saved_accounts = dict(auth._accounts)
        self._saved_active = auth._active_account
        self._saved_poll = auth._poll_enabled
        auth._accounts = {
            "acct-a": {"token": _credential("aaa"), "user_id": "acct-a", "label": "alpha"},
            "acct-b": {"token": _credential("bbb"), "user_id": "acct-b", "label": "beta"},
        }
        auth._active_account = "acct-a"
        auth._poll_enabled = False
        main_module._UPSTREAM_SESSION_LEASES.clear()
        main_module._CHAT_HISTORY_SESSIONS.clear()

    def tearDown(self):
        auth._accounts = self._saved_accounts
        auth._active_account = self._saved_active
        auth._poll_enabled = self._saved_poll
        main_module._UPSTREAM_SESSION_LEASES.clear()
        main_module._CHAT_HISTORY_SESSIONS.clear()

    def test_each_key_binds_its_own_account(self):
        bound_a = main_module._bind_chat_session(
            self.MESSAGES, {}, bound_account_id="acct-a"
        )
        bound_b = main_module._bind_chat_session(
            self.MESSAGES, {}, bound_account_id="acct-b"
        )
        self.assertEqual(bound_a["_account_id"], "acct-a")
        self.assertEqual(bound_b["_account_id"], "acct-b")
        self.assertTrue(bound_a["_pinned_account"])
        # Credentials must not leak across accounts.
        self.assertTrue(bound_a["_auth_token"].endswith(".aaa"))
        self.assertTrue(bound_b["_auth_token"].endswith(".bbb"))
        self.assertNotEqual(bound_a["session_id"], bound_b["session_id"])

    def test_pinned_routing_ignores_the_active_account(self):
        auth._active_account = "acct-b"
        bound = main_module._bind_chat_session(
            self.MESSAGES, {}, bound_account_id="acct-a"
        )
        self.assertEqual(bound["_account_id"], "acct-a")

    def test_missing_account_raises_instead_of_falling_back(self):
        auth._accounts.pop("acct-a")
        with self.assertRaises(main_module._PinnedAccountError):
            main_module._bind_chat_session(
                self.MESSAGES, {}, bound_account_id="acct-a"
            )

    def test_tokenless_account_raises(self):
        auth._accounts["acct-a"] = {"user_id": "acct-a", "label": "alpha"}
        with self.assertRaises(main_module._PinnedAccountError):
            main_module._bind_chat_session(
                self.MESSAGES, {}, bound_account_id="acct-a"
            )

    def test_unbound_request_keeps_legacy_behaviour(self):
        bound = main_module._bind_chat_session(self.MESSAGES, {})
        self.assertFalse(bound.get("_pinned_account"))
        self.assertEqual(bound["_account_id"], "acct-a")


class PinnedStatsScopeTests(unittest.TestCase):
    def setUp(self):
        self._saved_accounts = dict(auth._accounts)
        auth._accounts = {
            "acct-a": {"token": _credential("aaa"), "label": "alpha"},
            "acct-b": {"token": _credential("bbb"), "label": "beta"},
        }
        auth.set_account_api_key("acct-a", "sk-alpha")
        auth.set_account_api_key("acct-b", "sk-beta")
        auth._save_accounts()

    def tearDown(self):
        auth._accounts = self._saved_accounts
        auth._save_accounts()

    def test_api_key_query_resolves_to_its_account(self):
        from src.stats_agg import StatsStore

        store = StatsStore()
        store.set_path(self._tmp_path())
        store.record(model="m", in_tok=10, out_tok=1, credit=0.1, ok=True,
                     ts=1793268000, account_id="acct-a")
        store.record(model="m", in_tok=20, out_tok=2, credit=0.2, ok=True,
                     ts=1793268000, account_id="acct-b")

        self.assertEqual(store.snapshot(account_id="acct-a")["total"]["requests"], 1)
        self.assertEqual(store.snapshot(account_id="acct-b")["total"]["requests"], 1)
        self.assertEqual(store.snapshot()["total"]["requests"], 2)

    def _tmp_path(self) -> str:
        import tempfile
        import uuid

        return tempfile.mktemp(suffix=f"-{uuid.uuid4().hex}.json")


if __name__ == "__main__":
    unittest.main()
