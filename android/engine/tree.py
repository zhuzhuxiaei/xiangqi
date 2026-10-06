"""
象棋引擎 - 棋谱树数据模型。
从 xiangqi2.py 原样搬迁，纯 Python 无依赖。
"""
import json
import uuid
from dataclasses import dataclass, field, asdict
from typing import List, Optional, Dict, Any


@dataclass
class MoveNode:
    id: str = field(default_factory=lambda: str(uuid.uuid4())[:8])
    move: Optional[str] = None
    fen: str = ""
    comment: str = ""
    children: List["MoveNode"] = field(default_factory=list)
    parent: Optional["MoveNode"] = field(default=None, repr=False, compare=False)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id, "move": self.move, "fen": self.fen,
            "comment": self.comment,
            "children": [c.to_dict() for c in self.children],
        }

    @classmethod
    def from_dict(cls, data, parent=None):
        node = cls(
            id=data.get("id") or str(uuid.uuid4())[:8],
            move=data.get("move"),
            fen=data.get("fen", ""),
            comment=data.get("comment", ""),
        )
        node.parent = parent
        node.children = [cls.from_dict(c, node) for c in data.get("children", [])]
        return node

    def is_root(self):
        return self.parent is None

    def add_child(self, child):
        child.parent = self
        self.children.append(child)
        return child

    def remove_child(self, child):
        if child in self.children:
            self.children.remove(child)
            child.parent = None

    def get_path_from_root(self):
        path = []
        node = self
        while node is not None:
            path.append(node)
            node = node.parent
        return list(reversed(path))


@dataclass
class GameMetadata:
    title: str = "未命名棋谱"
    red_player: str = ""
    black_player: str = ""
    event: str = ""
    date: str = ""
    result: str = ""


@dataclass
class GameTree:
    metadata: GameMetadata = field(default_factory=GameMetadata)
    root: MoveNode = field(default_factory=MoveNode)
    initial_fen: str = "rnbakabnr/9/1c5c1/p1p1p1p1p/9/9/P1P1P1P1P/1C5C1/9/RNBAKABNR w - - 0 1"

    def to_dict(self):
        return {
            "version": "1.0",
            "metadata": asdict(self.metadata),
            "initial_fen": self.initial_fen,
            "root": self.root.to_dict(),
        }

    @classmethod
    def from_dict(cls, data):
        tree = cls()
        tree.metadata = GameMetadata(**data.get("metadata", {}))
        tree.initial_fen = data.get("initial_fen", tree.initial_fen)
        tree.root = MoveNode.from_dict(data["root"], parent=None)
        if not tree.root.fen:
            tree.root.fen = tree.initial_fen
        return tree

    def save(self, filepath):
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(self.to_dict(), f, ensure_ascii=False, indent=2)

    @classmethod
    def load(cls, filepath):
        with open(filepath, "r", encoding="utf-8") as f:
            return cls.from_dict(json.load(f))
