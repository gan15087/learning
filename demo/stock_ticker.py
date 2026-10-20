#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
本地化盯盘小窗  v2.5  ——  零依赖（仅 Python 标准库 + tkinter）

v2.5 新增：鼠标悬停 → 分时图浮窗
  · 鼠标停在某个标的上 0.32 秒，自动在它上方弹出当日分时图浮窗：
      分时线（昨收上方红 / 下方绿）+ 黄色均价线 + 底部成交量柱
      + 左价格刻度 / 右涨跌幅刻度 / 时间刻度 + 标题行现价与涨跌幅。
  · 浮窗贴在标的**上方**，上方放不下自动改到下方，并夹在屏幕内。
  · 分时数据同走腾讯免 key 接口，缓存 45 秒（鼠标划过不会反复请求）。
  · 右键菜单新增「悬停显示分时图」开关（配置项 hover_chart）。
  · 拖动 / 隐身 / 切换布局 / 改标的时自动收起浮窗，不会挂在半空。

v2.4 两项优化
  · 修复「标的多了显示不全 / 被截断」—— 真凶不是估算公式，而是量宽度的时机：
      原来用控件实测宽度（winfo_reqwidth）算窗口宽度，但首次建行时价格还是
      占位符 "--"，量出来偏小；等真实价格（3716.28 / +0.24%）填进去就超出了
      窗口宽度，右边的标的全被裁掉。
      现在：① 宽度改按 tkinter.font 真实字体度量估算，永远按最宽数字预留；
            ② 数据到位后再用实测宽度校正窗口（只加宽，不抖动）；
            ③ 超出屏幕先逐级缩字号（最低 7 号），仍放不下就自动折行（最多 4 行）；
            ④ 竖排名称列宽度按最长中文名自适应，不再把长名字截成半截。
  · 重做设置页面，简化 + 美化：
      启动窗口与「编辑标的」合并为同一套 UI（SettingsPanel）；
      扁平深色主题、卡片式输入框、可滚动已选列表（带计数 / 一行一个 ✕ 删除，
      内容不超高时滚动条自动隐藏）、横条/竖排分段选择器、状态提示行，
      窗口高度贴合内容，去掉了原来一堆单选按钮与按钮排。

v2.3 修复「双击后越来越淡、最后找不着」
  · 根因1：隐身档位 0.10 太狠（几乎不可见）→ 改为 3 档循环 88%/55%/25%
  · 根因2：隐身时自动取消了置顶 → 窗口沉到其他窗口后面，再也找不到。
           现在无论透明度多少都保持置顶。
  · 根因3：双击事件被重复绑定（根窗口 + 每个单元格），会触发多次。
           改为只绑根窗口（tkinter bindtags 会自动覆盖子控件）。
  · 新增「立即恢复清晰显示」菜单项 + --reset-alpha 兜底
  · 新增 double_click_action 配置：cycle(默认) / hide(旧版) / none

v2.1 新增
  · 横条模式（layout=bar）：一行铺开，自动贴任务栏上沿，像行情条一样
  · 竖排模式（layout=list）：老的列表样式，可放右上/左上/居中
  · 右键菜单切换「布局」和「位置」；拖动后自动记住位置（position 变custom）

v2.0 新增
  1. 启动时弹图形化窗口选标的（不需要在黑窗口里敲）
  2. 置顶强化：Windows 下置顶窗口常被别的窗口压住，本版每 3 秒重新置顶一次
  3. 图形化标的编辑器：右键 →「编辑标的…」可增删、上下移、即时搜索
  4. 刷新间隔菜单：3/5/10/30/60 秒随手切
  5. 命令行参数：--codes / --edit / --list / --no-input / --cli / --layout

交互用法
  python stock_ticker.py                     # 启动 → 弹窗选标的 → 开始盯盘
  python stock_ticker.py --no-input          # 跳过弹窗，按上次配置直接开
  python stock_ticker.py --codes 002506 603618
  python stock_ticker.py --layout list       # 竖排模式
  python stock_ticker.py --list              # 打印当前配置
  python stock_ticker.py --edit              # 直接打开标的编辑窗口
  python stock_ticker.py --cli               # 用黑窗口输入（老方式）
  python stock_ticker.py --selftest          # 自检（不进GUI，检查网络与数据源）
  python stock_ticker.py --reset-alpha       # 找回窗口：重置透明度并置顶

操作
  拖动 = 移动；双击 = 循环切换透明度（88% → 55% → 25% → 88%）
  右键 = 菜单（布局/位置/透明度/刷新间隔/编辑标的/立即恢复清晰显示/退出）
  ★ 最低档保留 25% 可见度，且始终置顶 —— 不会再"隐身到找不着"。
    真找不到时：右键菜单点「立即恢复清晰显示」，或跑 --reset-alpha

