# 通过 GitHub Actions 打包 APK

## 准备

1. 把项目推到 GitHub（如果没有仓库就新建一个）
   ```powershell
   cd "c:\Users\liulingyi\Desktop\象棋"
   git init
   git add .
   git commit -m "init: kivy android project"
   git branch -M main
   git remote add origin https://github.com/<你的用户名>/xiangqi.git
   git push -u origin main
   ```

2. 确认 [.gitignore](file:///c:\Users\liulingyi\Desktop\象棋\android\.gitignore) 已忽略 `.buildozer/` 与 `bin/`（已配置好）

## 触发打包

- **自动触发**：任何对 `android/` 目录的 push 或打 `v*` 标签
- **手动触发**：GitHub 仓库页面 → Actions 标签 → "Android APK Build" → Run workflow

## 下载 APK

1. 进入仓库 → Actions → 最近的运行 → 最下方 "Artifacts" → `xiangqi-debug-apk`
2. 解压下载的 zip，得到 `xiangqi-1.0-debug.apk`
3. 传到手机安装

## 首次打包耗时

GitHub Actions runner 在国外，下载 GitHub/Google 资源快。首次约 30-45 分钟（含 SDK/NDK 下载 + 编译）。后续命中缓存约 10-15 分钟。

## 发布 Release APK（可选）

如需 release 签名版：

1. 本地生成 keystore
   ```powershell
   keytool -genkey -v -keystore xiangqi.keystore -alias xiangqi -keyalg RSA -keysize 2048 -validity 10000
   ```
2. 在 GitHub 仓库 → Settings → Secrets and variables → Actions 添加：
   - `ANDROID_KEYSTORE`：base64 编码的 keystore 内容
     ```powershell
   [Convert]::ToBase64String([IO.File]::ReadAllBytes("xiangqi.keystore"))
   ```
   - `ANDROID_KEYSTORE_PASSWORD`
   - `ANDROID_KEY_ALIAS`
   - `ANDROID_KEY_PASSWORD`
3. 在 [android.yml](file:///c:\Users\liulingyi\Desktop\象棋\.github\workflows\android.yml) 的 build 步骤追加：
   ```yaml
   env:
     ANDROID_KEYSTORE: ${{ secrets.ANDROID_KEYSTORE }}
     ANDROID_KEYSTORE_PASSWORD: ${{ secrets.ANDROID_KEYSTORE_PASSWORD }}
     ANDROID_KEY_ALIAS: ${{ secrets.ANDROID_KEY_ALIAS }}
     ANDROID_KEY_PASSWORD: ${{ secrets.ANDROID_KEY_PASSWORD }}
   ```
   并把 `buildozer android debug` 改为 `buildozer android release`

## 故障排查

- **字体未打包**：确认 [fonts/NotoSansCJK-Regular.ttf](file:///c:\Users\liulingyi\Desktop\象棋\android\fonts) 已生成（本地预下载脚本生成的会被 commit 进仓库）
- **找不到 buildozer.spec**：CI 工作目录是 `android/`，spec 已在该目录
- **p4a 版本不兼容**：已用 `develop` 分支，包含 AAB 支持
- **NDK 版本警告**：p4a develop 要求 r28c，CI 会自动下载
