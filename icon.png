"""اتصال به صرافی‌ها با ccxt + سه نوع بازار: اسپات، مارجین، فیوچرز (قراردادهای دائمی USDT).

نماد داخلی برنامه همیشه «BTC/USDT» است؛ برای فیوچرز خودکار به «BTC/USDT:USDT» تبدیل می‌شود.
"""
from __future__ import annotations

import time

import ccxt
import pandas as pd

EXCHANGES = {  # کلید ccxt: (نام فارسی، نیاز به Passphrase، مارجین واقعی پشتیبانی می‌شود)
    "binance": ("بایننس", False, True),
    "bybit": ("بای‌بیت", False, True),
    "okx": ("او‌کی‌ایکس", True, True),
    "kucoin": ("کوکوین", True, True),
    "gateio": ("گیت", False, False),
    "mexc": ("ام‌ای‌ایکس‌سی", False, False),
    "bitget": ("بیت‌گت", True, False),
    "htx": ("اچ‌تی‌ایکس", False, False),
}
MARKET_TYPES = {"spot": "اسپات", "margin": "مارجین", "futures": "فیوچرز"}
MAX_LEV = {"spot": 1, "margin": 10, "futures": 50}
FUTURES_IDS = {"kucoin": "kucoinfutures"}  # بعضی صرافی‌ها برای فیوچرز کلاس جدا دارند

FA_NAMES = {
    "BTC": "بیت‌کوین", "ETH": "اتریوم", "BNB": "بی‌ان‌بی", "SOL": "سولانا", "XRP": "ریپل", "TON": "تون‌کوین",
    "DOGE": "دوج‌کوین", "ADA": "کاردانو", "TRX": "ترون", "AVAX": "آوالانچ", "SHIB": "شیبا", "DOT": "پولکادات",
    "LINK": "چین‌لینک", "LTC": "لایت‌کوین", "BCH": "بیت‌کوین کش", "NEAR": "نیر", "UNI": "یونی‌سواپ",
    "ATOM": "کازماس", "XLM": "استلار", "ETC": "اتریوم کلاسیک", "FIL": "فایل‌کوین", "APT": "آپتوس",
    "ARB": "آربیتروم", "OP": "اپتیمیزم", "SUI": "سویی", "PEPE": "پپه", "NOT": "نات‌کوین", "AAVE": "آوه",
}


class Market:
    def __init__(self, exchange_id, key=None, secret=None, password=None, testnet=False, mtype="spot"):
        self.mtype = mtype
        cid = FUTURES_IDS.get(exchange_id, exchange_id) if mtype == "futures" else exchange_id
        cfg = {"enableRateLimit": True, "timeout": 15000,
               "options": {"defaultType": "swap" if mtype == "futures" else "spot"}}
        if key and secret:
            cfg.update(apiKey=key, secret=secret)
            if password:
                cfg["password"] = password
        self.x = getattr(ccxt, cid)(cfg)
        if testnet:
            self.x.set_sandbox_mode(True)
        self.id = exchange_id
        self.authed = bool(key and secret)
        self.markets = {}

    def sym(self, s):  # BTC/USDT → نماد واقعی در این بازار
        return f"{s}:USDT" if self.mtype == "futures" and ":" not in s else s

    def has(self, s):
        return self.sym(s) in self.markets

    def load(self):
        self.markets = self.x.load_markets()
        out = []
        for s, m in self.markets.items():
            if m.get("quote") != "USDT" or m.get("active") is False:
                continue
            if self.mtype == "futures" and m.get("swap") and m.get("linear") and m.get("settle") == "USDT":
                out.append(f"{m['base']}/USDT")
            elif self.mtype != "futures" and m.get("spot"):
                if self.mtype == "margin" and m.get("margin") is False:
                    continue
                out.append(s)
        return sorted(set(out))

    def tickers(self, symbols):
        real = [self.sym(s) for s in symbols]
        try:
            tk = self.x.fetch_tickers(real)
        except Exception:
            tk = {}
            for s in real:
                try:
                    tk[s] = self.x.fetch_ticker(s)
                except Exception:
                    pass
        return {s.split(":")[0]: t for s, t in tk.items()}

    def price(self, s):
        return float(self.x.fetch_ticker(self.sym(s))["last"])

    def ohlcv(self, s, tf, limit=400):
        """کندل‌ها؛ اگر بیشتر از سقف یک درخواست لازم باشد، چند بار پشت سر هم می‌گیرد."""
        sym, step = self.sym(s), self.x.parse_timeframe(tf) * 1000
        per = 1000 if self.id in ("binance", "bybit") else 300
        if limit <= per:
            rows = self.x.fetch_ohlcv(sym, tf, limit=limit)
        else:
            since = self.x.milliseconds() - limit * step
            rows = []
            while len(rows) < limit:
                part = self.x.fetch_ohlcv(sym, tf, since=since, limit=per)
                if not part:
                    break
                rows += [r for r in part if not rows or r[0] > rows[-1][0]]
                since = part[-1][0] + step
                if since > self.x.milliseconds():
                    break
        df = pd.DataFrame(rows[-limit:], columns=["ts", "open", "high", "low", "close", "volume"])
        df["ts"] = df["ts"] / 1000
        return df.astype(float).reset_index(drop=True)

    def balance(self):
        params = {"type": "margin"} if self.mtype == "margin" and self.id == "binance" else {}
        b = self.x.fetch_balance(params)
        return {k: float(v) for k, v in (b.get("free") or {}).items() if v}

    def contract_size(self, s):
        return float(self.markets.get(self.sym(s), {}).get("contractSize") or 1)


