本目录用于存放中文字体文件，必须放置以下文件后才能正常显示中文：

  NotoSansCJK-Regular.ttc   # 棋子文字、按钮、走法记录
  KaiTi.ttf                  # 楚河汉界书法字体

下载地址：
  https://github.com/notofonts/noto-cjk

字体体积较大（~16MB），不会提交到代码仓库；
打包时通过 buildozer.spec 的 source.include_patterns = fonts/* 自动打包。

如需缩小 APK，可使用 fonttools subset 裁剪仅常用字符：
  pyftsubset NotoSansCJK-Regular.ttc \
      --text-file=chars.txt \
      --output-file=NotoSansCJK-subset.ttf
