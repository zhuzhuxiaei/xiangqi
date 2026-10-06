"""UI 样式常量：颜色、字体、尺寸。集中管理便于整体调色与适配。"""


class C:
    """配色表。命名约定：背景前景分离，红黑棋子色固定。"""
    # 棋盘
    BOARD_BG = (0.96, 0.87, 0.70, 1)        # #f5deb3 小麦色
    BOARD_BG_TOP = (0.97, 0.91, 0.77, 1)   # 渐变上端
    BOARD_BG_BOTTOM = (0.91, 0.85, 0.72, 1)  # 渐变下端
    BOARD_LINE = (0.30, 0.20, 0.10, 1)     # 棋盘线深棕
    RIVER_TEXT = (0.55, 0.27, 0.07, 1)     # 楚河汉界深棕

    # 棋子
    PIECE_BG = (1.0, 0.98, 0.84, 1)        # 棋子底色奶白
    PIECE_SHADOW = (0, 0, 0, 0.18)         # 棋子阴影
    RED_PIECE = (0.80, 0.0, 0.0, 1)        # 红子
    BLACK_PIECE = (0.10, 0.10, 0.10, 1)    # 黑子
    PIECE_OUTLINE_RED = (0.80, 0.0, 0.0, 1)
    PIECE_OUTLINE_BLACK = (0.10, 0.10, 0.10, 1)

    # 高亮
    LAST_MOVE = (1.0, 0.67, 0.0, 1)        # 上一手 #ffaa00
    SELECT = (0.0, 0.80, 0.0, 1)           # 选中框 #00cc00
    LEGAL_DOT = (0.0, 0.80, 0.0, 1)
    BRANCH_ARROW = (0.0, 0.67, 0.0, 1)     # 分支箭头 #00aa00
    BRANCH_ARROW_DARK = (0.0, 0.40, 0.0, 1)
    BRANCH_CIRCLE = (0.0, 0.80, 0.0, 1)

    # 主题
    PRIMARY = (0.17, 0.42, 0.69, 1)        # #2b6cb0
    PRIMARY_DARK = (0.12, 0.30, 0.50, 1)
    ACCENT = (0.92, 0.69, 0.0, 1)
    BG = (0.94, 0.91, 0.86, 1)             # 应用背景
    SURFACE = (1, 1, 1, 1)
    SURFACE_ALT = (0.98, 0.96, 0.92, 1)
    TEXT = (0.10, 0.10, 0.10, 1)
    TEXT_SECONDARY = (0.40, 0.40, 0.40, 1)
    DIVIDER = (0.80, 0.75, 0.65, 1)

    # 走法记录
    MOVE_TEXT = (0.10, 0.23, 0.55, 1)      # #1a3b8c
    MOVE_ACTIVE_BG = (0.17, 0.42, 0.69, 1)
    MOVE_ACTIVE_FG = (1, 1, 1, 1)
    VARIATION = (0.48, 0.36, 0.0, 1)       # #7a5c00
    COMMENT = (0.40, 0.40, 0.40, 1)
    NUMBER = (0.20, 0.20, 0.20, 1)


class S:
    """尺寸常量（dp / sp）。"""
    # 棋盘
    CELL = 60           # 单元格边长（按 widget 自适应缩放）
    MARGIN = 40         # 棋盘边距
    BOARD_W = 9 * CELL
    BOARD_H = 10 * CELL
    PIECE_RADIUS_OFFSET = 4   # 棋子半径相对 CELL/2 的缩进

    # 棋子字体
    PIECE_FONT_SIZE = 22
    RIVER_FONT_SIZE = 20
    BRANCH_NUM_FONT_SIZE = 10

    # UI
    TITLE_FONT_SIZE = 18
    BODY_FONT_SIZE = 14
    SMALL_FONT_SIZE = 11
    CARD_RADIUS = 12
    PADDING = 8
    PADDING_SM = 4
    BUTTON_HEIGHT = 44
    BUTTON_HEIGHT_SM = 36

    # 字体名（空字符串=系统默认；Kivy 中字体通过 LabelBase 注册）
    FONT_CN = "NotoSansCJK"   # 在 main.py 中注册到 fonts/NotoSansCJK-Regular.ttc
    FONT_KAI = "KaiTi"        # 书法字体（楚河汉界）


PIECE_TEXT = {
    "R": "车", "N": "马", "B": "相", "A": "仕", "K": "帅", "C": "炮", "P": "兵",
    "r": "车", "n": "马", "b": "象", "a": "士", "k": "将", "c": "炮", "p": "卒",
}
