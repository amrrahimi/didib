"""رابط کاربری دسکتاپ «دیده‌بان» (PySide6 + pyqtgraph)، فارسی و راست‌به‌چپ.

سه بخش اصلی:  تحلیل زنده و ربات  ·  بک‌تست و وین‌ریت  ·  حساب مجازی
"""
from __future__ import annotations

from datetime import datetime

import numpy as np
import pyqtgraph as pg
from PySide6.QtCore import QPointF, QRectF, Qt, QThread
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (QAbstractItemView, QButtonGroup, QCheckBox, QComboBox, QDialog, QDoubleSpinBox,
                               QFormLayout, QFrame, QGridLayout, QHBoxLayout, QHeaderView, QLabel, QLineEdit,
                               QListWidget, QListWidgetItem, QMainWindow, QMessageBox, QPlainTextEdit, QProgressBar,
                               QPushButton, QScrollArea, QSpinBox, QSplitter, QTableWidget, QTableWidgetItem,
                               QTabWidget, QVBoxLayout, QWidget)

from . import storage
from .engine import COMBINED, MODES, STRATEGIES, TIMEFRAMES, ema
from .exchange import EXCHANGES, FA_NAMES, MARKET_TYPES, MAX_LEV
from .worker import BacktestJob, Worker

TEAL, VIOLET, YELLOW, INK, PAPER, MUTED = "#0f8d7b", "#8942bd", "#eadd17", "#1e1a1a", "#eef6f4", "#56706b"
TONE = {"buy": TEAL, "sell": VIOLET, "hold": YELLOW}
WORDS = {"long": {"buy": "انباشت", "hold": "صبر", "sell": "کاهش سهم"},
         "short": {"buy": "خرید", "hold": "نگه‌داری", "sell": "فروش"},
         "scalp": {"buy": "ورود", "hold": "تماشا", "sell": "خروج"}}
WORDS_SHORT = {"long": "شورت بلندمدت", "short": "شورت", "scalp": "ورود شورت"}
EMAS = {"long": (50, 200), "short": (21, 55), "scalp": (9, 21)}
LOG_COLORS = {"info": "#cfdcd9", "buy": "#5fd6c2", "sell": "#c79bf0", "warn": YELLOW, "error": "#ff9b9b"}
SERIES = ["#0f8d7b", "#8942bd", "#d18a00", "#2d6f9e", "#c2416b", "#1e1a1a", "#5c9e2d", "#7a5af8", "#a0522d",
          "#008b9a", "#b8577a"]
TF_FA = {"5m": "۵ دقیقه", "15m": "۱۵ دقیقه", "1h": "۱ ساعت", "4h": "۴ ساعت", "1d": "روزانه"}

QSS = f"""
* {{ font-family: "Vazirmatn", "Segoe UI", "Tahoma", "Geeza Pro"; font-size: 14px; color: {INK}; }}
QMainWindow, #root {{ background: {PAPER}; }}
QFrame#card {{ background: white; border-radius: 18px; }}
QLabel#muted {{ color: {MUTED}; }}
QLabel#title {{ font-size: 24px; font-weight: 900; }}
QLabel#big {{ font-size: 40px; font-weight: 900; }}
QPushButton {{ border: none; border-radius: 12px; padding: 9px 16px; background: {PAPER}; font-weight: 700; }}
QPushButton:hover {{ background: #e2eeeb; }}
QPushButton:disabled {{ color: #9aa9a6; }}
QPushButton#mode {{ background: white; border-radius: 16px; padding: 12px 16px; font-size: 17px; font-weight: 900; text-align: right; }}
QPushButton#mode:checked {{ background: {INK}; color: white; border-bottom: 4px solid {TEAL}; }}
QPushButton#seg {{ background: white; border-radius: 10px; padding: 8px 14px; }}
QPushButton#seg:checked {{ background: {INK}; color: white; }}
QPushButton#primary {{ background: {INK}; color: white; }}
QPushButton#go {{ background: {TEAL}; color: white; }}
QPushButton#go:checked {{ background: {VIOLET}; }}
QPushButton#long {{ background: {TEAL}; color: white; }}
QPushButton#short {{ background: {VIOLET}; color: white; }}
QLineEdit, QComboBox, QSpinBox, QDoubleSpinBox {{ background: {PAPER}; border: none; border-radius: 10px; padding: 8px 12px; }}
QTableWidget, QListWidget {{ background: white; border: none; gridline-color: transparent; selection-background-color: {PAPER}; selection-color: {INK}; }}
QTableWidget::item {{ padding: 6px; }}
QHeaderView::section {{ background: white; border: none; color: {MUTED}; font-weight: 700; padding: 6px; }}
QTabWidget::pane {{ border: none; }}
QTabBar::tab {{ background: transparent; padding: 10px 18px; color: {MUTED}; font-weight: 800; font-size: 15px; }}
QTabBar::tab:selected {{ color: {INK}; border-bottom: 3px solid {TEAL}; }}
QPlainTextEdit#log {{ background: {INK}; border-radius: 14px; padding: 10px; color: #e8eeee; }}
QProgressBar {{ background: rgba(255,255,255,.25); border: none; border-radius: 6px; height: 12px; }}
QProgressBar::chunk {{ background: white; border-radius: 6px; }}
QProgressBar#bt {{ background: {PAPER}; }}
QProgressBar#bt::chunk {{ background: {TEAL}; }}
"""


def fmt(x):
    if x is None:
        return "—"
    x = float(x)
    return f"{x:,.0f}" if abs(x) >= 1000 else f"{x:,.2f}" if abs(x) >= 1 else f"{x:.4f}" if abs(x) >= 0.01 else f"{x:.8f}"


def wr_color(wr):
    if wr is None:
        return QColor("#d9e3e1")
    if wr >= 60:
        return QColor("#9fdcd1")
    if wr >= 50:
        return QColor("#d6eee9")
    if wr >= 40:
        return QColor("#f6f0b0")
    return QColor("#e2cdf3")


def card():
    f = QFrame()
    f.setObjectName("card")
    return f


def muted(text):
    l = QLabel(text)
    l.setObjectName("muted")
    return l


def table(cols, stretch=True):
    t = QTableWidget(0, len(cols))
    t.setHorizontalHeaderLabels(cols)
    t.verticalHeader().hide()
    t.setShowGrid(False)
    t.setEditTriggers(QAbstractItemView.NoEditTriggers)
    t.setSelectionBehavior(QAbstractItemView.SelectRows)
    if stretch:
        t.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
    return t


