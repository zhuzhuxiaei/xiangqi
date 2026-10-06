"""
象棋打谱软件（单文件版，含音效，线性走法记录）
运行：python xiangqi_pu.py
依赖：仅标准库

新增功能：
  1. 下一步存在多个分支时，棋盘用绿色箭头 + 序号指示候选走法。
  2. 右侧"分支选择"区为每个分支生成按钮，点击直接走该分支。
"""

import os
import sys
import math
import wave
import struct
import random
import tempfile
import subprocess
import threading
import json
import uuid
import tkinter as tk
from tkinter import ttk, filedialog, messagebox, simpledialog
from dataclasses import dataclass, field, asdict
from typing import List, Optional, Dict, Any
from shutil import which as _which_cmd


# ============================================================
# 音效合成与播放（纯标准库，跨平台）
# ============================================================

class SoundBank:
    SAMPLE_RATE = 22050

    def __init__(self):
        self.enabled = True
        self.cache_dir = os.path.join(tempfile.gettempdir(), "xq_sounds")
        os.makedirs(self.cache_dir, exist_ok=True)
        self.files = {}
        self._build_all()

    def _write_wav(self, path, samples):
        with wave.open(path, "w") as w:
            w.setnchannels(1)
            w.setsampwidth(2)
            w.setframerate(self.SAMPLE_RATE)
            frames = b"".join(
                struct.pack("<h", max(-32768, min(32767, int(s * 32767))))
                for s in samples
            )
            w.writeframes(frames)

    def _tone(self, freq, dur, volume=0.5, decay=True, wave_type="sine"):
        n = int(self.SAMPLE_RATE * dur)
        out = []
        for i in range(n):
            t = i / self.SAMPLE_RATE
            if wave_type == "sine":
                v = math.sin(2 * math.pi * freq * t)
            elif wave_type == "square":
                v = 1.0 if math.sin(2 * math.pi * freq * t) >= 0 else -1.0
            elif wave_type == "noise":
                v = random.uniform(-1, 1)
            else:
                v = math.sin(2 * math.pi * freq * t)
            env = math.exp(-6 * t / dur) if decay else 1.0
            attack = min(1.0, i / (self.SAMPLE_RATE * 0.005 + 1))
            out.append(v * env * attack * volume)
        return out

    def _synth(self, partials, dur, volume=0.5, decay_rate=6.0,
               attack=0.005, noise_amt=0.0):
        """
        以多个正弦分音叠加合成更柔和的音色。
        partials: [(freq, amp), ...]  amp 为相对权重
        noise_amt: 起始瞬态噪声占比（0~1），用于增加"木质"敲击感
        """
        n = int(self.SAMPLE_RATE * dur)
        out = [0.0] * n
        atk_n = int(self.SAMPLE_RATE * attack)
        for i in range(n):
            t = i / self.SAMPLE_RATE
            v = 0.0
            for freq, amp in partials:
                v += amp * math.sin(2 * math.pi * freq * t)
            env = math.exp(-decay_rate * t / dur) if decay_rate > 0 else 1.0
            a = min(1.0, i / (atk_n + 1))
            out[i] = v * env * a * volume
        # 叠加起始瞬态噪声，模拟木棋子落子瞬间的"咔"声
        if noise_amt > 0:
            burst_len = max(1, int(self.SAMPLE_RATE * 0.008))
            for i in range(min(burst_len, n)):
                env = math.exp(-40 * i / burst_len)
                out[i] += noise_amt * env * random.uniform(-1, 1) * volume
        # 归一化避免过载
        peak = max((abs(x) for x in out), default=1.0)
        if peak > 1.0:
            out = [x / peak for x in out]
        return out

    def _mix(self, *tracks):
        n = max(len(t) for t in tracks)
        out = [0.0] * n
        for t in tracks:
            for i, v in enumerate(t):
                out[i] += v
        return [max(-1.0, min(1.0, v)) for v in out]

    def _concat(self, *tracks):
        out = []
        for t in tracks:
            out.extend(t)
        return out

    def _silence(self, dur):
        return [0.0] * int(self.SAMPLE_RATE * dur)

    def _build_all(self):
        # 走子：木质轻敲，基频 A4(440) + 八度泛音，短促柔和
        move = self._synth(
            partials=[(440, 1.0), (880, 0.35), (1320, 0.12)],
            dur=0.12, volume=0.40, decay_rate=9.0, noise_amt=0.25,
        )

        # 吃子：更厚重的敲击 + 低频体感，叠加短噪声瞬态
        cap_body = self._synth(
            partials=[(196, 1.0), (294, 0.5), (392, 0.3)],
            dur=0.20, volume=0.55, decay_rate=7.0, noise_amt=0.35,
        )
        cap_bell = self._synth(
            partials=[(587, 1.0), (1175, 0.3)],
            dur=0.18, volume=0.22, decay_rate=8.0,
        )
        capture = self._mix(cap_body, cap_bell)

        # 将军：上行二音铃响 (E5 -> A5)，柔和正弦
        chk1 = self._synth(
            partials=[(659, 1.0), (1318, 0.25)],
            dur=0.16, volume=0.40, decay_rate=7.0,
        )
        chk2 = self._synth(
            partials=[(880, 1.0), (1760, 0.25)],
            dur=0.22, volume=0.42, decay_rate=6.5,
        )
        check = self._concat(chk1, self._silence(0.04), chk2)

        # 非法：低沉闷响 (A2 ~110Hz)，不刺耳
        illegal = self._synth(
            partials=[(110, 1.0), (165, 0.4)],
            dur=0.22, volume=0.45, decay_rate=5.5, noise_amt=0.15,
        )

        # 绝杀：下行三音收束 (A5 -> E5 -> A4)，哀而不噪
        m1 = self._synth([(880, 1.0), (1320, 0.3)], 0.16, 0.42, 7.0)
        m2 = self._synth([(659, 1.0), (988, 0.3)],  0.16, 0.42, 7.0)
        m3 = self._synth([(440, 1.0), (660, 0.3)],  0.30, 0.46, 5.5)
        mate = self._concat(m1, self._silence(0.03), m2,
                            self._silence(0.03), m3)

        # 使用版本化文件名，避免命中旧缓存导致音色不更新
        data = {"move_v2": move, "capture_v2": capture, "check_v2": check,
                "illegal_v2": illegal, "mate_v2": mate}
        # 对外仍用原名
        alias = {"move_v2": "move", "capture_v2": "capture",
                 "check_v2": "check", "illegal_v2": "illegal",
                 "mate_v2": "mate"}
        for name, samples in data.items():
            path = os.path.join(self.cache_dir, f"{name}.wav")
            if not os.path.exists(path):
                try:
                    self._write_wav(path, samples)
                except Exception:
                    continue
            self.files[alias[name]] = path

    def play(self, name):
        if not self.enabled:
            return
        path = self.files.get(name)
        if not path or not os.path.exists(path):
            return
        threading.Thread(target=self._play_sync, args=(path,), daemon=True).start()

    def _play_sync(self, path):
        try:
            if sys.platform.startswith("win"):
                import winsound
                winsound.PlaySound(path, winsound.SND_FILENAME | winsound.SND_ASYNC)
            elif sys.platform == "darwin":
                subprocess.Popen(["afplay", path],
                                 stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            else:
                for player in (["paplay"], ["aplay", "-q"],
                               ["ffplay", "-nodisp", "-autoexit", "-loglevel", "quiet"]):
                    if _which_cmd(player[0]):
                        subprocess.Popen(player + [path],
                                         stdout=subprocess.DEVNULL,
                                         stderr=subprocess.DEVNULL)
                        return
        except Exception:
            pass


# ============================================================
# 数据模型
# ============================================================

@dataclass
class MoveNode:
    id: str = field(default_factory=lambda: str(uuid.uuid4())[:8])
    move: Optional[str] = None
    fen: str = ""
    comment: str = ""
    children: List["MoveNode"] = field(default_factory=list)
    parent: Optional["MoveNode"] = field(default=None, repr=False, compare=False)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id, "move": self.move, "fen": self.fen,
            "comment": self.comment,
            "children": [c.to_dict() for c in self.children],
        }

    @classmethod
    def from_dict(cls, data, parent=None):
        node = cls(
            id=data.get("id") or str(uuid.uuid4())[:8],
            move=data.get("move"),
            fen=data.get("fen", ""),
            comment=data.get("comment", ""),
        )
        node.parent = parent
        node.children = [cls.from_dict(c, node) for c in data.get("children", [])]
        return node

    def is_root(self):
        return self.parent is None

    def add_child(self, child):
        child.parent = self
        self.children.append(child)
        return child

    def remove_child(self, child):
        if child in self.children:
            self.children.remove(child)
            child.parent = None

    def get_path_from_root(self):
        path = []
        node = self
        while node is not None:
            path.append(node)
            node = node.parent
        return list(reversed(path))


