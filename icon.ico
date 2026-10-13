"""ربات معامله‌گر: سیگنال → سفارش، با مدیریت ریسک. لانگ و (در مارجین/فیوچرز) شورت."""
from __future__ import annotations

from datetime import date, datetime

from . import storage
from .exchange import FEES


class Trader:
    def __init__(self, broker, risk: dict, log, mtype="spot", lev=1):
        self.b, self.risk, self.log = broker, risk, log
        self.mtype, self.lev = mtype, (1 if mtype == "spot" else max(1, int(lev)))
        self.kind = "live" if broker.live else "paper"
        self.pos = storage.load_positions(self.kind)
        self.day, self.day_pnl, self.day_start, self.halted = date.today().isoformat(), 0.0, None, False

    @property
    def allow_short(self):
        return self.mtype != "spot"

    def _save(self):
        storage.save_positions(self.pos, self.kind)

    def positions(self):
        return [dict(p) for p in self.pos.values()]

    def equity(self, prices):
        e = self.b.balance().get("USDT", 0.0)
        for p in self.pos.values():
            px = prices.get(p["symbol"]) or p["entry"]
            e += p["margin"] + p["side"] * (px - p["entry"]) * p["qty"] * p["csize"]
        return e

    def _roll(self):
        today = date.today().isoformat()
        if today != self.day or self.day_start is None:
            self.day, self.day_pnl, self.halted = today, 0.0, False
            self.day_start = self.b.balance().get("USDT", 0.0) + sum(p["margin"] for p in self.pos.values())

    # ── تصمیم ──
    def on_analysis(self, symbol, an, mode):
        self._roll()
        p = self.pos.get(symbol)
        want = 1 if an.signal == "buy" else -1 if an.signal == "sell" else 0
        if p and want == -p["side"]:
            self.close(symbol, "سیگنال مخالف")
            p = None
        if p or want == 0 or self.halted:
            return
        if want < 0 and not self.allow_short:
            return
        if an.confidence < self.risk["min_confidence"]:
            return
        if len(self.pos) >= int(self.risk["max_positions"]):
            self.log("info", f"{symbol}: سیگنال {'لانگ' if want > 0 else 'شورت'} ولی ظرفیت پوزیشن پر است")
            return
        self.open(symbol, want, an, mode)

    def open(self, symbol, side, an, mode):
        usdt = self.b.balance().get("USDT", 0.0)
        margin = round(usdt * float(self.risk["per_trade_pct"]) / 100, 2)
        if margin < 5:
            self.log("warn", f"{symbol}: موجودی تتر برای ورود کافی نیست ({usdt:.2f})")
            return
        try:
            qty, px, cs = self.b.open(symbol, side, margin, self.lev)
        except Exception as e:
            self.log("error", f"باز کردن {symbol} ناموفق: {e}")
            return
        dist_sl, dist_tp = abs(an.price - an.stop), abs(an.target - an.price)
        stop, target = px - side * dist_sl, px + side * dist_tp
        liq = None
        if self.lev > 1:
            liq = px * (1 - side * (1 / self.lev) * 0.9)
            if (side > 0 and stop <= liq) or (side < 0 and stop >= liq):
                stop = px - side * abs(px - liq) * 0.8
                self.log("warn", f"{symbol}: حد ضرر به خاطر اهرم {self.lev}x نزدیک‌تر شد تا قبل از لیکوئید شدن بسته شود")
        self.pos[symbol] = dict(symbol=symbol, side=side, qty=qty, csize=cs, entry=px, stop=stop, target=target,
                                lev=self.lev, margin=margin, liq=liq, mtype=self.mtype, mode=mode, be=False,
                                opened=datetime.now().strftime("%Y-%m-%d %H:%M"))
        self._save()
        tag = "لانگ" if side > 0 else "شورت"
        self.log("buy" if side > 0 else "sell",
                 f"باز شد: {tag} {symbol} {self.lev}x · ورود {px:.6g} · هدف {target:.6g} · حد ضرر {stop:.6g} [{self.b.name}]")

    def on_price(self, symbol, price):
        p = self.pos.get(symbol)
        if not p or not price:
            return
        s = p["side"]
        if p.get("liq") and not self.b.live and s * (price - p["liq"]) <= 0:
            self.close(symbol, "لیکوئید")
        elif s * (price - p["stop"]) <= 0:
            self.close(symbol, "حد ضرر")
        elif s * (price - p["target"]) >= 0:
            self.close(symbol, "حد سود")
        elif not p["be"] and s * (price - (p["entry"] + (p["target"] - p["entry"]) * 0.5)) >= 0:
            p["stop"], p["be"] = p["entry"] * (1 + s * 0.002), True
            self._save()
            self.log("info", f"{symbol}: نیمی از مسیر هدف طی شد؛ حد ضرر به نقطه‌ی ورود منتقل شد")

    def close(self, symbol, reason):
        p = self.pos.get(symbol)
        if not p:
            return
        try:
            px = self.b.close(p)
        except Exception as e:
            self.log("error", f"بستن {symbol} ناموفق: {e}")
            return
        fee = FEES[p.get("mtype", "spot")] * 2 * p["qty"] * p["csize"] * p["entry"]
        pnl = p["side"] * (px - p["entry"]) * p["qty"] * p["csize"] - fee
        if reason == "لیکوئید":
            pnl = -p["margin"]
        roe = pnl / p["margin"] * 100 if p["margin"] else 0
        self.day_pnl += pnl
        self.pos.pop(symbol, None)
        self._save()
        storage.append_trade(dict(time=datetime.now().strftime("%Y-%m-%d %H:%M"), symbol=symbol,
                                  side="لانگ" if p["side"] > 0 else "شورت", market=p.get("mtype", "spot"),
                                  lev=p["lev"], entry=f"{p['entry']:.8g}", exit=f"{px:.8g}",
                                  pnl=f"{pnl:.4f}", pct=f"{roe:.2f}", reason=reason, mode=p["mode"]), self.kind)
        self.log("sell" if pnl < 0 else "buy",
                 f"بسته شد ({reason}): {symbol} · {roe:+.2f}% · {pnl:+.2f} USDT [{self.b.name}]")
        if self.day_start and self.day_pnl < -self.day_start * float(self.risk["daily_loss_pct"]) / 100:
            self.halted = True
            self.log("error", "سقف ضرر روزانه رسید؛ ربات تا فردا پوزیشن جدید باز نمی‌کند")

    def close_all(self):
        for s in list(self.pos):
            self.close(s, "بستن دستی")
