"""
走法记录：富文本显示 + 点击跳转。

复用桌面版的渲染逻辑，但用 Kivy Label markup 代替 Text widget 的 tag 系统。
点击通过 kivy markup 的 <a> ref 或更简单的：把每个走法做成独立 Button。
这里采用更简单的方案：把每个走法渲染成一行行文本，用 markup 区分颜色，
点击时用 position 反查 token。
"""
from kivy.uix.scrollview import ScrollView
from kivy.uix.label import Label
from kivy.uix.boxlayout import BoxLayout
from kivy.properties import ListProperty, ObjectProperty

from ..engine.board import XiangqiBoard
from .styles import C, S


class MoveTextWidget(ScrollView):
    """走法记录容器（可滚动）。内部用 Label markup 显示文本。"""
    moves_data = ListProperty([])  # [(node, chinese_text, is_red, is_active, depth), ...]
    on_jump = ObjectProperty(None)

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.size_hint_y = None
        self.do_scroll_x = False
        self.do_scroll_y = True
        self.bar_width = 6
        # 内部用一个堆叠的 BoxLayout 容纳按钮
        self._container = BoxLayout(orientation='vertical', size_hint_y=None)
        self._container.bind(minimum_height=self._container.setter('height'))
        self.add_widget(self._container)

    def set_moves(self, moves_data, on_jump):
        """
        moves_data: list of dict {
            node: MoveNode,
            text: str,           # 中文走法
            is_red: bool,
            is_active: bool,
            depth: int,          # 0=主线
        }
        """
        self.moves_data = moves_data
        self.on_jump = on_jump
        self._container.clear_widgets()
        for item in moves_data:
            btn = MoveButton(
                text=item['text'],
                node=item['node'],
                is_active=item['is_active'],
                depth=item['depth'],
                on_jump=on_jump,
            )
            self._container.add_widget(btn)

    def scroll_to_active(self):
        # TODO: 滚动到当前 active 项；Kivy 没有 scroll_to_child，需用 measure
        pass


class MoveButton(Label):
    """单个走法行。Label + markup + on_touch_down 跳转。"""
    def __init__(self, text, node, is_active=False, depth=0, on_jump=None, **kwargs):
        super().__init__(**kwargs)
        self.node = node
        self.on_jump = on_jump
        self.size_hint_y = None
        self.height = 24
        self.padding = (8, 4)
        markup_color = (
            f"[color={_rgb(C.MOVE_ACTIVE_FG)}]" if is_active
            else (f"[color={_rgb(C.VARIATION)}]" if depth > 0
                  else f"[color={_rgb(C.MOVE_TEXT)}]")
        )
        end_color = "[/color]"
        bg = (
            f"[b]{text}[/b]"
        )
        self.markup = True
        self.text = f"{markup_color}{bg}{end_color}"
        self.font_size = S.BODY_FONT_SIZE
        # 触摸事件
        self.bind(on_touch_down=self._on_touch)

    def _on_touch(self, inst, touch):
        if inst.collide_point(touch.x, touch.y):
            if self.on_jump:
                self.on_jump(self.node)
            return True
        return False


def _rgb(c):
    """(r,g,b,a) -> 'rrggbb' 字符串供 markup 使用"""
    def to_byte(v):
        return int(round(v * 255))
    return f"{to_byte(c[0]):02x}{to_byte(c[1]):02x}{to_byte(c[2]):02x}"
