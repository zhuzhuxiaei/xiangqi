"""
象棋引擎 - 棋盘与规则。
从 xiangqi2.py 原样搬迁，纯 Python 无依赖。
"""
from typing import List, Optional


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