class Candles(pg.GraphicsObject):
    """شمع‌های ژاپنی؛ مستقیم رسم می‌شود تا قیمت‌های خیلی کوچک (مثل PEPE) هم درست دیده شوند."""

    def __init__(self):
        super().__init__()
        self.rows, self.w, self.rect = [], 1.0, QRectF()

    def set(self, df, width):
        self.prepareGeometryChange()
        self.rows = list(df[["ts", "open", "high", "low", "close"]].itertuples(index=False))
        self.w = float(width)
        lo, hi = float(df["low"].min()), float(df["high"].max())
        x0, x1 = float(df["ts"].min()) - self.w, float(df["ts"].max()) + self.w
        self.rect = QRectF(x0, lo, x1 - x0, (hi - lo) or abs(hi) * 0.01 or 1.0)
        self.update()

    def paint(self, p, *a):
        for t, o, h, l, c in self.rows:
            col = QColor("#7fc9bd" if c >= o else "#c7a6e3")
            p.setPen(pg.mkPen(col, width=1))
            p.drawLine(QPointF(t, l), QPointF(t, h))
            p.setBrush(pg.mkBrush(col))
            body = (c - o) or (h - l) * 0.01 or abs(c) * 1e-4
            p.drawRect(QRectF(t - self.w / 2, o, self.w, body))

    def boundingRect(self):
        return self.rect


def make_plot():
    pg.setConfigOptions(antialias=True, background="w", foreground=MUTED)
    p = pg.PlotWidget(axisItems={"bottom": pg.DateAxisItem()})
    p.setLayoutDirection(Qt.LeftToRight)
    p.showGrid(x=False, y=True, alpha=0.12)
    p.setMenuEnabled(False)
    return p


# ───────────────────────── پنجره‌ی اتصال ─────────────────────────
class ConnectDialog(QDialog):
    def __init__(self, parent, settings):
        super().__init__(parent)
        self.setWindowTitle("اتصال به صرافی")
        self.setLayoutDirection(Qt.RightToLeft)
        self.setMinimumWidth(500)
        lay = QVBoxLayout(self)
        t = QLabel("اتصال به صرافی")
        t.setObjectName("title")
        lay.addWidget(t)
        hint = muted("کلید API را از پنل صرافی بسازید. فقط دسترسی «خواندن» و «معامله» (اسپات/مارجین/فیوچرز) بدهید؛ هرگز «برداشت».")
        hint.setWordWrap(True)
        lay.addWidget(hint)
        form = QFormLayout()
        self.ex = QComboBox()
        for k, (fa, _, _) in EXCHANGES.items():
            self.ex.addItem(f"{fa}  ({k})", k)
        self.ex.setCurrentIndex(max(0, self.ex.findData(settings["exchange"])))
        self.key, self.sec, self.pw = QLineEdit(), QLineEdit(), QLineEdit()
        for w, ph in ((self.key, "API Key"), (self.sec, "API Secret"), (self.pw, "Passphrase")):
            w.setLayoutDirection(Qt.LeftToRight)
            w.setPlaceholderText(ph)
        self.sec.setEchoMode(QLineEdit.Password)
        self.pw.setEchoMode(QLineEdit.Password)
        form.addRow("صرافی", self.ex)
        form.addRow("API Key", self.key)
        form.addRow("API Secret", self.sec)
        self.pw_lbl = QLabel("Passphrase")
        form.addRow(self.pw_lbl, self.pw)
        lay.addLayout(form)
        self.testnet = QCheckBox("حالت تست‌نت (پول آزمایشی خود صرافی)")
        self.testnet.setChecked(settings.get("testnet", False))
        self.remember = QCheckBox("ذخیره‌ی امن کلیدها در Keychain / Credential Manager")
        self.remember.setChecked(True)
        self.live = QCheckBox("معامله‌ی واقعی با پول واقعی")
        warn = QLabel("بدون تیک: ربات با قیمت زنده ولی «حساب مجازی» معامله می‌کند. اول چند روز همین را تست کنید.")
        warn.setWordWrap(True)
        warn.setStyleSheet("background:#fbf6c4; border-radius:10px; padding:10px;")
        for w in (self.testnet, self.remember, self.live, warn):
            lay.addWidget(w)
        row = QHBoxLayout()
        ok = QPushButton("اتصال و شروع")
        ok.setObjectName("go")
        pub = QPushButton("فقط قیمت + حساب مجازی")
        forget = QPushButton("حذف کلیدها")
        row.addWidget(ok)
        row.addWidget(pub)
        row.addStretch()
        row.addWidget(forget)
        lay.addLayout(row)
        ok.clicked.connect(self._ok)
        pub.clicked.connect(self._public)
        forget.clicked.connect(self._forget)
        self.ex.currentIndexChanged.connect(self._load)
        self.result_data = None
        self.mtype = settings["market_type"]
        self._load()

    def _load(self):
        ex = self.ex.currentData()
        self.pw.setVisible(EXCHANGES[ex][1])
        self.pw_lbl.setVisible(EXCHANGES[ex][1])
        k = storage.load_keys(ex)
        self.key.setText(k[0] if k else "")
        self.sec.setText(k[1] if k else "")
        self.pw.setText(k[2] if k else "")

    def _forget(self):
        storage.delete_keys(self.ex.currentData())
        self._load()

    def _public(self):
        self.result_data = (self.ex.currentData(), None, self.testnet.isChecked(), False)
        self.accept()

    def _ok(self):
        ex = self.ex.currentData()
        k, s, p = self.key.text().strip(), self.sec.text().strip(), self.pw.text().strip()
        if not (k and s):
            QMessageBox.information(self, "کلید لازم است", "API Key و Secret را وارد کنید، یا «فقط قیمت + حساب مجازی» را بزنید.")
            return
        live = self.live.isChecked()
        if live and self.mtype == "margin" and not EXCHANGES[ex][2]:
            QMessageBox.warning(self, "مارجین", "مارجین واقعی برای این صرافی پشتیبانی نمی‌شود. از فیوچرز استفاده کنید.")
            return
        if live and QMessageBox.warning(self, "معامله‌ی واقعی",
                                        "ربات با پول واقعی خرید و فروش می‌کند و ممکن است ضرر کنید.\nمطمئن هستید؟",
                                        QMessageBox.Yes | QMessageBox.No, QMessageBox.No) != QMessageBox.Yes:
            return
        if self.remember.isChecked():
            storage.save_keys(ex, k, s, p)
        self.result_data = (ex, (k, s, p), self.testnet.isChecked(), live)
        self.accept()


