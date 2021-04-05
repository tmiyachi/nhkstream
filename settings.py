import os
import os.path

from dotenv import load_dotenv


dotenv_path = os.path.join(os.path.dirname(__file__), '.env')
load_dotenv(dotenv_path)

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
    #    ['入門ビジネス英語', 'english', 'business1', 7216],
    ['ラジオビジネス英語', 'english', 'business2', 8825],
    ['まいにちスペイン語（入門編）', 'spanish', 'kouza', 9145],
    #    ['まいにちスペイン語（中級編）', 'spanish', 'kouza2', 9145],
    ['まいにちスペイン語（応用編）', 'spanish', 'kouza2', 9145],
    ['まいにちロシア語（入門編）', 'russian', 'kouza', 9147],
    ['まいにちロシア語（応用編）', 'russian', 'kouza2', 9147],
    ['まいにちフランス語（入門編）', 'french', 'kouza', 9113],
    ['まいにちフランス語（応用編）', 'french', 'kouza2', 9113],
    ['まいにちドイツ語（入門編）', 'german', 'kouza', 9109],
    ['まいにちドイツ語（応用編）', 'german', 'kouza2', 9109],
    ['まいにちイタリア語（入門編）', 'italian', 'kouza', 9159],
    ['まいにちイタリア語（応用編）', 'italian', 'kouza2', 9159],
    ['まいにち中国語', 'chinese', 'kouza', 9101],
    #    ['ステップアップ中国語', 'chinese', 'stepup', 9099],
    ['まいにちハングル講座', 'hangeul', 'kouza', 9277],
    ['ステップアップハングル講座', 'hangeul', 'stepup', 9555],
]

# NHK語学講座XMLデータのURLテンプレート
XMLURL = "https://cgi2.nhk.or.jp/gogaku/st/xml/{language}/{kouza}/listdataflv.xml"
# NHK語学講座のストリーミングファイルURLテンプレート
MP4URL = 'https://nhks-vh.akamaihd.net/i/gogaku-stream/mp4/{mp4file}/master.m3u8'
# ファイルのサムネイルにするためのNHKテキストの画像ファイルのURLテンプレート
IMGURL = 'https://nhkbook.s3-ap-northeast-1.amazonaws.com/image/goods/{kouzano:09d}{date}/{kouzano:09d}{date}_01_420.jpg'  # noqa: E501

# 出力ディレクトリ
OUTBASEDIR = os.environ.get('OUTBASEDIR')
# 一時保存用出力ディレクトリ
TMPOUTDIR = os.environ.get('TMPOUTDIR')
# 作業ディレクトリ
TMPBASEDIR = os.environ.get('TMPBASEDIR')

# rtmpdumpとffmpegのコマンド
if os.name == 'nt':
    # Windowsの場合
    ffmpeg = os.path.join(os.path.dirname(__file__), 'ffmpeg')

    if not os.path.isfile(ffmpeg):
        ffmpeg = 'ffmpeg.exe'
else:
    ffmpeg = 'ffmpeg'

# 番組表データベースを使用してmp3ファイルのタグを設定するかどうか
USE_DB_TAG = True
# 番組表データベースファイルパス
DB_FILE = os.environ.get('DB_FILE')
# NHK番組表APIで取得される番組名と講座名の対応表
# 講座名はファイル名に使用するため空白が含まれない形式にする必要があり変換テーブルが必要
PROGRAMLIST = [
    ['ラジオ英会話', 'ラジオ英会話'],
    ['英会話タイムトライアル', '英会話タイムトライアル'],
    ['高校生からはじめる「現代英語」', '高校生からはじめる「現代英語」'],
    #    ['入門ビジネス英語', '入門ビジネス英語'],
    #    ['実践ビジネス英語', '実践ビジネス英語'],
    ['ラジオビジネス英語', 'ラジオビジネス英語'],
    ['まいにちスペイン語 入門編', 'まいにちスペイン語（入門編）'],
    #    ['まいにちスペイン語 中級編', 'まいにちスペイン語（中級編）'],
    ['まいにちスペイン語 応用編', 'まいにちスペイン語（応用編）'],
    ['まいにちロシア語 入門編', 'まいにちロシア語（入門編）'],
    ['まいにちロシア語 応用編', 'まいにちロシア語（応用編）'],
    ['まいにちフランス語 入門編', 'まいにちフランス語（入門編）'],
    ['まいにちフランス語 応用編', 'まいにちフランス語（応用編）'],
    ['まいにちドイツ語 入門編', 'まいにちドイツ語（入門編）'],
    ['まいにちドイツ語 応用編', 'まいにちドイツ語（応用編）'],
    ['まいにちイタリア語 入門編', 'まいにちイタリア語（入門編）'],
    ['まいにちイタリア語 応用編', 'まいにちイタリア語（応用編）'],
    ['まいにち中国語', 'まいにち中国語'],
    ['ステップアップ中国語', 'ステップアップ中国語'],
    ['まいにちハングル講座', 'まいにちハングル講座'],
    ['ステップアップ ハングル講座', 'ステップアップハングル講座'],
]

# NHK番組表API(https://api-portal.nhk.or.jp/ja)で使用するパラメータ
NHK_AREA = 130
NHK_SERVICE = 'r2'
NHK_GENRE = 1007
NHK_APIKEY = os.environ.get('NHK_APIKEY')
NHK_PROGRAM_API = 'https://api.nhk.or.jp/v2/pg/genre/{area}/{service}/{genre}/{date}.json?key={apikey}'

# SetnryのDSNキー
SENTRY_DSN_KEY = os.environ.get('SENTRY_DSN_KEY', None)
