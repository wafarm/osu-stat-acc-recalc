PyInstaller 我怎么调 Pandas 都搞不好，于是用 Python embedded 了

首次使用前需要生成数据文件（从你的 osu! 数据库里把 ranked 图的新 SR 读出来）
把 osu! 安装目录下的 osu!.db 复制到这个文件夹下，双击 osu-helper.exe 即可
应自动生成 osu_info.min.json

如果遇到某张图找不到信息就在 osu! 里把这张图下下来，等星数计算完重复上面的操作就行了

准备完成后，启动请双击 recalc.bat

osu-helper 的源码在 https://github.com/wafarm/osu-helper
