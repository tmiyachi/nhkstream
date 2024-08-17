from __future__ import annotations

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
#  [kouzaname, site_id, booknum]
# の順で設定する
# パラメータの意味は以下の通り
# kouzaname: ファイル名に使用する講座名
# site_id:
#  NHKらじるらじるJSONデータを取得するためのパラメータ
#  https://www.nhk.or.jp/radioondemand/json/{site_id}/bangumi_{site_id}_01.json
# booknum:
#  テキストの画像を取得するための番号のフォーマット文字列
#  month:放送月,year:放送年,annual:放送年度
#  weekday: 放送日
KOUZALIST: List[Tuple[str, str, str, list[int]]] = [
    ("ラジオ英会話", "PMMJ59J6N2", "000009137{month:02d}{year:04d}", [1, 2, 3, 4, 5]),
    ("英会話タイムトライアル", "8Z6XJ6J415", "000009105{month:02d}{year:04d}", [1, 2, 3, 4, 5]),
    ("ニュースで学ぶ「現代英語」", "77RQWQX1L6", None, [1, 2, 3, 4, 5]),
    ("ラジオビジネス英語", "368315KKP8", "000008825{month:02d}{year:04d}", [1, 2, 3, 4, 5]),
    ("まいにちスペイン語（初級編）", "NRZWXVGQ19", "000009145{month:02d}{year:04d}", [1, 2, 3]),
    ("まいにちスペイン語（応用編）", "NRZWXVGQ19", "000009145{month:02d}{year:04d}", [4, 5]),
    ("まいにちロシア語（初級編）", "YRLK72JZ7Q", "000009147{month:02d}{year:04d}", [1, 2, 3]),
    ("まいにちロシア語（応用編）", "YRLK72JZ7Q", "000009147{month:02d}{year:04d}", [4, 5]),
    ("まいにちフランス語（初級編）", "XQ487ZM61K", "000009113{month:02d}{year:04d}", [1, 2, 3]),
    ("まいにちフランス語（応用編）", "XQ487ZM61K", "000009113{month:02d}{year:04d}", [4, 5]),
    ("まいにちドイツ語（初級編）", "N8PZRZ9WQY", "000009109{month:02d}{year:04d}", [1, 2, 3]),
    ("まいにちドイツ語（応用編）", "N8PZRZ9WQY", "000009109{month:02d}{year:04d}", [4, 5]),
    ("まいにちイタリア語（初級編）", "LJWZP7XVMX", "000009159{month:02d}{year:04d}", [1, 2, 3]),
    ("まいにちイタリア語（応用編）", "LJWZP7XVMX", "000009159{month:02d}{year:04d}", [4, 5]),
    ("まいにち中国語", "983PKQPYN7", "000009101{month:02d}{year:04d}", [1, 2, 3, 4, 5]),
    ("ステップアップ中国語", "MYY93M57V6", "000009099{month:02d}{year:04d}", [1, 2]),
    ("まいにちハングル講座", "LR47WW9K14", "000009277{month:02d}{year:04d}", [1, 2, 3, 4, 5]),
    ("ステップアップハングル講座", "NLJM5V3WXK", "000062133{month:02d}{year:04d}", [4, 5]),
    # ("ポルトガル語講座入門", "N13V9K157Y", "00006213285{annual:04d}", [6]),
]

# らじるらじる聞き逃しjsonのURLテンプレート
JSONURL: str = "https://www.nhk.or.jp/radio-api/app/v1/web/ondemand/series?site_id={site_id}&corner_site_id=01"  # noqa: E501
# ファイルのサムネイルにするためのNHKテキストの画像ファイルのURLテンプレート
IMGURL: str = "https://nhkbook.s3-ap-northeast-1.amazonaws.com/image/goods/{id}/{id}_01_420.jpg"  # noqa: E501

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
    ("入門ビジネス英語", "入門ビジネス英語"),
    ("実践ビジネス英語", "実践ビジネス英語"),
    ("ラジオビジネス英語", "ラジオビジネス英語"),
    ("まいにちスペイン語 初級編", "まいにちスペイン語（初級編）"),
    ("まいにちスペイン語 入門編", "まいにちスペイン語（入門編）"),
    ("まいにちスペイン語 中級編", "まいにちスペイン語（中級編）"),
    ("まいにちスペイン語 応用編", "まいにちスペイン語（応用編）"),
    ("まいにちロシア語 初級編", "まいにちロシア語（初級編）"),
    ("まいにちロシア語 入門編", "まいにちロシア語（入門編）"),
    ("まいにちロシア語 応用編", "まいにちロシア語（応用編）"),
    ("まいにちフランス語 初級編", "まいにちフランス語（初級編）"),
    ("まいにちフランス語 入門編", "まいにちフランス語（入門編）"),
    ("まいにちフランス語 応用編", "まいにちフランス語（応用編）"),
    ("まいにちドイツ語 初級編", "まいにちドイツ語（初級編）"),
    ("まいにちドイツ語 入門編", "まいにちドイツ語（入門編）"),
    ("まいにちドイツ語 応用編", "まいにちドイツ語（応用編）"),
    ("まいにちイタリア語 初級編", "まいにちイタリア語（初級編）"),
    ("まいにちイタリア語 入門編", "まいにちイタリア語（入門編）"),
    ("まいにちイタリア語 応用編", "まいにちイタリア語（応用編）"),
    ("まいにち中国語", "まいにち中国語"),
    ("ステップアップ中国語", "ステップアップ中国語"),
    ("まいにちハングル講座", "まいにちハングル講座"),
    ("ステップアップ ハングル講座", "ステップアップハングル講座"),
    ("ポルトガル語講座 入門", "ポルトガル語講座入門"),
    ("ポルトガル語講座 ステップアップ", "ポルトガル語講座ステップアップ"),
]

# NHK番組表API(https://api-portal.nhk.or.jp/ja)で使用するパラメータ
NHK_AREA: int = 130
NHK_SERVICE: str = "r2"
NHK_GENRE: int = 1011
NHK_APIKEY: str = os.environ.get("NHK_APIKEY", default="")
NHK_PROGRAM_API: str = "https://api.nhk.or.jp/v2/pg/genre/{area}/{service}/{genre}/{date}.json?key={apikey}"

# SetnryのDSNキー
SENTRY_DSN_KEY: Optional[str] = os.environ.get("SENTRY_DSN_KEY", None)

# ロガー
stream_handler = StreamHandler()
stream_handler.setLevel(logging.INFO)
FORAT = "%(asctime)s [%(levelname)s] %(name)s:%(lineno)d %(message)s"
logging.basicConfig(level=logging.NOTSET, handlers=[stream_handler], format=FORAT)
