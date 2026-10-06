"""
棋盘 Widget：绘制 + 触摸 + 翻转 + 落子动画。

约定坐标：
  r 行号 0 在上 9 在下；c 列号 0 在左 8 在右。
  红方默认在下方（r=9），黑方在上方（r=0）。
  翻转后视觉上做 180° 旋转（行列同时取反）。
"""
from kivy.app import App
from kivy.core.window import Window
from kivy.graphics import Color, Line, Ellipse, Rectangle, PushMatrix, PopMatrix, Translate, Rotate
from kivy.graphics.instructions import InstructionGroup
from kivy.properties import ObjectProperty, NumericProperty, BooleanProperty, ListProperty
from kivy.uix.widget import Widget
from kivy.metrics import dp
from kivy.animation import Animation

from ..engine.board import XiangqiBoard
from .styles import C, S, PIECE_TEXT


class BoardWidget(Widget):
    """棋盘绘制 + 点击交互。

    外部通过 set_state(board, ...) 注入数据；通过注册 callback 接收事件。
    """
    flipped = BooleanProperty(False)

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        # 外部注入
        self.board = XiangqiBoard()
        self.selected = None           # (r, c) or None
        self.legal_targets = []       # [(r2, c2), ...]
        self.last_move = None         # (r1,c1,r2,c2) or None
        self.branch_moves = []        # [(idx, node, (r1,c1,r2,c2)), ...]

        # 事件回调（由 app 设置）
        self.on_select_cell = None     # callback(r, c)
        self.on_move_to = None         # callback(r1,c1,r2,c2)
        self.on_branch_click = None   # callback(node)

        # 动画：落子时移动的棋子
        self._animating_piece = None  # dict {piece, from_xy, to_xy, progress}

        # 绘图缓存
        self._scale = 1.0
        self._ox = 0.0
        self._oy = 0.0
        self.bind(pos=self._update_layout, size=self._update_layout)
        self._update_layout()

    # ---------- 布局 ----------
    def _update_layout(self, *args):
        # 自适应缩放：让 9*CELL 宽 × 10*CELL 高 的逻辑画布居中填满 widget
        if self.width <= 0 or self.height <= 0:
            return
        margin = S.MARGIN
        avail_w = self.width - 2 * margin
        avail_h = self.height - 2 * margin
        scale = min(avail_w / S.BOARD_W, avail_h / S.BOARD_H)
        self._scale = scale
        # 居中
        used_w = S.BOARD_W * scale
        used_h = S.BOARD_H * scale
        self._ox = (self.width - used_w) / 2
        self._oy = (self.height - used_h) / 2
        self.canvas.ask_update()

    def board_pos(self, r, c):
        """逻辑棋盘坐标 -> Widget 屏幕坐标（中心点）。考虑翻转。"""
        if self.flipped:
            c = 8 - c
            r = 9 - r
        x = self._ox + S.MARGIN * self._scale + c * S.CELL * self._scale + S.CELL * self._scale / 2
        y = self._oy + self._height_top_offset() + (9 - r) * S.CELL * self._scale + S.CELL * self._scale / 2
        return x, y

    def _height_top_offset(self):
        # 让 r=9 在下，r=0 在上；屏幕 y 向上为正
        return 0

    def _screen_to_cell(self, x, y):
        """屏幕坐标 -> 实际棋盘 (r, c)，考虑翻转。返回 (r, c) 或 None。"""
        sx = (x - self._ox) / self._scale
        sy = (y - self._oy) / self._scale
        # 减去 margin
        bx = sx - S.MARGIN
        by = sy - S.MARGIN
        if bx < 0 or by < 0:
            return None
        c = int(bx // S.CELL)
        r_from_top = int(by // S.CELL)  # y 向上为正，所以 r=0 对应 by=0~CELL
        if not (0 <= c < 9 and 0 <= r_from_top < 10):
            return None
        # 屏幕 y 向上为正 -> r=0 在上方 -> 直接得到 r
        r = r_from_top
        # 但 Kivy 中 y 是从下往上的，所以这里实际就是 r=9 在下方
        # 翻转反向换算
        if self.flipped:
            c = 8 - c
            r = 9 - r
        return r, c

    # ---------- 注入状态 ----------
    def set_state(self, board, last_move=None, selected=None,
                  legal_targets=None, branch_moves=None):
        self.board = board
        self.last_move = last_move
        self.selected = selected
        self.legal_targets = legal_targets or []
        self.branch_moves = branch_moves or []
        self.canvas.ask_update()

    # ---------- 绘制 ----------
    def draw(self):
        self.canvas.clear()
        if self.width <= 0 or self.height <= 0:
            return
        scale = self._scale
        ox, oy = self._ox, self._oy

        with self.canvas:
            # 背景渐变（用两个矩形近似）
            Color(*C.BOARD_BG)
            Rectangle(pos=self.pos, size=self.size)

            # 棋盘画布范围
            PushMatrix()
            Translate(ox, oy)
            # 用 scale 把后续绘制缩到合适大小
            # 注意：Rectangle 等使用 size，乘 scale
            margin = S.MARGIN * scale

            # 棋盘底色矩形
            Color(*C.BOARD_BG)
            bw = (S.BOARD_W + 2 * S.MARGIN) * scale
            bh = (S.BOARD_H + 2 * S.MARGIN) * scale
            Rectangle(pos=(0, 0), size=(bw, bh))

            # 棋盘线
            Color(*C.BOARD_LINE)
            line_w = max(1, 1.5 * scale)

            for r in range(10):
                y = margin + r * S.CELL * scale
                x1 = margin
                x2 = margin + 8 * S.CELL * scale
                Line(points=[x1, y, x2, y], width=line_w)
            for c in range(9):
                x = margin + c * S.CELL * scale
                if c == 0 or c == 8:
                    Line(points=[x, margin, x, margin + 9 * S.CELL * scale], width=line_w)
                else:
                    Line(points=[x, margin, x, margin + 4 * S.CELL * scale], width=line_w)
                    Line(points=[x, margin + 5 * S.CELL * scale,
                                 x, margin + 9 * S.CELL * scale], width=line_w)
            # 九宫斜线
            for (r1, r2) in [(0, 2), (7, 9)]:
                Line(points=[margin + 3 * S.CELL * scale, margin + r1 * S.CELL * scale,
                             margin + 5 * S.CELL * scale, margin + r2 * S.CELL * scale],
                     width=line_w)
                Line(points=[margin + 5 * S.CELL * scale, margin + r1 * S.CELL * scale,
                             margin + 3 * S.CELL * scale, margin + r2 * S.CELL * scale],
                     width=line_w)

            # 楚河汉界
            Color(*C.RIVER_TEXT)
            river_y = margin + 4.5 * S.CELL * scale
            # Kivy 标签绘制文字需用 Label，这里用 CoreLabel 渲染成纹理
            from kivy.core.text import Label as CoreLabel
            font_size = S.RIVER_FONT_SIZE * scale
            left_text, right_text = ("漢 界", "楚 河") if self.flipped else ("楚 河", "漢 界")
            for txt, cx in [(left_text, margin + 2 * S.CELL * scale),
                            (right_text, margin + 6 * S.CELL * scale)]:
                lbl = CoreLabel(text=txt, font_size=font_size,
                                font_name=S.FONT_KAI if S.FONT_KAI else "Roboto")
                lbl.refresh()
                tex = lbl.texture
                if tex:
                    Rectangle(texture=tex, pos=(cx - tex.width / 2,
                                                river_y - tex.height / 2),
                              size=tex.size)

            # 上一手高亮
            if self.last_move:
                r1, c1, r2, c2 = self.last_move
                Color(*C.LAST_MOVE)
                hl_w = 3 * scale
                for (r, c) in [(r1, c1), (r2, c2)]:
                    x, y = self.board_pos(r, c)
                    # 还原到 Translate 坐标系
                    x -= self._ox
                    y -= self._oy
                    rad = S.CELL * scale / 2 - 2 * scale
                    Line(points=[x - rad, y - rad, x + rad, y - rad,
                                 x + rad, y + rad, x - rad, y + rad,
                                 x - rad, y - rad],
                         width=hl_w, close=True)

            # 棋子
            for r in range(10):
                for c in range(9):
                    p = self.board.grid[r][c]
                    if p is None:
                        continue
                    self._draw_piece(r, c, p, scale)

            # 选中框 + 合法落点
            if self.selected:
                r, c = self.selected
                Color(*C.SELECT)
                x, y = self.board_pos(r, c)
                x -= self._ox
                y -= self._oy
                rad = S.CELL * scale / 2 - 1 * scale
                Line(points=[x - rad, y - rad, x + rad, y - rad,
                             x + rad, y + rad, x - rad, y + rad,
                             x - rad, y - rad],
                     width=3 * scale, close=True)
                Color(*C.LEGAL_DOT)
                dot_r = 6 * scale
                for (tr, tc) in self.legal_targets:
                    x2, y2 = self.board_pos(tr, tc)
                    x2 -= self._ox
                    y2 -= self._oy
                    Ellipse(pos=(x2 - dot_r, y2 - dot_r), size=(dot_r * 2, dot_r * 2))

            # 分支箭头 + 序号圆圈
            if self.branch_moves:
                self._draw_branch_arrows(scale)

            PopMatrix()

    def _draw_piece(self, r, c, p, scale):
        x, y = self.board_pos(r, c)
        x -= self._ox
        y -= self._oy
        rad = S.CELL * scale / 2 - S.PIECE_RADIUS_OFFSET * scale
        red = p.isupper()
        # 阴影
        Color(*C.PIECE_SHADOW)
        Ellipse(pos=(x - rad + 2 * scale, y - rad - 2 * scale),
                size=(rad * 2, rad * 2))
        # 棋子底
        Color(*C.PIECE_BG)
        Ellipse(pos=(x - rad, y - rad), size=(rad * 2, rad * 2))
        # 描边
        outline = C.PIECE_OUTLINE_RED if red else C.PIECE_OUTLINE_BLACK
        Color(*outline)
        Line(ellipse=(x - rad, y - rad, rad * 2, rad * 2),
             width=2 * scale)
        # 文字
        text_color = C.RED_PIECE if red else C.BLACK_PIECE
        Color(*text_color)
        from kivy.core.text import Label as CoreLabel
        lbl = CoreLabel(text=PIECE_TEXT[p],
                        font_size=S.PIECE_FONT_SIZE * scale,
                        font_name=S.FONT_CN if S.FONT_CN else "Roboto",
                        bold=True)
        lbl.refresh()
        tex = lbl.texture
        if tex:
            Rectangle(texture=tex,
                      pos=(x - tex.width / 2, y - tex.height / 2),
                      size=tex.size)

    def _draw_branch_arrows(self, scale):
        for idx, node, (r1, c1, r2, c2) in self.branch_moves:
            x1, y1 = self.board_pos(r1, c1)
            x2, y2 = self.board_pos(r2, c2)
            x1 -= self._ox; y1 -= self._oy
            x2 -= self._ox; y2 -= self._oy
            Color(*C.BRANCH_ARROW)
            Line(points=[x1, y1, x2, y2], width=3 * scale)
            # 箭头头部（三角）
            import math
            ang = math.atan2(y2 - y1, x2 - x1)
            head = 10 * scale
            p1 = (x2 - head * math.cos(ang - 0.4),
                  y2 - head * math.sin(ang - 0.4))
            p2 = (x2 - head * math.cos(ang + 0.4),
                  y2 - head * math.sin(ang + 0.4))
            Line(points=[p1[0], p1[1], x2, y2, p2[0], p2[1], p1[0], p1[1]],
                 width=3 * scale, close=True)

            # 序号圆圈
            mx, my = (x1 + x2) / 2, (y1 + y2) / 2
            off_x = -14 * scale if x2 >= x1 else 14 * scale
            off_y = -14 * scale if y2 >= y1 else 14 * scale
            cx, cy = mx + off_x, my + off_y
            r = 11 * scale
            Color(*C.BRANCH_CIRCLE)
            Ellipse(pos=(cx - r, cy - r), size=(r * 2, r * 2))
            Color(*C.BRANCH_ARROW_DARK)
            Line(ellipse=(cx - r, cy - r, r * 2, r * 2), width=2 * scale)
            Color(1, 1, 1, 1)
            from kivy.core.text import Label as CoreLabel
            lbl = CoreLabel(text=str(idx + 1),
                            font_size=S.BRANCH_NUM_FONT_SIZE * scale,
                            font_name=S.FONT_CN if S.FONT_CN else "Roboto",
                            bold=True)
            lbl.refresh()
            tex = lbl.texture
            if tex:
                Rectangle(texture=tex,
                          pos=(cx - tex.width / 2, cy - tex.height / 2),
                          size=tex.size)

    # ---------- 触摸 ----------
    def on_touch_down(self, touch):
        if not self.collide_point(touch.x, touch.y):
            return False

        # 优先：分支圆圈命中
        if self.branch_moves:
            scale = self._scale
            for idx, node, (r1, c1, r2, c2) in self.branch_moves:
                x1, y1 = self.board_pos(r1, c1)
                x2, y2 = self.board_pos(r2, c2)
                mx, my = (x1 + x2) / 2, (y1 + y2) / 2
                off_x = -14 * scale if x2 >= x1 else 14 * scale
                off_y = -14 * scale if y2 >= y1 else 14 * scale
                cx, cy = mx + off_x, my + off_y
                rr = 13 * scale
                if (touch.x - cx) ** 2 + (touch.y - cy) ** 2 <= rr * rr:
                    if self.on_branch_click:
                        self.on_branch_click(node)
                    return True

        cell = self._screen_to_cell(touch.x, touch.y)
        if cell is None:
            return False
        if self.on_select_cell:
            self.on_select_cell(cell[0], cell[1])
        return True
