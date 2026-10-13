"""ذخیره‌ی تنظیمات، پوزیشن‌ها و تاریخچه روی همین کامپیوتر. کلیدهای API فقط در Keychain/Credential Manager."""
from __future__ import annotations

import csv
import json
from pathlib import Path

try:
    import keyring
except Exception:  # pragma: no cover
    keyring = None

HOME = Path.home() / ".didban"
HOME.mkdir(parents=True, exist_ok=True)
SERVICE = "Didban-Crypto-Agent"

DEFAULTS = {
    "exchange": "binance",
    "testnet": False,
    "mode": "short",
    "selected": "BTC/USDT",
    "watchlist": ["BTC/USDT", "ETH/USDT", "BNB/USDT", "SOL/USDT", "XRP/USDT", "TON/USDT", "DOGE/USDT", "ADA/USDT"],
    "live_trading": False,
    "market_type": "spot",
    "leverage": 3,
    "margin_mode": "isolated",
    "risk": {"per_trade_pct": 5.0, "max_positions": 3, "min_confidence": 65, "daily_loss_pct": 5.0, "threshold": 35},
    "paper": {"start": 1000.0, "USDT": 1000.0},
}


def _read(name, default):
    p = HOME / name
    if p.exists():
        try:
            return json.loads(p.read_text(encoding="utf-8"))
        except Exception:
            pass
    return default


def _write(name, data):
    p = HOME / name
    tmp = p.with_suffix(".tmp")
    tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    tmp.replace(p)


def load_settings() -> dict:
    s = _read("settings.json", {})
    out = json.loads(json.dumps(DEFAULTS))
    out.update({k: v for k, v in s.items() if k != "risk"})
    out["risk"].update(s.get("risk", {}))
    out["paper"] = {"start": 1000.0, "USDT": 1000.0, **s.get("paper", {})}
    out["live_trading"] = False  # هر بار برنامه در حالت شبیه‌سازی باز می‌شود
    return out


def save_settings(s: dict):
    _write("settings.json", s)


def load_positions(kind: str = "paper") -> dict:
    return _read(f"positions_{kind}.json", {})


def save_positions(p: dict, kind: str = "paper"):
    _write(f"positions_{kind}.json", p)


FIELDS = ["time", "symbol", "side", "market", "lev", "entry", "exit", "pnl", "pct", "reason", "mode"]


def append_trade(row: dict, kind: str = "paper"):
    p = HOME / f"trades_{kind}.csv"
    new = not p.exists()
    with p.open("a", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=FIELDS, extrasaction="ignore")
        if new:
            w.writeheader()
        w.writerow(row)


def load_trades(kind: str = "paper") -> list[dict]:
    p = HOME / f"trades_{kind}.csv"
    if not p.exists():
        return []
    with p.open(encoding="utf-8") as f:
        return list(csv.DictReader(f))


def reset_paper(settings: dict, start: float):
    settings["paper"].clear()
    settings["paper"].update(start=float(start), USDT=float(start))
    save_positions({}, "paper")
    (HOME / "trades_paper.csv").unlink(missing_ok=True)
    save_settings(settings)


# ── کلیدهای API ──
def save_keys(exchange: str, key: str, secret: str, password: str = ""):
    if not keyring:
        return False
    keyring.set_password(SERVICE, f"{exchange}:key", key)
    keyring.set_password(SERVICE, f"{exchange}:secret", secret)
    keyring.set_password(SERVICE, f"{exchange}:password", password or "")
    return True


def load_keys(exchange: str):
    if not keyring:
        return None
    try:
        k = keyring.get_password(SERVICE, f"{exchange}:key")
        s = keyring.get_password(SERVICE, f"{exchange}:secret")
        p = keyring.get_password(SERVICE, f"{exchange}:password") or ""
        return (k, s, p) if k and s else None
    except Exception:
        return None


def delete_keys(exchange: str):
    if not keyring:
        return
    for part in ("key", "secret", "password"):
        try:
            keyring.delete_password(SERVICE, f"{exchange}:{part}")
        except Exception:
            pass
