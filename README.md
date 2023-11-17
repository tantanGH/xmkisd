# xmkisd

Cross Build System for ISPR-3.0/4.0

# INSTALL

1. Install ffmpeg

* [https://www.ffmpeg.org/](https://www.ffmpeg.org/)

2. Install git

* [https://gitforwindows.org/](https://gitforwindows.org/)

3. Install Python

* [https://www.python.org/](https://www.python.org/)

    pip install git+https://github.com/tantanGH/xmkisd.git

or

    py -m pip install git+https://github.com/tantanGH/xmkisd.git

# USAGE

例：MP4から200x156/30FPS/32.0kHz のISD(ISPR-4.0)を生成する。輝度ビットを使い65536色とする。PCMの音量を0.8倍とする。

    xmkisd -vw 200 -vh 156 -fps 30 -ib -pv 0.8 -pf 32000 hogehoge.mp4 hogehoge.isd

* 横方向は128以上256以下で8の倍数でなくてはならない
* 縦方向は240以下でなくてはならない