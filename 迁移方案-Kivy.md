# 象棋打谱软件 → Android 迁移方案（Kivy + Buildozer）

> 目标：保留已有引擎/棋谱/音效逻辑，UI 用 Kivy 重写为美观的 Android 应用，最终打包为可安装的 APK。
> 风格关键词：**美观、流畅、跨平台、代码复用**。

---

## 1. 总体策略

| 层级 | 现状 | 迁移策略 | 复用率 |
|---|---|---|---|
| 引擎层 `XiangqiBoard` | 纯 Python，无依赖 | 直接复用，仅做模块拆分 | ~100% |
| 数据层 `GameTree/MoveNode/GameMetadata` | dataclass + JSON | 直接复用 | ~100% |
| 音效层 `SoundBank` | 生成 WAV + winsound 播放 | 合成逻辑保留，播放改用 Kivy `SoundLoader` | ~85% |
| UI 层 `XiangqiUI` (tkinter) | Canvas/Button/Text | **全部重写**为 Kivy Widget | 0% |
| 入口 `main` | tkinter 主循环 | 改为 `XiangqiApp(MDApp)` + Intent 处理 | 重写 |

---

## 2. 技术栈

- **Python 3.9+**
- **Kivy 2.2+**：UI 框架，原生支持 Android 触摸/绘制
- **buildozer**：APK 打包工具链
- **NotoSansCJK / 思源宋体**：内置中文字体（解决 Android 默认无中文字符问题）
- 可选 **KivyMD**：Material Design 组件，提升美观度（按钮/卡片/Toolbar）

---

## 3. 目录结构

```
象棋/
├── xiangqi2.py                 # 原 tkinter 版本（保留作桌面版参考）
└── android/
    ├── main.py                 # Kivy App 入口
    ├── engine/                 # 复用引擎（从 xiangqi2.py 拆出）
    │   ├── __init__.py
    │   ├── board.py            # XiangqiBoard
    │   ├── tree.py             # GameTree / MoveNode / GameMetadata
    │   └── sound.py            # SoundBank（Kivy 适配版）
    ├── ui/
    │   ├── __init__.py
    │   ├── app.py              # XiangqiApp（MDApp 子类）
    │   ├── boardwidget.py      # 棋盘 Widget（绘制 + 触摸）
    │   ├── sidebar.py          # 右侧面板（走法/分支/备注/控制）
    │   ├── branchpanel.py     # 分支选择区
    │   ├── movetext.py         # 走法记录（带跳转）
    │   └── styles.py           # 颜色/字体/尺寸常量
    ├── fonts/
    │   └── NotoSansCJK-Regular.ttc
    ├── assets/
    │   └── sounds/             # 预生成或运行时生成的 WAV
    ├── buildozer.spec          # 打包配置
    └── requirements.txt
```

---

## 4. 模块迁移要点

### 4.1 引擎层（直接复用）

将 `XiangqiBoard`、`XiangqiBoard.uci_to_coord`、`move_to_chinese`、`legal_moves` 等原样搬入 `engine/board.py`。把 `MoveNode`、`GameTree`、`GameMetadata` 搬入 `engine/tree.py`。

### 4.2 音效层（小幅适配）

- 保留 `_synth`（多分音正弦叠加 + 瞬态噪声）的合成逻辑，音色不变。
- `_write_wav` 保留。
- 播放由 `winsound/afplay/aplay` 改为：
  ```python
  from kivy.core.audio import SoundLoader
  snd = SoundLoader.load(path)
  if snd: snd.play()
  ```
- 缓存目录改用 `App.get_running_app().user_data_dir`，避免 Android 沙盒权限问题。

### 4.3 UI 层（重写）

| 原 tkinter | Kivy 对应 |
|---|---|
| `Canvas.create_line/oval/text` | `Widget.canvas`: `Color/Line/Ellipse/Rectangle/Label` |
| `Button` | `Button` 或 KivyMD `MDFlatButton` |
| `Text`（走法记录） | `TextInput readonly=True` 或富文本 `Label markup=True` |
| `filedialog` | `FileChooserDialog` / `MDFileManager` |
| `messagebox` | `Popup` / `MDDialog` |
| `LabelFrame` | `BoxLayout + Label` 标题 + 卡片背景 |
| `<Button-1>` 点击 | `on_touch_down` / `on_touch_up` |
| `tk.DoubleVar` 等 | `kivy.properties.ObjectProperty/NumericProperty` |

---

## 5. UI 设计（美观要求）

### 配色
- 棋盘底：`#f5deb3`（小麦色）
- 主色：`#2b6cb0`（蓝）
- 红子：`#cc0000`，黑子：`#1a1a1a`
- 楚河汉界：`#8b4513`（深棕，书法字体）
- 高亮：`#ffaa00`（上一手）、`#00cc00`（候选/分支）
- 背景：`#f0e8d6` → `#e8d8b8` 渐变

### 视觉细节
- 棋子：圆形 `Ellipse` + 内描边 + 轻微阴影（`Color rgba=(0,0,0,.15)` + 偏移 2px）
- 选中棋子：脉冲动画（`Animation` t=0.4, repeat）
- 分支箭头：`Line` + 三角形箭头（`Mesh` 或三条 Line）+ 序号圆圈
- 卡片：` RoundedRectangle` 圆角 12dp + 阴影
- 按钮：扁平 + ripple 效果（KivyMD `MDFlatButton`）
- 楚河汉界字体：内置书法字体或思源宋体加粗

