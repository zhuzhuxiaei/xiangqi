"""
象棋打谱软件（单文件版）
- 树形结构保存走法，支持分叉
- 每个节点可添加备注
- 支持保存/打开棋谱（JSON 格式）
- 支持自动播放与间隔设置
运行：python xiangqi_pu.py
依赖：仅标准库 tkinter
"""

import json
import uuid
import copy
import tkinter as tk
from tkinter import ttk, filedialog, messagebox, simpledialog
from dataclasses import dataclass, field, asdict
from typing import List, Optional, Dict, Any


# ============================================================
# 数据模型：树形结构
# ============================================================

@dataclass
class MoveNode:
    """走法节点（树形结构核心）"""
    id: str = field(default_factory=lambda: str(uuid.uuid4())[:8])
    move: Optional[str] = None      # uci 走法，如 "h2e2"；根节点为 None
    fen: str = ""                   # 该节点对应局面
    comment: str = ""               # 用户备注
    children: List["MoveNode"] = field(default_factory=list)
    parent: Optional["MoveNode"] = field(default=None, repr=False, compare=False)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "move": self.move,
            "fen": self.fen,
            "comment": self.comment,
            "children": [c.to_dict() for c in self.children],
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any], parent: Optional["MoveNode"] = None) -> "MoveNode":
        node = cls(
            id=data.get("id") or str(uuid.uuid4())[:8],
            move=data.get("move"),
            fen=data.get("fen", ""),
            comment=data.get("comment", ""),
        )
        node.parent = parent
        node.children = [cls.from_dict(c, node) for c in data.get("children", [])]
        return node

    def is_root(self) -> bool:
        return self.parent is None

    def is_leaf(self) -> bool:
        return len(self.children) == 0

    def add_child(self, child: "MoveNode") -> "MoveNode":
        child.parent = self
        self.children.append(child)
        return child

    def remove_child(self, child: "MoveNode"):
        if child in self.children:
            self.children.remove(child)
            child.parent = None

    def get_path_from_root(self) -> List["MoveNode"]:
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

    def to_dict(self) -> Dict[str, Any]:
        return {
            "version": "1.0",
            "metadata": asdict(self.metadata),
            "initial_fen": self.initial_fen,
            "root": self.root.to_dict(),
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "GameTree":
        tree = cls()
        tree.metadata = GameMetadata(**data.get("metadata", {}))
        tree.initial_fen = data.get("initial_fen", tree.initial_fen)
        tree.root = MoveNode.from_dict(data["root"], parent=None)
        # 若根节点无 fen，则用初始 fen 填充
        if not tree.root.fen:
            tree.root.fen = tree.initial_fen
        return tree

    def save(self, filepath: str):
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(self.to_dict(), f, ensure_ascii=False, indent=2)

    @classmethod
    def load(cls, filepath: str) -> "GameTree":
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

    # ---------- FEN ----------
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

    # ---------- 工具 ----------
    def get(self, r, c):
        if 0 <= r < 10 and 0 <= c < 9:
            return self.grid[r][c]
        return None

    def clone(self):
        b = XiangqiBoard.__new__(XiangqiBoard)
        b.grid = [row[:] for row in self.grid]
        b.turn = self.turn
        return b

    # ---------- 走法生成 ----------
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

    def _piece_moves(self, r, c, p) -> List[tuple]:
        kind = p.upper()
        red = is_red(p)
        res = []

        def add(rr, cc):
            if not (0 <= rr < 10 and 0 <= cc < 9):
                return False
            t = self.grid[rr][cc]
            if t is None:
                res.append((rr, cc))
                return True
            if is_red(t) != red:
                res.append((rr, cc))
            return False

        if kind == "R":  # 车
            for dr, dc in [(1, 0), (-1, 0), (0, 1), (0, -1)]:
                rr, cc = r + dr, c + dc
                while 0 <= rr < 10 and 0 <= cc < 9:
                    if not add(rr, cc):
                        break
                    rr += dr; cc += dc
        elif kind == "C":  # 炮
            for dr, dc in [(1, 0), (-1, 0), (0, 1), (0, -1)]:
                rr, cc = r + dr, c + dc
                jumped = False
                while 0 <= rr < 10 and 0 <= cc < 9:
                    t = self.grid[rr][cc]
                    if not jumped:
                        if t is None:
                            res.append((rr, cc))
                        else:
                            jumped = True
                    else:
                        if t is not None:
                            if is_red(t) != red:
                                res.append((rr, cc))
                            break
                    rr += dr; cc += dc
        elif kind == "N":  # 马
            horse = [(1, 0, 2, 1), (1, 0, 2, -1), (-1, 0, -2, 1), (-1, 0, -2, -1),
                     (0, 1, 1, 2), (0, 1, -1, 2), (0, -1, 1, -2), (0, -1, -1, -2)]
            for lr, lc, dr, dc in horse:
                if self.get(r + lr, c + lc) is None:
                    add(r + dr, c + dc)
        elif kind == "B":  # 象/相
            for dr, dc in [(2, 2), (2, -2), (-2, 2), (-2, -2)]:
                rr, cc = r + dr, c + dc
                if red and rr < 5:
                    continue
                if not red and rr > 4:
                    continue
                if self.get(r + dr // 2, c + dc // 2) is None:
                    add(rr, cc)
        elif kind == "A":  # 士/仕
            for dr, dc in [(1, 1), (1, -1), (-1, 1), (-1, -1)]:
                rr, cc = r + dr, c + dc
                if not (3 <= cc <= 5):
                    continue
                if red and not (7 <= rr <= 9):
                    continue
                if not red and not (0 <= rr <= 2):
                    continue
                add(rr, cc)
        elif kind == "K":  # 将/帅
            for dr, dc in [(1, 0), (-1, 0), (0, 1), (0, -1)]:
                rr, cc = r + dr, c + dc
                if not (3 <= cc <= 5):
                    continue
                if red and not (7 <= rr <= 9):
                    continue
                if not red and not (0 <= rr <= 2):
                    continue
                add(rr, cc)
        elif kind == "P":  # 兵/卒
            if red:
                add(r - 1, c)
                if r <= 4:
                    add(r, c - 1)
                    add(r, c + 1)
            else:
                add(r + 1, c)
                if r >= 5:
                    add(r, c - 1)
                    add(r, c + 1)
        return res

    def _find_king(self, red: bool):
        target = "K" if red else "k"
        for r in range(10):
            for c in range(9):
                if self.grid[r][c] == target:
                    return (r, c)
        return None

    def _is_attacked(self, r, c, by_red) -> bool:
        for rr in range(10):
            for cc in range(9):
                p = self.grid[rr][cc]
                if p is None:
                    continue
                if is_red(p) != by_red:
                    continue
                if (r, c) in self._piece_moves(rr, cc, p):
                    return True
        return False

    def _kings_face(self) -> bool:
        rk = self._find_king(True)
        bk = self._find_king(False)
        if not rk or not bk:
            return False
        if rk[1] != bk[1]:
            return False
        c = rk[1]
        for r in range(bk[0] + 1, rk[0]):
            if self.grid[r][c] is not None:
                return False
        return True

    def _move_is_safe(self, r1, c1, r2, c2) -> bool:
        board = self.clone()
        board.grid[r2][c2] = board.grid[r1][c1]
        board.grid[r1][c1] = None
        red = is_red(board.grid[r2][c2])
        king = board._find_king(red)
        if king is None:
            return False
        if board._kings_face():
            return False
        if board._is_attacked(king[0], king[1], not red):
            return False
        return True

    def make_move(self, r1, c1, r2, c2) -> "XiangqiBoard":
        board = self.clone()
        board.grid[r2][c2] = board.grid[r1][c1]
        board.grid[r1][c1] = None
        board.turn = "b" if self.turn == "w" else "w"
        return board

    # ---------- 记谱 ----------
    COL_NAMES_RED = "九八七六五四三二一"
    COL_NAMES_BLACK = "１２３４５６７８９"
    NUM_CN = "一二三四五六七八九"

    def move_to_chinese(self, r1, c1, r2, c2) -> str:
        p = self.grid[r1][c1]
        if p is None:
            return "?"
        red = is_red(p)
        kind = p.upper()
        names = {"R": "车", "N": "马", "B": "相" if red else "象",
                 "A": "仕" if red else "士", "K": "帅" if red else "将",
                 "C": "炮", "P": "兵" if red else "卒"}

        if red:
            col_from = self.COL_NAMES_RED[c1]
            col_to = self.COL_NAMES_RED[c2]
            if r1 == r2:
                return f"{names[kind]}{col_from}平{col_to}"
            forward = r2 < r1
            if kind in "NBA":
                num = self.NUM_CN[abs(r1 - r2) - 1]
            else:
                num = col_to
            return f"{names[kind]}{col_from}{'进' if forward else '退'}{num}"
        else:
            col_from = self.COL_NAMES_BLACK[c1]
            col_to = self.COL_NAMES_BLACK[c2]
            if r1 == r2:
                return f"{names[kind]}{col_from}平{col_to}"
            forward = r2 > r1
            if kind in "NBA":
                num = self.NUM_CN[abs(r1 - r2) - 1]
            else:
                num = col_to
            return f"{names[kind]}{col_from}{'进' if forward else '退'}{num}"

    @staticmethod
    def coord_to_uci(r1, c1, r2, c2) -> str:
        return f"{chr(97 + c1)}{9 - r1}{chr(97 + c2)}{9 - r2}"

    @staticmethod
    def uci_to_coord(uci: str):
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
        "R": "车", "N": "马", "B": "相", "A": "仕", "K": "帅", "C": "炮", "P": "兵",
        "r": "车", "n": "马", "b": "象", "a": "士", "k": "将", "c": "炮", "p": "卒",
    }

    def __init__(self, root):
        self.root = root
        self.root.title("象棋打谱软件")
        self.root.geometry("1080x820")

        self.tree = GameTree()
        self.tree.root.fen = self.tree.initial_fen
        self.current_node = self.tree.root
        self.board = XiangqiBoard(self.tree.initial_fen)

        self.selected = None
        self.legal_targets = []
        self.last_move = None

        self.autoplay = False
        self.autoplay_interval = tk.DoubleVar(value=1.5)

        self._build_ui()
        self.refresh()

    # ---------- UI ----------
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

        tk.Label(right, text="走法树（点击任意节点跳转 / 分叉）", anchor="w").pack(fill=tk.X, padx=6)
        tree_frame = tk.Frame(right)
        tree_frame.pack(fill=tk.BOTH, expand=True, padx=6, pady=4)
        self.treeview = ttk.Treeview(tree_frame, height=14)
        sb = ttk.Scrollbar(tree_frame, orient="vertical", command=self.treeview.yview)
        self.treeview.configure(yscrollcommand=sb.set)
        self.treeview.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        sb.pack(side=tk.RIGHT, fill=tk.Y)
        self.treeview.bind("<<TreeviewSelect>>", self.on_tree_select)

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

        self.status = tk.Label(self.root, text="就绪", anchor="w", bd=1, relief=tk.SUNKEN)
        self.status.pack(side=tk.BOTTOM, fill=tk.X)

    # ---------- 绘制 ----------
    def board_pos(self, r, c):
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

        self.canvas.create_text(M + 2 * C, M + 4.5 * C, text="楚 河",
                                font=("KaiTi", 20), fill="#8b4513")
        self.canvas.create_text(M + 6 * C, M + 4.5 * C, text="漢 界",
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
                if p is None:
                    continue
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

    # ---------- 交互 ----------
    def on_click(self, event):
        c = round((event.x - self.MARGIN) / self.CELL)
        r = round((event.y - self.MARGIN) / self.CELL)
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
        self.refresh()

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
            messagebox.showinfo("提示", "当前存在多个分叉，请在走法树中点击选择")
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
        if parent is None:
            self.last_move = None
            return
        if self.current_node.move:
            r1, c1, r2, c2 = XiangqiBoard.uci_to_coord(self.current_node.move)
            self.last_move = (r1, c1, r2, c2)
        else:
            self.last_move = None

    # ---------- 树视图 ----------
    def refresh(self):
        self.draw_board()
        self._refresh_tree()
        self._refresh_comment()
        self._refresh_status()

    def _refresh_tree(self):
        self.treeview.delete(*self.treeview.get_children())

        def add_node(parent_item, node):
            label = self._node_label(node)
            item = self.treeview.insert(parent_item, "end", iid=node.id, text=label)
            if node is self.current_node:
                self.treeview.selection_set(item)
                self.treeview.see(item)
            for ch in node.children:
                add_node(item, ch)

        root_label = f"【开局】{self.tree.metadata.title or ''}"
        root_item = self.treeview.insert("", "end", iid=self.tree.root.id,
                                         text=root_label, open=True)
        for ch in self.tree.root.children:
            add_node(root_item, ch)
        if self.current_node is self.tree.root:
            self.treeview.selection_set(root_item)

    def _node_label(self, node):
        if node.is_root():
            return "开局"
        parent = node.parent
        pb = XiangqiBoard(parent.fen)
        r1, c1, r2, c2 = XiangqiBoard.uci_to_coord(node.move)
        text = pb.move_to_chinese(r1, c1, r2, c2)
        if node.comment:
            text += " 💬"
        return text

    def on_tree_select(self, event):
        sel = self.treeview.selection()
        if not sel:
            return
        node = self._find_node_by_id(self.tree.root, sel[0])
        if node and node is not self.current_node:
            self.current_node = node
            self.board = XiangqiBoard(node.fen)
            self._update_last_move()
            self.selected = None
            self.legal_targets = []
            self.draw_board()
            self._refresh_comment()
            self._refresh_status()

    def _find_node_by_id(self, node, node_id):
        if node.id == node_id:
            return node
        for ch in node.children:
            r = self._find_node_by_id(ch, node_id)
            if r:
                return r
        return None

    # ---------- 备注 ----------
    def _refresh_comment(self):
        self.comment_text.delete("1.0", tk.END)
        self.comment_text.insert("1.0", self.current_node.comment)

    def save_comment(self):
        self.current_node.comment = self.comment_text.get("1.0", tk.END).strip()
        self._refresh_tree()
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
            self.status.config(text="⚠ 存在分叉，请在走法树中选择分支后继续")
            self.autoplay = False
            self.autoplay_btn.config(text="▶ 自动播放")
            return

        self.current_node = self.current_node.children[0]
        self.board = XiangqiBoard(self.current_node.fen)
        self._update_last_move()
        self.draw_board()
        self._refresh_tree()
        self._refresh_comment()
        self._refresh_status()

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
        if not fp:
            return
        try:
            self.tree.save(fp)
            self.status.config(text=f"已保存到 {fp}")
        except Exception as e:
            messagebox.showerror("保存失败", str(e))

    def load_game(self):
        fp = filedialog.askopenfilename(
            filetypes=[("象棋棋谱", "*.xq"), ("JSON", "*.json")],
        )
        if not fp:
            return
        try:
            self.tree = GameTree.load(fp)
            self.current_node = self.tree.root
            self.board = XiangqiBoard(self.tree.root.fen or self.tree.initial_fen)
            self.selected = None
            self.legal_targets = []
            self.last_move = None
            self.refresh()
            self.status.config(text=f"已加载 {fp}")
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
        self.current_node = parent
        self.board = XiangqiBoard(parent.fen)
        self._update_last_move()
        self.refresh()

    # ---------- 元信息 / 重置 ----------
    def edit_metadata(self):
        dlg = tk.Toplevel(self.root)
        dlg.title("编辑棋谱信息")
        dlg.transient(self.root)
        dlg.grab_set()

        fields = [("标题", "title"), ("红方", "red_player"), ("黑方", "black_player"),
                  ("赛事", "event"), ("日期", "date"), ("结果", "result")]
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
            self._refresh_tree()
            self.status.config(text="棋谱信息已更新")

        tk.Button(dlg, text="确定", command=on_ok).grid(row=len(fields), column=0, columnspan=2, pady=8)

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
        self.refresh()


# ============================================================
# 入口
# ============================================================

def main():
    root = tk.Tk()
    app = XiangqiUI(root)
    root.mainloop()


if __name__ == "__main__":
    main()