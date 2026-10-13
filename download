"""رشته‌های پس‌زمینه: قیمت زنده + تحلیل + ربات، و بک‌تست. رابط کاربری هیچ‌وقت قفل نمی‌شود."""
from __future__ import annotations

import queue
import threading
import time
import traceback

import ccxt
from PySide6.QtCore import QObject, QThread, Signal

from . import storage
from .engine import MODES, analyze, backtest
from .exchange import LiveBroker, Market, PaperBroker
from .trader import Trader

SEL_EVERY = {"long": 60, "short": 20, "scalp": 8}
BOT_EVERY = {"long": 300, "short": 60, "scalp": 20}


class Worker(QObject):
    markets = Signal(list)
    tickers = Signal(dict)
    analysis = Signal(str, str, object, object)
    log = Signal(str, str)
    account = Signal(object, object, float)  # positions, balance, equity
    status = Signal(str, bool)

    def __init__(self, settings):
        super().__init__()
        self.s, self.q, self.lock = settings, queue.Queue(), threading.Lock()
        self.running, self.bot_on, self.dirty = True, False, True
        self.market = self.trader = None
        self.prices = {}

    # ── فرمان‌ها از رابط کاربری ──
    def connect_exchange(self, exchange, keys, testnet, live, mtype, lev, mm):
        self.q.put(("connect", exchange, keys, testnet, live, mtype, lev, mm))

    def set_selected(self, sym):
        with self.lock:
            self.s["selected"], self.dirty = sym, True

    def set_mode(self, mode):
        with self.lock:
            self.s["mode"], self.dirty = mode, True

    def set_bot(self, on):
        self.bot_on = on
        self.log.emit("info", "ربات روشن شد؛ ارزهای منتخب پایش می‌شوند" if on else
                      "ربات خاموش شد (پوزیشن‌های باز همچنان با حد ضرر/سود مدیریت می‌شوند)")

    def close_position(self, sym):
        self.q.put(("close", sym))

    def close_all(self):
        self.q.put(("close_all",))

    def reset_paper(self, start):
        self.q.put(("reset_paper", start))

    def manual(self, sym, side):
        self.q.put(("manual", sym, side))

    def stop(self):
        self.running = False

    # ── اتصال ──
    def _connect(self, exchange, keys, testnet, live, mtype, lev, mm):
        k, sec, pw = keys or (None, None, None)
        self.status.emit("در حال اتصال…", True)
        m = Market(exchange, k, sec, pw, testnet, mtype)
        syms = m.load()
        if m.authed and live:
            m.balance()  # آزمایش درستی کلیدها
        live = live and m.authed
        self.market = m
        broker = LiveBroker(m, mm) if live else PaperBroker(m, self.s["paper"])
        self.trader = Trader(
            broker, self.s["risk"], lambda lv, msg: self.log.emit(lv, msg), mtype, lev)
        self.s.update(exchange=exchange, testnet=testnet, live_trading=live, market_type=mtype, leverage=lev,
                      margin_mode=mm)
        self.markets.emit(syms)
        acct = "حساب واقعی" if live else "حساب مجازی"
        lev_txt = f" · اهرم {lev}x" if mtype != "spot" else ""
        self.status.emit(f"{exchange.upper()}{' (تست‌نت)' if testnet else ''} · {acct} · "
                         f"{ {'spot': 'اسپات', 'margin': 'مارجین', 'futures': 'فیوچرز'}[mtype]}{lev_txt}", True)
        self.log.emit("info", f"به {exchange} وصل شد · {len(syms)} بازار · {acct}")
        self.dirty = True
        self._emit_account()

    def _emit_account(self):
        if not self.trader:
            return
        try:
            bal = self.trader.b.balance()
            eq = self.trader.equity(self.prices)
        except Exception as e:
            bal, eq = {"error": str(e)}, 0.0
        self.account.emit(self.trader.positions(), bal, eq)
        storage.save_settings(self.s)

    def _handle(self, c):
        if c[0] == "connect":
            try:
                self._connect(*c[1:])
            except Exception as e:
                self.status.emit(f"اتصال ناموفق: {e}", False)
                self.log.emit("error", f"اتصال ناموفق: {e}")
            return
        if not self.trader:
            return
        if c[0] == "close":
            self.trader.close(c[1], "بستن دستی")
        elif c[0] == "close_all":
            self.trader.close_all()
        elif c[0] == "reset_paper":
            if self.trader.b.live:
                self.log.emit("warn", "برای ریست حساب مجازی، اول به حالت مجازی برگردید")
            else:
                self.trader.pos.clear()
                storage.reset_paper(self.s, c[1])
                self.log.emit("info", f"حساب مجازی با {c[1]:,.0f} تتر از نو شروع شد")
        elif c[0] == "manual":
            sym, side = c[1], c[2]
            if sym in self.trader.pos:
                self.log.emit("warn", f"{sym} از قبل پوزیشن باز دارد")
            elif side < 0 and not self.trader.allow_short:
                self.log.emit("warn", "شورت فقط در مارجین و فیوچرز ممکن است")
            else:
                cfg = MODES[self.s["mode"]]
                df = self.market.ohlcv(sym, cfg["tf"], cfg["limit"])
                an = analyze(df, self.s["mode"], self.s["risk"]["threshold"], with_winrate=False)
                if (side > 0) != (an.target > an.price):  # سطوح را با جهت دستی هماهنگ کن
                    an.stop, an.target = 2 * an.price - an.stop, 2 * an.price - an.target
                self.trader.open(sym, side, an, self.s["mode"])
        self._emit_account()

    # ── حلقه‌ی اصلی ──
    def run(self):
        s = self.s
        for keys in ((storage.load_keys(s["exchange"]), None) if s.get("live_trading") else (None,)):
            try:
                self._connect(s["exchange"], keys, s.get("testnet", False), False, s["market_type"],
                              s["leverage"], s["margin_mode"])
                break
            except Exception as e:
                self.status.emit(f"اتصال اولیه ناموفق: {e}", False)
                self.log.emit("error", f"اتصال ناموفق: {e}")
        t_tick = t_sel = t_bot = t_acc = 0.0
        while self.running:
            try:
                while not self.q.empty():
                    self._handle(self.q.get_nowait())
                if not self.market:
                    time.sleep(1)
                    continue
                now = time.time()
                with self.lock:
                    mode, sel, watch = s["mode"], s["selected"], list(s["watchlist"])
                    dirty, self.dirty = self.dirty, False
                cfg = MODES[mode]
                if now - t_tick >= 4:
                    t_tick = now
                    held = list(self.trader.pos) if self.trader else []
                    syms = [x for x in dict.fromkeys(watch + [sel] + held) if self.market.has(x)]
                    tk = self.market.tickers(syms)
                    self.prices.update({k: v.get("last") for k, v in tk.items()})
                    self.tickers.emit(tk)
                    if self.trader and held:
                        for x in held:
                            self.trader.on_price(x, self.prices.get(x))
                        self._emit_account()
                if (dirty or now - t_sel >= SEL_EVERY[mode]) and self.market.has(sel):
                    t_sel = now
                    df = self.market.ohlcv(sel, cfg["tf"], cfg["limit"])
                    an = analyze(df, mode, s["risk"]["threshold"],
                                 allow_short=bool(self.trader and self.trader.allow_short))
                    self.analysis.emit(sel, mode, df, an)
                if self.bot_on and self.trader and now - t_bot >= BOT_EVERY[mode]:
                    t_bot = now
                    for x in watch:
                        if not (self.running and self.bot_on):
                            break
                        if self.market.has(x):
                            df = self.market.ohlcv(x, cfg["tf"], cfg["limit"])
                            self.trader.on_analysis(x, analyze(df, mode, s["risk"]["threshold"], False), mode)
                    self._emit_account()
                if now - t_acc >= 30:
                    t_acc = now
                    self._emit_account()
            except (ccxt.NetworkError, ccxt.ExchangeNotAvailable) as e:
                self.log.emit("warn", f"قطعی شبکه/صرافی، تلاش دوباره… ({e.__class__.__name__})")
                time.sleep(5)
            except Exception as e:
                self.log.emit("error", f"{e.__class__.__name__}: {e}")
                traceback.print_exc()
                time.sleep(3)
            time.sleep(0.25)


