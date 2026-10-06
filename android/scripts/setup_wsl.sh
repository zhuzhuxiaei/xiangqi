#!/bin/bash
# WSL2 Ubuntu 一次性准备脚本：为 buildozer 打包 APK 安装依赖
# 用法（在 WSL 终端中执行）：
#   bash /mnt/c/Users/liulingyi/Desktop/象棋/android/scripts/setup_wsl.sh
set -e

echo "=== [1/4] apt 系统依赖 ==="
sudo apt-get update
sudo apt-get install -y --no-install-recommends \
    autoconf automake libtool pkg-config \
    zlib1g-dev libffi-dev libssl-dev \
    libltdl-dev libncurses-dev \
    unzip zip ccache git wget ca-certificates \
    build-essential

echo "=== [2/4] Python 包 ==="
python3 -m pip install --upgrade pip
python3 -m pip install --user \
    buildozer cython==0.29.36 virtualenv

echo "=== [3/4] 检查 buildozer ==="
~/.local/bin/buildozer version || buildozer version

echo "=== [4/4] 完成 ==="
echo "依赖安装完成。请回到原终端，让我继续下载字体并打包。"
