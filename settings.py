import os
import os.path

# 取得したい講座のパラメータのリストを
#  [kouzaname, language, kouza, kouzano]
# の順で設定する
# パラメータの意味は以下の通り
# kouzaname: ファイル名に使用する講座名
# language, kouza:
#  NHK語学講座XMLデータを取得するためのパラメータ
#  https://cgi2.nhk.or.jp/gogaku/st/xml/{language}/{kouza}/listdataflv.xml
# kouzano:
#  テキストの画像を取得するためのパラメータ
#  https://www.nhk-book.co.jp/detail/00000{kouzano}052020.html
KOUZALIST = [
    ['ラジオ英会話', 'english', 'kaiwa', 9137],
    ['英会話タイムトライアル', 'english', 'timetrial', 9105],
    ['高校生からはじめる「現代英語」', 'english', 'gendai', 9535],
    ['まいにちスペイン語（入門編）', 'spanish', 'kouza', 9145],
    ['まいにちスペイン語（中級編）', 'spanish', 'kouza2', 9145],
    ['まいにちロシア語（入門編）', 'russian', 'kouza', 9147],
    ['まいにちロシア語（応用編）', 'russian', 'kouza2', 9147],
    ['まいにちフランス語（入門編）', 'french', 'kouza', 9113],
    ['まいにちフランス語（応用編）', 'french', 'kouza2', 9113],
    ['まいにちドイツ語（入門編）', 'german', 'kouza', 9109],
    ['まいにちドイツ語（応用編）', 'german', 'kouza2', 9109],
    ['まいにちイタリア語（入門編）', 'italian', 'kouza', 9159],
    ['まいにちイタリア語（応用編）', 'italian', 'kouza2', 9159],
    ['まいにち中国語', 'chinese', 'kouza', 9101],
]

# NHK語学講座XMLデータのURLテンプレート
XMLURL = "https://cgi2.nhk.or.jp/gogaku/st/xml/{language}/{kouza}/listdataflv.xml"
# NHK語学講座のストリーミングファイルURLテンプレート
MP4URL = 'https://nhks-vh.akamaihd.net/i/gogaku-stream/mp4/{mp4file}/master.m3u8'
# ファイルのサムネイルにするためのNHKテキストの画像ファイルのURLテンプレート
IMGURL = 'https://nhkbook.jp-east-2.storage.api.nifcloud.com/image/goods/{kouzano:09d}{date}/{kouzano:09d}{date}_01_420.jpg'

# 出力ディレクトリ
OUTBASEDIR = '/mnt/hdd/raspberrypi/Music/NHK'
# 一時保存用出力ディレクトリ
TMPOUTDIR = '/mnt/hdd/raspberrypi/Music/TMP'
# 作業ディレクトリ
TMPBASEDIR = '/mnt/hdd/raspberrypi/.tmp'

# rtmpdumpとffmpegのコマンド
if os.name == 'nt':
    # Windowsの場合
    ffmpeg = os.path.join(os.path.dirname(__file__), 'ffmpeg')

    if not os.path.isfile(ffmpeg):
        ffmpeg = 'ffmpeg.exe'
else:
    ffmpeg = 'ffmpeg'
