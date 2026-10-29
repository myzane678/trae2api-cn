# stats_agg.py - persistent daily/model aggregates for the console.
#
# The raw request log is capped (recent N entries) so it cannot back a 7-day
# trend or lifetime totals.  This module keeps a small, permanently accurate
# rollup instead: totals since first use, one bucket per day, one per model,
# plus per-day model breakdowns for the console's distribution view.
# Mirrors workbuddy2api's stats store, which the console UI was modelled on.
from __future__ import annotations

import json
import logging
import os
import threading
import time
from datetime import datetime
from typing import Mapping, Optional

logger = logging.getLogger("trae2api.stats")

KEEP_DAYS = 30


def _default_path() -> str:
    return os.environ.get("TRAE_STATS_PATH") or os.path.join("data", "stats.json")


def _blank_day(date: str) -> dict:
    return {
        "date": date,
        "requests": 0,
        "errors": 0,
        "in_tok": 0,
        "out_tok": 0,
        "credit": 0.0,
        "ttfb_n": 0,
        "ttfb_sum": 0.0,
        "models": {},
    }


def _blank_model() -> dict:
    return {"requests": 0, "errors": 0, "in_tok": 0, "out_tok": 0, "credit": 0.0}


class StatsStore:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._loaded = False
        self._path: Optional[str] = None
        self.total: dict = {
            "since": "",
            "requests": 0,
            "errors": 0,
            "in_tok": 0,
            "out_tok": 0,
            "credit": 0.0,
        }
        self.days: dict[str, dict] = {}
        # Per-account rollups, kept alongside the global ones so the console can
        # show the ACTIVE account's numbers instead of a pool-wide blend. Shape:
        #   {"<account_id>": {"total": {...}, "days": {...}}}
        self.accounts: dict[str, dict] = {}

    @property
    def path(self) -> str:
        if self._path is None:
            self._path = _default_path()
        return self._path

    def set_path(self, path: str) -> None:
        """Point the store at another file (tests use this for isolation)."""
        with self._lock:
            self._path = path
            self._loaded = False
            self.total = {
                "since": "",
                "requests": 0,
                "errors": 0,
                "in_tok": 0,
                "out_tok": 0,
                "credit": 0.0,
            }
            self.days = {}
            self.accounts = {}

    # ── persistence ──────────────────────────────────────────────────
    def _load_locked(self) -> None:
        if self._loaded:
            return
        self._loaded = True
        try:
            with open(self.path, "r", encoding="utf-8") as fh:
                payload = json.load(fh)
        except (OSError, ValueError):
            return
        if not isinstance(payload, Mapping):
            return
        total = payload.get("total")
        if isinstance(total, Mapping):
            self.total.update({k: total.get(k, self.total.get(k)) for k in self.total})
        days = payload.get("days")
        if isinstance(days, Mapping):
            for date, day in days.items():
                if isinstance(day, Mapping):
                    merged = _blank_day(str(date))
                    merged.update({k: day.get(k, merged[k]) for k in merged if k != "models"})
                    models = day.get("models")
                    if isinstance(models, Mapping):
                        for name, stat in models.items():
                            if isinstance(stat, Mapping):
                                entry = _blank_model()
                                entry.update({k: stat.get(k, entry[k]) for k in entry})
                                merged["models"][str(name)] = entry
                    self.days[str(date)] = merged
        # Per-account rollups are additive: older files simply have no
        # "accounts" key, and those calls still show up in the global totals.
        accounts = payload.get("accounts")
        if isinstance(accounts, Mapping):
            for account_id, bucket in accounts.items():
                if not isinstance(bucket, Mapping):
                    continue
                self.accounts[str(account_id)] = self._load_account_locked(bucket)

    @staticmethod
    def _load_account_locked(bucket: Mapping) -> dict:
        """Rebuild one per-account bucket (same shape as the global one)."""
        total = {
            "since": "",
            "requests": 0,
            "errors": 0,
            "in_tok": 0,
            "out_tok": 0,
            "credit": 0.0,
        }
        raw_total = bucket.get("total")
        if isinstance(raw_total, Mapping):
            total.update({k: raw_total.get(k, total[k]) for k in total})
        days: dict[str, dict] = {}
        raw_days = bucket.get("days")
        if isinstance(raw_days, Mapping):
            for date, day in raw_days.items():
                if not isinstance(day, Mapping):
                    continue
                merged = _blank_day(str(date))
                merged.update({k: day.get(k, merged[k]) for k in merged if k != "models"})
                models = day.get("models")
                if isinstance(models, Mapping):
                    for name, stat in models.items():
                        if isinstance(stat, Mapping):
                            entry = _blank_model()
                            entry.update({k: stat.get(k, entry[k]) for k in entry})
                            merged["models"][str(name)] = entry
                days[str(date)] = merged
        return {"total": total, "days": days}

    def _save_locked(self) -> None:
        try:
            os.makedirs(os.path.dirname(self.path) or ".", exist_ok=True)
            payload = {"version": 1, "total": self.total, "days": self.days,
                       "accounts": self.accounts}
            tmp = self.path + ".tmp"
            with open(tmp, "w", encoding="utf-8") as fh:
                json.dump(payload, fh, ensure_ascii=False, separators=(",", ":"))
            os.replace(tmp, self.path)
        except OSError as exc:
            logger.warning("stats could not be saved: %s", exc)

    def _prune_locked(self) -> None:
        if len(self.days) <= KEEP_DAYS:
            return
        keep = sorted(self.days)[-KEEP_DAYS:]
        self.days = {date: self.days[date] for date in keep}

    # ── recording ────────────────────────────────────────────────────
    def record(
        self,
        *,
        model: str,
        in_tok: int,
        out_tok: int,
        credit: Optional[float],
        ok: bool,
        ttfb_ms: Optional[float] = None,
        ts: Optional[float] = None,
        account_id: Optional[str] = None,
    ) -> None:
        stamp = float(ts if ts is not None else time.time())
        date = datetime.fromtimestamp(stamp).strftime("%Y-%m-%d")
        with self._lock:
            self._load_locked()
            day = self.days.setdefault(date, _blank_day(date))
            credit_value = float(credit or 0.0)
            for bucket in (self.total, day):
                bucket["requests"] += 1
                if not ok:
                    bucket["errors"] += 1
                bucket["in_tok"] += int(in_tok or 0)
                bucket["out_tok"] += int(out_tok or 0)
                bucket["credit"] = round(float(bucket["credit"]) + credit_value, 6)
            if ttfb_ms:
                day["ttfb_n"] += 1
                day["ttfb_sum"] = round(float(day["ttfb_sum"]) + float(ttfb_ms), 3)
            stat = day["models"].setdefault(model or "unknown", _blank_model())
            stat["requests"] += 1
            if not ok:
                stat["errors"] += 1
            stat["in_tok"] += int(in_tok or 0)
            stat["out_tok"] += int(out_tok or 0)
            stat["credit"] = round(float(stat["credit"]) + credit_value, 6)
            if not self.total["since"]:
                self.total["since"] = date
            # Mirror the same numbers into the owning account's bucket, so the
            # overview can be read per account rather than pool-wide.
            if account_id:
                key = str(account_id)
                bucket = self.accounts.get(key)
                if bucket is None:
                    bucket = self.accounts[key] = {
                        "total": {"since": "", "requests": 0, "errors": 0,
                                  "in_tok": 0, "out_tok": 0, "credit": 0.0},
                        "days": {},
                    }
                a_day = bucket["days"].setdefault(date, _blank_day(date))
                for target in (bucket["total"], a_day):
                    target["requests"] += 1
                    if not ok:
                        target["errors"] += 1
                    target["in_tok"] += int(in_tok or 0)
                    target["out_tok"] += int(out_tok or 0)
                    target["credit"] = round(float(target["credit"]) + credit_value, 6)
                if ttfb_ms:
                    a_day["ttfb_n"] += 1
                    a_day["ttfb_sum"] = round(float(a_day["ttfb_sum"]) + float(ttfb_ms), 3)
                a_stat = a_day["models"].setdefault(model or "unknown", _blank_model())
                a_stat["requests"] += 1
                if not ok:
                    a_stat["errors"] += 1
                a_stat["in_tok"] += int(in_tok or 0)
                a_stat["out_tok"] += int(out_tok or 0)
                a_stat["credit"] = round(float(a_stat["credit"]) + credit_value, 6)
                if not bucket["total"]["since"]:
                    bucket["total"]["since"] = date
            self._prune_locked()
            self._save_locked()

    # ── reading ──────────────────────────────────────────────────────
    def snapshot(self, account_id: Optional[str] = None) -> dict:
        """Console payload: totals, today, the 7-day series and per-model split.

        ``account_id`` scopes the numbers to one account. Per-account history
        only starts from the build that added it, so the payload reports
        ``accounts_tracked`` / ``scoped`` for the console to label honestly
        instead of silently showing an empty page.
        """
        with self._lock:
            self._load_locked()
            if account_id:
                key = str(account_id)
                bucket = self.accounts.get(key)
                # An account with no recorded history yet must still return a
                # zero-value payload, not an empty dict, or the console would
                # throw on total.requests.
                source_days = (bucket or {}).get("days") or {}
                source_total = (bucket or {}).get("total") or {
                    "since": "", "requests": 0, "errors": 0,
                    "in_tok": 0, "out_tok": 0, "credit": 0.0,
                }
                return self._build_payload(
                    source_days, source_total, scoped=bool(bucket),
                    account_id=key,
                )
            return self._build_payload(self.days, self.total, scoped=False,
                                       account_id=None)

    def _build_payload(
        self,
        source_days: Mapping,
        source_total: Mapping,
        *,
        scoped: bool,
        account_id: Optional[str],
    ) -> dict:
        dates = sorted(source_days)
        days = []
        for date in dates[-7:]:
            day = source_days[date]
            days.append(
                {
                    "date": date,
                    "requests": day["requests"],
                    "errors": day["errors"],
                    "in_tok": day["in_tok"],
                    "out_tok": day["out_tok"],
                    "credit": day["credit"],
                }
            )
        today = datetime.now().strftime("%Y-%m-%d")
        today_day = source_days.get(today, _blank_day(today))
        models_total: list[dict] = []
        for date in dates:
            for name, stat in source_days[date]["models"].items():
                entry = next((m for m in models_total if m["model"] == name), None)
                if entry is None:
                    entry = {"model": name, **_blank_model()}
                    models_total.append(entry)
                entry["requests"] += stat["requests"]
                entry["errors"] += stat["errors"]
                entry["in_tok"] += stat["in_tok"]
                entry["out_tok"] += stat["out_tok"]
                entry["credit"] = round(float(entry["credit"]) + float(stat["credit"]), 6)
        models_total.sort(key=lambda m: m["in_tok"] + m["out_tok"], reverse=True)
        today_models = [
            {"model": name, **stat}
            for name, stat in sorted(
                today_day["models"].items(),
                key=lambda kv: kv[1]["in_tok"] + kv[1]["out_tok"],
                reverse=True,
            )
        ]
        return {
            "total": dict(source_total),
            "today": {
                "date": today,
                "requests": today_day["requests"],
                "errors": today_day["errors"],
                "in_tok": today_day["in_tok"],
                "out_tok": today_day["out_tok"],
                "credit": today_day["credit"],
                "ttfb_n": today_day["ttfb_n"],
                "ttfb_avg_ms": round(
                    today_day["ttfb_sum"] / today_day["ttfb_n"], 1
                )
                if today_day["ttfb_n"]
                else 0,
                "models": today_models,
            },
            "days": days,
            "models_total": models_total[:10],
            "available_dates": dates,
            # Console hints: whether the numbers are account-scoped, and
            # whether that account has any recorded history yet.
            "scoped_account": account_id,
            "scoped": scoped,
            "accounts_tracked": len(self.accounts),
        }


stats_agg = StatsStore()
