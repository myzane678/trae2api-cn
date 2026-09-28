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
from typing import Any, Mapping, Optional

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

    def _save_locked(self) -> None:
        try:
            os.makedirs(os.path.dirname(self.path) or ".", exist_ok=True)
            payload = {"version": 1, "total": self.total, "days": self.days}
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
            self._prune_locked()
            self._save_locked()

    # ── reading ──────────────────────────────────────────────────────
    def snapshot(self) -> dict:
        """Console payload: totals, today, the 7-day series and per-model split."""
        with self._lock:
            self._load_locked()
            dates = sorted(self.days)
            days = []
            for date in dates[-7:]:
                day = self.days[date]
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
            today_day = self.days.get(today, _blank_day(today))
            models_total: list[dict] = []
            for date in dates:
                for name, stat in self.days[date]["models"].items():
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
                "total": dict(self.total),
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
            }


stats_agg = StatsStore()