# ───────────────────────── بروکرها ─────────────────────────
# رابط مشترک:  open(symbol, side, margin_usdt, lev) -> (qty, price, contract_size)
#              close(position) -> price
FEES = {"spot": 0.001, "margin": 0.001, "futures": 0.0005}


class PaperBroker:
    """حساب مجازی: قیمت واقعی بازار، پول مجازی. اسپات، مارجین و فیوچرز (با اهرم و شورت)."""
    live = False
    name = "مجازی"

    def __init__(self, market: Market, wallet: dict):
        self.m, self.w = market, wallet  # wallet = {"start":…, "USDT":…}
        self.fee = FEES[market.mtype]

    def balance(self):
        return {"USDT": self.w["USDT"]}

    def open(self, symbol, side, margin, lev):
        if self.w["USDT"] < margin:
            raise RuntimeError("موجودی مجازی کافی نیست")
        p = self.m.price(symbol)
        notional = margin * lev
        self.w["USDT"] -= margin + notional * self.fee
        return notional / p, p, 1.0

    def close(self, pos):
        p = self.m.price(pos["symbol"])
        pnl = pos["side"] * (p - pos["entry"]) * pos["qty"] * pos["csize"]
        notional = pos["qty"] * pos["csize"] * p
        self.w["USDT"] += max(0.0, pos["margin"] + pnl) - notional * self.fee
        return p


class LiveBroker:
    """سفارش واقعی Market روی صرافی."""
    live = True
    name = "واقعی"

    def __init__(self, market: Market, margin_mode="isolated"):
        if not market.authed:
            raise RuntimeError("برای معامله‌ی واقعی کلید API لازم است")
        self.m, self.mm = market, margin_mode

    def balance(self):
        return self.m.balance()

    def _fill(self, order, sym, fallback):
        for _ in range(5):
            if order.get("filled") and order.get("average"):
                break
            time.sleep(0.6)
            try:
                order = self.m.x.fetch_order(order["id"], sym)
            except Exception:
                break
        return float(order.get("filled") or fallback), float(order.get("average") or order.get("price") or self.m.price(sym))

    def _margin_params(self, opening):
        p = {"marginMode": "cross"}
        if self.m.id == "binance":
            p["sideEffectType"] = "MARGIN_BUY" if opening else "AUTO_REPAY"
        if self.m.id == "bybit":
            p["isLeverage"] = 1
        return p

    def open(self, symbol, side, margin, lev):
        x, mt, sym = self.m.x, self.m.mtype, self.m.sym(symbol)
        p = self.m.price(symbol)
        if mt == "spot" and side < 0:
            raise RuntimeError("در اسپات فروش استقراضی (شورت) ممکن نیست")
        params = {}
        if mt == "futures":
            for fn, args in (("set_margin_mode", (self.mm, sym)), ("set_leverage", (lev, sym))):
                try:
                    getattr(x, fn)(*args)
                except Exception:
                    pass  # بعضی صرافی‌ها تنظیم تکراری را خطا می‌دانند
        elif mt == "margin":
            params = self._margin_params(True)
        cs = self.m.contract_size(symbol)
        amount = float(x.amount_to_precision(sym, margin * lev / p / cs))
        if amount <= 0:
            raise RuntimeError("مبلغ کمتر از حداقل سفارش صرافی است")
        o = x.create_order(sym, "market", "buy" if side > 0 else "sell", amount, None, params)
        qty, avg = self._fill(o, sym, amount)
        fee = o.get("fee") or {}
        if mt == "spot" and fee.get("currency") == symbol.split("/")[0] and fee.get("cost"):
            qty -= float(fee["cost"])
        return qty, avg, cs

    def close(self, pos):
        x, mt, sym = self.m.x, self.m.mtype, self.m.sym(pos["symbol"])
        qty = pos["qty"]
        params = {}
        if mt == "futures":
            params = {"reduceOnly": True}
        elif mt == "margin":
            params = self._margin_params(False)
        else:
            qty = min(qty, self.m.balance().get(pos["symbol"].split("/")[0], 0))
        amount = float(x.amount_to_precision(sym, qty))
        o = x.create_order(sym, "market", "sell" if pos["side"] > 0 else "buy", amount, None, params)
        return self._fill(o, sym, amount)[1]
