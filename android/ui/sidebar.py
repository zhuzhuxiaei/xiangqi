"""右侧面板：标题 + 走法记录 + 分支选择 + 备注 + 控制按钮。"""
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.scrollview import ScrollView
from kivy.uix.label import Label
from kivy.uix.textinput import TextInput
from kivy.uix.button import Button
from kivy.uix.gridlayout import GridLayout
from kivy.uix.popup import Popup
from kivy.properties import ObjectProperty, StringProperty
from kivy.metrics import dp

from .styles import C, S
from .movetext import MoveTextWidget
from .branchpanel import BranchPanel


class SidebarWidget(BoxLayout):
    """右侧整体面板。"""
    def __init__(self, app_callbacks, **kwargs):
        super().__init__(**kwargs)
        self.orientation = 'vertical'
        self.size_hint_x = 0.42
        self.spacing = dp(4)
        self.padding = dp(6)

        cb = app_callbacks  # dict of callbacks

        # 标题
        self.title = Label(
            text="象棋打谱",
            size_hint_y=None,
            height=dp(32),
            color=C.PRIMARY,
            font_size=S.TITLE_FONT_SIZE,
            bold=True,
            halign='left',
            valign='middle',
        )
        self.add_widget(self.title)

        # 走法记录
        self.movetext = MoveTextWidget(size_hint_y=0.35)
        self.add_widget(self.movetext)

        # 分支选择
        self.branch_panel = BranchPanel(size_hint_y=None)
        self.branch_panel.on_pick = cb.get('on_jump')
        self.add_widget(self.branch_panel)

        # 备注
        lbl_comment = Label(
            text="当前局面备注",
            size_hint_y=None,
            height=dp(20),
            color=C.TEXT_SECONDARY,
            font_size=S.SMALL_FONT_SIZE,
            halign='left',
        )
        self.add_widget(lbl_comment)

        self.comment_input = TextInput(
            size_hint_y=None,
            height=dp(80),
            multiline=True,
            font_size=S.BODY_FONT_SIZE,
            background_color=C.SURFACE[:3] + (1,),
        )
        self.add_widget(self.comment_input)

        btn_save_comment = Button(
            text="保存备注",
            size_hint_y=None,
            height=dp(34),
            font_size=S.BODY_FONT_SIZE,
            background_color=C.PRIMARY[:3] + (1,),
            color=C.SURFACE[:3] + (1,),
        )
        btn_save_comment.bind(on_release=cb.get('on_save_comment') or (lambda x: None))
        self.add_widget(btn_save_comment)

        # 控制按钮网格
        grid = GridLayout(
            cols=4,
            size_hint_y=None,
            spacing=dp(4),
            padding=dp(2),
        )
        grid.bind(minimum_height=grid.setter('height'))
        control_buttons = [
            ("◀ 上一步", cb.get('on_back')),
            ("下一步 ▶", cb.get('on_forward')),
            ("⟲ 开头", cb.get('on_start')),
            ("⇅ 翻转", cb.get('on_flip')),
            ("▶ 播放", cb.get('on_autoplay')),
            ("💾 保存", cb.get('on_save')),
            ("📂 打开", cb.get('on_open')),
            ("🗑 删分支", cb.get('on_delete_branch')),
            ("✎ 信息", cb.get('on_edit_meta')),
            ("↺ 重置", cb.get('on_reset')),
            ("★ 主线", cb.get('on_set_mainline')),
            ("🔊 音效", cb.get('on_toggle_sound')),
        ]
        for text, handler in control_buttons:
            b = Button(
                text=text,
                size_hint_y=None,
                height=dp(S.BUTTON_HEIGHT_SM),
                font_size=S.SMALL_FONT_SIZE,
                color=C.TEXT,
                background_color=C.SURFACE_ALT[:3] + (1,),
            )
            if handler:
                b.bind(on_release=handler)
            grid.add_widget(b)
        self.add_widget(grid)

        # 状态栏
        self.status = Label(
            text="就绪",
            size_hint_y=None,
            height=dp(22),
            color=C.TEXT_SECONDARY,
            font_size=S.SMALL_FONT_SIZE,
            halign='left',
            valign='middle',
        )
        self.add_widget(self.status)

    def set_status(self, text):
        self.status.text = text

    def set_title(self, text):
        self.title.text = text
