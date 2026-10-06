"""
Kivy App 入口：XiangqiApp。
职责：
  - 组装 BoardWidget + SidebarWidget
  - 桥接 UI 事件 <-> 引擎/棋谱
  - 文件打开/保存
  - 手势（左滑上一步 / 右滑下一步）
  - Android Intent 读取 .xq 路径
"""
import os
import sys
from kivy.app import App
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.popup import Popup
from kivy.uix.label import Label
from kivy.uix.button import Button
from kivy.uix.filechooser import FileChooserListView
from kivy.core.window import Window
from kivy.clock import Clock
from kivy.metrics import dp

from ..engine.board import XiangqiBoard
from ..engine.tree import GameTree, MoveNode
from ..engine.sound import SoundBank
from .boardwidget import BoardWidget
from .sidebar import SidebarWidget
from .styles import C, S


class XiangqiRoot(BoxLayout):
    """根容器：左棋盘 + 右面板。"""
    def __init__(self, app, **kwargs):
        super().__init__(**kwargs)
        self.app = app
        self.orientation = 'horizontal'

        # 棋盘
        self.board_widget = BoardWidget(size_hint_x=0.58)
        self.board_widget.on_select_cell = app.on_cell_click
        self.board_widget.on_branch_click = app.on_branch_pick
        self.add_widget(self.board_widget)

        # 侧边栏
        self.sidebar = SidebarWidget(app.get_callbacks())
        self.add_widget(self.sidebar)


