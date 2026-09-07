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

# src/main is importable here; the test modules reuse the cached module.
# The module-level _load_allowlist_file() would still read the runtime
# data/model-allowlist.json, so neutralize both the loaded set and any
# later reload.
from src import main as _main  # noqa: E402

_main.MODEL_ALLOWLIST.clear()
_main._load_allowlist_file = lambda: None  # type: ignore[method-assign]