### 布局
```
┌───────────────┬──────────────────────┐
│               │  Toolbar（标题）     │
│               ├──────────────────────┤
│               │  走法记录（滚动）    │
│   棋盘 Widget │                      │
│  （自适应缩放）├──────────────────────┤
│               │  分支选择卡片         │
│               ├──────────────────────┤
│               │  备注 + 控制按钮网格 │
└───────────────┴──────────────────────┘
```
横屏为主，棋盘占据左侧 ~60%，右侧面板可纵向滚动。

### 动画
- 落子：棋子从起点滑到终点（`Animation` pos, t=0.18, t='out_quint`）
- 选中：绿色框脉冲
- 翻转棋盘：180° 旋转动画（`Animation angle=180`）

---

## 6. 交互

| 手势/快捷 | 行为 |
|---|---|
| 单击己方棋子 | 选中，显示合法落点 |
| 单击合法落点 | 落子 |
| 单击候选分支圆圈 | 走该分支 |
| 双指捏合 | 缩放棋盘（可选） |
| 右滑（手势） | 下一步 |
| 左滑（手势） | 上一步 |
| 长按棋子 | 弹出该步备注编辑 Popup |
| 返回键 | 弹出菜单（保存/打开/翻转/退出） |

---

## 7. 文件关联（双击 .xq 打开）

### 7.1 buildozer.spec 增项
在 `[app]` 段添加：
```
android.app.intent_filters = intent_filter.xml
```
新增 `android/intent_filter.xml`：
```xml
<intent-filter>
  <action android:name="android.intent.action.VIEW"/>
  <category android:name="android.intent.category.DEFAULT"/>
  <data android:scheme="file"/>
  <data android:scheme="content"/>
  <data android:mimeType="*/*"/>
  <data android:pathPattern=".*\\.xq"/>
  <data android:pathPattern=".*\\.json"/>
</intent-filter>
```

### 7.2 启动时读取 Intent
在 `XiangqiApp.on_start` 中通过 `python-for-android` 的 `Intent` 接口（或 `jnius`）读取传入的 URI，复制到 `user_data_dir` 后调用 `load_from_path()`。

---

## 8. 持久化与权限

| 数据 | 位置 | 说明 |
|---|---|---|
| 最近打开列表 | `user_data_dir/recent.json` | 最近 20 个棋谱路径 |
| 自动保存草稿 | `user_data_dir/autosave.xq` | 每走一步自动保存 |
| 音效缓存 | `user_data_dir/sounds/*.wav` | 首次启动生成 |
| 用户棋谱 | SAF 返回的 URI | 通过 Storage Access Framework |

- **权限策略**：优先使用 **Storage Access Framework**，不申请 `READ_EXTERNAL_STORAGE`，符合 Android 11+ 沙盒趋势。
- 仅声明 `android.permission.VIBRATE`（落子震动反馈，可选）。

---

## 9. buildozer.spec 关键项

```ini
[app]
title = 象棋打谱
package.name = xiangqi
package.domain = com.example
source.dir = .
source.include_exts = py,png,jpg,ttf,tc,ttc,wav,json
version = 1.0

requirements = python3,kivy,jnius

orientation = landscape
fullscreen = 0
android.app.intent_filters = intent_filter.xml

# 字体打包
source.include_patterns = fonts/*,assets/*

[build]
log_level = 2
```

---

## 10. 实施步骤

1. 创建 `android/` 目录结构
2. 从 `xiangqi2.py` 拆分引擎到 `engine/board.py`、`engine/tree.py`
3. 适配 `engine/sound.py`（Kivy `SoundLoader`）
4. 编写 `ui/styles.py`（颜色/尺寸常量）
5. 编写 `ui/boardwidget.py`：棋盘绘制 + 触摸 + 动画
6. 编写 `ui/sidebar.py`：右侧面板（走法/分支/备注/控制）
7. 编写 `ui/app.py`：`XiangqiApp` 入口 + Intent 处理 + 快捷手势
8. 打包中文字体到 `fonts/`
9. 编写 `buildozer.spec` 与 `intent_filter.xml`
10. 本地用 `python main.py` 在桌面调试 Kivy 版
11. `buildozer android debug` 打包 APK，真机测试
12. 美化细节迭代（阴影/动画/字体）

---

## 11. 风险与权衡

| 风险 | 影响 | 缓解 |
|---|---|---|
| 中文字体体积大 | APK 增大 ~16MB | 用 `fonttools` 裁剪仅常用 3500 字 |
| Kivy 启动稍慢 | 冷启动 ~2s | 启动画面 splash；预加载引擎 |
| Android 沙盒限制 .xq 访问 | 用户文件难直接读 | 用 SAF 选取文件 |
| 触摸事件区分点击/滑动 | 误触 | 加 8dp 容差 + 250ms 长按判定 |
| 楚河汉界书法字体 | 默认无 | 内置 `KaiTi.ttf` 或思源宋体 |

---

## 12. 验收标准

- [ ] 引擎层在 Android 上行为与桌面一致（合法着法/中文记谱/FEN）
- [ ] 音效（5 种）能正常播放
- [ ] 能打开/保存 .xq 文件
- [ ] 双击 .xq 文件可启动 App 并加载
- [ ] 翻转棋盘、分支选择、备注、自动播放均可用
- [ ] 棋盘动画/阴影/字体符合美观要求
- [ ] APK 在真机 Android 10/12 上可安装运行