class XiangqiApp(App):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        # 数据
        self.tree = GameTree()
        self.tree.root.fen = self.tree.initial_fen
        self.current_node = self.tree.root
        self.board = XiangqiBoard(self.tree.initial_fen)

        # UI 状态
        self.selected = None
        self.legal_targets = []
        self.last_move = None
        self.flipped = False

        # 主线选择 + 走法映射
        self.mainline_choice = {}
        self._move_tag_map = {}

        # 自动播放
        self.autoplay = False
        self._autoplay_event = None

        # 音效
        self.sounds = None  # build() 后初始化

        # 启动时通过 Intent / 命令行传入的文件路径
        self._pending_file = None

    # ---------- App 生命周期 ----------
    def build(self):
        from kivy.core.text import LabelBase
        # 注册中文字体（路径相对 main.py）
        fonts_dir = os.path.join(os.path.dirname(__file__), '..', 'fonts')
        noto = os.path.join(fonts_dir, 'NotoSansCJK-Regular.ttc')
        if os.path.exists(noto):
            try:
                LabelBase.register(name=S.FONT_CN, fn_regular=noto)
            except Exception:
                pass
        kai = os.path.join(fonts_dir, 'KaiTi.ttf')
        if os.path.exists(kai):
            try:
                LabelBase.register(name=S.FONT_KAI, fn_regular=kai)
            except Exception:
                pass

        # 音效
        try:
            self.sounds = SoundBank(cache_dir=self.user_data_dir(), enabled=True)
        except Exception:
            self.sounds = None

        self.root_widget = XiangqiRoot(self)

        # 手势：在 root 上挂触摸事件
        self.root_widget.bind(on_touch_down=self._on_root_touch_down)
        self.root_widget.bind(on_touch_up=self._on_root_touch_up)

        # Android Intent 处理：延迟一帧
        Clock.schedule_once(self._load_intent, 0.1)
        # 启动后刷新一次
        Clock.schedule_once(lambda dt: self.refresh(), 0.05)
        return self.root_widget

    def user_data_dir(self):
        # App.user_data_dir 在 build() 之前不可用，这里做兜底
        try:
            return App.user_data_dir(self)
        except Exception:
            return os.path.abspath('.')

    # ---------- 回调聚合 ----------
    def get_callbacks(self):
        return {
            'on_back': lambda inst: self.go_back(),
            'on_forward': lambda inst: self.go_forward(),
            'on_start': lambda inst: self.go_start(),
            'on_flip': lambda inst: self.toggle_flip(),
            'on_autoplay': lambda inst: self.toggle_autoplay(),
            'on_save': lambda inst: self.save_game(),
            'on_open': lambda inst: self.open_file_picker(),
            'on_delete_branch': lambda inst: self.delete_branch(),
            'on_edit_meta': lambda inst: self.edit_metadata(),
            'on_reset': lambda inst: self.reset_game(),
            'on_set_mainline': lambda inst: self.set_mainline(),
            'on_toggle_sound': lambda inst: self.toggle_sound(),
            'on_save_comment': lambda inst: self.save_comment(),
            'on_jump': lambda node: self._jump_to_node(node),
        }

    # ---------- 注入到棋盘 ----------
    def _inject_board_state(self):
        self.board_widget.set_state(
            board=self.board,
            last_move=self.last_move,
            selected=self.selected,
            legal_targets=self.legal_targets,
            branch_moves=self._collect_branches(),
        )
        self.board_widget.flipped = self.flipped
        self.board_widget.draw()

    def _collect_branches(self):
        moves = []
        node = self.current_node
        if len(node.children) <= 1:
            return moves
        for i, ch in enumerate(node.children):
            if not ch.move:
                continue
            try:
                r1, c1, r2, c2 = XiangqiBoard.uci_to_coord(ch.move)
            except Exception:
                continue
            moves.append((i, ch, (r1, c1, r2, c2)))
        return moves

    # ---------- 棋盘交互 ----------
    def on_cell_click(self, r, c):
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
        self.refresh()

    def _filter_targets(self, r, c):
        return [(r2, c2) for (r1, c1, r2, c2) in self.board.legal_moves()
                if r1 == r and c1 == c]

    def on_branch_pick(self, node):
        self._jump_to_node(node)

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
        in_check = self._is_in_check(self.board)
        if in_check and not opponent_moves:
            self.sounds.play("mate")
        elif in_check:
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
            self._toast("当前存在多个分叉，请点击分支按钮选择")
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

    # ---------- 翻转 ----------
    def toggle_flip(self):
        self.flipped = not self.flipped
        self.selected = None
        self.legal_targets = []
        self.refresh()
        self._set_status("棋盘已" + ("翻转" if self.flipped else "恢复"))

    # ---------- 自动播放 ----------
    def toggle_autoplay(self):
        if self.autoplay:
            self.autoplay = False
            if self._autoplay_event:
                self._autoplay_event.cancel()
                self._autoplay_event = None
            self._set_status("已暂停")
        else:
            self.autoplay = True
            self._autoplay_loop()

    def _autoplay_loop(self, *_):
        if not self.autoplay:
            return
        if not self.current_node.children:
            self.autoplay = False
            self._set_status("已播放到末尾")
            return
        if len(self.current_node.children) > 1:
            self.autoplay = False
            self._set_status("存在分叉，请选择分支后继续")
            self.refresh()
            return
        self.current_node = self.current_node.children[0]
        self.board = XiangqiBoard(self.current_node.fen)
        self._update_last_move()
        self.refresh()
        delay = 1.5
        self._autoplay_event = Clock.schedule_once(self._autoplay_loop, delay)

    # ---------- 文件 ----------
    def open_file_picker(self):
        content = BoxLayout(orientation='vertical')
        fc = FileChooserListView(filters=['*.xq', '*.json'], size_hint=(1, 0.9))
        content.add_widget(fc)
        btns = BoxLayout(size_hint=(1, 0.1))
        btn_ok = Button(text="打开")
        btn_cancel = Button(text="取消")
        btns.add_widget(btn_ok)
        btns.add_widget(btn_cancel)
        content.add_widget(btns)
        popup = Popup(title="打开棋谱", content=content, size_hint=(0.9, 0.9))
        btn_cancel.bind(on_release=popup.dismiss)
        btn_ok.bind(on_release=lambda inst: self._on_file_picked(fc, popup))
        popup.open()

    def _on_file_picked(self, fc, popup):
        sel = fc.selection
        popup.dismiss()
        if sel:
            self.load_from_path(sel[0])

    def load_from_path(self, fp):
        try:
            self.tree = GameTree.load(fp)
            self.current_node = self.tree.root
            self.board = XiangqiBoard(self.tree.root.fen or self.tree.initial_fen)
            self.selected = None
            self.legal_targets = []
            self.last_move = None
            self.mainline_choice = {}
            self.refresh()
            self._set_status(f"已加载 {fp}")
            if hasattr(self, 'root_widget'):
                self.root_widget.sidebar.set_title(
                    f"象棋打谱 - {os.path.basename(fp)}")
        except Exception as e:
            self._toast(f"加载失败: {e}")

    def save_game(self):
        self.current_node.comment = self.root_widget.sidebar.comment_input.text.strip()
        from kivy.uix.textinput import TextInput
        content = BoxLayout(orientation='vertical')
        fc = FileChooserListView(dir_select=True, size_hint=(1, 0.9))
        content.add_widget(fc)
        ti = TextInput(text="untitled.xq", size_hint=(1, 0.08))
        content.add_widget(ti)
        btns = BoxLayout(size_hint=(1, 0.08))
        btn_ok = Button(text="保存")
        btn_cancel = Button(text="取消")
        btns.add_widget(btn_ok)
        btns.add_widget(btn_cancel)
        content.add_widget(btns)
        popup = Popup(title="保存棋谱", content=content, size_hint=(0.9, 0.9))
        btn_cancel.bind(on_release=popup.dismiss)
        def _save(inst):
            d = fc.path
            name = ti.text.strip() or "untitled.xq"
            if not name.lower().endswith((".xq", ".json")):
                name += ".xq"
            fp = os.path.join(d, name)
            popup.dismiss()
            try:
                self.tree.save(fp)
                self._set_status(f"已保存到 {fp}")
            except Exception as e:
                self._toast(f"保存失败: {e}")
        btn_ok.bind(on_release=_save)
        popup.open()

    def delete_branch(self):
        if self.current_node.is_root():
            self._toast("无法删除根节点")
            return
        parent = self.current_node.parent
        parent.remove_child(self.current_node)
        self.mainline_choice.pop(self.current_node.id, None)
        self.current_node = parent
        self.board = XiangqiBoard(parent.fen)
        self._update_last_move()
        self.refresh()
        self._set_status("已删除分支")

    def set_mainline(self):
        node = self.current_node
        if node.is_root():
            self._toast("根节点无需设为主线")
            return
        parent = node.parent
        idx = parent.children.index(node)
        if idx == 0:
            self._set_status("当前已是主线")
            return
        self.mainline_choice[parent.id] = idx
        self.refresh()
        self._set_status("已设为主线")

    def edit_metadata(self):
        from kivy.uix.textinput import TextInput
        content = BoxLayout(orientation='vertical', spacing=dp(4))
        fields = {}
        for key, label in [("title", "标题"), ("red_player", "红方"),
                          ("black_player", "黑方"), ("event", "赛事"),
                          ("date", "日期"), ("result", "结果")]:
            row = BoxLayout(size_hint=(1, None), height=dp(40))
            row.add_widget(Label(text=label, size_hint=(0.3, 1)))
            ti = TextInput(text=getattr(self.tree.metadata, key), size_hint=(0.7, 1))
            row.add_widget(ti)
            content.add_widget(row)
            fields[key] = ti
        btns = BoxLayout(size_hint=(1, None), height=dp(40))
        btn_ok = Button(text="确定")
        btn_cancel = Button(text="取消")
        btns.add_widget(btn_ok)
        btns.add_widget(btn_cancel)
        content.add_widget(btns)
        popup = Popup(title="编辑棋谱信息", content=content, size_hint=(0.9, 0.8))
        btn_cancel.bind(on_release=popup.dismiss)
        def _ok(inst):
            for key, ti in fields.items():
                setattr(self.tree.metadata, key, ti.text.strip())
            popup.dismiss()
            self.refresh()
            self._set_status("棋谱信息已更新")
        btn_ok.bind(on_release=_ok)
        popup.open()

    def reset_game(self):
        self.tree = GameTree()
        self.tree.root.fen = self.tree.initial_fen
        self.current_node = self.tree.root
        self.board = XiangqiBoard(self.tree.initial_fen)
        self.selected = None
        self.legal_targets = []
        self.last_move = None
        self.mainline_choice = {}
        self.refresh()
        self._set_status("已重置")

    def toggle_sound(self):
        if self.sounds:
            self.sounds.enabled = not self.sounds.enabled
            self._set_status("音效：" + ("开" if self.sounds.enabled else "关"))

    def save_comment(self):
        self.current_node.comment = \
            self.root_widget.sidebar.comment_input.text.strip()
        self._render_movetext()
        self._set_status("备注已保存")

    def _jump_to_node(self, node):
        if node is self.current_node:
            return
        self.current_node = node
        self.board = XiangqiBoard(node.fen)
        self._update_last_move()
        self.selected = None
        self.legal_targets = []
        self.refresh()

    # ---------- 刷新 ----------
    def refresh(self, *_):
        self._inject_board_state()
        self._render_movetext()
        self._refresh_branches()
        self._refresh_comment()
        self._refresh_status()

    def _render_movetext(self):
        """渲染线性走法记录（主线 + 变着）。"""
        moves_data = []
        path_ids = {n.id for n in self.current_node.get_path_from_root()}

        main = self._main_child(self.tree.root)
        if main is None:
            # 空棋谱
            self.root_widget.sidebar.movetext.set_moves([], self.get_callbacks()['on_jump'])
            return
        turn_no = 1
        node = main
        while node is not None:
            parent = node.parent
            pb = XiangqiBoard(parent.fen)
            r1, c1, r2, c2 = XiangqiBoard.uci_to_coord(node.move)
            move_text = pb.move_to_chinese(r1, c1, r2, c2)
            is_red = (pb.turn == "w")
            moves_data.append({
                'node': node,
                'text': (f"{turn_no}. " if is_red else "") + move_text,
                'is_active': node.id in path_ids,
                'depth': 0,
            })
            main_child = self._main_child(node)
            # 变着
            for ch in node.children:
                if ch is main_child:
                    continue
                pcb = XiangqiBoard(ch.parent.fen)
                cr1, cc1, cr2, cc2 = XiangqiBoard.uci_to_coord(ch.move)
                ctext = pcb.move_to_chinese(cr1, cc1, cr2, cc2)
                moves_data.append({
                    'node': ch,
                    'text': f"({turn_no}... {ctext})",
                    'is_active': ch.id in path_ids,
                    'depth': 1,
                })
            if not is_red:
                turn_no += 1
            node = main_child

        self.root_widget.sidebar.movetext.set_moves(
            moves_data, self.get_callbacks()['on_jump'])

    def _main_child(self, node):
        if not node.children:
            return None
        idx = self.mainline_choice.get(node.id, 0)
        if not (0 <= idx < len(node.children)):
            idx = 0
        return node.children[idx]

    def _refresh_branches(self):
        self.root_widget.sidebar.branch_panel.set_branches(self.current_node)

    def _refresh_comment(self):
        self.root_widget.sidebar.comment_input.text = self.current_node.comment

    def _refresh_status(self):
        path = self.current_node.get_path_from_root()
        turn = "红方" if self.board.turn == "w" else "黑方"
        self._set_status(
            f"手数 {len(path)-1}  轮到 {turn}  分叉 {len(self.current_node.children)}"
        )

    def _set_status(self, text):
        if hasattr(self, 'root_widget'):
            self.root_widget.sidebar.set_status(text)

    def _toast(self, text):
        # 简单 Popup 提示
        content = BoxLayout(orientation='vertical')
        content.add_widget(Label(text=text))
        btn = Button(text="确定", size_hint=(1, 0.3))
        content.add_widget(btn)
        popup = Popup(title="提示", content=content, size_hint=(0.6, 0.4))
        btn.bind(on_release=popup.dismiss)
        popup.open()

    # ---------- 手势 ----------
    def _on_root_touch_down(self, inst, touch):
        touch.ud['start_x'] = touch.x
        touch.ud['start_y'] = touch.y
        touch.ud['start_time'] = Clock.get_time()

    def _on_root_touch_up(self, inst, touch):
        sx = touch.ud.get('start_x', touch.x)
        sy = touch.ud.get('start_y', touch.y)
        dx = touch.x - sx
        dy = touch.y - sy
        if abs(dx) > dp(80) and abs(dx) > abs(dy) * 1.5:
            # 横向滑动
            if dx > 0:
                self.go_back()
            else:
                self.go_forward()

    # ---------- Android Intent ----------
    def _load_intent(self, *_):
        """读取启动时通过 Intent 传入的 .xq 文件 URI。"""
        try:
            from jnius import autoclass
            PythonActivity = autoclass('org.kivy.android.PythonActivity')
            activity = PythonActivity.mActivity
            intent = activity.getIntent()
            if intent:
                data = intent.getData()
                if data:
                    path = data.getPath()
                    if path and os.path.isfile(path):
                        self.load_from_path(path)
        except Exception:
            # 桌面调试：检查 sys.argv
            for a in sys.argv[1:]:
                if os.path.isfile(a) and a.lower().endswith(('.xq', '.json')):
                    self.load_from_path(a)
                    break