@dataclass
class GameMetadata:
    title: str = "未命名棋谱"
    red_player: str = ""
    black_player: str = ""
    event: str = ""
    date: str = ""
    result: str = ""


@dataclass
class GameTree:
    metadata: GameMetadata = field(default_factory=GameMetadata)
    root: MoveNode = field(default_factory=MoveNode)
    initial_fen: str = "rnbakabnr/9/1c5c1/p1p1p1p1p/9/9/P1P1P1P1P/1C5C1/9/RNBAKABNR w - - 0 1"

    def to_dict(self):
        return {
            "version": "1.0",
            "metadata": asdict(self.metadata),
            "initial_fen": self.initial_fen,
            "root": self.root.to_dict(),
        }

    @classmethod
    def from_dict(cls, data):
        tree = cls()
        tree.metadata = GameMetadata(**data.get("metadata", {}))
        tree.initial_fen = data.get("initial_fen", tree.initial_fen)
        tree.root = MoveNode.from_dict(data["root"], parent=None)
        if not tree.root.fen:
            tree.root.fen = tree.initial_fen
        return tree

    def save(self, filepath):
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(self.to_dict(), f, ensure_ascii=False, indent=2)

    @classmethod
    def load(cls, filepath):
        with open(filepath, "r", encoding="utf-8") as f:
            return cls.from_dict(json.load(f))


# ============================================================
# 象棋引擎
# ============================================================

def is_red(p: str) -> bool:
    return p.isupper()


