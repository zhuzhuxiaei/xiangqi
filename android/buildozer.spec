[app]

# 应用元信息
title = 象棋打谱
package.name = xiangqi
package.domain = com.example

# 源码目录
source.dir = .
source.include_exts = py,png,jpg,ttf,tc,ttc,wav,json

# 资源文件
source.include_patterns = fonts/*,assets/*

# 版本
version = 1.0

# 依赖
requirements = python3,kivy,jnius

# 朝向与全屏
orientation = landscape
fullscreen = 0

# Intent filter（用于双击 .xq 打开）
android.app_intent_filters = intent_filter.xml

# 权限
android.permissions = VIBRATE

# 不使用 pygame sdl2
android.api = 31
android.minapi = 21
android.archs = arm64-v8a, armeabi-v7a

# 图标（可选，放 assets/icon.png）
# android.icon = assets/icon.png

# 不使用源码内 service
services =

[build]
log_level = 2
warn_on_root = 1
