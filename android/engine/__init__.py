"""引擎层：从 xiangqi2.py 拆分而来，纯 Python 无依赖。"""
from .board import XiangqiBoard, is_red
from .tree import GameTree, MoveNode, GameMetadata
from .sound import SoundBank

__all__ = [
    "XiangqiBoard", "is_red",
    "GameTree", "MoveNode", "GameMetadata",
    "SoundBank",
]