class XiangqiBoard:
    INITIAL_FEN = "rnbakabnr/9/1c5c1/p1p1p1p1p/9/9/P1P1P1P1P/1C5C1/9/RNBAKABNR w - - 0 1"

    def __init__(self, fen: str = None):
        self.grid = [[None] * 9 for _ in range(10)]
        self.turn = "w"
        self.from_fen(fen or self.INITIAL_FEN)

    def from_fen(self, fen: str):
        parts = fen.split()
        rows = parts[0].split("/")
        self.grid = [[None] * 9 for _ in range(10)]
        for r, row_str in enumerate(rows):
            c = 0
            for ch in row_str:
                if ch.isdigit():
                    c += int(ch)
                else:
                    if 0 <= r < 10 and 0 <= c < 9:
                        self.grid[r][c] = ch
                    c += 1
        self.turn = parts[1] if len(parts) > 1 else "w"

    def to_fen(self) -> str:
        rows = []
        for r in range(10):
            s = ""
            empty = 0
            for c in range(9):
                p = self.grid[r][c]
                if p is None:
                    empty += 1
                else:
                    if empty:
                        s += str(empty)
                        empty = 0
                    s += p
            if empty:
                s += str(empty)
            rows.append(s)
        return "/".join(rows) + f" {self.turn} - - 0 1"

    def get(self, r, c):
        if 0 <= r < 10 and 0 <= c < 9:
            return self.grid[r][c]
        return None

    def clone(self):
        b = XiangqiBoard.__new__(XiangqiBoard)
        b.grid = [row[:] for row in self.grid]
        b.turn = self.turn
        return b

    def legal_moves(self) -> List[tuple]:
        moves = []
        for r in range(10):
            for c in range(9):
                p = self.grid[r][c]
                if p is None:
                    continue
                if is_red(p) != (self.turn == "w"):
                    continue
                for (r2, c2) in self._piece_moves(r, c, p):
                    if self._move_is_safe(r, c, r2, c2):
                        moves.append((r, c, r2, c2))
        return moves

    def _piece_moves(self, r, c, p):
        kind = p.upper()
        red = is_red(p)
        res = []

        def add(rr, cc):
            if not (0 <= rr < 10 and 0 <= cc < 9):
                return False
            t = self.grid[rr][cc]
            if t is None:
                res.append((rr, cc)); return True
            if is_red(t) != red:
                res.append((rr, cc))
            return False

        if kind == "R":
            for dr, dc in [(1, 0), (-1, 0), (0, 1), (0, -1)]:
                rr, cc = r + dr, c + dc
                while 0 <= rr < 10 and 0 <= cc < 9:
                    if not add(rr, cc): break
                    rr += dr; cc += dc
        elif kind == "C":
            for dr, dc in [(1, 0), (-1, 0), (0, 1), (0, -1)]:
                rr, cc = r + dr, c + dc
                jumped = False
                while 0 <= rr < 10 and 0 <= cc < 9:
                    t = self.grid[rr][cc]
                    if not jumped:
                        if t is None: res.append((rr, cc))
                        else: jumped = True
                    else:
                        if t is not None:
                            if is_red(t) != red: res.append((rr, cc))
                            break
                    rr += dr; cc += dc
        elif kind == "N":
            for lr, lc, dr, dc in [(1,0,2,1),(1,0,2,-1),(-1,0,-2,1),(-1,0,-2,-1),
                                    (0,1,1,2),(0,1,-1,2),(0,-1,1,-2),(0,-1,-1,-2)]:
                if self.get(r + lr, c + lc) is None:
                    add(r + dr, c + dc)
        elif kind == "B":
            for dr, dc in [(2,2),(2,-2),(-2,2),(-2,-2)]:
                rr, cc = r + dr, c + dc
                if red and rr < 5: continue
                if not red and rr > 4: continue
                if self.get(r + dr // 2, c + dc // 2) is None:
                    add(rr, cc)
        elif kind == "A":
            for dr, dc in [(1,1),(1,-1),(-1,1),(-1,-1)]:
                rr, cc = r + dr, c + dc
                if not (3 <= cc <= 5): continue
                if red and not (7 <= rr <= 9): continue
                if not red and not (0 <= rr <= 2): continue
                add(rr, cc)
        elif kind == "K":
            for dr, dc in [(1,0),(-1,0),(0,1),(0,-1)]:
                rr, cc = r + dr, c + dc
                if not (3 <= cc <= 5): continue
                if red and not (7 <= rr <= 9): continue
                if not red and not (0 <= rr <= 2): continue
                add(rr, cc)
        elif kind == "P":
            if red:
                add(r - 1, c)
                if r <= 4:
                    add(r, c - 1); add(r, c + 1)
            else:
                add(r + 1, c)
                if r >= 5:
                    add(r, c - 1); add(r, c + 1)
        return res

    def _find_king(self, red):
        target = "K" if red else "k"
        for r in range(10):
            for c in range(9):
                if self.grid[r][c] == target:
                    return (r, c)
        return None

    def _is_attacked(self, r, c, by_red):
        for rr in range(10):
            for cc in range(9):
                p = self.grid[rr][cc]
                if p is None: continue
                if is_red(p) != by_red: continue
                if (r, c) in self._piece_moves(rr, cc, p):
                    return True
        return False

    def _kings_face(self):
        rk = self._find_king(True)
        bk = self._find_king(False)
        if not rk or not bk: return False
        if rk[1] != bk[1]: return False
        c = rk[1]
        for r in range(bk[0] + 1, rk[0]):
            if self.grid[r][c] is not None:
                return False
        return True

    def _move_is_safe(self, r1, c1, r2, c2):
        board = self.clone()
        board.grid[r2][c2] = board.grid[r1][c1]
        board.grid[r1][c1] = None
        red = is_red(board.grid[r2][c2])
        king = board._find_king(red)
        if king is None: return False
        if board._kings_face(): return False
        if board._is_attacked(king[0], king[1], not red): return False
        return True

    def make_move(self, r1, c1, r2, c2):
        board = self.clone()
        board.grid[r2][c2] = board.grid[r1][c1]
        board.grid[r1][c1] = None
        board.turn = "b" if self.turn == "w" else "w"
        return board

    COL_NAMES_RED = "九八七六五四三二一"
    COL_NAMES_BLACK = "１２３４５６７８９"
    NUM_CN = "一二三四五六七八九"

    def move_to_chinese(self, r1, c1, r2, c2):
        """
        将一步走法转换为中文记谱。
        坐标约定: r 为行号(0 在上方), c 为列号(0 在左侧)。
        红方在下(行号大), 黑方在上(行号小)。
        """
        p = self.grid[r1][c1]
        if p is None:
            return "?"

        red = is_red(p)
        kind = p.upper()

        names = {
            "R": "车", "N": "马", "B": "相" if red else "象",
            "A": "仕" if red else "士", "K": "帅" if red else "将",
            "C": "炮", "P": "兵" if red else "卒",
        }
        name = names[kind]

        cols = self.COL_NAMES_RED if red else self.COL_NAMES_BLACK
        col_from = cols[c1]
        col_to = cols[c2]

        # ---------- 1. 计算"前/后/中"前缀 ----------
        same_col = []
        for r in range(len(self.grid)):
            q = self.grid[r][c1]
            if q is not None and is_red(q) == red and q.upper() == kind:
                same_col.append(r)

        prefix = name
        if len(same_col) > 1:
            same_col.sort()
            if red:
                ordered = same_col
            else:
                ordered = same_col[::-1]
            idx = ordered.index(r1)
            n = len(ordered)
            if n == 2:
                tag = "前" if idx == 0 else "后"
            elif n == 3:
                tag = ["前", "中", "后"][idx]
            else:
                if idx == 0:
                    tag = "前"
                elif idx == n - 1:
                    tag = "后"
                else:
                    tag = self.NUM_CN[idx - 1]
            prefix = tag + name
            col_from = None

        # ---------- 2. 生成走法描述 ----------
        if r1 == r2:
            body = f"平{col_to}"
        else:
            forward = (r2 < r1) if red else (r2 > r1)
            direction = "进" if forward else "退"

            if kind in ("N", "B", "A"):
                body = f"{direction}{col_to}"
            else:
                steps = abs(r1 - r2)
                body = f"{direction}{self.NUM_CN[steps - 1]}"

        # ---------- 3. 组装 ----------
        if col_from is None:
            return f"{prefix}{body}"
        else:
            return f"{prefix}{col_from}{body}"

    @staticmethod
    def coord_to_uci(r1, c1, r2, c2):
        return f"{chr(97 + c1)}{9 - r1}{chr(97 + c2)}{9 - r2}"

    @staticmethod
    def uci_to_coord(uci):
        c1 = ord(uci[0]) - 97
        r1 = 9 - int(uci[1])
        c2 = ord(uci[2]) - 97
        r2 = 9 - int(uci[3])
        return r1, c1, r2, c2


# ============================================================
# GUI
# ============================================================

class XiangqiUI:
    CELL = 60
    MARGIN = 40
    BOARD_W = 9 * CELL
    BOARD_H = 10 * CELL

    PIECE_TEXT = {
        "R":"车","N":"马","B":"相","A":"仕","K":"帅","C":"炮","P":"兵",
        "r":"车","n":"马","b":"象","a":"士","k":"将","c":"炮","p":"卒",
    }

    def __init__(self, root):
        self.root = root
        self.root.title("象棋打谱软件")
        self.root.geometry("1080x900")

        self.tree = GameTree()
        self.tree.root.fen = self.tree.initial_fen
        self.current_node = self.tree.root
        self.board = XiangqiBoard(self.tree.initial_fen)

        self.selected = None
        self.legal_targets = []
        self.last_move = None
        self.flipped = False  # 棋盘是否翻转（黑方在下方视角）

        self.autoplay = False
        self.autoplay_interval = tk.DoubleVar(value=1.5)

        try:
            self.sounds = SoundBank()
        except Exception:
            self.sounds = None

        # 主线选择 + 走法点击映射
        self.mainline_choice = {}
        self._move_tag_map = {}

        # 分支选择缓存：[(idx, node, (r1,c1,r2,c2)), ...]
        self.branch_moves = []

        self._build_ui()
        self.refresh()

    def _build_ui(self):
        main = tk.Frame(self.root)
        main.pack(fill=tk.BOTH, expand=True)

        left = tk.Frame(main)
        left.pack(side=tk.LEFT, fill=tk.BOTH, expand=False)
        self.canvas = tk.Canvas(
            left,
            width=self.BOARD_W + 2 * self.MARGIN,
            height=self.BOARD_H + 2 * self.MARGIN,
            bg="#f5deb3",
        )
        self.canvas.pack(padx=8, pady=8)
        self.canvas.bind("<Button-1>", self.on_click)

        right = tk.Frame(main)
        right.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        tk.Label(right, text="走法记录（点击任意走法跳转）", anchor="w").pack(fill=tk.X, padx=6)
        tree_frame = tk.Frame(right)
        tree_frame.pack(fill=tk.BOTH, expand=True, padx=6, pady=4)
        self.movetext = tk.Text(tree_frame, height=14, wrap=tk.WORD,
                                font=("Microsoft YaHei", 11), cursor="arrow",
                                bg="#fafafa", relief=tk.SUNKEN, borderwidth=1)
        sb = ttk.Scrollbar(tree_frame, orient="vertical", command=self.movetext.yview)
        self.movetext.configure(yscrollcommand=sb.set)
        self.movetext.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        sb.pack(side=tk.RIGHT, fill=tk.Y)

        self.movetext.tag_configure("move", foreground="#1a3b8c",
                                    spacing1=1, spacing3=1)
        self.movetext.tag_configure("move_active", foreground="#ffffff",
                                    background="#2b6cb0")
        self.movetext.tag_configure("variation", foreground="#7a5c00")
        self.movetext.tag_configure("comment", foreground="#666666",
                                    font=("Microsoft YaHei", 9, "italic"))
        self.movetext.tag_configure("number", foreground="#333333",
                                    font=("Consolas", 11, "bold"))
        self.movetext.tag_configure("paren", foreground="#888888")
        self.movetext.configure(state=tk.DISABLED)
        self.movetext.bind("<Button-1>", self.on_movetext_click)
        self.movetext.tag_bind("move", "<Enter>",
                               lambda e: self.movetext.config(cursor="hand2"))
        self.movetext.tag_bind("move", "<Leave>",
                               lambda e: self.movetext.config(cursor="arrow"))
        self.movetext.tag_bind("move_active", "<Enter>",
                               lambda e: self.movetext.config(cursor="hand2"))
        self.movetext.tag_bind("move_active", "<Leave>",
                               lambda e: self.movetext.config(cursor="arrow"))

        # ---------- 分支选择区（移到走法记录下方，便于点击）----------
        self.branch_frame = tk.LabelFrame(right, text="分支选择（下一步候选走法）")
        self.branch_frame.pack(fill=tk.X, padx=6, pady=(4, 6))

        self.branch_hint = tk.Label(
            self.branch_frame, text="当前无分支",
            anchor="w", fg="#888888",
        )
        self.branch_hint.pack(fill=tk.X, padx=4, pady=2)

        self.branch_btn_frame = tk.Frame(self.branch_frame)
        self.branch_btn_frame.pack(fill=tk.X, padx=4, pady=4)

        tk.Label(right, text="当前局面备注", anchor="w").pack(fill=tk.X, padx=6)
        self.comment_text = tk.Text(right, height=5, wrap=tk.WORD)
        self.comment_text.pack(fill=tk.X, padx=6, pady=2)
        tk.Button(right, text="保存备注", command=self.save_comment).pack(padx=6, pady=2, anchor="w")

        ctrl = tk.LabelFrame(right, text="控制")
        ctrl.pack(fill=tk.X, padx=6, pady=6)

        row1 = tk.Frame(ctrl); row1.pack(fill=tk.X, pady=2)
        tk.Button(row1, text="◀ 上一步", command=self.go_back).pack(side=tk.LEFT, padx=2)
        tk.Button(row1, text="下一步 ▶", command=self.go_forward).pack(side=tk.LEFT, padx=2)
        tk.Button(row1, text="⟲ 回到开头", command=self.go_start).pack(side=tk.LEFT, padx=2)
        tk.Button(row1, text="⇅ 翻转棋盘", command=self.toggle_flip).pack(side=tk.LEFT, padx=2)

        row2 = tk.Frame(ctrl); row2.pack(fill=tk.X, pady=2)
        self.autoplay_btn = tk.Button(row2, text="▶ 自动播放", command=self.toggle_autoplay)
        self.autoplay_btn.pack(side=tk.LEFT, padx=2)
        tk.Label(row2, text="间隔(秒):").pack(side=tk.LEFT, padx=4)
        tk.Spinbox(row2, from_=0.2, to=10, increment=0.1,
                   textvariable=self.autoplay_interval, width=6).pack(side=tk.LEFT)

        row3 = tk.Frame(ctrl); row3.pack(fill=tk.X, pady=2)
        tk.Button(row3, text="💾 保存棋谱", command=self.save_game).pack(side=tk.LEFT, padx=2)
        tk.Button(row3, text="📂 打开棋谱", command=self.load_game).pack(side=tk.LEFT, padx=2)
        tk.Button(row3, text="🗑 删除当前分支", command=self.delete_branch).pack(side=tk.LEFT, padx=2)

        row4 = tk.Frame(ctrl); row4.pack(fill=tk.X, pady=2)
        tk.Button(row4, text="✎ 编辑棋谱信息", command=self.edit_metadata).pack(side=tk.LEFT, padx=2)
        tk.Button(row4, text="↺ 重置棋谱", command=self.reset_game).pack(side=tk.LEFT, padx=2)
        tk.Button(row4, text="★ 设为主线", command=self.set_mainline).pack(side=tk.LEFT, padx=2)

        row5 = tk.Frame(ctrl); row5.pack(fill=tk.X, pady=2)
        self.sound_var = tk.BooleanVar(value=True)
        tk.Checkbutton(row5, text="🔊 音效", variable=self.sound_var,
                       command=self.toggle_sound).pack(side=tk.LEFT, padx=2)
        tk.Button(row5, text="试听", command=lambda: self.sounds and self.sounds.play("move")
                  ).pack(side=tk.LEFT, padx=2)
        tk.Button(row5, text="🔗 关联.xq", command=self.associate_xq_file
                  ).pack(side=tk.LEFT, padx=2)

        # 快捷键提示
        tk.Label(ctrl, text="快捷键: ←/→ 上下步  Home 开头  Space 自动播放  "
                           "F 翻转  Ctrl+S 保存  Ctrl+O 打开  Del 删分支  "
                           "M 主线  Esc 取消选中",
                 anchor="w", fg="#666666", wraplength=300,
                 font=("Microsoft YaHei", 8)).pack(fill=tk.X, padx=4, pady=(4, 2))

        self.status = tk.Label(self.root, text="就绪", anchor="w", bd=1, relief=tk.SUNKEN)
        self.status.pack(side=tk.BOTTOM, fill=tk.X)

    # ---------- 绘制 ----------
    def board_pos(self, r, c):
        # 翻转时把坐标做 180° 旋转（行列同时翻转）
        if self.flipped:
            c = 8 - c
            r = 9 - r
        return self.MARGIN + c * self.CELL, self.MARGIN + r * self.CELL

    def draw_board(self):
        self.canvas.delete("all")
        M, C = self.MARGIN, self.CELL

        for r in range(10):
            y = M + r * C
            self.canvas.create_line(M, y, M + 8 * C, y, width=1.5)
        for c in range(9):
            x = M + c * C
            if c == 0 or c == 8:
                self.canvas.create_line(x, M, x, M + 9 * C, width=1.5)
            else:
                self.canvas.create_line(x, M, x, M + 4 * C, width=1.5)
                self.canvas.create_line(x, M + 5 * C, x, M + 9 * C, width=1.5)
        for (r1, r2) in [(0, 2), (7, 9)]:
            self.canvas.create_line(M + 3 * C, M + r1 * C, M + 5 * C, M + r2 * C, width=1.5)
            self.canvas.create_line(M + 5 * C, M + r1 * C, M + 3 * C, M + r2 * C, width=1.5)
        # 翻转后楚河/漢界左右对调，保持各自仍在原本的"半边"
        left_text, right_text = ("漢 界", "楚 河") if self.flipped else ("楚 河", "漢 界")
        self.canvas.create_text(M + 2 * C, M + 4.5 * C, text=left_text,
                                font=("KaiTi", 20), fill="#8b4513")
        self.canvas.create_text(M + 6 * C, M + 4.5 * C, text=right_text,
                                font=("KaiTi", 20), fill="#8b4513")

        if self.last_move:
            r1, c1, r2, c2 = self.last_move
            for (r, c) in [(r1, c1), (r2, c2)]:
                x, y = self.board_pos(r, c)
                self.canvas.create_rectangle(x - C / 2 + 2, y - C / 2 + 2,
                                             x + C / 2 - 2, y + C / 2 - 2,
                                             outline="#ffaa00", width=3)

        for r in range(10):
            for c in range(9):
                p = self.board.grid[r][c]
                if p is None: continue
                x, y = self.board_pos(r, c)
                red = p.isupper()
                fill = "#fffacd"
                outline = "#cc0000" if red else "#000000"
                color = "#cc0000" if red else "#000000"
                self.canvas.create_oval(x - C / 2 + 4, y - C / 2 + 4,
                                        x + C / 2 - 4, y + C / 2 - 4,
                                        fill=fill, outline=outline, width=2)
                self.canvas.create_text(x, y, text=self.PIECE_TEXT[p],
                                        font=("KaiTi", 22, "bold"), fill=color)

        if self.selected:
            r, c = self.selected
            x, y = self.board_pos(r, c)
            self.canvas.create_rectangle(x - C / 2 + 1, y - C / 2 + 1,
                                         x + C / 2 - 1, y + C / 2 - 1,
                                         outline="#00cc00", width=3)
            for (tr, tc) in self.legal_targets:
                x2, y2 = self.board_pos(tr, tc)
                self.canvas.create_oval(x2 - 6, y2 - 6, x2 + 6, y2 + 6,
                                        fill="#00cc00", outline="")

        # 分支箭头
        self._draw_branch_arrows()

    # ---------- 分支箭头绘制 ----------
    def _draw_branch_arrows(self):
        """下一步存在多个分支时，用绿色箭头 + 序号指示每个候选走法。"""
        if not self.branch_moves:
            return
        for idx, node, (r1, c1, r2, c2) in self.branch_moves:
            x1, y1 = self.board_pos(r1, c1)
            x2, y2 = self.board_pos(r2, c2)

            # 绿色箭头
            self.canvas.create_line(
                x1, y1, x2, y2,
                arrow=tk.LAST, arrowshape=(16, 20, 6),
                fill="#00aa00", width=3, smooth=False,
            )

            # 序号圆圈（中点偏移一点）
            mx, my = (x1 + x2) / 2, (y1 + y2) / 2
            off_x = -14 if x2 >= x1 else 14
            off_y = -14 if y2 >= y1 else 14
            cx, cy = mx + off_x, my + off_y
            rad = 11
            self.canvas.create_oval(
                cx - rad, cy - rad, cx + rad, cy + rad,
                fill="#00cc00", outline="#006600", width=2,
            )
            self.canvas.create_text(
                cx, cy, text=str(idx + 1),
                font=("Arial", 10, "bold"), fill="white",
            )

    def _collect_branches(self):
        """收集当前节点下一步的所有候选走法。"""
        self.branch_moves = []
        node = self.current_node
        if len(node.children) <= 1:
            return
        for i, ch in enumerate(node.children):
            if not ch.move:
                continue
            try:
                r1, c1, r2, c2 = XiangqiBoard.uci_to_coord(ch.move)
            except Exception:
                continue
            self.branch_moves.append((i, ch, (r1, c1, r2, c2)))

    # ---------- 分支按钮 ----------
    def _refresh_branch_buttons(self):
        """根据当前节点的子节点，重建分支按钮。"""
        for w in self.branch_btn_frame.winfo_children():
            w.destroy()

        node = self.current_node
        if len(node.children) <= 1:
            self.branch_hint.config(
                text="当前无分支" if not node.children else "下一步只有唯一走法",
                fg="#888888",
            )
            return

        self.branch_hint.config(
            text=f"下一步有 {len(node.children)} 种走法，点击按钮直接走：",
            fg="#006600",
        )

        circled = "①②③④⑤⑥⑦⑧⑨⑩"
        for i, ch in enumerate(node.children):
            if not ch.move:
                continue
            try:
                r1, c1, r2, c2 = XiangqiBoard.uci_to_coord(ch.move)
            except Exception:
                continue
            pb = XiangqiBoard(ch.parent.fen)
            move_text = pb.move_to_chinese(r1, c1, r2, c2)

            mark = circled[i] if i < len(circled) else f"({i+1})"

            btn = tk.Button(
                self.branch_btn_frame,
                text=f"{mark} {move_text}",
                anchor="w",
                fg="#006600",
                command=lambda n=ch: self._jump_to_node(n),
            )
            btn.pack(fill=tk.X, pady=1)

    # ---------- 交互 ----------
    def on_click(self, event):
        # 优先判断是否点击了分支序号圆圈
        if self.branch_moves:
            for idx, node, (r1, c1, r2, c2) in self.branch_moves:
                x1, y1 = self.board_pos(r1, c1)
                x2, y2 = self.board_pos(r2, c2)
                mx, my = (x1 + x2) / 2, (y1 + y2) / 2
                off_x = -14 if x2 >= x1 else 14
                off_y = -14 if y2 >= y1 else 14
                cx, cy = mx + off_x, my + off_y
                if (event.x - cx) ** 2 + (event.y - cy) ** 2 <= 13 ** 2:
                    self._jump_to_node(node)
                    return

        c = round((event.x - self.MARGIN) / self.CELL)
        r = round((event.y - self.MARGIN) / self.CELL)
        # 屏幕坐标 -> 实际棋盘坐标（翻转时反向换算）
        if self.flipped:
            c = 8 - c
            r = 9 - r
        if not (0 <= r < 10 and 0 <= c < 9):
            return
        p = self.board.grid[r][c]
        turn_red = (self.board.turn == "w")

        if self.selected:
            r1, c1 = self.selected
            if p is not None and (p.isupper() == turn_red):
                self.selected = (r, c)
                self.legal_targets = self._filter_targets(r, c)
            elif (r, c) in self.legal_targets:
                self.do_move(r1, c1, r, c)
                self.selected = None
                self.legal_targets = []
            else:
                if p is not None and (p.isupper() != turn_red):
                    if self.sounds:
                        self.sounds.play("illegal")
                self.selected = None
                self.legal_targets = []
        else:
            if p is not None and (p.isupper() == turn_red):
                self.selected = (r, c)
                self.legal_targets = self._filter_targets(r, c)

        self.draw_board()

    def _filter_targets(self, r, c):
        return [(r2, c2) for (r1, c1, r2, c2) in self.board.legal_moves()
                if r1 == r and c1 == c]

    def do_move(self, r1, c1, r2, c2):
        uci = self.board.coord_to_uci(r1, c1, r2, c2)
        captured = self.board.grid[r2][c2] is not None

        existing = next((ch for ch in self.current_node.children if ch.move == uci), None)
        if existing:
            self.current_node = existing
        else:
            new_board = self.board.make_move(r1, c1, r2, c2)
            node = MoveNode(move=uci, fen=new_board.to_fen())
            self.current_node.add_child(node)
            self.current_node = node

        self.board = XiangqiBoard(self.current_node.fen)
        self.last_move = (r1, c1, r2, c2)

        self._play_move_sound(captured)
        self.refresh()

    def _play_move_sound(self, captured):
        if not self.sounds or not self.sounds.enabled:
            return
        opponent_moves = self.board.legal_moves()
        opponent_in_check = self._is_in_check(self.board)
        if opponent_in_check and not opponent_moves:
            self.sounds.play("mate")
        elif opponent_in_check:
            self.sounds.play("check")
        elif captured:
            self.sounds.play("capture")
        else:
            self.sounds.play("move")

    @staticmethod
    def _is_in_check(board):
        red_to_move = (board.turn == "w")
        king = board._find_king(red_to_move)
        if king is None:
            return False
        return board._is_attacked(king[0], king[1], not red_to_move)

    # ---------- 导航 ----------
    def go_back(self):
        if self.current_node.parent is not None:
            self.current_node = self.current_node.parent
            self.board = XiangqiBoard(self.current_node.fen)
            self._update_last_move()
            self.refresh()

    def go_forward(self):
        if not self.current_node.children:
            return
        if len(self.current_node.children) > 1:
            messagebox.showinfo("提示", "当前存在多个分叉，请点击右侧分支按钮或走法记录选择")
            return
        self.current_node = self.current_node.children[0]
        self.board = XiangqiBoard(self.current_node.fen)
        self._update_last_move()
        self.refresh()

    def go_start(self):
        self.current_node = self.tree.root
        self.board = XiangqiBoard(self.tree.root.fen)
        self.last_move = None
        self.refresh()

    def _update_last_move(self):
        parent = self.current_node.parent
        if parent is None or not self.current_node.move:
            self.last_move = None
            return
        r1, c1, r2, c2 = XiangqiBoard.uci_to_coord(self.current_node.move)
        self.last_move = (r1, c1, r2, c2)

    # ---------- 刷新 ----------
    def refresh(self):
        self._collect_branches()
        self.draw_board()
        self._render_movetext()
        self._refresh_comment()
        self._refresh_branch_buttons()
        self._refresh_status()

    # ---------- 线性走法记录 ----------
    def _main_child(self, node):
        if not node.children:
            return None
        idx = self.mainline_choice.get(node.id, 0)
        if not (0 <= idx < len(node.children)):
            idx = 0
        return node.children[idx]

    def _render_movetext(self):
        self.movetext.configure(state=tk.NORMAL)
        self.movetext.delete("1.0", tk.END)
        self._move_tag_map.clear()

        path_ids = {n.id for n in self.current_node.get_path_from_root()}

        main = self._main_child(self.tree.root)
        if main is None:
            self.movetext.insert(tk.END, "（空棋谱，点击棋盘开始走子）", "comment")
        else:
            self._render_mainline(main, path_ids, turn_no=1)

        self.movetext.configure(state=tk.DISABLED)

    def _render_mainline(self, start_node, path_ids, turn_no):
        node = start_node
        while node is not None:
            parent = node.parent
            pb = XiangqiBoard(parent.fen)
            r1, c1, r2, c2 = XiangqiBoard.uci_to_coord(node.move)
            move_text = pb.move_to_chinese(r1, c1, r2, c2)
            is_red_turn = (pb.turn == "w")

            if is_red_turn:
                self.movetext.insert(tk.END, f"{turn_no}. ", "number")

            tag = f"mv_{node.id}"
            self.movetext.insert(tk.END, move_text,
                                 ("move_active" if node.id in path_ids else "move", tag))
            self._move_tag_map[tag] = node
            self.movetext.insert(tk.END, " ")

            main_child = self._main_child(node)
            for ch in node.children:
                if ch is main_child:
                    continue
                pcb = XiangqiBoard(ch.parent.fen)
                self.movetext.insert(tk.END, "(", "paren")
                if pcb.turn == "w":
                    self.movetext.insert(tk.END, f"{turn_no}. ", "number")
                else:
                    self.movetext.insert(tk.END, f"{turn_no}... ", "number")
                self._render_variation(ch, path_ids, turn_no)
                self.movetext.insert(tk.END, ") ", "paren")

            if not is_red_turn:
                turn_no += 1

            if node.comment:
                self.movetext.insert(tk.END, f"{{{node.comment}}} ", "comment")

            node = main_child

    def _render_variation(self, node, path_ids, turn_no):
        cur = node
        while cur is not None:
            parent = cur.parent
            pb = XiangqiBoard(parent.fen)
            r1, c1, r2, c2 = XiangqiBoard.uci_to_coord(cur.move)
            move_text = pb.move_to_chinese(r1, c1, r2, c2)
            is_red_turn = (pb.turn == "w")

            tag = f"mv_{cur.id}"
            self.movetext.insert(tk.END, move_text,
                                 ("move_active" if cur.id in path_ids else "variation", tag))
            self._move_tag_map[tag] = cur
            self.movetext.insert(tk.END, " ")

            main_child = self._main_child(cur)
            for ch in cur.children:
                if ch is main_child:
                    continue
                pcb = XiangqiBoard(ch.parent.fen)
                self.movetext.insert(tk.END, "(", "paren")
                if pcb.turn == "w":
                    self.movetext.insert(tk.END, f"{turn_no}. ", "number")
                else:
                    self.movetext.insert(tk.END, f"{turn_no}... ", "number")
                self._render_variation(ch, path_ids, turn_no)
                self.movetext.insert(tk.END, ") ", "paren")

            if not is_red_turn:
                turn_no += 1

            if cur.comment:
                self.movetext.insert(tk.END, f"{{{cur.comment}}} ", "comment")

            cur = main_child

    def on_movetext_click(self, event):
        idx = self.movetext.index(f"@{event.x},{event.y}")
        for tag_name in self.movetext.tag_names(idx):
            if tag_name in self._move_tag_map:
                self._jump_to_node(self._move_tag_map[tag_name])
                return

    def _jump_to_node(self, node):
        if node is self.current_node:
            return
        self.current_node = node
        self.board = XiangqiBoard(node.fen)
        self._update_last_move()
        self.selected = None
        self.legal_targets = []
        self.refresh()

    # ---------- 备注 ----------
    def _refresh_comment(self):
        self.comment_text.delete("1.0", tk.END)
        self.comment_text.insert("1.0", self.current_node.comment)

    def save_comment(self):
        self.current_node.comment = self.comment_text.get("1.0", tk.END).strip()
        self._render_movetext()
        self.status.config(text="备注已保存")

    # ---------- 状态 ----------
    def _refresh_status(self):
        path = self.current_node.get_path_from_root()
        turn = "红方" if self.board.turn == "w" else "黑方"
        self.status.config(
            text=f"当前手数: {len(path) - 1}  轮到: {turn}  "
                 f"分叉数: {len(self.current_node.children)}  "
                 f"FEN: {self.board.to_fen()}"
        )

    # ---------- 自动播放 ----------
    def toggle_autoplay(self):
        if self.autoplay:
            self.autoplay = False
            self.autoplay_btn.config(text="▶ 自动播放")
            self.status.config(text="已暂停")
        else:
            self.autoplay = True
            self.autoplay_btn.config(text="⏸ 暂停")
            self._autoplay_loop()

    def _autoplay_loop(self):
        if not self.autoplay:
            return
        if not self.current_node.children:
            self.autoplay = False
            self.autoplay_btn.config(text="▶ 自动播放")
            self.status.config(text="已播放到末尾")
            return
        if len(self.current_node.children) > 1:
            self.status.config(text="⚠ 存在分叉，请点击右侧分支按钮选择分支后继续")
            self.autoplay = False
            self.autoplay_btn.config(text="▶ 自动播放")
            self.refresh()
            return

        self.current_node = self.current_node.children[0]
        self.board = XiangqiBoard(self.current_node.fen)
        self._update_last_move()
        self.refresh()

        delay = int(self.autoplay_interval.get() * 1000)
        self.root.after(delay, self._autoplay_loop)

    # ---------- 保存 / 打开 ----------
    def save_game(self):
        self.current_node.comment = self.comment_text.get("1.0", tk.END).strip()
        if not self.tree.metadata.title or self.tree.metadata.title == "未命名棋谱":
            title = simpledialog.askstring("棋谱标题", "请输入棋谱标题:",
                                           initialvalue="未命名棋谱")
            if title:
                self.tree.metadata.title = title
        fp = filedialog.asksaveasfilename(
            defaultextension=".xq",
            filetypes=[("象棋棋谱", "*.xq"), ("JSON", "*.json")],
        )
        if not fp: return
        try:
            self.tree.save(fp)
            self.status.config(text=f"已保存到 {fp}")
        except Exception as e:
            messagebox.showerror("保存失败", str(e))

    def load_game(self):
        fp = filedialog.askopenfilename(
            filetypes=[("象棋棋谱", "*.xq"), ("JSON", "*.json")],
        )
        if not fp: return
        self.load_from_path(fp)

    def load_from_path(self, fp):
        """从给定路径加载棋谱（不弹对话框）。供命令行启动 / 双击 .xq 调用。"""
        try:
            self.tree = GameTree.load(fp)
            self.current_node = self.tree.root
            self.board = XiangqiBoard(self.tree.root.fen or self.tree.initial_fen)
            self.selected = None
            self.legal_targets = []
            self.last_move = None
            self.mainline_choice = {}
            self.refresh()
            self.status.config(text=f"已加载 {fp}")
            self.root.title(f"象棋打谱软件 - {os.path.basename(fp)}")
        except Exception as e:
            messagebox.showerror("加载失败", str(e))

    def delete_branch(self):
        if self.current_node.is_root():
            messagebox.showwarning("提示", "无法删除根节点")
            return
        if not messagebox.askyesno("确认", "确定删除当前分支及其所有子分支？"):
            return
        parent = self.current_node.parent
        parent.remove_child(self.current_node)
        self.mainline_choice.pop(self.current_node.id, None)
        self.current_node = parent
        self.board = XiangqiBoard(parent.fen)
        self._update_last_move()
        self.refresh()

    # ---------- 主线 ----------
    def set_mainline(self):
        node = self.current_node
        if node.is_root():
            messagebox.showinfo("提示", "根节点无需设为主线")
            return
        parent = node.parent
        idx = parent.children.index(node)
        if idx == 0:
            self.status.config(text="当前已是主线")
            return
        self.mainline_choice[parent.id] = idx
        self._render_movetext()
        self.status.config(text="已设为主线")

    # ---------- 元信息 / 重置 ----------
    def edit_metadata(self):
        dlg = tk.Toplevel(self.root)
        dlg.title("编辑棋谱信息")
        dlg.transient(self.root); dlg.grab_set()
        fields = [("标题","title"),("红方","red_player"),("黑方","black_player"),
                  ("赛事","event"),("日期","date"),("结果","result")]
        entries = {}
        for i, (label, key) in enumerate(fields):
            tk.Label(dlg, text=label).grid(row=i, column=0, padx=6, pady=4, sticky="e")
            e = tk.Entry(dlg, width=30)
            e.grid(row=i, column=1, padx=6, pady=4)
            e.insert(0, getattr(self.tree.metadata, key))
            entries[key] = e

        def on_ok():
            for key, e in entries.items():
                setattr(self.tree.metadata, key, e.get().strip())
            dlg.destroy()
            self._render_movetext()
            self.status.config(text="棋谱信息已更新")
        tk.Button(dlg, text="确定", command=on_ok).grid(row=len(fields), column=0,
                                                        columnspan=2, pady=8)

    def reset_game(self):
        if not messagebox.askyesno("确认", "确定清空当前棋谱？"):
            return
        self.tree = GameTree()
        self.tree.root.fen = self.tree.initial_fen
        self.current_node = self.tree.root
        self.board = XiangqiBoard(self.tree.initial_fen)
        self.selected = None
        self.legal_targets = []
        self.last_move = None
        self.mainline_choice = {}
        self.refresh()

    # ---------- 音效开关 ----------
    def toggle_sound(self):
        if self.sounds:
            self.sounds.enabled = self.sound_var.get()
        self.status.config(text="音效：" + ("开" if self.sound_var.get() else "关"))

    # ---------- 棋盘翻转 ----------
    def toggle_flip(self):
        self.flipped = not self.flipped
        # 翻转后清除选中状态，避免视觉错位
        self.selected = None
        self.legal_targets = []
        self.refresh()
        self.status.config(text="棋盘已" + ("翻转（黑方视角）" if self.flipped else "恢复（红方视角）"))

    # ---------- 快捷键 ----------
    def bind_shortcuts(self, root):
        """绑定全局快捷键。单字母快捷键在文本框聚焦时不触发，避免误输入。"""
        def is_typing(widget):
            return isinstance(widget, (tk.Text, tk.Entry, ttk.Entry, tk.Spinbox))

        def guard(fn):
            def wrapped(e):
                if is_typing(e.widget):
                    return
                try:
                    fn()
                except Exception:
                    pass
            return wrapped

        root.bind("<Left>",      lambda e: self.go_back())
        root.bind("<Right>",     lambda e: self.go_forward())
        root.bind("<Home>",      lambda e: self.go_start())
        root.bind("<space>",     lambda e: self.toggle_autoplay())
        root.bind("<Key-f>",     guard(self.toggle_flip))
        root.bind("<Key-F>",     guard(self.toggle_flip))
        root.bind("<Key-m>",     guard(self.set_mainline))
        root.bind("<Key-M>",     guard(self.set_mainline))
        root.bind("<Control-s>", lambda e: self.save_game())
        root.bind("<Control-S>", lambda e: self.save_game())
        root.bind("<Control-o>", lambda e: self.load_game())
        root.bind("<Control-O>", lambda e: self.load_game())
        root.bind("<Delete>",    guard(self.delete_branch))
        root.bind("<Escape>",    lambda e: self._cancel_selection())

    def _cancel_selection(self):
        """取消当前选中棋子。"""
        self.selected = None
        self.legal_targets = []
        self.draw_board()

    # ---------- 关联 .xq 文件（Windows 双击打开）----------
    def associate_xq_file(self):
        """在 Windows 注册表中注册 .xq 扩展名，使双击即可用本程序打开。"""
        if not sys.platform.startswith("win"):
            messagebox.showinfo("提示", "文件关联仅在 Windows 下支持。")
            return

        try:
            import winreg
        except Exception:
            messagebox.showerror("错误", "无法导入 winreg 模块")
            return

        # 本脚本绝对路径（用 pythonw 启动，避免弹出黑色控制台窗口）
        script_path = os.path.abspath(__file__)
        exe_path = _which_cmd("pythonw") or _which_cmd("python") or sys.executable
        # 构造调用命令
        if exe_path.lower().endswith(("python.exe", "pythonw.exe")):
            cmd = f'"{exe_path}" "{script_path}" "%1"'
        else:
            cmd = f'"{exe_path}" "{script_path}" "%1"'

        try:
            with winreg.CreateKey(winreg.HKEY_CURRENT_USER, r".xq") as key:
                winreg.SetValueEx(key, None, 0, winreg.REG_SZ, "XiangqiGameRecord")
            with winreg.CreateKey(winreg.HKEY_CURRENT_USER,
                                 r"XiangqiGameRecord") as key:
                winreg.SetValueEx(key, None, 0, winreg.REG_SZ, "象棋棋谱文件")
            with winreg.CreateKey(winreg.HKEY_CURRENT_USER,
                                 r"XiangqiGameRecord\DefaultIcon") as key:
                winreg.SetValueEx(key, None, 0, winreg.REG_SZ, f'"{exe_path}",0')
            with winreg.CreateKey(winreg.HKEY_CURRENT_USER,
                                 r"XiangqiGameRecord\shell\open\command") as key:
                winreg.SetValueEx(key, None, 0, winreg.REG_SZ, cmd)
            messagebox.showinfo(
                "关联成功",
                f"已将 .xq 文件关联到本程序。\n\n"
                f"调用命令: {cmd}\n\n"
                "此后双击 .xq 文件即可启动本软件并自动加载棋谱。",
            )
            self.status.config(text=".xq 文件关联已设置")
        except Exception as e:
            messagebox.showerror("关联失败", str(e))


# ============================================================
# 入口
# ============================================================

def main():
    # 支持命令行参数：xiangqi2.py <file.xq>  (双击 .xq 文件时由系统传入)
    args = sys.argv[1:]
    initial_file = None
    for a in args:
        if isinstance(a, str) and os.path.isfile(a) and a.lower().endswith((".xq", ".json")):
            initial_file = a
            break

    root = tk.Tk()
    app = XiangqiUI(root)
    # 绑定快捷键
    app.bind_shortcuts(root)
    # 如有命令行传入的棋谱文件，启动后立即加载
    if initial_file:
        root.after(50, lambda: app.load_from_path(initial_file))
    root.mainloop()


if __name__ == "__main__":
    main()