#!/bin/bash
# 第二步：补装 JDK（默认 jre 不含 javac）
# 用法：bash /mnt/c/Users/liulingyi/Desktop/象棋/android/scripts/setup_wsl_step2.sh
set -e

echo "=== 安装 OpenJDK 17 (含 javac) ==="
sudo apt-get install -y --no-install-recommends openjdk-17-jdk

echo "=== 验证 ==="
javac -version

echo "=== 完成，请回到原终端继续 ==="