数据源：腾讯财经实时行情 + smartbox 名称检索（均免key，公网可直连）
运行：python stock_ticker.py   （需本机 Python 3.8+ 含 tkinter，无需 pip 任何包）
"""
import os
import re
import sys
import json
import time
import threading
import datetime
import urllib.parse
import urllib.request
import tkinter as tk
from tkinter import Menu
try:
    import tkinter.font as tkfont
except Exception:      # 无显示/精简环境
    tkfont = None

BASE = os.path.dirname(os.path.abspath(__file__))
CONFIG_PATH = os.path.join(BASE, "ticker_config.json")

BG = "#14161a"
FG = "#c8ccd4"
DIM = "#555b66"
UP = "#ff5b5b"      # 涨=红（中国市场惯例）
DOWN = "#26d07c"    # 跌=绿
FLAT = "#c8ccd4"

DEFAULT_CONFIG = {
    # 想盯什么就往 codes 里加，格式 sh上海/sz深圳/bj北交所/hk港股 + 6位代码
    # 指数：sh000001上证 sz399001深证 sz399006创业板 sh000688科创50 sz399959军工指数
    # 个股/ETF：sz002506 协鑫集成、sz159516 设备ETF国泰、sh603618 杭电股份
    "codes": ["sh000001", "sz399001", "sz399006", "sh000688", "sz002506", "sz159516"],
    # 自定义显示名（不填则用接口返回名）
    "labels": {
        "sh000001": "上证", "sz399001": "深证", "sz399006": "创业板",
        "sh000688": "科创50", "sz002506": "协鑫", "sz159516": "设备ETF"
    },
    "refresh_ms": 5000,
    # 双击循环切换的透明度档位（务必保留一个 ≥0.2 的档，否则你自己也找不到它）
    "opacity_steps": [0.88, 0.55, 0.25],
    "opacity": 0.88,          # 兼容旧配置：正常透明度
    "hidden_opacity": 0.25,   # 兼容旧配置：最低档
    # 双击行为：cycle=循环切换透明度（推荐）/ hide=旧版隐身 / none=不响应
    "double_click_action": "cycle",
    "always_onmost": True,    # 置顶并周期性重新置顶
    "topmost_every_ms": 3000,
    # 布局：bar = 横条（贴任务栏上方）/ list = 竖排列表
    "layout": "bar",
    # 位置：bottom=任务栏上方 / top_right=右上 / top_left=左上 / center=居中 / custom=记住上次
    "position": "bottom",
    "taskbar_gap": 3,          # 距任务栏顶边的像素间隙
    "bar_align": "center",     # 横条在底部水平对齐：left/center/right
    "geometry": "",            # 留空 = 按 layout/position 自动计算
    "hover_chart": True,       # 鼠标悬停到某个标的上时，浮窗显示当日分时图
    "margin": 24,              # 竖排模式下的边距
    "font": "Microsoft YaHei",
    "font_size": 10
}

# 上交所指数（6 位数字会与个股冲突，单独判定）
SH_INDEX = {
    "000001", "000010", "000016", "000300", "000688", "000852",
    "000905", "000922", "000852", "000688", "000016", "000300",
}
SZ_INDEX = {"399001", "399006", "399005", "399101", "399303", "399106", "399959", "399905"}


# ---------------------------------------------------------------- 代码解析
def guess_market(code6: str) -> str:
    """6 位数字 -> 市场前缀（沪深京）"""
    if code6 in SH_INDEX:
        return "sh"
    if code6 in SZ_INDEX:
        return "sz"
    # 北交所新代码段920 开头（2024 新规）
    if code6.startswith("92"):
        return "bj"
    c = code6[0]
    if c in ("6", "5", "9"):
        return "sh"
    if c in ("0", "3", "1", "2"):
        return "sz"
    if c in ("4", "8"):
        return "bj"
    return "sh"


def normalize_code(raw: str):
    """把用户输入规范化成腾讯行情代码。支持：
       002506 / sz002506 / SH600183 / 002506.SZ / 600183.sh / 159516
       返回 (code, label_hint) 或 None
    """
    s = raw.strip().lower().replace(" ", "")
    if not s:
        return None
    # 提取市场前缀
    mkt = ""
    for p in ("sh", "sz", "bj", "hk"):
        if s.startswith(p):
            mkt, s = p, s[len(p):]
            break
    # 处理 600183.sh / 002506.SZ 这种后缀
    if "." in s:
        a, b = s.split(".", 1)
        if b in ("sh", "sz", "bj", "hk"):
            if not mkt:
                mkt = b
            s = a
    s = re.sub(r"\D", "", s)
    if not s:
        return None
    if not mkt:
        mkt = guess_market(s)
    return mkt + s


def search_by_name(keyword: str, limit=12):
    """中文/拼音关键词 -> [(code, name, type)]，走腾讯 smartbox 免 key 接口"""
    kw = keyword.strip()
    if not kw:
        return []
    url = "https://smartbox.gtimg.cn/s3/?t=all&q=" + urllib.parse.quote(kw)
    req = urllib.request.Request(url, headers={
        "User-Agent": "Mozilla/5.0", "Referer": "https://gu.qq.com/"})
    try:
        raw = urllib.request.urlopen(req, timeout=8).read().decode("gbk", errors="ignore")
    except Exception:
        return []
    out = []
    for item in re.findall(r'v_hint="([^"]+)"', raw):
        for rec in item.split("^"):
            p = rec.split("~")
            if len(p) < 5:
                continue
            mkt, code, name = p[0], p[1], p[2]
            if mkt not in ("sh", "sz", "bj", "hk"):
                continue
            if not re.fullmatch(r"\d{5,6}", code):
                continue
            out.append((mkt + code, name, p[4]))
            if len(out) >= limit:
                return out
    return out


def fetch_quotes(codes):
    """返回 {code: {name, price, chg_pct}}，失败返回空 dict"""
    result = {}
    if not codes:
        return result
    url = "https://qt.gtimg.cn/q=" + ",".join(codes)
    req = urllib.request.Request(url, headers={
        "User-Agent": "Mozilla/5.0", "Referer": "https://gu.qq.com/"})
    try:
        raw = urllib.request.urlopen(req, timeout=15).read().decode("gbk", errors="ignore")
    except Exception:
        return result
    for m in re.finditer(r'v_(\w+)="([^"]+)"', raw):
        code, f = m.group(1), m.group(2).split("~")
        if len(f) < 33:
            continue
        try:
            price, prev = float(f[3]), float(f[4])
            try:
                chg_pct = float(f[32])
            except ValueError:
                chg_pct = ((price - prev) / prev * 100) if prev else 0.0
            result[code] = {"name": f[1], "price": price, "chg_pct": chg_pct}
        except Exception:
            continue
    return result


def fetch_minute(code):
    """拉当日分时数据（免 key）。返回：
        {"name","price","prev","open","date",
         "pts": [(hhmm, price, cum_vol, cum_amt), ...]}
        失败 / 无数据返回 None。"""
    url = "https://web.ifzq.gtimg.cn/appstock/app/minute/query?code=" + code
    req = urllib.request.Request(url, headers={
        "User-Agent": "Mozilla/5.0", "Referer": "https://gu.qq.com/"})
    try:
        raw = urllib.request.urlopen(req, timeout=10).read().decode(
            "utf-8", errors="ignore")
        d = json.loads(raw)
    except Exception:
        return None
    node = (d.get("data") or {}).get(code) or {}
    inner = node.get("data") or {}
    arr = inner.get("data") or []
    if not arr:
        return None
    qt = (node.get("qt") or {}).get(code) or []

    def qnum(i, dflt=0.0):
        try:
            return float(qt[i])
        except Exception:
            return dflt

    pts = []
    for line in arr:
        p = line.split()
        if len(p) < 2:
            continue
        try:
            pts.append((p[0], float(p[1]),
                        float(p[2]) if len(p) > 2 else 0.0,
                        float(p[3]) if len(p) > 3 else 0.0))
        except ValueError:
            continue
    if not pts:
        return None
    return {
        "name": qt[1] if len(qt) > 1 else code,
        "price": qnum(3) or pts[-1][1],
        "prev": qnum(4) or pts[0][1],
        "open": qnum(5),
        "date": inner.get("date", ""),
        "pts": pts,
    }


def load_config():
    if not os.path.exists(CONFIG_PATH):
        save_config(dict(DEFAULT_CONFIG))
        return dict(DEFAULT_CONFIG)
    try:
        with open(CONFIG_PATH, encoding="utf-8") as f:
            cfg = json.load(f)
    except Exception:
        return dict(DEFAULT_CONFIG)
    for k, v in DEFAULT_CONFIG.items():
        cfg.setdefault(k, v)
    return cfg


def save_config(cfg):
    try:
        with open(CONFIG_PATH, "w", encoding="utf-8") as f:
            json.dump(cfg, f, ensure_ascii=False, indent=2)
    except Exception:
        pass


# ---------------------------------------------------------------- 启动交互
def prompt_codes(cfg, force=False):
    """控制台交互输入标的。返回是否接受本次输入。"""
    if not sys.stdin or not sys.stdin.isatty():
        return False
    cur = ", ".join(cfg["codes"])
    print("=" * 62)
    print(" 本地化盯盘小窗 v2.0")
    print("=" * 62)
    print(f" 当前标的({len(cfg['codes'])}个)：{cur}")
    print(" 输入方式：6位代码 / 中文名 / 拼音首字母，逗号或空格分隔")
    print("   例：002506 杭电 军工  sh000001    |    直接回车=沿用当前配置")
    print("=" * 62)
    try:
        line = input(" 标的 > ").strip()
    except (EOFError, KeyboardInterrupt):
        print("\n 已取消，沿用当前配置。\n")
        return False
    if not line:
        if not force:
            return False
        line = cur
    tokens = [t for t in re.split(r"[,，\s、;；]+", line) if t]
    new_codes, labels, missing = [], {}, []
    for tk_ in tokens:
        code = normalize_code(tk_)
        if code:
            if code not in new_codes:
                new_codes.append(code)
            continue
        hits = search_by_name(tk_, limit=1)
        if hits:
            c, n, _ = hits[0]
            if c not in new_codes:
                new_codes.append(c)
                labels[c] = n
        else:
            missing.append(tk_)
    if missing:
        print("  ⚠ 未识别：" + "、".join(missing))
    if not new_codes:
        print(" ⚠ 未解析到有效标的，沿用当前配置。\n")
        return False
    old_labels = cfg.get("labels", {})
    for c in new_codes:
        if c not in labels and c not in old_labels:
            labels.pop(c, None)
    merged = dict(old_labels)
    merged.update(labels)
    cfg["codes"] = new_codes
    cfg["labels"] = {k: v for k, v in merged.items() if k in new_codes} or {}
    print(f" ✓ 已设置 {len(new_codes)} 个标的：" + ", ".join(new_codes) + "\n")
    return True


# ---------------------------------------------------------------- 设置面板（v2.4 统一 UI）
# 扁平深色主题（配合 BG 使用）
CARD = "#1b1e24"        # 输入框 / 卡片
ROW = "#1e222a"         # 列表行
ROW_HL = "#272d37"      # 行悬停
BORDER = "#2b3038"
TEXT = "#e6e9ef"
MUTED = "#8b929e"
ACCENT = "#2e7d5b"


def flat_btn(parent, text, cmd, bg="#252a33", fg=TEXT, font=None, width=None,
             padx=12, pady=5):
    """统一的扁平按钮（padx/pady 为按钮内部留白）"""
    b = tk.Button(parent, text=text, command=cmd, bg=bg, fg=fg,
                  activebackground=ROW_HL, activeforeground="#ffffff",
                  relief="flat", bd=0, highlightthickness=0, padx=padx, pady=pady,
                  font=font or ("Microsoft YaHei", 9), cursor="hand2")
    if width:
        b.config(width=width)
    return b


class ScrollFrame:
    """带滚轮的纵向滚动容器（用于已选标的列表）"""

    def __init__(self, parent, height=190, bg=BG):
        self.outer = tk.Frame(parent, bg=bg)
        self.canvas = tk.Canvas(self.outer, bg=bg, highlightthickness=0,
                                height=height, bd=0)
        self.bar = tk.Scrollbar(self.outer, orient="vertical", width=9, bd=0,
                                relief="flat", highlightthickness=0,
                                troughcolor=bg, bg=BORDER,
                                activebackground=ROW_HL,
                                command=self.canvas.yview)
        self.canvas.configure(yscrollcommand=self.bar.set)
        self.canvas.pack(side="left", fill="both", expand=True)
        self._bar_shown = False           # 不再常驻：内容超高才显示
        self.inner = tk.Frame(self.canvas, bg=bg)
        self._win = self.canvas.create_window((0, 0), window=self.inner,
                                              anchor="nw")
        self.inner.bind("<Configure>", self._on_inner)
        self.canvas.bind("<Configure>", self._on_canvas)
        self._pending = None
        self._tries = 0
        self.bind_wheel(self.canvas)
        self.bind_wheel(self.inner)

    def bind_wheel(self, widget):
        """滚轮事件只发给鼠标下的控件，所以每个子控件都要绑一次"""
        try:
            widget.bind("<MouseWheel>", self._on_wheel)
        except Exception:
            pass

    def _on_inner(self, e=None):
        # 滚动区域立即更新；是否显示滚动条延到 idle 再判定
        # （<Configure> 期间窗口可能还没 realize，winfo_height 会返回 1）
        try:
            self.canvas.configure(scrollregion=self.canvas.bbox("all"))
        except Exception:
            pass
        self._schedule_bar_check()

    def _schedule_bar_check(self):
        if self._pending:
            return
        try:
            self._pending = self.outer.after_idle(self._apply_bar)
        except Exception:
            self._pending = None
            self._apply_bar()

    def _apply_bar(self):
        self._pending = None
        try:
            vis = int(self.canvas.winfo_height())
            if vis <= 1 and self._tries < 20:      # 还没 realize，下一轮再看
                self._tries += 1
                self._schedule_bar_check()
                return
            self._tries = 0
            show = int(self.inner.winfo_reqheight()) > vis + 2
            if show and not self._bar_shown:
                self.bar.pack(side="right", fill="y")
                self._bar_shown = True
            elif not show and self._bar_shown:
                self.bar.pack_forget()
                self._bar_shown = False
        except Exception:
            pass

    def _on_canvas(self, e):
        try:
            self.canvas.itemconfigure(self._win, width=e.width)
        except Exception:
            pass
        self._schedule_bar_check()

    def _on_wheel(self, e):
        try:
            if self._bar_shown:
                self.canvas.yview_scroll(int(-e.delta / 120), "units")
        except Exception:
            pass

    def clear(self):
        for w in self.inner.winfo_children():
            w.destroy()

    def set_height(self, px):
        """按标的数量自适应列表高度（避免少的时候留一大片空）"""
        try:
            px = max(40, int(px))
            self.canvas.configure(height=px)
            self.outer.configure(height=px)
            self._on_inner()
        except Exception:
            pass

    # 让 ScrollFrame 能像普通控件一样被布局（内部转发给 outer Frame）
    def pack(self, **kw):
        self.outer.pack(**kw)

    def grid(self, **kw):
        self.outer.grid(**kw)


# ---------------------------------------------------------------- 设置面板
class SettingsPanel:
    """统一的标的设置面板。
    mode="start"：启动时使用（铺满主窗口，主按钮=开始盯盘）
    mode="edit" ：运行时从右键菜单打开（独立小窗，主按钮=保存并应用）
    """

    def __init__(self, parent, cfg, on_done, mode="start"):
        self.mode = mode
        self.cfg = cfg
        self.on_done = on_done
        self.work = list(cfg["codes"])
        self.labels = dict(cfg.get("labels", {}))
        self.names = {}
        self.results = []
        self._deb = None

        if mode == "start":
            self.win = parent
            self.root = parent
            self.win.geometry("540x600")
        else:
            self.root = parent
            self.win = tk.Toplevel(parent)
            self.win.geometry("540x580")

        w = self.win
        w.title("盯盘小窗")
        w.configure(bg=BG)
        w.resizable(False, False)
        try:
            w.attributes("-topmost", True)
        except Exception:
            pass

        F = "Microsoft YaHei"
        # ---------- 头部
        head = tk.Frame(w, bg=BG)
        head.pack(fill="x", padx=22, pady=(18, 0))
        tk.Label(head, text="盯盘小窗", bg=BG, fg="#ffffff",
                 font=(F, 15, "bold")).pack(anchor="w")
        tk.Label(head, text="输入代码或中文名，选好后点开始",
                 bg=BG, fg=MUTED, font=(F, 9)).pack(anchor="w", pady=(3, 0))

        # ---------- 已选列表
        cap = tk.Frame(w, bg=BG)
        cap.pack(fill="x", padx=22, pady=(16, 6))
        self.count_lbl = tk.Label(cap, text="", bg=BG, fg=MUTED, font=(F, 9))
        self.count_lbl.pack(side="left")
        tk.Button(cap, text="清空", command=self._clear, bg=BG, fg=MUTED,
                  activebackground=BG, activeforeground=UP, relief="flat",
                  bd=0, highlightthickness=0, cursor="hand2",
                  font=(F, 9)).pack(side="right")

        # 列表外面套一层卡片，空的时候也不会显得是「漏排版」
        box = tk.Frame(w, bg=CARD, highlightbackground=BORDER,
                       highlightthickness=1)
        box.pack(fill="x", padx=22)
        self.scroll = ScrollFrame(box, height=170, bg=CARD)
        self.scroll.pack(fill="both", expand=True)
        self.rows_host = self.scroll.inner

        # ---------- 输入行
        add_row = tk.Frame(w, bg=BG)
        add_row.pack(fill="x", padx=22, pady=(14, 0))
        box = tk.Frame(add_row, bg=CARD, highlightbackground=BORDER,
                       highlightthickness=1)
        box.pack(side="left", fill="x", expand=True)
        self.ent = tk.Entry(box, bg=CARD, fg="#ffffff", insertbackground="#ffffff",
                            relief="flat", bd=0, font=("Consolas", 11))
        self.ent.pack(fill="x", padx=10, pady=7)
        self.ent.bind("<Return>", lambda e: self._commit_entry())
        self.ent.bind("<KeyRelease>", self._on_key)
        flat_btn(add_row, "添加", self._commit_entry, bg=ACCENT, fg="#ffffff",
                 width=6, padx=8, pady=6).pack(side="left", padx=(8, 0))

        # 搜索结果（有结果才显示）
        self.res_lb = tk.Listbox(w, bg=CARD, fg=TEXT, height=4,
                                 highlightthickness=1, highlightbackground=BORDER,
                                 bd=0, selectbackground=ROW_HL,
                                 selectforeground="#ffffff", activestyle="none",
                                 font=("Consolas", 9))
        self.res_lb.bind("<ButtonRelease-1>", lambda e: self._add_result())

        self.hint = tk.Label(w, text="", bg=BG, fg=MUTED, font=(F, 8))
        self.hint.pack(anchor="w", padx=22, pady=(5, 0))

        # ---------- 样式
        style = tk.Frame(w, bg=BG)
        style.pack(fill="x", padx=22, pady=(14, 0))
        tk.Label(style, text="样式", bg=BG, fg=MUTED, font=(F, 9)).pack(side="left")
        self.layout_var = tk.StringVar(value=cfg.get("layout", "bar"))
        self._seg_btns = {}
        for val, txt in (("bar", "横条"), ("list", "竖排")):
            b = tk.Label(style, text=txt, bg=ROW, fg=MUTED,
                         font=(F, 9), padx=14, pady=4, cursor="hand2")
            b.pack(side="left", padx=(8, 0))
            b.bind("<Button-1>", lambda e, v=val: self._pick_layout(v))
            self._seg_btns[val] = b

        # ---------- 主按钮
        self.primary = flat_btn(
            w, "开始盯盘  ▶" if mode == "start" else "保存并应用",
            self._done, bg=ACCENT, fg="#ffffff", font=(F, 11),
            padx=0, pady=9)
        self.primary.pack(fill="x", padx=22, pady=(18, 0))

        foot = tk.Frame(w, bg=BG)
        foot.pack(fill="x", padx=22, pady=(8, 16))
        tk.Button(foot, text="恢复默认", command=self._reset, bg=BG, fg=MUTED,
                  activebackground=BG, activeforeground=TEXT, relief="flat",
                  bd=0, highlightthickness=0, cursor="hand2",
                  font=(F, 9)).pack(side="left")
        if mode == "edit":
            tk.Button(foot, text="取消", command=self.win.destroy, bg=BG,
                      fg=MUTED, activebackground=BG, activeforeground=TEXT,
                      relief="flat", bd=0, highlightthickness=0, cursor="hand2",
                      font=(F, 9)).pack(side="right")

        self._pick_layout(self.layout_var.get())
        self._render()
        self.ent.focus_set()

    # ---------- 渲染
    def _render(self):
        self.scroll.clear()
        for code in self.work:
            disp = self.labels.get(code) or self.names.get(code) or code
            row = tk.Frame(self.rows_host, bg=ROW)
            row.pack(fill="x", pady=1)
            name_lb = tk.Label(row, text=disp, bg=ROW, fg=TEXT,
                               font=("Microsoft YaHei", 10), anchor="w")
            name_lb.pack(side="left", padx=(10, 6), pady=6)
            code_lb = tk.Label(row, text=code, bg=ROW, fg=MUTED,
                               font=("Consolas", 9), anchor="w")
            code_lb.pack(side="left")
            x = tk.Label(row, text="✕", bg=ROW, fg=MUTED,
                         font=("Microsoft YaHei", 10), padx=10, cursor="hand2")
            x.pack(side="right")
            x.bind("<Button-1>", lambda e, c=code: self._remove(c))
            for w in (row, x, name_lb, code_lb):
                w.bind("<Enter>", lambda e, r=row: self._hl(r, True))
                w.bind("<Leave>", lambda e, r=row: self._hl(r, False))
                self.scroll.bind_wheel(w)     # 悬停在行上也能滚
        if self.work:
            tk.Frame(self.rows_host, bg=CARD, height=6).pack(fill="x")
        n = len(self.work)
        self.count_lbl.config(text=f"已选 {n} 个" if n else "还没有标的")
        # 列表高度按实测行高自适应：正好容纳 ≤5 行，多了才出滚动条
        need = 0
        try:
            self.win.update_idletasks()
            need = int(self.rows_host.winfo_reqheight())
        except Exception:
            need = 0
        self.scroll.set_height(min(204, need + 4) if need > 2 else 42)
        try:
            self.scroll._on_inner()
        except Exception:
            pass
        self._fit()

    def _fit(self):
        """让窗口高度贴合内容（宽度固定 540），避免底部大片留白"""
        try:
            self.win.update_idletasks()
            h = int(self.win.winfo_reqheight())
            if h > 120:
                self.win.geometry(f"540x{h}")
        except Exception:
            pass

    @staticmethod
    def _hl(row, on):
        try:
            row.config(bg=ROW_HL if on else ROW)
            for c in row.winfo_children():
                c.config(bg=ROW_HL if on else ROW)
        except Exception:
            pass

    def _pick_layout(self, val):
        self.layout_var.set(val)
        for v, b in self._seg_btns.items():
            if v == val:
                b.config(bg=ACCENT, fg="#ffffff")
            else:
                b.config(bg=ROW, fg=MUTED)

    # ---------- 输入 / 检索
    def _on_key(self, e):
        if e.keysym in ("Up", "Down", "Return", "Tab", "Escape"):
            return
        if self._deb:
            try:
                self.win.after_cancel(self._deb)
            except Exception:
                pass
        self._deb = self.win.after(350, self._search)

    def _hide_results(self):
        self.res_lb.pack_forget()
        self.results = []

    def _commit_entry(self):
        if self.res_lb.winfo_ismapped() and self.res_lb.curselection():
            self._add_result()
            return
        self._search(auto_add=True)

    def _search(self, auto_add=False):
        kw = self.ent.get().strip()
        self.hint.config(text="")
        if not kw:
            self._hide_results()
            return
        code = normalize_code(kw)
        if code and re.fullmatch(r"(sh|sz|bj|hk)\d{5,6}", code):
            self._add_code(code)
            self.ent.delete(0, "end")
            self._hide_results()
            self.hint.config(text=f"已添加 {code}")
            return
        self.results = search_by_name(kw, limit=8)
        if not self.results:
            self._hide_results()
            self.hint.config(text=f"没找到「{kw}」")
            return
        if len(self.results) == 1 and auto_add:
            self._add_result(0)
            return
        self.res_lb.delete(0, "end")
        for c, n, t in self.results:
            self.res_lb.insert("end", f"  {n}   {c}   [{t}]")
        self.res_lb.pack(fill="x", padx=22, pady=(6, 0), before=self.hint)
        self.hint.config(text="点击选择")

    def _add_result(self, idx=None):
        sel = [idx] if idx is not None else list(self.res_lb.curselection())
        if not sel:
            return
        c, n, _ = self.results[sel[0]]
        self.names[c] = n
        self.labels.pop(c, None)
        self._add_code(c)
        self.ent.delete(0, "end")
        self._hide_results()
        self.hint.config(text=f"已添加 {n}  {c}")

    def _add_code(self, code):
        if code not in self.work:
            self.work.append(code)
            self._render()

    def _remove(self, code):
        if code in self.work:
            self.work.remove(code)
            self._render()

    def _clear(self):
        self.work = []
        self._render()

    def _reset(self):
        self.work = list(DEFAULT_CONFIG["codes"])
        self.labels = dict(DEFAULT_CONFIG["labels"])
        self._pick_layout(DEFAULT_CONFIG["layout"])
        self._render()

    # ---------- 完成
    def _done(self):
        if not self.work:
            self.hint.config(text="请至少添加一个标的")
            return
        self.cfg["codes"] = list(self.work)
        self.cfg["labels"] = {k: v for k, v in self.labels.items()
                              if k in self.work and v}
        lay = self.layout_var.get()
        self.cfg["layout"] = lay
        if self.cfg.get("position") == "bottom" and lay != "bar":
            self.cfg["position"] = "top_right"
        if self.cfg.get("position") in ("custom", "") and lay == "bar":
            self.cfg["position"] = "bottom"
        self.cfg["geometry"] = ""
        save_config(self.cfg)
        if self.mode == "start":
            for c in self.win.winfo_children():
                c.destroy()
            try:
                self.win.title("")
            except Exception:
                pass
        else:
            self.win.destroy()
        self.on_done()


# 兼容旧名称
Launcher = SettingsPanel


# ---------------------------------------------------------------- 主窗口
class Ticker:
    """盯盘小窗。layout=bar 时为横条（可贴任务栏上沿），layout=list 时为竖排列表。"""

    def __init__(self, root, cfg):
        self.root = root
        self.cfg = cfg
        self.hidden = False
        self.rows = {}
        self._built_codes = []
        self._dragged = False
        # 悬停分时浮窗
        self.tip = None            # 浮窗 Toplevel
        self.tip_cv = None         # 浮窗画布
        self.tip_code = None
        self._hit = {}             # code -> 参与悬停判定的控件列表
        self._minute_cache = {}    # code -> (时间戳, 分时数据)
        self._show_job = None
        self._hide_job = None
        self._build()
        self._refresh()
        if cfg.get("always_onmost", True):
            self._keep_topmost()

    # ---------- UI
    def _build(self):
        r = self.root
        r.overrideredirect(True)
        r.attributes("-alpha", max(self._steps()))
        r.configure(bg=BG)
        try:
            r.attributes("-topmost", bool(self.cfg.get("always_onmost", True)))
        except Exception:
            pass

        self.bar = self.cfg.get("layout", "bar") == "bar"
        if self.bar:
            self._build_bar()
        else:
            self._build_list()
        r.geometry(self._calc_geometry())

        # 只绑在根窗口即可：tkinter 的 bindtags 机制会自动把根窗口
        # 作为所有子控件的绑定目标，重复绑定会导致双击触发多次。
        r.bind("<ButtonPress-1>", self._start_drag)
        r.bind("<B1-Motion>", self._on_drag)
        r.bind("<Double-Button-1>", self._on_double_click)
        r.bind("<Button-3>", self._show_menu)
        r.bind("<Configure>", self._on_configure)
        r.bind("<Destroy>", self._on_destroy)
        self._build_menu()
        self._render_rows()      # 建行（必须最后调用：需要 menu/几何都已就绪）

    def _build_bar(self):
        """横条：上证 3716 +0.24% | 协鑫 2.26 +0.88% | ... | 17:39:52"""
        r = self.root
        self.hlbl = tk.Label(r, text="", bg=BG, fg=DIM, font=(self.cfg["font"], 8))
        self.body = tk.Frame(r, bg=BG)
        self.body.pack(fill="both", expand=True)
        self.body.grid_columnconfigure(0, weight=1)
        self.time_lbl = tk.Label(self.body, text="--:--:--", bg=BG, fg=DIM,
                                 font=(self.cfg["font"], 8))
        self.rows_frame = tk.Frame(self.body, bg=BG)
        self.rows_frame.grid(row=0, column=0, sticky="w", padx=(8, 4))
        self.time_lbl.grid(row=0, column=1, sticky="e", padx=(0, 8))

    def _build_list(self):
        """竖排：名称 / 价格 / 涨跌幅"""
        r = self.root
        tk.Label(r, text="盯盘", bg=BG, fg=DIM, font=(self.cfg["font"], 8),
                 anchor="w").grid(row=0, column=0, sticky="w", padx=6, pady=(4, 1))
        self.hlbl = tk.Label(r, text="", bg=BG, fg=DIM,
                             font=(self.cfg["font"], 8), anchor="e")
        self.hlbl.grid(row=0, column=2, sticky="e", padx=6)
        self.body = tk.Frame(r, bg=BG)
        self.body.grid(row=1, column=0, columnspan=3, sticky="nw")
        self.time_lbl = tk.Label(r, text="--:--:--", bg=BG, fg=DIM,
                                 font=(self.cfg["font"], 8), anchor="w")
        self.time_lbl.grid(row=2, column=0, columnspan=3, sticky="w", padx=6, pady=(1, 4))

    def _build_menu(self):
        r = self.root
        self.menu = Menu(r, tearoff=0)
        self.menu.add_command(label="编辑标的…", command=self._open_editor)
        self.menu.add_separator()
        lay = Menu(self.menu, tearoff=0)
        self.layout_var = tk.StringVar(value=self.cfg.get("layout", "bar"))
        lay.add_radiobutton(label="横条（贴任务栏）", variable=self.layout_var,
                            value="bar", command=lambda: self._switch_layout("bar"))
        lay.add_radiobutton(label="竖排列表", variable=self.layout_var,
                            value="list", command=lambda: self._switch_layout("list"))
        self.menu.add_cascade(label="布局", menu=lay)

        pos = Menu(self.menu, tearoff=0)
        self.pos_var = tk.StringVar(value=self.cfg.get("position", "bottom"))
        for val, txt in (("bottom", "任务栏上方"), ("top_right", "右上角"),
                         ("top_left", "左上角"), ("center", "屏幕居中")):
            pos.add_radiobutton(label=txt, variable=self.pos_var, value=val,
                                command=lambda v=val: self._set_position(v))
        self.menu.add_cascade(label="位置", menu=pos)

        rf = Menu(self.menu, tearoff=0)
        self.rf_var = tk.StringVar(value=str(self.cfg.get("refresh_ms", 5000)))
        for ms, txt in ((3000, "3 秒"), (5000, "5 秒"), (10000, "10 秒"),
                        (30000, "30 秒"), (60000, "60 秒")):
            rf.add_radiobutton(label=txt, variable=self.rf_var, value=str(ms),
                               command=lambda v=ms: self._set_refresh(v))
        self.menu.add_cascade(label="刷新间隔", menu=rf)

        self.menu.add_separator()
        # 透明度档位（双击切换的就是这几档）
        op = Menu(self.menu, tearoff=0)
        self.alpha_var = tk.StringVar(value=f"{self._steps()[0]:.2f}")
        for v in self._steps():
            op.add_radiobutton(label=f"{int(v*100)}%", variable=self.alpha_var,
                               value=f"{v:.2f}",
                               command=lambda x=v: self._set_alpha(x))
        self.menu.add_cascade(label="透明度（双击切换）", menu=op)
        self.menu.add_command(label="立即恢复清晰显示", command=self._emergency_reset_alpha)
        self.menu.add_separator()
        self.onmost_var = tk.BooleanVar(value=bool(self.cfg.get("always_onmost", True)))
        self.menu.add_checkbutton(label="始终置顶", variable=self.onmost_var,
                                  command=self._toggle_topmost)
        self.hover_var = tk.BooleanVar(value=bool(self.cfg.get("hover_chart", True)))
        self.menu.add_checkbutton(label="悬停显示分时图", variable=self.hover_var,
                                  command=self._toggle_hover_chart)
        self.menu.add_separator()
        self.menu.add_command(label="立即刷新", command=self._refresh_now)
        self.menu.add_command(label="退出", command=r.destroy)

    # ---------- 行渲染
    def _render_rows(self):
        """建行。横条模式下若内容超出屏幕宽度会自动缩字号重排，
        保证所有标的都完整显示（而不是被裁掉后半截）。"""
        self._hide_tip()             # 行控件即将重建，先收掉悬停浮窗
        self._eff_font = self.cfg.get("font_size", 10)
        self._measured_w = 0          # 重置实测宽度（旧值会误导重排判断）
        self._bar_rows = 1            # 横条行数（超宽时自动折行）
        self._do_render()
        if not self.bar:
            self._refresh_now()
            return
        sw = self.root.winfo_screenwidth()
        m = int(self.cfg.get("margin", 24))
        limit = sw - 2 * m
        # 1) 先缩字号
        for _ in range(6):
            if self._content_width() <= limit or self._eff_font <= 7:
                break
            self._eff_font -= 1
            self._do_render()
        # 2) 缩到最小还放不下就折行（保证一个标的都不被裁掉）
        rows = 1
        while self._content_width() > limit and rows < 4:
            rows += 1
            self._bar_rows = rows
            self._do_render()
        self._refresh_now()

    def _do_render(self):
        for w in (self.rows_frame.winfo_children() if self.bar
                  else self.body.winfo_children()):
            w.destroy()
        self.rows.clear()
        self._hit = {}
        fs = getattr(self, "_eff_font", self.cfg.get("font_size", 10))
        font = (self.cfg["font"], fs)
        labels = self.cfg.get("labels", {})
        if not self.bar:
            self._name_units = self._calc_name_units(fs, labels)
        for i, code in enumerate(self.cfg["codes"]):
            disp = labels.get(code) or code
            hit = []
            if self.bar:
                rows = max(1, int(getattr(self, "_bar_rows", 1)))
                per = -(-len(self.cfg["codes"]) // rows)   # 每行放几个
                cell = tk.Frame(self.rows_frame, bg=BG)
                cell.grid(row=i // per, column=i % per, padx=(0, 11), pady=1)
                name_lb = tk.Label(cell, text=disp, bg=BG, fg="#9aa0ac",
                                   font=(self.cfg["font"], max(7, fs - 1)),
                                   anchor="w")
                name_lb.grid(row=0, column=0, sticky="w", padx=(0, 5))
                pl = tk.Label(cell, text="--", bg=BG, fg=FG, font=font, anchor="e")
                pl.grid(row=0, column=1, sticky="e")
                cl = tk.Label(cell, text="--", bg=BG, fg=FG, font=font, anchor="e")
                cl.grid(row=0, column=2, sticky="e", padx=(4, 0))
                # 不绑拖拽/双击：tkinter 的 bindtags 会把根窗口作为所有子控件的
                # 绑定目标，再绑一次会导致双击/拖拽重复触发。
                # 但 Enter/Leave 根窗口没绑，可以安全绑在单元格上（悬停分时用）。
                hit = [cell, name_lb, pl, cl]
                self.rows[code] = (pl, cl)
            else:
                nw = max(6, int(getattr(self, "_name_units", 9)))
                name_lb = tk.Label(self.body, text=disp, bg=BG, fg=FG, font=font,
                                   width=nw, anchor="w")
                name_lb.grid(row=i, column=0, sticky="w", padx=6)
                pl = tk.Label(self.body, text="--", bg=BG, fg=FG, font=font,
                              width=9, anchor="e")
                pl.grid(row=i, column=1, sticky="e")
                cl = tk.Label(self.body, text="--", bg=BG, fg=FG, font=font,
                              width=8, anchor="e")
                cl.grid(row=i, column=2, sticky="e", padx=6)
                hit = [name_lb, pl, cl]
                self.rows[code] = (pl, cl)
            self._hit[code] = hit
            for w in hit:
                w.bind("<Enter>", lambda e, c=code: self._on_hover_in(c))
                w.bind("<Leave>", lambda e, c=code: self._on_hover_out(c))
        self._built_codes = list(self.cfg["codes"])
        try:
            self.root.update_idletasks()
            self.root.geometry(self._calc_geometry())
        except Exception:
            pass

    # ---------- 几何
    def _taskbar_top(self):
        """取 Windows 任务栏顶部 y 坐标。贴底任务栏返回 workarea.bottom，
        贴顶返回 workarea.top；自动任务栏/取不到返回 None。"""
        try:
            import ctypes
            SPI_GETWORKAREA = 0x0030

            class RECT(ctypes.Structure):
                _fields_ = [("left", ctypes.c_long), ("top", ctypes.c_long),
                            ("right", ctypes.c_long), ("bottom", ctypes.c_long)]
            r = RECT()
            if not ctypes.windll.user32.SystemParametersInfoW(
                    SPI_GETWORKAREA, 0, ctypes.byref(r), 0):
                return None
            h = self.root.winfo_screenheight()
            if r.bottom < h - 8:      # 任务栏贴底
                return r.bottom
            if r.top > 8:             # 任务栏贴顶
                return r.top
            return None
        except Exception:
            return None

    def _calc_geometry(self):
        n = max(1, len(self.cfg["codes"]))
        m = int(self.cfg.get("margin", 24))
        pos = self.cfg.get("position", "bottom")
        sw = self.root.winfo_screenwidth()
        sh = self.root.winfo_screenheight()

        if self.bar:
            # 按控件实际需求宽度取尺寸（原来按每格 96px 估算，标的多了会被截断）
            w = self._content_width()
            w = min(w, sw - 2 * m)
            h = 27 * max(1, int(getattr(self, "_bar_rows", 1)))
        else:
            w = min(self._content_width(), sw - 2 * m)
            h = 30 + n * 20 + 26

        # 已记忆的手动位置优先（拖动过就尊重用户）
        g = self.cfg.get("geometry", "")
        if g and pos == "custom":
            if re.match(r"(\d+)x(\d+)\+(-?\d+)\+(-?\d+)", g):
                mm = re.match(r"(\d+)x", g)
                # 位置沿用用户拖的，但宽度按最新内容重算，避免加标的被截
                if mm:
                    y = re.search(r"\+(-?\d+)\+(-?\d+)$", g)
                    if y:
                        return f"{w}x{h}+{y.group(1)}+{y.group(2)}"

        if self.bar and pos == "bottom":
            y = self._taskbar_top()
            y = (y - h - int(self.cfg.get("taskbar_gap", 3))) if y else (sh - h - m)
            align = self.cfg.get("bar_align", "center")
            x = {"left": m, "right": sw - w - m}.get(align, (sw - w) // 2)
        elif pos == "top_right":
            x, y = sw - w - m, m
        elif pos == "top_left":
            x, y = m, m
        elif pos == "center":
            x, y = (sw - w) // 2, (sh - h) // 2
        else:
            x, y = m, m
        return f"{w}x{h}+{int(max(0, x))}+{int(max(0, y))}"

    def _content_width(self):
        """内容需要的宽度 = max(字体度量估算, 数据到位后的实测宽度)。

        为什么不能只用控件实测 reqwidth：首次建行时价格还是占位符 "--"，
        量出来偏小；等真实价格（如 3716.28 / +0.24%）填进去就超出了窗口宽度，
        右边的标的全被裁掉 —— 这正是"显示个数不完整"的真正原因。
        """
        return max(self._analytic_width(), int(getattr(self, "_measured_w", 0)))

    def _analytic_width(self):
        """按字体真实度量估算宽度（不依赖当前控件文本，永远按最宽的数字估）"""
        fs = getattr(self, "_eff_font", self.cfg.get("font_size", 10))
        fam = self.cfg.get("font", "Microsoft YaHei")
        labels = self.cfg.get("labels", {})
        if tkfont is None:
            px = fs * 1.45
            per = px * 4 + 20 * 1.0 + px * 7 + px * 7 + 20
            return int(28 + len(self.cfg["codes"]) * per)
        try:
            f = tkfont.Font(family=fam, size=fs)
            f2 = tkfont.Font(family=fam, size=max(7, fs - 1))
        except Exception:
            px = fs * 1.45
            return int(28 + len(self.cfg["codes"]) * (px * 20))
        if self.bar:
            price_px = f.measure("88888.88")     # 最宽的价格形态
            chg_px = f.measure("+88.88%")        # 最宽的涨跌幅形态
            cells = [f2.measure(labels.get(c) or c) + 5 + price_px + 4 + chg_px + 11
                     for c in self.cfg["codes"]]
            rows = max(1, int(getattr(self, "_bar_rows", 1)))
            per = -(-len(cells) // rows) or 1
            widest = max([sum(cells[r * per:(r + 1) * per])
                          for r in range(rows)] or [0])
            return int(widest + 34)
        # 竖排：名称列自适应宽度 + 价格列 9 / 涨跌幅列 8 字符
        nw = max(6, int(getattr(self, "_name_units", 9)))
        return int(f.measure("0") * (nw + 9 + 8) + 44)

    def _calc_name_units(self, fs, labels):
        """竖排名称列需要多少个「平均字符宽」（中文名宽，避免被截断）"""
        disps = [labels.get(c) or c for c in self.cfg["codes"]]
        longest = max([len(d) for d in disps] or [4])
        if tkfont is None:
            return min(18, max(6, longest * 2))
        try:
            f = tkfont.Font(family=self.cfg.get("font", "Microsoft YaHei"), size=fs)
            unit = max(1, f.measure("0"))
            widest = max([f.measure(d) for d in disps] or [0])
            return min(18, max(6, -(-widest // unit) + 1))
        except Exception:
            return min(18, max(6, longest * 2))

    def _grow_to_fit(self):
        """真实数据到位后按控件实测宽度校正窗口：
        能加宽就加宽；超出屏幕则缩小字号重排。"""
        if getattr(self, "_sizing", False) or not self.bar:
            return
        self._sizing = True
        try:
            self.root.update_idletasks()
            self._measured_w = int(self.body.winfo_reqwidth()) + 8
            sw = self.root.winfo_screenwidth()
            m = int(self.cfg.get("margin", 24))
            limit = sw - 2 * m
            if self._measured_w > limit and getattr(self, "_eff_font", 10) > 7:
                self._eff_font = max(7, getattr(self, "_eff_font", 10) - 1)
                self._do_render()
                self.root.update_idletasks()
                self._measured_w = int(self.body.winfo_reqwidth()) + 8
            # 缩到最小字号仍超屏 -> 折行（保证一个标的都不被裁掉）
            while (self._measured_w > limit
                   and int(getattr(self, "_bar_rows", 1)) < 4):
                self._bar_rows = int(getattr(self, "_bar_rows", 1)) + 1
                self._do_render()
                self.root.update_idletasks()
                self._measured_w = int(self.body.winfo_reqwidth()) + 8
            self._apply_quotes(getattr(self, "_last_quotes", {}))
            self.root.update_idletasks()
            self._measured_w = int(self.body.winfo_reqwidth()) + 8
            if self._content_width() > self.root.winfo_width() + 2:
                self.root.geometry(self._calc_geometry())
        except Exception:
            pass
        finally:
            self._sizing = False

    # ---------- 悬停分时浮窗
    TIP_W = 336
    TIP_H = 202

    def _hover_enabled(self):
        return bool(self.cfg.get("hover_chart", True)) and not self.hidden

    def _cancel_job(self, name):
        job = getattr(self, name, None)
        if job:
            try:
                self.root.after_cancel(job)
            except Exception:
                pass
            setattr(self, name, None)

    def _on_hover_in(self, code):
        """进入某个标的：取消待隐藏，延时后弹分时浮窗"""
        self._cancel_job("_hide_job")
        if not self._hover_enabled():
            return
        if self.tip is not None and self.tip_code == code:
            return
        self._cancel_job("_show_job")
        try:
            self._show_job = self.root.after(
                320, lambda: self._show_tip(code))
        except Exception:
            self._show_job = None

    def _on_hover_out(self, code):
        """离开标的：延时隐藏（留一点时间让鼠标移到浮窗上）"""
        self._cancel_job("_show_job")
        if self.tip is None:
            return
        self._cancel_job("_hide_job")
        try:
            self._hide_job = self.root.after(160, self._hide_tip)
        except Exception:
            self._hide_job = None

    def _hit_rect(self, code):
        """该标的在屏幕上占的矩形（横条取整格，竖排取三列并集）"""
        xs, ys, x2, y2 = [], [], [], []
        for w in self._hit.get(code, []):
            try:
                x, y = w.winfo_rootx(), w.winfo_rooty()
                xs.append(x); ys.append(y)
                x2.append(x + w.winfo_width())
                y2.append(y + w.winfo_height())
            except Exception:
                continue
        if not xs:
            return None
        return min(xs), min(ys), max(x2) - min(xs), max(y2) - min(ys)

    def _ensure_tip(self):
        if self.tip is not None:
            return
        t = tk.Toplevel(self.root)
        t.overrideredirect(True)
        try:
            t.attributes("-topmost", True)
            t.attributes("-alpha", 0.97)
        except Exception:
            pass
        t.configure(bg="#0f1116")
        cv = tk.Canvas(t, width=self.TIP_W, height=self.TIP_H,
                       bg="#0f1116", highlightthickness=1,
                       highlightbackground="#3a4150", bd=0)
        cv.pack()
        cv.bind("<Enter>", lambda e: self._cancel_job("_hide_job"))
        cv.bind("<Leave>", lambda e: self._on_hover_out(self.tip_code))
        self.tip, self.tip_cv = t, cv

    def _show_tip(self, code):
        self._show_job = None
        if not self._hover_enabled():
            return
        rect = self._hit_rect(code)
        if rect is None:
            return
        self._ensure_tip()
        self.tip_code = code
        # 定位：默认贴在标的**上方**，上方放不下就放下面；水平居中并夹在屏内
        W, H = self.TIP_W, self.TIP_H
        sw = self.root.winfo_screenwidth()
        sh = self.root.winfo_screenheight()
        x = rect[0] + rect[2] // 2 - W // 2
        y = rect[1] - H - 6
        if y < 4:
            y = rect[1] + rect[3] + 6
        x = max(4, min(x, sw - W - 4))
        y = max(4, min(y, sh - H - 4))
        try:
            self.tip.geometry(f"{W}x{H}+{x}+{y}")
            self.tip.deiconify()
            self.tip.lift()
            self.tip_cv.delete("all")
            self.tip_cv.create_text(W // 2, H // 2, text="分时加载中…",
                                    fill="#8b929e",
                                    font=("Microsoft YaHei", 10))
        except Exception:
            pass
        # 缓存 45 秒，避免鼠标划过时反复打接口
        now = time.time()
        cached = self._minute_cache.get(code)
        if cached and now - cached[0] < 45:
            self._draw_tip(code, cached[1])
            return

        def job():
            data = fetch_minute(code)

            def back():
                try:
                    if self.tip is None or self.tip_code != code:
                        return
                    if data:
                        self._minute_cache[code] = (time.time(), data)
                    self._draw_tip(code, data)
                except Exception:
                    pass

            try:
                self.root.after(0, back)
            except Exception:
                pass

        threading.Thread(target=job, daemon=True).start()

    def _hide_tip(self):
        self._hide_job = None
        self._cancel_job("_show_job")
        self.tip_code = None
        if self.tip is None:
            return
        try:
            self.tip.withdraw()
        except Exception:
            pass

    def _destroy_tip(self):
        """彻底销毁浮窗（重建控件前必须调，否则 tip 引用会失效）"""
        self._cancel_job("_show_job")
        self._cancel_job("_hide_job")
        self.tip_code = None
        if self.tip is not None:
            try:
                self.tip.destroy()
            except Exception:
                pass
        self.tip, self.tip_cv = None, None

    def _draw_tip(self, code, data):
        cv = self.tip_cv
        if cv is None:
            return
        W, H = self.TIP_W, self.TIP_H
        cv.delete("all")
        if not data or not data.get("pts"):
            cv.create_text(W // 2, H // 2, text="分时数据拉取失败",
                           fill="#ff9f43", font=("Microsoft YaHei", 10))
            return

        pts = data["pts"]
        prev = data["prev"] or pts[0][1]
        last = data["price"] or pts[-1][1]
        pct = ((last - prev) / prev * 100) if prev else 0.0
        col = UP if pct > 0 else (DOWN if pct < 0 else FLAT)

        # ---- 标题行
        cv.create_text(12, 15, anchor="w", text=f"{data['name']}",
                       fill="#e6e9ef", font=("Microsoft YaHei", 10, "bold"))
        cv.create_text(12 + len(data["name"]) * 13 + 8, 15, anchor="w",
                       text=code[2:] if len(code) > 2 else code,
                       fill="#6f7684", font=("Consolas", 9))
        cv.create_text(W - 12, 15, anchor="e",
                       text=f"{last:.2f}  {pct:+.2f}%", fill=col,
                       font=("Consolas", 11, "bold"))
        cv.create_line(12, 27, W - 12, 27, fill="#262b34")

        # ---- 绘图区
        L, R, T, B = 48, W - 46, 36, H - 34
        pw, ph = R - L, B - T
        vol_h = int(ph * 0.22)              # 底部 22% 放成交量
        price_h = ph - vol_h - 4
        prices = [p for _, p, _, _ in pts] + [prev]
        hi, lo = max(prices), min(prices)
        if hi - lo < 1e-9:
            hi, lo = hi + 0.01, lo - 0.01
        pad = (hi - lo) * 0.10
        hi, lo = hi + pad, lo - pad
        n = len(pts)

        def X(i):
            return L + pw * i / max(1, n - 1)

        def Y(p):
            return T + price_h * (hi - p) / (hi - lo)

        def VY(h):                          # 成交量高度
            return B - vol_h * h

        # 网格 + 基准线
        for f in (0.0, 0.25, 0.5, 0.75, 1.0):
            yy = T + price_h * f
            cv.create_line(L, yy, R, yy, fill="#1e232b")
        yb = Y(prev)
        cv.create_line(L, yb, R, yb, fill="#5a6070", dash=(3, 3))
        # 11:30 / 13:00 分隔
        mid = X(n // 2)
        cv.create_line(mid, T, mid, B, fill="#262b34", dash=(2, 3))

        # 成交量柱
        vmax = 0.0
        per_vol = [0.0] * n
        for i in range(1, n):
            v = max(0.0, pts[i][2] - pts[i - 1][2])
            per_vol[i] = v
            vmax = max(vmax, v)
        if vmax > 0:
            bw = max(1.0, pw / max(1, n) - 0.6)
            for i in range(1, n):
                if per_vol[i] <= 0:
                    continue
                c = UP if pts[i][1] >= pts[i - 1][1] else DOWN
                x = X(i)
                cv.create_rectangle(x, VY(per_vol[i] / vmax), x + bw, B,
                                    fill=c, outline="")

        # 分时线（逐段按是否在昨收上方着色）
        for i in range(n - 1):
            p1, p2 = pts[i][1], pts[i + 1][1]
            c = UP if (p1 + p2) / 2 >= prev else DOWN
            cv.create_line(X(i), Y(p1), X(i + 1), Y(p2), fill=c, width=1)
        # 均价线（累计额 / 累计量）
        if pts[-1][3] > 0:
            for i in range(n - 1):
                a1 = (pts[i][3] / (pts[i][2] * 100)) if pts[i][2] else pts[i][1]
                a2 = (pts[i + 1][3] / (pts[i + 1][2] * 100)) \
                    if pts[i + 1][2] else pts[i + 1][1]
                cv.create_line(X(i), Y(a1), X(i + 1), Y(a2),
                               fill="#e8c46a", width=1)

        # 价格刻度（左）/ 涨跌幅刻度（右）
        for p, va in ((hi, "n"), (prev, "c"), (lo, "n")):
            yy = Y(p)
            cv.create_text(L - 6, yy, anchor="e", text=f"{p:.2f}",
                           fill="#8b929e", font=("Consolas", 8))
        for p in (hi, lo):
            d = ((p - prev) / prev * 100) if prev else 0.0
            cv.create_text(R + 6, Y(p), anchor="w", text=f"{d:+.1f}%",
                           fill=UP if d > 0 else (DOWN if d < 0 else FLAT),
                           font=("Consolas", 8))
        # 时间刻度
        for i, tx in ((0, "09:30"), (n // 2, "11:30/13:00"), (n - 1, "15:00")):
            cv.create_text(X(i), B + 10, text=tx, fill="#6f7684",
                           font=("Consolas", 8), anchor="c")
        # 底部说明
        cv.create_text(12, H - 8, anchor="w",
                       text=f"分时 · {data.get('date', '')} · 腾讯行情",
                       fill="#4d5461", font=("Microsoft YaHei", 7))

    # ---------- 布局/位置切换
    def _switch_layout(self, layout):
        self.cfg["layout"] = layout
        self.cfg["geometry"] = ""
        self.cfg["position"] = "bottom" if layout == "bar" else "top_right"
        self.pos_var.set(self.cfg["position"])
        save_config(self.cfg)
        self._rebuild()

    def _set_position(self, pos):
        self.cfg["position"] = pos
        self.cfg["geometry"] = ""
        save_config(self.cfg)
        self.root.geometry(self._calc_geometry())

    def _rebuild(self):
        r = self.root
        self._destroy_tip()          # 浮窗是 root 的子窗口，会被一起 destroy
        for w in r.winfo_children():
            w.destroy()
        self.rows.clear()
        self._built_codes = []
        self._build()
        self._render_rows()

    # ---------- 交互
    def _start_drag(self, e):
        # 拖动时先收掉分时浮窗，免得它挂在半空挡视线
        self._hide_tip()
        # 用屏幕坐标：事件可能来自根窗口，也可能来自子控件（bindtags 机制），
        # 用 e.x/e.y 会因参照系不同而产生跳动。
        self._dx = e.x_root - self.root.winfo_x()
        self._dy = e.y_root - self.root.winfo_y()
        self._dragged = False

    def _on_drag(self, e):
        x = e.x_root - self._dx
        y = e.y_root - self._dy
        self.root.geometry(f"+{int(x)}+{int(y)}")
        self._dragged = True

    def _on_double_click(self, e=None):
        """按配置决定双击行为。默认 cycle：在透明度档位间循环，
        永远不会把自己彻底隐藏到找不到（最低档仍保留 25% 可见度）。"""
        act = self.cfg.get("double_click_action", "cycle")
        if act == "none":
            return
        if act == "hide":
            self._toggle_hidden()
            return
        self._cycle_opacity()

    def _steps(self):
        """取透明度档位；兼容旧配置的 opacity / hidden_opacity"""
        s = self.cfg.get("opacity_steps")
        if not s:
            s = [self.cfg.get("opacity", 0.88), self.cfg.get("hidden_opacity", 0.25)]
        s = [float(x) for x in s if 0 < float(x) <= 1]
        return s or [0.88, 0.55, 0.25]

    def _cycle_opacity(self):
        steps = self._steps()
        cur = self.root.attributes("-alpha")
        try:
            cur = float(cur)
        except Exception:
            cur = steps[0]
        # 找到当前档位，切到下一档
        idx = min(range(len(steps)), key=lambda i: abs(steps[i] - cur))
        nxt = steps[(idx + 1) % len(steps)]
        self.root.attributes("-alpha", nxt)
        self._alpha_idx = (idx + 1) % len(steps)
        # 只有最低档才显示「隐」提示
        try:
            self.hlbl.config(text="(隐)" if nxt == min(steps) else "")
        except Exception:
            pass
        self._sync_alpha_menu()

    def _set_alpha(self, val):
        self.root.attributes("-alpha", float(val))
        steps = self._steps()
        try:
            self.hlbl.config(text="(隐)" if abs(float(val) - min(steps)) < 1e-6 else "")
        except Exception:
            pass
        self._sync_alpha_menu()

    def _sync_alpha_menu(self):
        var = getattr(self, "alpha_var", None)
        if var is None:
            return
        try:
            cur = float(self.root.attributes("-alpha"))
        except Exception:
            return
        best = min(self._steps(), key=lambda v: abs(v - cur))
        var.set(f"{best:.2f}")

    def _toggle_hidden(self):
        """旧版隐身：切到最低档 / 恢复最高档（不再关闭置顶）"""
        steps = self._steps()
        cur = self.root.attributes("-alpha")
        try:
            cur = float(cur)
        except Exception:
            cur = steps[0]
        hidden = abs(cur - min(steps)) < 1e-6
        target = max(steps) if hidden else min(steps)
        self.hidden = not hidden
        self.root.attributes("-alpha", target)
        try:
            self.hlbl.config(text="(隐)" if not hidden else "")
        except Exception:
            pass
        if not hidden:
            self._destroy_tip()      # 隐身/调淡时不要留个浮窗挂在那
        self._sync_alpha_menu()

    def _toggle_topmost(self):
        v = bool(self.onmost_var.get())
        self.cfg["always_onmost"] = v
        self.root.attributes("-topmost", v)
        save_config(self.cfg)

    def _set_refresh(self, ms):
        self.cfg["refresh_ms"] = ms
        save_config(self.cfg)
        self._refresh_now()

    def _open_editor(self):
        try:
            self.menu.unpost()
        except Exception:
            pass
        SettingsPanel(self.root, self.cfg, self._apply_codes, mode="edit")

    def _apply_codes(self):
        self.cfg["geometry"] = ""
        self._destroy_tip()
        self._render_rows()

    def _toggle_hover_chart(self):
        self.cfg["hover_chart"] = not bool(self.cfg.get("hover_chart", True))
        save_config(self.cfg)
        if not self.cfg["hover_chart"]:
            self._destroy_tip()
        try:
            self.hover_var.set(bool(self.cfg["hover_chart"]))
        except Exception:
            pass

    def _show_menu(self, e):
        self.menu.post(e.x_root, e.y_root)

    def _on_configure(self, e):
        if e.widget is self.root:
            g = self.root.geometry()
            if re.match(r"^\d+x\d+\+(-?\d+)\+(-?\d+)$", g) and self._dragged:
                self.cfg["geometry"] = g
                self.cfg["position"] = "custom"

    def _on_destroy(self, e):
        if e.widget is self.root:
            save_config(self.cfg)
            self._destroy_tip()

    # ---------- 置顶强化（Windows 上 topmost 会被抢）
    def _keep_topmost(self):
        """周期性重新置顶。注意：无论透明度多少都保持置顶，
        否则一旦调低透明度窗口会沉到其他窗口后面，用户再也找不到它。"""
        def beat():
            while True:
                try:
                    self.root.attributes(
                        "-topmost", bool(self.cfg.get("always_onmost", True)))
                except Exception:
                    pass
                time.sleep(max(1.0, self.cfg.get("topmost_every_ms", 3000) / 1000.0))
        threading.Thread(target=beat, daemon=True).start()

    def _emergency_reset_alpha(self):
        """兜底：恢复最大不透明度并重新置顶"""
        try:
            self.root.attributes("-alpha", max(self._steps()))
            self.root.attributes("-topmost", True)
            self.cfg["always_onmost"] = True
            self.onmost_var.set(True)
            self.hidden = False
            self.hlbl.config(text="")
            self._sync_alpha_menu()
        except Exception:
            pass

    # ---------- 数据
    def _refresh_now(self):
        try:
            if self.root.winfo_exists() and self._built_codes:
                self._pull(self._built_codes)
        except Exception:
            pass

    def _refresh(self):
        def job():
            quotes = fetch_quotes(self.cfg["codes"])

            def update():
                try:
                    if not self.root.winfo_exists():
                        return
                    got = self._apply_quotes(quotes)
                    if got:
                        # 真实数字比占位符 "--" 宽得多，第一次拿到数据后
                        # 必须按实测宽度校正窗口，否则右边的标的全被裁掉
                        self._grow_to_fit()
                    now = datetime.datetime.now().strftime("%H:%M:%S")
                    if got == 0:
                        # 全军覆没：多半是网络/数据源问题，明确提示而不是干等
                        self.time_lbl.config(text=now + "  无数据·网络异常", fg="#ff9f43")
                        self._fail_count = getattr(self, "_fail_count", 0) + 1
                    else:
                        self.time_lbl.config(text=now + ("  ·" * min(3, got and 0)),
                                             fg=DIM)
                        self._fail_count = 0
                except Exception:
                    pass
                finally:
                    # 无论成败都续上定时链，避免一次异常后永久停更
                    try:
                        self.root.after(self.cfg["refresh_ms"], self._refresh)
                    except Exception:
                        pass

            self.root.after(0, update)

        threading.Thread(target=job, daemon=True).start()

    def _pull(self, codes):
        quotes = fetch_quotes(codes)
        self._last_quotes = quotes
        self._apply_quotes(quotes)
        return quotes

    def _apply_quotes(self, quotes):
        """把行情填进各行（重建行后可再次调用，立刻恢复显示）"""
        got = 0
        for code, (pl, cl) in self.rows.items():
            q = quotes.get(code)
            if not q:
                continue
            got += 1
            p, pct = q["price"], q["chg_pct"]
            pl.config(text=f"{p:.3f}" if p < 10 else f"{p:.2f}")
            cl.config(text=f"{pct:+.2f}%",
                      fg=UP if pct > 0 else (DOWN if pct < 0 else FLAT))
        return got


def selftest():
    """命令行自检：验证配置 + 网络 + 数据解析，不开窗口"""
    cfg = load_config()
    print("=" * 56)
    print("盯盘小窗自检")
    print("=" * 56)
    print(f"[1] Python        : {sys.version.split()[0]}")
    print(f"[2] tkinter       : OK")
    print(f"[3] 配置布局      : layout={cfg.get('layout')} position={cfg.get('position')}")
    print(f"[4] 标的数量      : {len(cfg.get('codes', []))}")
    print(f"[5] 标的清单      : {', '.join(cfg.get('codes', []))}")
    print("-" * 56)
    print("[6] 测试数据源 qt.gtimg.cn ...")
    q = fetch_quotes(cfg.get("codes", []))
    if not q:
        print("    ✗ 拉取失败！检查网络/代理/防火墙")
        return False
    for c, v in q.items():
        print(f"      {c:<10} {v['name']:<10} {v['price']:>10} {v['chg_pct']:>7.2f}%")
    print("-" * 56)
    print("[7] 测试名称检索 smartbox ...")
    for kw in ("杭电", "军工"):
        hits = search_by_name(kw, limit=2)
        print(f"      「{kw}」-> " + (", ".join(f"{n}({c})" for c, n, _ in hits) or "无结果"))
    print("-" * 56)
    print("[8] 测试分时数据（悬停浮窗用的）...")
    probe = (cfg.get("codes") or ["sh000001"])[0]
    md = fetch_minute(probe)
    if not md:
        print(f"      ✗ {probe} 分时拉取失败（浮窗会显示「拉取失败」）")
    else:
        print(f"      {probe} {md['name']}  昨收 {md['prev']}  现价 {md['price']}"
              f"  分时点 {len(md['pts'])} 个  日期 {md['date']}")
    print("=" * 56)
    print("自检通过。若 GUI 仍无数据显示，请把上面的报错发我。")
    return True


# ---------------------------------------------------------------- 入口
def main():
    args = sys.argv[1:]
    cfg = load_config()

    if "--list" in args:
        print(json.dumps({"codes": cfg["codes"], "labels": cfg.get("labels", {})},
                         ensure_ascii=False, indent=2))
        return

    if "--selftest" in args or "--诊断" in args:
        selftest()
        return

    if "--reset-alpha" in args or "--找回窗口" in args:
        cfg["opacity_steps"] = [0.88, 0.55, 0.25]
        cfg["always_onmost"] = True
        cfg["position"] = "bottom"
        cfg["geometry"] = ""
        save_config(cfg)
        print("已重置：透明度 88% / 始终置顶 / 回到任务栏上方")
        return

    # 命令行指定 codes
    if "--codes" in args:
        i = args.index("--codes")
        toks = [t for t in args[i + 1:] if not t.startswith("-")]
        new = []
        for t in toks:
            c = normalize_code(t)
            if not c:
                hits = search_by_name(t, limit=1)
                c = hits[0][0] if hits else None
                if c:
                    cfg.setdefault("labels", {})[c] = hits[0][1]
            if c and c not in new:
                new.append(c)
        if new:
            cfg["codes"] = new
        save_config(cfg)

    force_edit = "--edit" in args
    force_cli = "--cli" in args
    # 只有显式 --cli 才走黑窗口输入；默认弹图形窗口
    if force_cli and not force_edit and "--codes" not in args and "--no-input" not in args:
        prompt_codes(cfg)
    if "--layout" in args:
        i = args.index("--layout")
        if i + 1 < len(args):
            cfg["layout"] = args[i + 1]
    save_config(cfg)

    root = tk.Tk()
    tk.Tk.report_callback_exception = lambda *a: None

    direct = force_cli or force_edit or "--no-input" in args or \
        "--codes" in args or "--layout" in args
    if direct:
        t = Ticker(root, cfg)
        if force_edit:
            root.after(200, t._open_editor)
    else:
        # 默认：先弹图形化设置窗口，选完再开小窗
        SettingsPanel(root, cfg, lambda: Ticker(root, cfg), mode="start")
    root.mainloop()


if __name__ == "__main__":
    main()