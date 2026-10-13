"""موتور تحلیل و بک‌تست.

اندیکاتورها و استراتژی‌های محبوب تریدینگ‌ویو، به صورت برداری (روی کل تاریخچه) بازنویسی شده‌اند:
هر استراتژی برای هر کندل یک رأی می‌دهد: +1 خرید، -1 فروش، 0 خنثی.
- تحلیل زنده = رأی آخرین کندل‌ها، وزن‌دار جمع می‌شود.
- بک‌تست = همان رأی‌ها روی کل تاریخچه + حد ضرر/سود ATR ← وین‌ریت، بازده، Profit Factor.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable

import numpy as np
import pandas as pd


# ───────────────────────── اندیکاتورها (منطبق با توابع ta.* در Pine Script) ─────────────────────────
def ema(s, n):
    return s.ewm(span=n, adjust=False).mean()


def rma(s, n):
    return s.ewm(alpha=1 / n, adjust=False).mean()


def rsi(close, n=14):
    d = close.diff()
    up, dn = rma(d.clip(lower=0), n), rma(-d.clip(upper=0), n)
    return (100 - 100 / (1 + up / dn.replace(0, np.nan))).fillna(100)


def atr(df, n=14):
    h, l, c = df["high"], df["low"], df["close"]
    tr = pd.concat([h - l, (h - c.shift()).abs(), (l - c.shift()).abs()], axis=1).max(axis=1)
    return rma(tr, n)


def macd(close, f=12, s=26, sig=9):
    m = ema(close, f) - ema(close, s)
    sg = ema(m, sig)
    return m, sg, m - sg


def bollinger(close, n=20, k=2.0):
    mid = close.rolling(n).mean()
    sd = close.rolling(n).std(ddof=0)
    return mid - k * sd, mid, mid + k * sd


def supertrend(df, n=10, mult=3.0):
    hl2 = (df["high"] + df["low"]) / 2
    a = atr(df, n)
    up = (hl2 - mult * a).to_numpy(copy=True)
    dn = (hl2 + mult * a).to_numpy(copy=True)
    c = df["close"].to_numpy()
    d = np.ones(len(c))
    for i in range(1, len(c)):
        if c[i - 1] > up[i - 1]:
            up[i] = max(up[i], up[i - 1])
        if c[i - 1] < dn[i - 1]:
            dn[i] = min(dn[i], dn[i - 1])
        if d[i - 1] == -1 and c[i] > dn[i - 1]:
            d[i] = 1
        elif d[i - 1] == 1 and c[i] < up[i - 1]:
            d[i] = -1
        else:
            d[i] = d[i - 1]
    return pd.Series(d, index=df.index)


def stoch_rsi(close, n=14, k=3, d=3):
    r = rsi(close, n)
    lo, hi = r.rolling(n).min(), r.rolling(n).max()
    kk = (100 * (r - lo) / (hi - lo).replace(0, np.nan)).rolling(k).mean()
    return kk, kk.rolling(d).mean()


def vwap(df, n=48):
    tp = (df["high"] + df["low"] + df["close"]) / 3
    v = df["volume"].replace(0, np.nan)
    return ((tp * v).rolling(n).sum() / v.rolling(n).sum()).fillna(tp)


def ichimoku(df, t=9, k=26, s=52):
    h, l = df["high"], df["low"]
    tenkan = (h.rolling(t).max() + l.rolling(t).min()) / 2
    kijun = (h.rolling(k).max() + l.rolling(k).min()) / 2
    span_a = ((tenkan + kijun) / 2).shift(k)
    span_b = ((h.rolling(s).max() + l.rolling(s).min()) / 2).shift(k)
    return tenkan, kijun, span_a, span_b


def adx(df, n=14):
    h, l = df["high"], df["low"]
    upm, dnm = h.diff(), -l.diff()
    pdm = pd.Series(np.where((upm > dnm) & (upm > 0), upm, 0.0), index=df.index)
    ndm = pd.Series(np.where((dnm > upm) & (dnm > 0), dnm, 0.0), index=df.index)
    a = atr(df, n).replace(0, np.nan)
    pdi, ndi = 100 * rma(pdm, n) / a, 100 * rma(ndm, n) / a
    dx = 100 * (pdi - ndi).abs() / (pdi + ndi).replace(0, np.nan)
    return rma(dx.fillna(0), n)


# ───────────────────────── استراتژی‌ها (هر کدام یک سری رأی برمی‌گرداند) ─────────────────────────
def _sig(up, dn, index):
    return pd.Series(np.where(up, 1, np.where(dn, -1, 0)), index=index).astype(int)


def st_supertrend(df):
    return supertrend(df).astype(int)


def st_ema(f, s):
    def fn(df):
        a, b = ema(df["close"], f), ema(df["close"], s)
        return _sig(a > b, a < b, df.index)
    return fn


def st_macd_rsi(df):
    _, _, h = macd(df["close"])
    r = rsi(df["close"])
    return _sig((h > 0) & (h > h.shift()) & (r < 70), (h < 0) & (h < h.shift()) & (r > 30), df.index)


def st_bb_rsi(df, n_rsi=7):
    lo, _, up = bollinger(df["close"])
    r, c = rsi(df["close"], n_rsi), df["close"]
    return _sig((c <= lo) & (r < 30), (c >= up) & (r > 70), df.index)


def st_stoch(df):
    k, d = stoch_rsi(df["close"])
    return _sig((k.shift() < d.shift()) & (k > d) & (k < 25), (k.shift() > d.shift()) & (k < d) & (k > 75), df.index)


def st_vwap(df):
    c, w, e = df["close"], vwap(df), ema(df["close"], 9)
    return _sig((c > w) & (c > e), (c < w) & (c < e), df.index)


def st_ichimoku(df):
    t, k, a, b = ichimoku(df)
    c = df["close"]
    top, bot = np.maximum(a, b), np.minimum(a, b)
    return _sig((c > top) & (t > k), (c < bot) & (t < k), df.index)


def st_rsi_div(df, w=30):
    c, r = df["close"].to_numpy(), rsi(df["close"]).to_numpy()
    out = np.zeros(len(c), dtype=int)
    h = w // 2
    for i in range(w, len(c)):
        a, b = c[i - w + 1:i - h + 1], c[i - h + 1:i + 1]
        ra, rb = r[i - w + 1:i - h + 1], r[i - h + 1:i + 1]
        i1, i2 = a.argmin(), b.argmin()
        j1, j2 = a.argmax(), b.argmax()
        if b[i2] < a[i1] and rb[i2] > ra[i1] and r[i] < 45:
            out[i] = 1
        elif b[j2] > a[j1] and rb[j2] < ra[j1] and r[i] > 55:
            out[i] = -1
    return pd.Series(out, index=df.index)


@dataclass
class Strategy:
    key: str
    name: str
    fn: Callable
    kind: str  # state: رأی پیوسته (روند) · event: رأی لحظه‌ای (برگشت)
    why: Callable


STRATEGIES = {s.key: s for s in [
    Strategy("supertrend", "Supertrend (10, 3)", st_supertrend, "state",
             lambda df, v: "روند صعودی" if v > 0 else "روند نزولی"),
    Strategy("ema50_200", "EMA 50/200 (Golden Cross)", st_ema(50, 200), "state",
             lambda df, v: "EMA50 بالای EMA200" if v > 0 else "EMA50 زیر EMA200"),
    Strategy("ema21_55", "EMA 21/55", st_ema(21, 55), "state",
             lambda df, v: "سریع بالای کند" if v > 0 else "سریع زیر کند"),
    Strategy("ema9_21", "EMA 9/21", st_ema(9, 21), "state",
             lambda df, v: "سریع بالای کند" if v > 0 else "سریع زیر کند"),
    Strategy("ichimoku", "Ichimoku Cloud", st_ichimoku, "state",
             lambda df, v: "بالای ابر" if v > 0 else "زیر ابر" if v < 0 else "داخل ابر"),
    Strategy("macd_rsi", "MACD + RSI", st_macd_rsi, "state",
             lambda df, v: f"RSI={rsi(df['close']).iloc[-1]:.0f}، هیستوگرام " + ("قوی‌شونده" if v else "خنثی")),
    Strategy("vwap", "VWAP + EMA9", st_vwap, "state",
             lambda df, v: "بالای VWAP" if v > 0 else "زیر VWAP" if v < 0 else "حوالی VWAP"),
    Strategy("bb_rsi", "Bollinger + RSI(7)", st_bb_rsi, "event",
             lambda df, v: "برگشت از باند پایین" if v > 0 else "برگشت از باند بالا" if v < 0 else "داخل باندها"),
    Strategy("stoch", "Stochastic RSI", st_stoch, "event",
             lambda df, v: f"K={stoch_rsi(df['close'])[0].iloc[-1]:.0f}"),
    Strategy("rsi_div", "واگرایی RSI", st_rsi_div, "event",
             lambda df, v: "واگرایی مثبت" if v > 0 else "واگرایی منفی" if v < 0 else "بدون واگرایی"),
]}
COMBINED = "agent"  # کلید «عامل ترکیبی» در بک‌تست

# ───────────────────────── حالت‌ها ─────────────────────────
MODES = {
    "long": dict(title="بلندمدت", tf="1d", limit=400, sl_atr=3.0, tp_atr=6.0,
                 strategies={"ema50_200": 1.3, "ichimoku": 1.3, "supertrend": 1.0, "rsi_div": 1.2}),
    "short": dict(title="کوتاه‌مدت", tf="4h", limit=400, sl_atr=2.0, tp_atr=3.5,
                  strategies={"supertrend": 1.2, "macd_rsi": 1.0, "ema21_55": 1.0, "rsi_div": 1.2}),
    "scalp": dict(title="نوسان‌گیری", tf="5m", limit=400, sl_atr=1.2, tp_atr=1.8,
                  strategies={"vwap": 1.0, "bb_rsi": 1.2, "stoch": 1.0, "ema9_21": 1.0}),
}
TIMEFRAMES = ["5m", "15m", "1h", "4h", "1d"]


def votes_series(df, key):
    s = STRATEGIES[key]
    v = s.fn(df).fillna(0).astype(int)
    if s.kind == "event":  # سیگنال برگشتی تا ۲ کندل بعد هم معتبر می‌ماند
        v = v.replace(0, np.nan).ffill(limit=2).fillna(0).astype(int)
    return v


def score_series(df, weights: dict, mode_id=None):
    tot = sum(weights.values()) or 1
    sc = sum(votes_series(df, k) * w for k, w in weights.items()) * 100 / tot
    if mode_id != "scalp":
        sc = sc.where(adx(df) >= 18, sc * 0.7)  # بازار بی‌روند ← سیگنال ضعیف‌تر
    return sc


# ───────────────────────── تحلیل زنده ─────────────────────────
@dataclass
class Vote:
    key: str
    name: str
    vote: int
    weight: float
    why: str
    winrate: float | None = None
    trades: int = 0


@dataclass
class Analysis:
    signal: str
    score: float
    confidence: int
    price: float
    stop: float
    target: float
    votes: list = field(default_factory=list)
    trend_strength: float = 0.0
    agent_winrate: float | None = None


def analyze(df, mode, threshold=35, with_winrate=True, allow_short=False):
    cfg = MODES[mode]
    votes = []
    for k, w in cfg["strategies"].items():
        s = STRATEGIES[k]
        try:
            v = int(votes_series(df, k).iloc[-1])
            why = s.why(df, v)
        except Exception as e:
            v, why = 0, f"داده ناکافی ({e.__class__.__name__})"
        vt = Vote(k, s.name, v, w, why)
        if with_winrate:
            try:
                r = backtest(df, k, cfg["sl_atr"], cfg["tp_atr"], allow_short=allow_short)
                vt.winrate, vt.trades = r.winrate, len(r.trades)
            except Exception:
                pass
        votes.append(vt)
    sc = score_series(df, cfg["strategies"], mode)
    score = float(sc.iloc[-1])
    sig = "buy" if score >= threshold else "sell" if score <= -threshold else "hold"
    side = 1 if score > 0 else -1
    agree = sum(1 for v in votes if v.vote == side) / max(1, len(votes))
    conf = int(min(95, 40 + abs(score) * 0.4 + agree * 20))
    p, at = float(df["close"].iloc[-1]), float(atr(df).iloc[-1])
    d = -1 if sig == "sell" else 1
    an = Analysis(sig, round(score, 1), conf, p, p - d * cfg["sl_atr"] * at, p + d * cfg["tp_atr"] * at,
                  votes, float(adx(df).iloc[-1]))
    if with_winrate:
        try:
            an.agent_winrate = backtest(df, COMBINED, cfg["sl_atr"], cfg["tp_atr"], allow_short=allow_short,
                                        mode=mode, threshold=threshold).winrate
        except Exception:
            pass
    return an


# ───────────────────────── بک‌تست ─────────────────────────
@dataclass
class Trade:
    side: int
    i_in: int
    i_out: int
    t_in: float
    t_out: float
    p_in: float
    p_out: float
    pct: float
    reason: str


@dataclass
class BTResult:
    key: str
    name: str
    tf: str
    trades: list
    winrate: float | None
    total_pct: float
    profit_factor: float | None
    max_dd: float
    equity: list


def signals_for(df, key, mode=None, threshold=35):
    if key == COMBINED:
        m = mode or "short"
        sc = score_series(df, MODES[m]["strategies"], m)
        return pd.Series(np.where(sc >= threshold, 1, np.where(sc <= -threshold, -1, 0)), index=df.index)
    return STRATEGIES[key].fn(df).fillna(0).astype(int)


def backtest(df, key, sl_atr=2.0, tp_atr=3.0, allow_short=False, fee=0.001, mode=None, threshold=35, tf="",
             warmup=60):
    sig = signals_for(df, key, mode, threshold).to_numpy()
    a = atr(df).to_numpy()
    o, h, l, c, ts = (df[k].to_numpy() for k in ("open", "high", "low", "close", "ts"))
    trades, pos = [], None
    for i in range(max(1, warmup), len(c)):
        if pos:
            side, i_in, p_in, stop, tgt = pos
            hit = None
            if side > 0:
                if l[i] <= stop:
                    hit = (min(stop, o[i]), "حد ضرر")
                elif h[i] >= tgt:
                    hit = (max(tgt, o[i]) if o[i] > tgt else tgt, "حد سود")
            else:
                if h[i] >= stop:
                    hit = (max(stop, o[i]), "حد ضرر")
                elif l[i] <= tgt:
                    hit = (min(tgt, o[i]) if o[i] < tgt else tgt, "حد سود")
            if not hit and sig[i] == -side:
                hit = (c[i], "سیگنال مخالف")
            if hit:
                px, why = hit
                pct = side * (px / p_in - 1) * 100 - fee * 2 * 100
                trades.append(Trade(side, i_in, i, ts[i_in], ts[i], p_in, px, pct, why))
                pos = None
        if pos is None and sig[i] != 0 and sig[i] != sig[i - 1] and not np.isnan(a[i]):
            side = int(sig[i])
            if side < 0 and not allow_short:
                continue
            pos = (side, i, c[i], c[i] - side * sl_atr * a[i], c[i] + side * tp_atr * a[i])
    eq, e, peak, dd = [], 100.0, 100.0, 0.0
    for t in trades:
        e *= 1 + t.pct / 100
        peak = max(peak, e)
        dd = max(dd, (peak - e) / peak * 100)
        eq.append((t.t_out, e))
    wins = [t.pct for t in trades if t.pct > 0]
    loss = [-t.pct for t in trades if t.pct <= 0]
    name = "عامل ترکیبی" if key == COMBINED else STRATEGIES[key].name
    return BTResult(key, name, tf, trades,
                    len(wins) / len(trades) * 100 if trades else None,
                    e - 100, (sum(wins) / sum(loss)) if loss else (None if not wins else float("inf")), dd, eq)
