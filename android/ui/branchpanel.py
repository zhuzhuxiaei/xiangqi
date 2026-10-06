"""分支选择区：当下一步存在多个分支时，列出候选走法按钮。"""
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.label import Label
from kivy.uix.button import Button
from kivy.uix.scrollview import ScrollView
from kivy.properties import ObjectProperty, ListProperty
from kivy.metrics import dp

from ..engine.board import XiangqiBoard
from .styles import C, S


class BranchPanel(BoxLayout):
    """分支选择区。"""
    on_pick = ObjectProperty(None)  # callback(node)

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.orientation = 'vertical'
        self.size_hint_y = None
        self.spacing = dp(2)
        self.padding = dp(4)
        self.bind(minimum_height=self.setter('height'))

        self.hint = Label(
            text="当前无分支",
            color=C.TEXT_SECONDARY,
            size_hint_y=None,
            height=dp(24),
            font_size=S.SMALL_FONT_SIZE,
            halign='left',
            valign='middle',
        )
        self.hint.bind(size=lambda *a: self.hint.textur
                       if False else None)  # noqa
        self.add_widget(self.hint)

        # 按钮容器（可滚动）
        self.scroll = ScrollView(
            size_hint=(1, None),
            do_scroll_x=False,
            do_scroll_y=True,
            bar_width=dp(4),
        )
        self.scroll.bind(height=self._on_scroll_height)
        self._btn_container = BoxLayout(
            orientation='vertical',
            size_hint_y=None,
            spacing=dp(2),
        )
        self._btn_container.bind(minimum_height=self._btn_container.setter('height'))
        self.scroll.add_widget(self._btn_container)
        self.add_widget(self.scroll)

    def _on_scroll_height(self, *a):
        # 限制最大高度，避免占满面板
        max_h = dp(160)
        self.scroll.height = min(self._btn_container.height, max_h)
        self.height = self.hint.height + self.scroll.height + dp(16)

    def set_branches(self, node):
        """根据当前节点的子节点重建按钮。"""
        self._btn_container.clear_widgets()
        if len(node.children) <= 1:
            self.hint.text = "当前无分支" if not node.children else "下一步只有唯一走法"
            self.hint.color = C.TEXT_SECONDARY
            self.scroll.height = 0
            self.height = self.hint.height + dp(8)
            return

        self.hint.text = f"下一步有 {len(node.children)} 种走法，点击按钮直接走："
        self.hint.color = C.BRANCH_ARROW_DARK

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

            btn = Button(
                text=f"{mark} {move_text}",
                size_hint_y=None,
                height=dp(34),
                color=C.BRANCH_ARROW_DARK,
                background_color=C.SURFACE[:3] + (1,),
                font_size=S.BODY_FONT_SIZE,
            )
            btn.bind(on_release=lambda inst, n=ch: self._pick(n))
            self._btn_container.add_widget(btn)

        # 调整高度
        self._btn_container.height = sum(c.height for c in self._btn_container.children) + \
            (len(self._btn_container.children) - 1) * dp(2)
        self.scroll.height = min(self._btn_container.height, dp(160))
        self.height = self.hint.height + self.scroll.height + dp(16)

    def _pick(self, node):
        if self.on_pick:
            self.on_pick(node)
