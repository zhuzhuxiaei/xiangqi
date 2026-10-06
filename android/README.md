# 象棋打谱软件 - Android 版（Kivy + Buildozer）

## 目录结构

```
android/
├── main.py                 # 入口：python main.py
├── engine/                 # 引擎层（从 xiangqi2.py 拆分复用）
│   ├── __init__.py
│   ├── board.py            # XiangqiBoard
│   ├── tree.py             # GameTree / MoveNode
│   └── sound.py            # SoundBank（Kivy SoundLoader）
├── ui/
│   ├── __init__.py
│   ├── app.py              # XiangqiApp 入口
│   ├── boardwidget.py      # 棋盘绘制 + 触摸
│   ├── sidebar.py          # 右侧面板
│   ├── branchpanel.py      # 分支选择区
│   ├── movetext.py         # 走法记录
│   └── styles.py           # 配色/尺寸常量
├── fonts/                  # 字体目录（需放入 NotoSansCJK 等）
├── buildozer.spec          # 打包配置
├── intent_filter.xml       # 双击 .xq 文件打开
├── requirements.txt
└── README.md
```

## 桌面调试

```powers
cd android
pip install kivy
python main.py
```

字体可选：未放入时使用 Kivy 默认字体，中文会显示为方框；
打包前请按 `fonts/README.txt` 放入 `NotoSansCJK-Regular.ttc` 与 `KaiTi.ttf`。

## 打包 APK

```powers
pip install buildozer cython
cd android
buildozer android debug
```
生成的 APK 在 `bin/` 目录下。

## 双击 .xq 打开

打包时通过 `intent_filter.xml` 注册 `.xq` MIME 类型，
启动后由 `ui/app.py` 的 `_load_intent()` 读取 Intent URI 调用 `load_from_path()`。

## 已实现功能

- 棋盘绘制（线条/九宫/楚河汉界/棋子/阴影/描边）
- 落子、选中、合法落点提示、上一手高亮
- 翻转棋盘（视觉 180° 旋转）
- 走法记录（中文记谱，点击跳转）
- 分支选择（多分支时按钮直接走）
- 备注、自动播放
- 5 种音效（走子/吃子/将军/非法/绝杀）
- 保存/打开 .xq 文件
- 删分支、设主线、编辑棋谱信息、重置
- 横向滑动手势（右滑上一步 / 左滑下一步）

## 与桌面版差异

| 项 | 桌面 (xiangqi2.py) | Android (android/) |
|---|---|---|
| UI 框架 | tkinter | Kivy |
| 绘制 | Canvas widget | graphics instructions |
| 文件选择 | filedialog | FileChooserListView |
| 弹窗 | messagebox | Popup |
| 文件关联 | Windows 注册表 | Android Intent filter |
| 触摸 | 鼠标点击 | 触摸 + 手势 |
| 音效播放 | winsound/afplay | Kivy SoundLoader |
| 引擎/棋谱/音效合成 | 单文件 | 拆分模块，逻辑一致 |
