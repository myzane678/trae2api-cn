# conftest.py - Test environment isolation.
#
# A production checkout runs with an operator-configured .env
# (TRAE_MODEL_ALLOWLIST, TRAE_REMOTE_PROMPT_TOOLS_ENABLED) and runtime data
# files (data/model-allowlist.json) that would otherwise make every
# model=auto / caller-owned-tools test fail in a locally configured
# deployment. Pytest loads this file before collecting any test module, so
# the overrides below win over dotenv (load_dotenv never overwrites existing
# variables) and match what the tests already assume.
import os

os.environ["RELAY_API_KEYS"] = ""
os.environ["TRAE_MODEL_ALLOWLIST"] = ""
os.environ["TRAE_REMOTE_PROMPT_TOOLS_ENABLED"] = "false"
# Region/language defaults must not depend on the operator's .env: tests
# assert the CN defaults the code ships with.
for _key in ("TRAE_WEB_USER_REGION", "TRAE_WEB_REGION", "TRAE_WEB_AI_REGION",
             "TRAE_WEB_APP_LANGUAGE", "TRAE_WEB_ID", "TRAE_BIZ_USER_ID",
             "TRAE_USER_UNIQUE_ID", "TRAE_TOKEN", "TRAE_REFRESH_TOKEN",
             "TRAE_USER_ID", "TRAE_TOKEN_EXPIRES"):
    os.environ.pop(_key, None)

# src/main is importable here; the test modules reuse the cached module.
# The module-level _load_allowlist_file() would still read the runtime
# data/model-allowlist.json, so neutralize both the loaded set and any
# later reload.
from src import main as _main  # noqa: E402

_main.MODEL_ALLOWLIST.clear()
_main._load_allowlist_file = lambda: None  # type: ignore[method-assign]

# Runtime-state isolation: several handlers persist to files under data/ and
# .env (usage records, check-in history, the account store). Without this
# fixture every test run would write fixture accounts and fake usage rows into
# the operator's live state - observed repeatedly as "uid-1" accounts and
# account-1/acct-N check-in rows appearing in the real console.
import pytest  # noqa: E402


@pytest.fixture(autouse=True)
def _isolate_runtime_state(tmp_path, monkeypatch):
    from src import auth as _auth

    monkeypatch.setattr(_auth, "ENV_PATH", tmp_path / ".env")
    monkeypatch.setattr(_auth, "ACCOUNTS_PATH", tmp_path / "accounts.json")
    monkeypatch.setattr(_main, "_USAGE_RECORDS_PATH", tmp_path / "usage_records.json")
    monkeypatch.setattr(_main, "_CHECKIN_HISTORY_PATH", tmp_path / "checkin_history.json")
    # The console allowlist persists to data/model-allowlist.json; without this
    # redirect a test run overwrites the operator's real allowlist.
    monkeypatch.setattr(_main, "ALLOWLIST_PATH", str(tmp_path / "model-allowlist.json"))
    yield
