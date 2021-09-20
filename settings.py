import logging
import os.path
from logging import StreamHandler
from pathlib import Path
from typing import List, Optional, Tuple

from dotenv import load_dotenv

dotenv_path = os.path.join(os.path.dirname(__file__), ".env")
load_dotenv(dotenv_path)

BASEDIR = Path(__file__).parent

# 取得したい講座のパラメータのリストを
#  [kouzaname, site_id, kouzano]
# の順で設定する
# パラメータの意味は以下の通り
# kouzaname: ファイル名に使用する講座名
# site_id:
#  NHKらじるらじるJSONデータを取得するためのパラメータ
#  https://www.nhk.or.jp/radioondemand/json/{site_id}/bangumi_{site_id}_01.json
# kouzano:
#  テキストの画像を取得するためのパラメータ
#  https://www.nhk-book.co.jp/detail/00000{kouzano}052020.html
KOUZALIST: List[Tuple[str, str, int]] = [
    ("ラジオ英会話", "0916", 9137),
    ("英会話タイムトライアル", "2331", 9105),
    ("高校生からはじめる「現代英語」", "4407", 9535),
    ("ラジオビジネス英語", "6809", 8825),
    ("まいにちスペイン語（入門編）", "0948", 9145),
    ("まいにちスペイン語（応用編）", "4413", 9145),
    ("まいにちロシア語（入門編）", "0956", 9147),
    ("まいにちロシア語（応用編）", "4414", 9147),
    ("まいにちフランス語（入門編）", "0953", 9113),
    ("まいにちフランス語（応用編）", "4412", 9113),
    ("まいにちドイツ語（入門編）", "0943", 9109),
    ("まいにちドイツ語（応用編）", "4410", 9109),
    ("まいにちイタリア語（入門編）", "0946", 9159),
    ("まいにちイタリア語（応用編）", "4411", 9159),
    ("まいにち中国語", "0915", 9101),
    #    ('ステップアップ中国語', '6581', 9099),
    ("まいにちハングル講座", "0951", 9277),
    ("ステップアップハングル講座", "6810", 9555),
]

# らじるらじる聞き逃しjsonのURLテンプレート
JSONURL: str = "https://www.nhk.or.jp/radioondemand/json/{site_id}/bangumi_{site_id}_01.json"  # noqa: E501
# ファイルのサムネイルにするためのNHKテキストの画像ファイルのURLテンプレート
IMGURL: str = "https://nhkbook.s3-ap-northeast-1.amazonaws.com/image/goods/{kouzano:09d}{date}/{kouzano:09d}{date}_01_420.jpg"  # noqa: E501

# 出力ディレクトリ
OUTBASEDIR: Path = Path(os.environ.get("OUTBASEDIR", default=BASEDIR / "Music" / "NHK"))
# 一時保存用出力ディレクトリ
TMPOUTDIR: Path = Path(os.environ.get("TMPOUTDIR", default=BASEDIR / "Music" / "TMP"))
# 作業ディレクトリ
TMPBASEDIR: Path = Path(os.environ.get("TMPBASEDIR", default=BASEDIR / "tmp"))

# rtmpdumpとffmpegのコマンド
if os.name == "nt":
    # Windowsの場合
    ffmpeg = os.path.join(BASEDIR, "ffmpeg")

    if not os.path.isfile(ffmpeg):
        ffmpeg = "ffmpeg.exe"
else:
    ffmpeg = "ffmpeg"

# 番組表データベースを使用してmp3ファイルのタグを設定するかどうか
USE_DB_TAG: bool = True
# 番組表データベースファイルパス
DB_FILE: Path = Path(os.environ.get("DB_FILE", default=BASEDIR / "program.db"))
# NHK番組表APIで取得される番組名と講座名の対応表
# 講座名はファイル名に使用するため空白が含まれない形式にする必要があり変換テーブルが必要
PROGRAMLIST: List[Tuple[str, str]] = [
    ("ラジオ英会話", "ラジオ英会話"),
    ("英会話タイムトライアル", "英会話タイムトライアル"),
    ("高校生からはじめる「現代英語」", "高校生からはじめる「現代英語」"),
    #    ('入門ビジネス英語', '入門ビジネス英語'),
    #    ('実践ビジネス英語', '実践ビジネス英語'),
    ("ラジオビジネス英語", "ラジオビジネス英語"),
    ("まいにちスペイン語 入門編", "まいにちスペイン語（入門編）"),
    #    ('まいにちスペイン語 中級編', 'まいにちスペイン語（中級編）'),
    ("まいにちスペイン語 応用編", "まいにちスペイン語（応用編）"),
    ("まいにちロシア語 入門編", "まいにちロシア語（入門編）"),
    ("まいにちロシア語 応用編", "まいにちロシア語（応用編）"),
    ("まいにちフランス語 入門編", "まいにちフランス語（入門編）"),
    ("まいにちフランス語 応用編", "まいにちフランス語（応用編）"),
    ("まいにちドイツ語 入門編", "まいにちドイツ語（入門編）"),
    ("まいにちドイツ語 応用編", "まいにちドイツ語（応用編）"),
    ("まいにちイタリア語 入門編", "まいにちイタリア語（入門編）"),
    ("まいにちイタリア語 応用編", "まいにちイタリア語（応用編）"),
    ("まいにち中国語", "まいにち中国語"),
    ("ステップアップ中国語", "ステップアップ中国語"),
    ("まいにちハングル講座", "まいにちハングル講座"),
    ("ステップアップ ハングル講座", "ステップアップハングル講座"),
]

# NHK番組表API(https://api-portal.nhk.or.jp/ja)で使用するパラメータ
NHK_AREA: int = 130
NHK_SERVICE: str = "r2"
NHK_GENRE: int = 1007
NHK_APIKEY: str = os.environ.get("NHK_APIKEY", default="")
NHK_PROGRAM_API: str = "https://api.nhk.or.jp/v2/pg/genre/{area}/{service}/{genre}/{date}.json?key={apikey}"

# SetnryのDSNキー
SENTRY_DSN_KEY: Optional[str] = os.environ.get("SENTRY_DSN_KEY", None)

# ロガー
stream_handler = StreamHandler()
stream_handler.setLevel(logging.INFO)
logging.basicConfig(level=logging.NOTSET, handlers=[stream_handler])
