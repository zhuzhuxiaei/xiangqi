#!/usr/bin/env python3
"""
下载 NotoSansCJK 并裁剪到象棋常用字符集，输出到 android/fonts/。
使用清华镜像源加速国内下载。

用法（在 WSL 中）：
  python3 /mnt/c/Users/liulingyi/Desktop/象棋/android/scripts/fetch_and_subset_font.py
"""
import os
import sys
import urllib.request
import urllib.error
import subprocess
import tempfile

ANDROID_DIR = "/mnt/c/Users/liulingyi/Desktop/象棋/android"
FONTS_DIR = os.path.join(ANDROID_DIR, "fonts")
os.makedirs(FONTS_DIR, exist_ok=True)

# 多个备选源：jsDelivr GitHub CDN / GitHub raw / fastgit / 淘宝 NPM
MIRRORS = [
    # jsDelivr CDN 镜像（国内可访问，速度较快）
    "https://cdn.jsdelivr.net/gh/notofonts/noto-cjk@main/Sans/OTF/SimplifiedChinese/NotoSansCJKsc-Regular.otf",
    # fastgit 镜像
    "https://raw.fastgit.org/notofonts/noto-cjk/main/Sans/OTF/SimplifiedChinese/NotoSansCJKsc-Regular.otf",
    # GitHub raw 原始
    "https://github.com/notofonts/noto-cjk/raw/main/Sans/OTF/SimplifiedChinese/NotoSansCJKsc-Regular.otf",
]

KAITI_URL = (
    "https://cdn.jsdelivr.net/gh/googlefonts/SourceHanSerif@2.004R/SubsetOTF/CN/SourceHanSerifCN-Regular.otf"
)

XQ_CHARS = set("车马象相士仕帅将炮兵卒")
APP_UI_CHARS = set(
    "象棋打谱软件未命名棋谱红方黑方赛事日期结果当前局面备注保存打开删除分支"
    "上下一步回到开头翻转自动播放间隔秒编辑信息重置主线音效试听候选走法"
    "提示确认取消加载失败已加载已保存标题关联加载手数轮到分叉数空棋谱点击"
    "任意跳转存在多个请点击右侧选择后继续暂停已播放末尾无法根节点无需当前"
    "下一步只有唯一走法有种种楚河汉界进退平前后中"
    "0123456789一二三四五六七八九十abcdefghij"
    "红黑先手后手胜负和棋杀将绝不允许操作成功错误警告信息"
)


def get_common_chinese():
    chars = set()
    for i in range(0x4E00, 0x4E00 + 3755):
        try:
            chars.add(chr(i))
        except Exception:
            pass
    return chars


def download(url, dest):
    print(f"下载: {url}", flush=True)
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=120) as r, open(dest, "wb") as f:
            total = int(r.headers.get("Content-Length", 0))
            done = 0
            while True:
                buf = r.read(65536)
                if not buf:
                    break
                f.write(buf)
                done += len(buf)
                if total:
                    pct = done * 100 // total
                    sys.stdout.write(f"\r  {pct}% ({done//1024}KB / {total//1024}KB)")
                    sys.stdout.flush()
                else:
                    sys.stdout.write(f"\r  {done//1024}KB")
                    sys.stdout.flush()
            print()
        return True
    except (urllib.error.URLError, Exception) as e:
        print(f"\n  下载失败: {e}", flush=True)
        return False


def subset(src, dest, text):
    with tempfile.NamedTemporaryFile("w", suffix=".txt", delete=False) as tf:
        tf.write(text)
        chars_file = tf.name
    try:
        cmd = [
            sys.executable, "-m", "fontTools.subset",
            src,
            f"--text-file={chars_file}",
            f"--output-file={dest}",
            "--no-hinting",
            "--desubroutinize",
            "--layout-features=''",
            "--recalc-bounds",
        ]
        print(f"裁剪 -> {dest}", flush=True)
        subprocess.run(cmd, check=True)
    finally:
        os.unlink(chars_file)


def main():
    chars = XQ_CHARS | APP_UI_CHARS | get_common_chinese()
    text = "".join(sorted(chars))
    print(f"目标字符集大小: {len(chars)}", flush=True)

    # NotoSansCJK
    noto_dst = os.path.join(FONTS_DIR, "NotoSansCJK-Regular.ttf")
    if os.path.exists(noto_dst) and os.path.getsize(noto_dst) > 1000:
        print(f"NotoSansCJK 已存在: {noto_dst}")
    else:
        downloaded = False
        for url in MIRRORS:
            noto_src = os.path.join(FONTS_DIR, "_src_font")
            if download(url, noto_src):
                downloaded = True
                try:
                    subset(noto_src, noto_dst, text)
                finally:
                    if os.path.exists(noto_src):
                        os.unlink(noto_src)
                break
        if not downloaded:
            print("所有下载源失败。请手动放置 NotoSansCJK-Regular.ttc 到 fonts/", flush=True)
            return 1
    print(f"OK: {noto_dst} ({os.path.getsize(noto_dst)//1024} KB)", flush=True)

    # KaiTi（楚河汉界，可选）
    kai_dst = os.path.join(FONTS_DIR, "KaiTi.ttf")
    if os.path.exists(kai_dst) and os.path.getsize(kai_dst) > 1000:
        print(f"KaiTi 已存在: {kai_dst}")
    else:
        kai_src = os.path.join(FONTS_DIR, "_src_kai")
        if download(KAITI_URL, kai_src):
            try:
                subset(kai_src, kai_dst, "楚河漢界")
            finally:
                if os.path.exists(kai_src):
                    os.unlink(kai_src)
        else:
            print("KaiTi 下载失败（不影响主功能），将用默认字体渲染楚河汉界。", flush=True)
    if os.path.exists(kai_dst):
        print(f"OK: {kai_dst} ({os.path.getsize(kai_dst)//1024} KB)", flush=True)

    return 0


if __name__ == "__main__":
    sys.exit(main())