# ───────────────────────── پنجره‌ی اصلی ─────────────────────────
class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.s = storage.load_settings()
        self.setWindowTitle("دیده‌بان · عامل هوشمند بازار رمزارز")
        self.resize(1440, 920)
        self.all_syms, self.tk, self.positions, self.equity = [], {}, [], 0.0
        self.bt_res, self.bt_frames, self.bt_job = {}, {}, None
        self.keys = None  # کلیدهای جلسه‌ی فعلی (فقط در حافظه)
        root = QWidget()
        root.setObjectName("root")
        self.setCentralWidget(root)
        L = QVBoxLayout(root)
        L.setContentsMargins(22, 16, 22, 14)
        L.setSpacing(12)
        L.addLayout(self._header())
        self.main_tabs = QTabWidget()
        self.main_tabs.addTab(self._live_tab(), "تحلیل زنده و ربات")
        self.main_tabs.addTab(self._backtest_tab(), "بک‌تست و وین‌ریت استراتژی‌ها")
        self.main_tabs.addTab(self._paper_tab(), "حساب مجازی")
        L.addWidget(self.main_tabs, 1)
        foot = muted("قیمت‌ها زنده از صرافی · این نرم‌افزار توصیه‌ی مالی نیست؛ نتایج گذشته تضمین آینده نیست.")
        foot.setAlignment(Qt.AlignCenter)
        L.addWidget(foot)

        self.th = QThread(self)
        self.w = Worker(self.s)
        self.w.moveToThread(self.th)
        self.th.started.connect(self.w.run)
        self.w.markets.connect(self.on_markets)
        self.w.tickers.connect(self.on_tickers)
        self.w.analysis.connect(self.on_analysis)
        self.w.log.connect(self.on_log)
        self.w.account.connect(self.on_account)
        self.w.status.connect(lambda t, ok: self.status_lbl.setText(t))
        self.th.start()
        self.fill_history()
        self.refresh_paper()
        self._badge()

    # ═════════ سربرگ ═════════
    def _header(self):
        top = QHBoxLayout()
        logo = QLabel("◉")
        logo.setStyleSheet(f"background:{INK}; color:{YELLOW}; border-radius:14px; font-size:22px; padding:6px 12px;")
        tt = QVBoxLayout()
        a = QLabel("دیده‌بان")
        a.setObjectName("title")
        self.status_lbl = muted("در حال آماده‌سازی…")
        tt.addWidget(a)
        tt.addWidget(self.status_lbl)
        top.addWidget(logo)
        top.addLayout(tt)
        top.addStretch()
        # نوع بازار + اهرم
        self.mt_group = QButtonGroup(self)
        for k, fa in MARKET_TYPES.items():
            b = QPushButton(fa)
            b.setObjectName("seg")
            b.setCheckable(True)
            b.setChecked(k == self.s["market_type"])
            b.setProperty("k", k)
            self.mt_group.addButton(b)
            top.addWidget(b)
        self.mt_group.buttonClicked.connect(lambda b: self._lev_range())
        self.lev = QSpinBox()
        self.lev.setPrefix("اهرم ")
        self.lev.setSuffix("x")
        self.lev.setValue(int(self.s["leverage"]))
        self.mm = QComboBox()
        self.mm.addItem("ایزوله", "isolated")
        self.mm.addItem("کراس", "cross")
        self.mm.setCurrentIndex(max(0, self.mm.findData(self.s["margin_mode"])))
        b_apply = QPushButton("اعمال")
        b_apply.clicked.connect(self.apply_market)
        top.addWidget(self.lev)
        top.addWidget(self.mm)
        top.addWidget(b_apply)
        self._lev_range()
        top.addSpacing(16)
        self.badge = QLabel("")
        top.addWidget(self.badge)
        b_conn = QPushButton("اتصال به صرافی")
        b_conn.setObjectName("primary")
        b_conn.clicked.connect(self.open_connect)
        self.b_bot = QPushButton("▶  شروع ربات")
        self.b_bot.setObjectName("go")
        self.b_bot.setCheckable(True)
        self.b_bot.toggled.connect(self.toggle_bot)
        top.addWidget(b_conn)
        top.addWidget(self.b_bot)
        return top

    def _mtype(self):
        b = self.mt_group.checkedButton()
        return b.property("k") if b else "spot"

    def _lev_range(self):
        mt = self._mtype()
        self.lev.setRange(1, MAX_LEV[mt])
        self.lev.setEnabled(mt != "spot")
        self.mm.setEnabled(mt == "futures")

    def apply_market(self):
        mt, lev, mm = self._mtype(), self.lev.value(), self.mm.currentData()
        if mt == "futures" and lev > 10 and QMessageBox.warning(
                self, "اهرم بالا", f"با اهرم {lev}x، حرکت {100 / lev:.1f}٪ خلاف جهت کل مارجین را از بین می‌برد. ادامه؟",
                QMessageBox.Yes | QMessageBox.No) != QMessageBox.Yes:
            return
        self._reconnect(self.s["exchange"], self.keys, self.s.get("testnet", False), self.s.get("live_trading", False))

    def _reconnect(self, ex, keys, testnet, live):
        if self.b_bot.isChecked():
            self.b_bot.setChecked(False)
        if self.positions and QMessageBox.question(
                self, "پوزیشن باز", "پوزیشن باز دارید. با تغییر بازار، مدیریت آن‌ها تا برگشت به همین بازار متوقف می‌شود. ادامه؟"
        ) != QMessageBox.Yes:
            return
        self.w.connect_exchange(ex, keys, testnet, live, self._mtype(), self.lev.value(), self.mm.currentData())

    def _badge(self):
        live = self.s.get("live_trading", False)
        self.badge.setText(("● حساب واقعی" if live else "● حساب مجازی") + (f" · {self.equity:,.2f} USDT" if self.equity else ""))
        self.badge.setStyleSheet(f"background:{VIOLET if live else '#fbf6c4'}; color:{'white' if live else INK};"
                                 "border-radius:12px; padding:8px 14px; font-weight:800;")

    # ═════════ تب ۱: تحلیل زنده ═════════
    def _live_tab(self):
        page = QWidget()
        L = QVBoxLayout(page)
        L.setContentsMargins(0, 10, 0, 0)
        modes = QHBoxLayout()
        self.mg = QButtonGroup(self)
        desc = {"long": "روزانه · EMA 50/200، ایچیموکو، سوپرترند", "short": "۴ ساعته · سوپرترند، MACD+RSI، EMA 21/55",
                "scalp": "۵ دقیقه · VWAP، بولینگر، Stoch RSI"}
        for k, cfg in MODES.items():
            b = QPushButton(f"{cfg['title']}\n{desc[k]}")
            b.setObjectName("mode")
            b.setCheckable(True)
            b.setChecked(k == self.s["mode"])
            b.clicked.connect(lambda _=False, k=k: self.set_mode(k))
            self.mg.addButton(b)
            modes.addWidget(b)
        L.addLayout(modes)

        split = QSplitter(Qt.Horizontal)
        L.addWidget(split, 1)
        side = card()
        sl = QVBoxLayout(side)
        self.search = QLineEdit()
        self.search.setPlaceholderText("🔍  جستجوی ارز… مثلاً SUI یا سولانا")
        self.search.textChanged.connect(self.fill_coins)
        sl.addWidget(self.search)
        self.list_lbl = muted("")
        sl.addWidget(self.list_lbl)
        self.coins = table(["★", "ارز", "قیمت", "۲۴ ساعت"], stretch=False)
        h = self.coins.horizontalHeader()
        h.setSectionResizeMode(1, QHeaderView.Stretch)
        for i in (0, 2, 3):
            h.setSectionResizeMode(i, QHeaderView.ResizeToContents)
        self.coins.cellClicked.connect(self.coin_clicked)
        sl.addWidget(self.coins)
        split.addWidget(side)

        mid = card()
        ml = QVBoxLayout(mid)
        hd = QHBoxLayout()
        self.sym_lbl = QLabel("")
        self.sym_lbl.setStyleSheet("font-size:20px; font-weight:900;")
        self.px_lbl = QLabel("")
        self.px_lbl.setStyleSheet("font-size:28px; font-weight:900;")
        self.chg_lbl = QLabel("")
        b_l = QPushButton("لانگ دستی")
        b_l.setObjectName("long")
        b_l.clicked.connect(lambda: self.manual(1))
        self.b_s = QPushButton("شورت دستی")
        self.b_s.setObjectName("short")
        self.b_s.clicked.connect(lambda: self.manual(-1))
        hd.addWidget(self.sym_lbl)
        hd.addWidget(b_l)
        hd.addWidget(self.b_s)
        hd.addStretch()
        hd.addWidget(self.chg_lbl)
        hd.addWidget(self.px_lbl)
        ml.addLayout(hd)
        self.plot = make_plot()
        self.candles = Candles()
        self.plot.addItem(self.candles)
        self.e1 = self.plot.plot(pen=pg.mkPen(INK, width=1.6))
        self.e2 = self.plot.plot(pen=pg.mkPen("#c9a800", width=1.6))
        self.l_tp = pg.InfiniteLine(angle=0, pen=pg.mkPen(TEAL, width=1.4, style=Qt.DashLine), label="هدف",
                                    labelOpts={"color": TEAL, "position": 0.05})
        self.l_sl = pg.InfiniteLine(angle=0, pen=pg.mkPen(VIOLET, width=1.4, style=Qt.DashLine), label="حد ضرر",
                                    labelOpts={"color": VIOLET, "position": 0.05})
        self.plot.addItem(self.l_tp)
        self.plot.addItem(self.l_sl)
        ml.addWidget(self.plot, 1)
        lv = QGridLayout()
        self.lv = {}
        for i, (k, t, c) in enumerate([("entry", "نقطه‌ی ورود", INK), ("target", "هدف", TEAL), ("stop", "حد ضرر", VIOLET)]):
            box = QFrame()
            box.setStyleSheet(f"background:{PAPER}; border-radius:12px;")
            bl = QVBoxLayout(box)
            v = QLabel("—")
            v.setStyleSheet(f"font-size:17px; font-weight:900; color:{c};")
            bl.addWidget(muted(t))
            bl.addWidget(v)
            self.lv[k] = v
            lv.addWidget(box, 0, i)
        ml.addLayout(lv)
        split.addWidget(mid)

        right = QWidget()
        rl = QVBoxLayout(right)
        rl.setContentsMargins(0, 0, 0, 0)
        self.vcard = QFrame()
        vl = QVBoxLayout(self.vcard)
        vl.setContentsMargins(22, 18, 22, 18)
        self.v_head = QLabel("نظر عامل")
        self.v_word = QLabel("…")
        self.v_word.setStyleSheet("font-size:48px; font-weight:900;")
        self.v_conf = QProgressBar()
        self.v_conf.setTextVisible(False)
        self.v_meta = QLabel("در انتظار اولین تحلیل…")
        self.v_meta.setWordWrap(True)
        for w in (self.v_head, self.v_word, self.v_conf, self.v_meta):
            vl.addWidget(w)
        self.vcard.setStyleSheet(f"QFrame{{background:{INK}; border-radius:22px;}} QLabel{{color:white;}}")
        rl.addWidget(self.vcard)
        why = card()
        wl = QVBoxLayout(why)
        wl.addWidget(muted("رأی استراتژی‌ها · وین‌ریت روی ۴۰۰ کندل اخیر همین تایم‌فریم"))
        self.votes = table(["استراتژی", "رأی", "وین‌ریت", "دلیل"], stretch=False)
        self.votes.horizontalHeader().setSectionResizeMode(3, QHeaderView.Stretch)
        wl.addWidget(self.votes)
        rl.addWidget(why, 1)
        split.addWidget(right)
        split.setSizes([290, 740, 420])

        self.tabs = QTabWidget()
        self.tabs.setMaximumHeight(240)
        self.logbox = QPlainTextEdit()
        self.logbox.setObjectName("log")
        self.logbox.setReadOnly(True)
        self.tabs.addTab(self.logbox, "گزارش زنده‌ی عامل")
        pw = QWidget()
        pl = QVBoxLayout(pw)
        pl.setContentsMargins(0, 6, 0, 0)
        self.pos_tbl = table(["ارز", "جهت", "اهرم", "ورود", "فعلی", "سود (ROE)", "حد ضرر / هدف", "لیکوئید", ""])
        pl.addWidget(self.pos_tbl)
        b_all = QPushButton("بستن همه‌ی پوزیشن‌ها")
        b_all.clicked.connect(self.close_all)
        pl.addWidget(b_all, 0, Qt.AlignLeft)
        self.tabs.addTab(pw, "پوزیشن‌های باز")
        self.hist_tbl = table(["زمان", "ارز", "جهت", "بازار", "اهرم", "ورود", "خروج", "ROE", "سود/زیان", "دلیل"])
        self.tabs.addTab(self.hist_tbl, "تاریخچه")
        self.tabs.addTab(self._risk_tab(), "مدیریت ریسک")
        L.addWidget(self.tabs)
        return page

    def _risk_tab(self):
        w = QWidget()
        f = QFormLayout(w)
        r = self.s["risk"]
        self.r_pct = QDoubleSpinBox(); self.r_pct.setRange(0.5, 100); self.r_pct.setSuffix(" ٪"); self.r_pct.setValue(r["per_trade_pct"])
        self.r_max = QSpinBox(); self.r_max.setRange(1, 20); self.r_max.setValue(int(r["max_positions"]))
        self.r_conf = QSpinBox(); self.r_conf.setRange(40, 95); self.r_conf.setSuffix(" ٪"); self.r_conf.setValue(int(r["min_confidence"]))
        self.r_day = QDoubleSpinBox(); self.r_day.setRange(0.5, 50); self.r_day.setSuffix(" ٪"); self.r_day.setValue(r["daily_loss_pct"])
        self.r_th = QSpinBox(); self.r_th.setRange(10, 90); self.r_th.setValue(int(r["threshold"]))
        f.addRow("مارجین هر معامله (٪ از موجودی)", self.r_pct)
        f.addRow("حداکثر پوزیشن هم‌زمان", self.r_max)
        f.addRow("حداقل اطمینان برای ورود", self.r_conf)
        f.addRow("سقف ضرر روزانه", self.r_day)
        f.addRow("حساسیت سیگنال (امتیاز لازم)", self.r_th)
        b = QPushButton("ذخیره")
        b.setObjectName("primary")
        b.clicked.connect(self.save_risk)
        f.addRow("", b)
        return w

    # ═════════ تب ۲: بک‌تست ═════════
    def _backtest_tab(self):
        page = QWidget()
        L = QHBoxLayout(page)
        L.setContentsMargins(0, 10, 0, 0)
        L.setSpacing(14)
        ctl = card()
        ctl.setFixedWidth(300)
        cl = QVBoxLayout(ctl)
        t = QLabel("بک‌تست")
        t.setObjectName("title")
        cl.addWidget(t)
        cl.addWidget(muted("ارز"))
        self.bt_sym = QComboBox()
        self.bt_sym.setEditable(True)
        self.bt_sym.setLayoutDirection(Qt.LeftToRight)
        cl.addWidget(self.bt_sym)
        cl.addWidget(muted("تایم‌فریم‌ها"))
        tfrow = QGridLayout()
        self.bt_tfs = {}
        for i, tf in enumerate(TIMEFRAMES):
            c = QCheckBox(TF_FA[tf])
            c.setChecked(tf in ("15m", "1h", "4h", "1d"))
            self.bt_tfs[tf] = c
            tfrow.addWidget(c, i // 2, i % 2)
        cl.addLayout(tfrow)
        cl.addWidget(muted("استراتژی‌ها"))
        self.bt_strats = {}
        box = QWidget()
        bl = QVBoxLayout(box)
        bl.setContentsMargins(0, 0, 0, 0)
        for k in [COMBINED] + list(STRATEGIES):
            c = QCheckBox("عامل ترکیبی (همه با هم)" if k == COMBINED else STRATEGIES[k].name)
            c.setChecked(True)
            self.bt_strats[k] = c
            bl.addWidget(c)
        sc = QScrollArea()
        sc.setWidget(box)
        sc.setWidgetResizable(True)
        sc.setFrameShape(QFrame.NoFrame)
        cl.addWidget(sc, 1)
        f = QFormLayout()
        self.bt_sl = QDoubleSpinBox(); self.bt_sl.setRange(0.5, 10); self.bt_sl.setSingleStep(0.5); self.bt_sl.setValue(2.0); self.bt_sl.setSuffix(" × ATR")
        self.bt_tp = QDoubleSpinBox(); self.bt_tp.setRange(0.5, 20); self.bt_tp.setSingleStep(0.5); self.bt_tp.setValue(3.0); self.bt_tp.setSuffix(" × ATR")
        self.bt_bars = QSpinBox(); self.bt_bars.setRange(300, 3000); self.bt_bars.setSingleStep(100); self.bt_bars.setValue(1000)
        self.bt_short = QCheckBox("شورت هم بگیرد (مثل فیوچرز)")
        f.addRow("حد ضرر", self.bt_sl)
        f.addRow("حد سود", self.bt_tp)
        f.addRow("تعداد کندل", self.bt_bars)
        cl.addLayout(f)
        cl.addWidget(self.bt_short)
        self.bt_go = QPushButton("اجرای بک‌تست")
        self.bt_go.setObjectName("go")
        self.bt_go.clicked.connect(self.run_backtest)
        cl.addWidget(self.bt_go)
        self.bt_prog = QProgressBar()
        self.bt_prog.setObjectName("bt")
        self.bt_prog.setTextVisible(False)
        self.bt_msg = muted("")
        cl.addWidget(self.bt_prog)
        cl.addWidget(self.bt_msg)
        L.addWidget(ctl)

        right = QSplitter(Qt.Vertical)
        mat = card()
        ml = QVBoxLayout(mat)
        ml.addWidget(muted("ماتریس وین‌ریت · روی هر خانه کلیک کنید تا معاملاتش روی چارت بیاید"))
        self.bt_tbl = table([])
        self.bt_tbl.setSelectionMode(QAbstractItemView.NoSelection)
        self.bt_tbl.cellClicked.connect(self.bt_cell)
        ml.addWidget(self.bt_tbl)
        right.addWidget(mat)
        ch = card()
        chl = QHBoxLayout(ch)
        left = QVBoxLayout()
        top = QHBoxLayout()
        self.bt_tf_view = QComboBox()
        self.bt_tf_view.currentIndexChanged.connect(self.draw_bt)
        top.addWidget(muted("تایم‌فریم چارت"))
        top.addWidget(self.bt_tf_view)
        top.addStretch()
        top.addWidget(muted("▲ لانگ  ▼ شورت  ● خروج با سود  ✕ خروج با ضرر"))
        left.addLayout(top)
        self.bt_plot = make_plot()
        self.bt_plot.addLegend(offset=(10, 10), labelTextColor=INK, brush=pg.mkBrush(255, 255, 255, 220))
        left.addWidget(self.bt_plot, 3)
        self.bt_eq = make_plot()
        self.bt_eq.setXLink(self.bt_plot)
        self.bt_eq.setMaximumHeight(150)
        self.bt_eq.setLabel("left", "سرمایه ٪")
        left.addWidget(self.bt_eq, 1)
        chl.addLayout(left, 1)
        lg = QVBoxLayout()
        lg.addWidget(muted("روی چارت نشان بده"))
        self.bt_list = QListWidget()
        self.bt_list.setFixedWidth(260)
        self.bt_list.itemChanged.connect(self.bt_list_changed)
        lg.addWidget(self.bt_list)
        chl.addLayout(lg)
        right.addWidget(ch)
        right.setSizes([300, 520])
        L.addWidget(right, 1)
        return page

    # ═════════ تب ۳: حساب مجازی ═════════
    def _paper_tab(self):
        page = QWidget()
        L = QVBoxLayout(page)
        L.setContentsMargins(0, 10, 0, 0)
        row = QHBoxLayout()
        self.pp = {}
        for k, t in [("eq", "ارزش کل حساب"), ("pnl", "سود / زیان کل"), ("wr", "وین‌ریت معاملات"), ("n", "تعداد معاملات"),
                     ("free", "تتر آزاد")]:
            c = card()
            cl = QVBoxLayout(c)
            cl.setContentsMargins(20, 16, 20, 16)
            v = QLabel("—")
            v.setObjectName("big" if k == "eq" else "title")
            cl.addWidget(muted(t))
            cl.addWidget(v)
            self.pp[k] = v
            row.addWidget(c, 2 if k == "eq" else 1)
        L.addLayout(row)
        mid = QHBoxLayout()
        gc = card()
        gl = QVBoxLayout(gc)
        gl.addWidget(muted("منحنی سرمایه‌ی حساب مجازی"))
        self.pp_plot = make_plot()
        gl.addWidget(self.pp_plot)
        mid.addWidget(gc, 1)
        ctl = card()
        ctl.setFixedWidth(320)
        cl = QVBoxLayout(ctl)
        t = QLabel("پول مجازی")
        t.setObjectName("title")
        cl.addWidget(t)
        d = muted("با قیمت واقعی بازار و پول مجازی تمرین کنید؛ ربات، معامله‌ی دستی، مارجین و فیوچرز همه اینجا کار می‌کنند. "
                  "هیچ سفارشی به صرافی نمی‌رود.")
        d.setWordWrap(True)
        cl.addWidget(d)
        cl.addWidget(muted("موجودی شروع"))
        self.pp_start = QDoubleSpinBox()
        self.pp_start.setRange(50, 10_000_000)
        self.pp_start.setDecimals(0)
        self.pp_start.setSingleStep(500)
        self.pp_start.setSuffix(" USDT")
        self.pp_start.setValue(self.s["paper"]["start"])
        cl.addWidget(self.pp_start)
        quick = QHBoxLayout()
        for v in (100, 1000, 10000):
            b = QPushButton(f"{v:,}")
            b.clicked.connect(lambda _=False, v=v: self.pp_start.setValue(v))
            quick.addWidget(b)
        cl.addLayout(quick)
        b = QPushButton("شروع دوباره با این موجودی")
        b.setObjectName("primary")
        b.clicked.connect(self.reset_paper)
        cl.addWidget(b)
        b2 = QPushButton("رفتن به حساب مجازی")
        b2.clicked.connect(lambda: self._reconnect(self.s["exchange"], None, False, False))
        cl.addWidget(b2)
        cl.addStretch()
        mid.addWidget(ctl)
        L.addLayout(mid, 1)
        self.pp_tbl = table(["زمان", "ارز", "جهت", "بازار", "اهرم", "ورود", "خروج", "ROE", "سود/زیان", "دلیل"])
        self.pp_tbl.setMaximumHeight(220)
        L.addWidget(self.pp_tbl)
        return page

    # ═════════ رویدادها ═════════
    def save_risk(self):
        self.s["risk"].update(per_trade_pct=self.r_pct.value(), max_positions=self.r_max.value(),
                              min_confidence=self.r_conf.value(), daily_loss_pct=self.r_day.value(), threshold=self.r_th.value())
        storage.save_settings(self.s)
        self.on_log("info", "تنظیمات ریسک ذخیره شد")

    def open_connect(self):
        d = ConnectDialog(self, {**self.s, "market_type": self._mtype()})
        d.setStyleSheet(QSS)
        if d.exec() and d.result_data:
            ex, keys, testnet, live = d.result_data
            self.keys = keys
            self._reconnect(ex, keys, testnet, live)

    def toggle_bot(self, on):
        if on and self.s.get("live_trading") and QMessageBox.question(
                self, "شروع ربات", "ربات با پول واقعی معامله می‌کند. شروع شود؟") != QMessageBox.Yes:
            self.b_bot.setChecked(False)
            return
        self.b_bot.setText("■  توقف ربات" if on else "▶  شروع ربات")
        self.w.set_bot(on)

    def manual(self, side):
        sym = self.s["selected"]
        txt = "لانگ" if side > 0 else "شورت"
        acct = "واقعی" if self.s.get("live_trading") else "مجازی"
        if QMessageBox.question(self, f"{txt} دستی", f"{txt} {sym} با {self.s['risk']['per_trade_pct']}٪ موجودی "
                                f"(حساب {acct})، حد ضرر و هدف خودکار. باز شود؟") == QMessageBox.Yes:
            self.w.manual(sym, side)

    def set_mode(self, k):
        self.s["mode"] = k
        self.w.set_mode(k)
        storage.save_settings(self.s)

    def reset_paper(self):
        v = self.pp_start.value()
        if QMessageBox.question(self, "شروع دوباره", f"همه‌ی پوزیشن‌ها و تاریخچه‌ی مجازی پاک و موجودی {v:,.0f} تتر شود؟") == QMessageBox.Yes:
            self.w.reset_paper(v)

    def on_markets(self, syms):
        self.all_syms = syms
        self.s["market_type"] = self._mtype()
        self.b_s.setEnabled(self._mtype() != "spot")
        cur = self.bt_sym.currentText() or self.s["selected"]
        self.bt_sym.blockSignals(True)
        self.bt_sym.clear()
        self.bt_sym.addItems(syms)
        self.bt_sym.setCurrentText(cur)
        self.bt_sym.blockSignals(False)
        self.fill_coins()
        self._badge()

    def on_tickers(self, tk):
        self.tk.update(tk)
        self.fill_coins()
        t = self.tk.get(self.s["selected"])
        if t:
            self.px_lbl.setText(f"${fmt(t.get('last'))}")
            ch = t.get("percentage") or 0
            self.chg_lbl.setText(f"{'▲' if ch >= 0 else '▼'} {ch:+.2f}%")
            self.chg_lbl.setStyleSheet(f"font-weight:800; color:{TEAL if ch >= 0 else VIOLET};")
        self.refresh_positions()

    def fill_coins(self, *_):
        q = self.search.text().strip().upper()
        if q:
            rows = [s for s in self.all_syms if q in s or q in FA_NAMES.get(s.split("/")[0], "")][:150]
            self.list_lbl.setText(f"نتایج ({len(rows)}) · روی ☆ بزنید تا به منتخب اضافه شود")
        else:
            rows = self.s["watchlist"]
            self.list_lbl.setText("ارزهای منتخب · ربات فقط این‌ها را معامله می‌کند")
        self.coins.setRowCount(len(rows))
        for i, s in enumerate(rows):
            base = s.split("/")[0]
            t = self.tk.get(s, {})
            ch = t.get("percentage")
            on = s in self.s["watchlist"]
            star = QTableWidgetItem("★" if on else "☆")
            star.setForeground(QColor("#b5a800" if on else MUTED))
            name = QTableWidgetItem(f"{FA_NAMES.get(base, base)}  ·  {base}")
            name.setData(Qt.UserRole, s)
            px = QTableWidgetItem(fmt(t.get("last")) if t else "—")
            cg = QTableWidgetItem(f"{ch:+.2f}%" if ch is not None else "")
            cg.setForeground(QColor(TEAL if (ch or 0) >= 0 else VIOLET))
            for j, it in enumerate((star, name, px, cg)):
                self.coins.setItem(i, j, it)
            if s == self.s["selected"]:
                self.coins.selectRow(i)

    def coin_clicked(self, r, c):
        s = self.coins.item(r, 1).data(Qt.UserRole)
        if c == 0:
            wl = self.s["watchlist"]
            wl.remove(s) if s in wl else wl.append(s)
            storage.save_settings(self.s)
            self.fill_coins()
            return
        self.s["selected"] = s
        self.w.set_selected(s)
        self.bt_sym.setCurrentText(s)
        self.sym_lbl.setText(f"{FA_NAMES.get(s.split('/')[0], '')}  {s}")

    def on_analysis(self, sym, mode, df, an):
        if sym != self.s["selected"]:
            return
        self.sym_lbl.setText(f"{FA_NAMES.get(sym.split('/')[0], '')}  {sym}  ·  {TF_FA.get(MODES[mode]['tf'], '')}")
        d = df.tail(160)
        w = (d["ts"].iloc[-1] - d["ts"].iloc[-2]) * 0.7 if len(d) > 1 else 1
        self.candles.set(d, w)
        f, s = EMAS[mode]
        self.e1.setData(d["ts"].to_numpy(), ema(df["close"], f).tail(160).to_numpy())
        self.e2.setData(d["ts"].to_numpy(), ema(df["close"], s).tail(160).to_numpy())
        self.l_tp.setValue(an.target)
        self.l_sl.setValue(an.stop)
        self.plot.setYRange(min(d["low"].min(), an.stop, an.target), max(d["high"].max(), an.stop, an.target), padding=0.04)
        self.plot.setXRange(d["ts"].iloc[0], d["ts"].iloc[-1] + w * 4, padding=0)
        for k in ("entry", "target", "stop"):
            self.lv[k].setText(f"${fmt(an.price if k == 'entry' else getattr(an, k))}")
        col = TONE[an.signal]
        fg = INK if an.signal == "hold" else "white"
        self.vcard.setStyleSheet(f"QFrame{{background:{col}; border-radius:22px;}} QLabel{{color:{fg};}}")
        self.v_head.setText(f"نظر عامل · {MODES[mode]['title']} · {MARKET_TYPES[self._mtype()]}")
        word = WORDS[mode][an.signal]
        if an.signal == "sell" and self._mtype() != "spot":
            word = WORDS_SHORT[mode]
        self.v_word.setText(word)
        self.v_conf.setValue(an.confidence)
        wr = f" · وین‌ریت عامل {an.agent_winrate:.0f}٪" if an.agent_winrate is not None else ""
        self.v_meta.setText(f"اطمینان {an.confidence}٪ · امتیاز {an.score:+.0f} · ADX {an.trend_strength:.0f}{wr}")
        self.votes.setRowCount(len(an.votes))
        for i, v in enumerate(an.votes):
            vi = QTableWidgetItem({1: "خرید", -1: "فروش", 0: "خنثی"}[v.vote])
            vi.setForeground(QColor({1: TEAL, -1: VIOLET, 0: MUTED}[v.vote]))
            wi = QTableWidgetItem(f"{v.winrate:.0f}٪ ({v.trades})" if v.winrate is not None else "—")
            wi.setBackground(wr_color(v.winrate))
            for j, it in enumerate((QTableWidgetItem(v.name), vi, wi, QTableWidgetItem(v.why))):
                self.votes.setItem(i, j, it)
        self.votes.resizeColumnsToContents()
        self.votes.horizontalHeader().setSectionResizeMode(3, QHeaderView.Stretch)

    def on_log(self, level, msg):
        t = datetime.now().strftime("%H:%M:%S")
        self.logbox.appendHtml(f'<span style="color:#8fa5a1">{t}</span>&nbsp;&nbsp;'
                               f'<span style="color:{LOG_COLORS.get(level, "#fff")}">{msg}</span>')
        if "بسته شد" in msg or "از نو" in msg:
            self.fill_history()
            self.refresh_paper()

    def on_account(self, positions, bal, eq):
        self.positions, self.equity = positions, eq
        self._badge()
        self.refresh_positions()
        if not self.s.get("live_trading"):
            self.pp["free"].setText(f"{bal.get('USDT', 0):,.2f}")
            self.refresh_paper()

    def refresh_positions(self):
        ps = self.positions
        self.pos_tbl.setRowCount(len(ps))
        for i, p in enumerate(ps):
            cur = (self.tk.get(p["symbol"]) or {}).get("last") or p["entry"]
            roe = p["side"] * (cur / p["entry"] - 1) * 100 * p["lev"]
            vals = [p["symbol"], "لانگ" if p["side"] > 0 else "شورت", f"{p['lev']}x", fmt(p["entry"]), fmt(cur),
                    f"{roe:+.2f}%", f"{fmt(p['stop'])} / {fmt(p['target'])}", fmt(p.get("liq"))]
            for j, v in enumerate(vals):
                it = QTableWidgetItem(v)
                if j in (1, 5):
                    good = (p["side"] > 0) if j == 1 else roe >= 0
                    it.setForeground(QColor(TEAL if good else VIOLET))
                self.pos_tbl.setItem(i, j, it)
            b = QPushButton("بستن")
            b.clicked.connect(lambda _=False, s=p["symbol"]: self.w.close_position(s))
            self.pos_tbl.setCellWidget(i, 8, b)

    def close_all(self):
        if QMessageBox.question(self, "بستن همه", "همه‌ی پوزیشن‌ها با قیمت بازار بسته شوند؟") == QMessageBox.Yes:
            self.w.close_all()

    def _fill_trades(self, tbl, rows):
        rows = rows[::-1][:300]
        tbl.setRowCount(len(rows))
        for i, r in enumerate(rows):
            pnl = float(r.get("pnl") or 0)
            vals = [r.get("time"), r.get("symbol"), r.get("side"), MARKET_TYPES.get(r.get("market"), r.get("market")),
                    f"{r.get('lev')}x", r.get("entry"), r.get("exit"), f"{float(r.get('pct') or 0):+.2f}%",
                    f"{pnl:+.2f}", r.get("reason")]
            for j, v in enumerate(vals):
                it = QTableWidgetItem(str(v))
                if j in (7, 8):
                    it.setForeground(QColor(TEAL if pnl >= 0 else VIOLET))
                tbl.setItem(i, j, it)

    def fill_history(self):
        self._fill_trades(self.hist_tbl, storage.load_trades("live" if self.s.get("live_trading") else "paper"))

    def refresh_paper(self):
        tr = storage.load_trades("paper")
        start = self.s["paper"]["start"]
        self._fill_trades(self.pp_tbl, tr)
        pnl = sum(float(t["pnl"]) for t in tr)
        wins = sum(1 for t in tr if float(t["pnl"]) > 0)
        eq = self.equity if (self.equity and not self.s.get("live_trading")) else self.s["paper"]["USDT"]
        self.pp["eq"].setText(f"{eq:,.2f}")
        self.pp["pnl"].setText(f"{pnl:+,.2f}  ({pnl / start * 100:+.1f}٪)")
        self.pp["pnl"].setStyleSheet(f"color:{TEAL if pnl >= 0 else VIOLET};")
        self.pp["wr"].setText(f"{wins / len(tr) * 100:.0f}٪" if tr else "—")
        self.pp["n"].setText(str(len(tr)))
        self.pp_plot.clear()
        if tr:
            xs = [datetime.strptime(t["time"], "%Y-%m-%d %H:%M").timestamp() for t in tr]
            ys = list(np.cumsum([float(t["pnl"]) for t in tr]) + start)
            xs, ys = [xs[0] - 60] + xs, [start] + ys
            self.pp_plot.plot(xs, ys, pen=pg.mkPen(TEAL, width=2.5), fillLevel=start, brush=pg.mkBrush(15, 141, 123, 40),
                              symbol="o", symbolSize=6, symbolBrush=TEAL, symbolPen=None)
            self.pp_plot.addItem(pg.InfiniteLine(start, angle=0, pen=pg.mkPen(MUTED, style=Qt.DotLine)))

    # ── بک‌تست ──
    def run_backtest(self):
        if self.bt_job and self.bt_job.isRunning():
            return
        sym = self.bt_sym.currentText().strip().upper()
        if "/" not in sym:
            sym = f"{sym}/USDT"
        tfs = [tf for tf, c in self.bt_tfs.items() if c.isChecked()]
        keys = [k for k, c in self.bt_strats.items() if c.isChecked()]
        if not tfs or not keys:
            QMessageBox.information(self, "بک‌تست", "حداقل یک تایم‌فریم و یک استراتژی انتخاب کنید.")
            return
        self.bt_sym_used = sym
        self.bt_go.setEnabled(False)
        self.bt_prog.setValue(0)
        self.bt_job = BacktestJob(self.s["exchange"], sym, None, tfs, self.bt_sl.value(), self.bt_tp.value(),
                                  self.bt_short.isChecked(), self.s["mode"], self.s["risk"]["threshold"], self.bt_bars.value())
        self.bt_job.progress.connect(lambda v, m: (self.bt_prog.setValue(v), self.bt_msg.setText(m)))
        self.bt_job.result.connect(self.on_bt)
        self.bt_job.failed.connect(lambda e: (self.bt_go.setEnabled(True), self.bt_msg.setText(f"خطا: {e}")))
        self.bt_job.start()

    def on_bt(self, res, frames):
        self.bt_res, self.bt_frames = res, frames
        self.bt_go.setEnabled(True)
        self.bt_msg.setText(f"تمام شد · {self.bt_sym_used}")
        tfs = [tf for tf in TIMEFRAMES if tf in frames]
        keys = list(dict.fromkeys(k for k, _ in res))
        self.bt_keys, self.bt_tfs_done = keys, tfs
        self.bt_tbl.setColumnCount(len(tfs) + 1)
        self.bt_tbl.setHorizontalHeaderLabels(["استراتژی"] + [TF_FA[t] for t in tfs])
        self.bt_tbl.setRowCount(len(keys))
        for i, k in enumerate(keys):
            nm = QTableWidgetItem(res[(k, tfs[0])].name)
            if k == COMBINED:
                f = nm.font()
                f.setBold(True)
                nm.setFont(f)
            self.bt_tbl.setItem(i, 0, nm)
            for j, tf in enumerate(tfs):
                r = res[(k, tf)]
                pf = "∞" if r.profit_factor == float("inf") else f"{r.profit_factor:.2f}" if r.profit_factor else "—"
                txt = (f"{r.winrate:.0f}٪  ·  {len(r.trades)} معامله\nبازده {r.total_pct:+.1f}٪ · PF {pf}"
                       if r.winrate is not None else "بدون معامله")
                it = QTableWidgetItem(txt)
                it.setBackground(wr_color(r.winrate))
                it.setTextAlignment(Qt.AlignCenter)
                it.setToolTip(f"حداکثر افت سرمایه: {r.max_dd:.1f}٪")
                self.bt_tbl.setItem(i, j + 1, it)
        self.bt_tbl.resizeRowsToContents()
        self.bt_tf_view.blockSignals(True)
        self.bt_tf_view.clear()
        for tf in tfs:
            self.bt_tf_view.addItem(TF_FA[tf], tf)
        self.bt_tf_view.blockSignals(False)
        # بهترین سه استراتژی در اولین تایم‌فریم پیش‌فرض روی چارت
        self.bt_checked = set(sorted(keys, key=lambda k: -(res[(k, tfs[0])].winrate or 0))[:3])
        self.draw_bt()

    def bt_cell(self, r, c):
        if c == 0 or not self.bt_res:
            return
        k = self.bt_keys[r]
        self.bt_checked.add(k)
        self.bt_tf_view.setCurrentIndex(c - 1)
        self.draw_bt()

    def bt_list_changed(self, _item=None):
        if self.bt_list.signalsBlocked():
            return
        self.bt_checked = {self.bt_list.item(i).data(Qt.UserRole) for i in range(self.bt_list.count())
                           if self.bt_list.item(i).checkState() == Qt.Checked}
        self.draw_bt()

    def draw_bt(self, *_):
        if not self.bt_res or self.bt_tf_view.count() == 0:
            return
        tf = self.bt_tf_view.currentData()
        self.bt_list.blockSignals(True)
        self.bt_list.clear()
        for i, k in enumerate(self.bt_keys):
            r = self.bt_res[(k, tf)]
            wr = f"{r.winrate:.0f}٪" if r.winrate is not None else "—"
            it = QListWidgetItem(f"{r.name}\nوین‌ریت {wr} · {len(r.trades)} معامله · {r.total_pct:+.1f}٪")
            it.setData(Qt.UserRole, k)
            it.setFlags(it.flags() | Qt.ItemIsUserCheckable)
            it.setCheckState(Qt.Checked if k in self.bt_checked else Qt.Unchecked)
            it.setForeground(QColor(SERIES[i % len(SERIES)]))
            self.bt_list.addItem(it)
        self.bt_list.blockSignals(False)

        df = self.bt_frames[tf]
        self.bt_plot.clear()
        self.bt_eq.clear()
        w = (df["ts"].iloc[-1] - df["ts"].iloc[-2]) * 0.7
        c = Candles()
        c.set(df, w)
        self.bt_plot.addItem(c)
        span = float(df["high"].max() - df["low"].min())
        for i, k in enumerate(self.bt_keys):
            if k not in self.bt_checked:
                continue
            r, col = self.bt_res[(k, tf)], SERIES[i % len(SERIES)]
            wr = f"{r.winrate:.0f}%" if r.winrate is not None else "—"
            label = f"{r.name} · وین‌ریت {wr} ({len(r.trades)})"
            off = span * 0.012 * (1 + i % 3)
            L = [t for t in r.trades if t.side > 0]
            S = [t for t in r.trades if t.side < 0]
            self.bt_plot.addItem(pg.ScatterPlotItem(
                [t.t_in for t in L] + [t.t_in for t in S],
                [df["low"].iloc[t.i_in] - off for t in L] + [df["high"].iloc[t.i_in] + off for t in S],
                symbol=["t1"] * len(L) + ["t"] * len(S), size=13, brush=pg.mkBrush(col), pen=pg.mkPen("w", width=0.8),
                name=label))
            win = [t for t in r.trades if t.pct > 0]
            los = [t for t in r.trades if t.pct <= 0]
            self.bt_plot.addItem(pg.ScatterPlotItem([t.t_out for t in win], [t.p_out for t in win], symbol="o", size=9,
                                                    brush=pg.mkBrush(col), pen=pg.mkPen("w", width=0.8)))
            self.bt_plot.addItem(pg.ScatterPlotItem([t.t_out for t in los], [t.p_out for t in los], symbol="x", size=10,
                                                    brush=pg.mkBrush(col), pen=pg.mkPen(col, width=1.5)))
            xs, ys = [], []
            for t in r.trades:
                xs += [t.t_in, t.t_out]
                ys += [t.p_in, t.p_out]
            if xs:
                self.bt_plot.plot(np.array(xs), np.array(ys), connect="pairs",
                                  pen=pg.mkPen(col, width=1.2, style=Qt.DashLine))
                ex = [df["ts"].iloc[0]] + [e[0] for e in r.equity]
                ey = [100.0] + [e[1] for e in r.equity]
                self.bt_eq.plot(ex, ey, pen=pg.mkPen(col, width=2), stepMode=None)
        self.bt_eq.addItem(pg.InfiniteLine(100, angle=0, pen=pg.mkPen(MUTED, style=Qt.DotLine)))
        self.bt_plot.setXRange(df["ts"].iloc[0], df["ts"].iloc[-1], padding=0.01)
        self.bt_plot.setYRange(df["low"].min(), df["high"].max(), padding=0.05)

    def closeEvent(self, e):
        storage.save_settings(self.s)
        self.w.stop()
        self.th.quit()
        self.th.wait(3000)
        if self.bt_job:
            self.bt_job.wait(2000)
        super().closeEvent(e)
