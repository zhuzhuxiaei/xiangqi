[app]

# 应用元信息
title = 象棋打谱
package.name = xiangqi
package.domain = com.example

# 源码目录
source.dir = .
source.include_exts = py,png,jpg,ttf,tc,ttc,otf,wav,json,txt

# 资源文件
source.include_patterns = fonts/*,assets/*

# 版本
version = 1.0

# 依赖（kivymd 仅在需要时启用，目前不需要以减小体积）
requirements = python3,kivy,jnius

# 朝向与全屏
orientation = landscape
fullscreen = 0

# Intent filter（用于双击 .xq 打开）
android.app_intent_filters = intent_filter.xml

# 权限
android.permissions = VIBRATE

# Android 构建设置（API 33 / 最低 21 / 双 ABI）
android.api = 33
android.minapi = 21
android.archs = arm64-v8a, armeabi-v7a
android.accept_bsdlicenses = True

# 桌面调试时使用本地的 Python（仅用于运行 main.py，不影响打包）
# p4a 配置（develop 分支持持 AAB，buildozer 1.6 需要）
p4a.branch = develop

# 图标（可选，放 assets/icon.png）
# android.icon = assets/icon.png

# 不使用源码内 service
services =

[build]
log_level = 2
warn_on_root = 1
