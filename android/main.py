"""
象棋打谱软件 - Android / Kivy 版入口。

运行：
  桌面调试：python main.py
  打包 APK：buildozer android debug
"""
import os
import sys

# 让相对导入 (from ..engine import ...) 在直接运行 main.py 时也能工作
_HERE = os.path.dirname(os.path.abspath(__file__))
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)

from ui.app import XiangqiApp


def main():
    app = XiangqiApp()
    app.run()


if __name__ == "__main__":
    main()