class BacktestJob(QThread):
    """بک‌تست چند استراتژی × چند تایم‌فریم روی داده‌ی واقعی صرافی."""
    progress = Signal(int, str)
    result = Signal(object, object)  # results{(key, tf): BTResult}, frames{tf: df}
    failed = Signal(str)

    def __init__(self, exchange, symbol, keys, tfs, sl, tp, allow_short, mode, threshold, bars):
        super().__init__()
        self.a = (exchange, symbol, keys, tfs, sl, tp, allow_short, mode, threshold, bars)

    def run(self):
        ex, sym, keys, tfs, sl, tp, short, mode, th, bars = self.a
        try:
            m = Market(ex)
            m.load()
            res, frames, n, done = {}, {}, len(tfs) * len(keys), 0
            for tf in tfs:
                self.progress.emit(int(done / n * 100), f"دریافت کندل‌های {tf}…")
                df = m.ohlcv(sym, tf, bars)
                frames[tf] = df
                for k in keys:
                    res[(k, tf)] = backtest(df, k, sl, tp, allow_short=short, mode=mode, threshold=th, tf=tf)
                    done += 1
                    self.progress.emit(int(done / n * 100), f"{tf} · {res[(k, tf)].name}")
            self.result.emit(res, frames)
        except Exception as e:
            traceback.print_exc()
            self.failed.emit(str(e))
