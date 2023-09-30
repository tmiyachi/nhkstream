# coding:utf-8
import logging
import os
import os.path
import shutil
import sqlite3
import time
import urllib.request
from datetime import datetime
from pathlib import Path
from subprocess import STDOUT, CalledProcessError, TimeoutExpired, check_call
from typing import Any, Dict, List, Tuple, Optional, Union

import requests
import sentry_sdk
from dateutil import parser
from dateutil.relativedelta import FR, MO, TU, relativedelta
from mutagen import MutagenError
from mutagen.mp4 import MP4, MP4Cover
from sentry_sdk.integrations.logging import LoggingIntegration

from settings import (
    DB_FILE,
    IMGURL,
    JSONURL,
    KOUZALIST,
    OUTBASEDIR,
    SENTRY_DSN_KEY,
    TMPBASEDIR,
    TMPOUTDIR,
    ffmpeg,
)
from util import dict_factory

logger = logging.getLogger("nhkstream")


# mp4ファイルにタグを保存する
def settag(
    mp4file,
    image: Union[str, Path, None] = None,
    title: Optional[str] = None,
    album: Optional[str] = None,
    artist: Optional[str] = None,
    track_num: Optional[int] = None,
    year: Optional[int] = None,
    genre: Optional[str] = None,
    total_track_num: Optional[int] = None,
    disc_num: Optional[int] = None,
    total_disc_num: Optional[int] = None,
) -> None:
    audio = MP4(mp4file)
    try:
        audio.add_tags()
    except MutagenError:
        pass

    if image is not None:
        with open(image, "rb") as f:
            audio.tags["covr"] = [MP4Cover(f.read(), imageformat=MP4Cover.FORMAT_JPEG)]

    if title is not None:
        audio.tags["\xa9nam"] = title
    if album is not None:
        audio.tags["\xa9alb"] = album
    if artist is not None:
        audio.tags["\xa9ART"] = artist  # artist
        audio.tags["aART"] = artist  # album artist
    if track_num is not None:
        if total_track_num is None:
            audio.tags["trkn"] = [(track_num, track_num)]
        else:
            audio.tags["trkn"] = [(track_num, total_track_num)]
    if disc_num is not None:
        if total_disc_num is None:
            audio.tags["disk"] = [(disc_num, disc_num)]
        else:
            audio.tags["disk"] = [(disc_num, total_disc_num)]
    if genre is not None:
        audio.tags["\xa9gen"] = genre
    if year is not None:
        audio.tags["\xa9day"] = str(year)
    audio.save()


class ondemandParser:
    def __init__(self, site_id: str):
        url = JSONURL.format(site_id=site_id)
        res = requests.get(url)
        self.info_list = [
            {
                "mp4url": detail["file_list"][0]["file_name"],
                "date": self.truncate_dt(
                    parser.parse(
                        detail["file_list"][0]["aa_vinfo4"].split("_")[0]
                    ).replace(hour=0, minute=0, second=0, microsecond=0)
                ),
            }
            for detail in res.json()["main"]["detail_list"]
        ]

    def truncate_dt(self, dt: datetime) -> datetime:
        return datetime(dt.year, dt.month, dt.day)

    def get_info_list(self) -> List[Dict[str, Any]]:
        return self.info_list

    def get_date_list(self) -> List[datetime]:
        return [d["date"] for d in self.info_list]

    def get_mp4url_list(self) -> List[str]:
        return [d["mp4url"] for d in self.info_list]


class CommandExecError(Exception):
    ...


def get_textbook_volume(
    kouzaname: str, date: datetime, max_kouzanum: int
) -> Tuple[int, int]:
    """放送日から何月号のテキストかを判定する"""

    this_week_monday = date + relativedelta(weekday=MO)
    this_week_tuesday = date + relativedelta(weekday=TU)
    this_week_friday = date + relativedelta(weekday=FR)

    # 月曜日の月号のファイルをカウントし1か月分以上あれば次放送とする
    textbook_year = this_week_monday.year
    textbook_month = this_week_monday.month

    filename = f"{kouzaname}_{date:%Y_%m_%d}.m4a"

    OUTDIR = OUTBASEDIR / kouzaname / f"{textbook_year:d}年{textbook_month:02d}月号"
    file_list = [file.name for file in OUTDIR.glob("*.m4a")]

    # 既に取得済みなら取得済みファイルのテキスト年月を返す
    if filename in file_list:
        return textbook_year, textbook_month

    if len(file_list) == 0:
        # ファイルがなければ放送日から判定
        if this_week_monday.month == this_week_friday.month:
            # 放送日の週のはじめと終わりが同じ年月なら放送日の年月をテキスト年月とする
            textbook_year = this_week_monday.year
            textbook_month = this_week_monday.month
        elif (this_week_tuesday.day - 1) // 7 + 1 == 5:
            # 火曜日が第5週なら次号とする
            textbook_year = this_week_friday.year
            textbook_month = this_week_friday.month
        else:
            # 火曜日が第5週でなければ前号とする
            textbook_year = this_week_tuesday.year
            textbook_month = this_week_tuesday.month
    elif len(file_list) >= max_kouzanum:
        # 4週分既に取得済みであれば次号扱いとする
        textbook_year = (this_week_monday + relativedelta(months=1)).year
        textbook_month = (this_week_monday + relativedelta(months=1)).month
    else:
        textbook_year = this_week_monday.year
        textbook_month = this_week_monday.month

    return textbook_year, textbook_month


def get_img_url(
    textbook_year: int, textbook_month: int, textbook_id_format: str
) -> str:
    if textbook_month in [1, 2, 3]:
        # 1,2,3月放送分のテキストのサムネイルはなぜか前年の1月になっている
        annual = textbook_year - 1
    else:
        annual = textbook_year

    if textbook_month == 1:
        # 1月号のテキストのサムネイルはなぜか前年の1月になっている
        year = textbook_year - 1
    else:
        year = textbook_year

    url = IMGURL.format(
        id=textbook_id_format.format(month=textbook_month, year=year, annual=annual)
    )
    return url


# メイン関数
def streamedump(kouzaname: str, site_id: str, textbook_id_format: str) -> None:
    # ファイル名と放送日リストの取得
    oparser = ondemandParser(site_id)
    mp4url_list = oparser.get_mp4url_list()
    date_list = oparser.get_date_list()

    # 番組表データベースに接続
    con = sqlite3.connect(DB_FILE)
    con.row_factory = dict_factory

    # mp4ファイルをダウンロードする
    FNULL = open(os.devnull, "w")
    TMPDIR = TMPBASEDIR / "nhkdump"
    if TMPDIR.is_dir():
        shutil.rmtree(TMPDIR, ignore_errors=True)
    TMPDIR.mkdir(parents=True)
    for mp4url, date in zip(mp4url_list, date_list):
        textbook_year, textbook_month = get_textbook_volume(kouzaname, date, 4)
        OUTDIR = OUTBASEDIR / kouzaname / f"{textbook_year:d}年{textbook_month:02d}月号"
        if not OUTDIR.is_dir():
            OUTDIR.mkdir(parents=True)

        # アルバム名
        albumname = f"{kouzaname}{textbook_year:d}年{textbook_month:02d}月号"

        # トータルトラック数
        if kouzaname == "英会話タイムトライアル" and textbook_month == 5:
            # 英会話タイムトライアルは5月は他講座より再放送が1週少ない
            total_track_num = 5 * 3
        else:
            total_track_num = 5 * 4

        # 出力ディレクトリに存在するファイルの数からトラックナンバーを決定する
        audio_file_list = list(OUTDIR.glob("*.m4a"))
        audio_file_count = len(audio_file_list)

        # ジャケット画像ファイルを取得する
        try:
            img_url = get_img_url(textbook_year, textbook_month, textbook_id_format)
            img_file = TMPDIR / os.path.basename(img_url)
            img_data = urllib.request.urlopen(img_url)
            with open(img_file, "wb") as f:
                f.write(img_data.read())
            img_data.close()
        except (urllib.error.HTTPError, urllib.error.URLError):
            logger.warning("ジャケット画像の取得に失敗しました。ジャケット画像なしで保存します。")
            img_file = None

        # 番組表データベースに接続
        con = sqlite3.connect(DB_FILE)
        con.row_factory = dict_factory

        # 番組表データベースからタイトルと出演者情報を取得
        try:
            cur = con.cursor()
            cur.execute(
                "SELECT * FROM programs WHERE kouza=? and date=?", (kouzaname, date)
            )
            program = cur.fetchone()
            title = program["title"]
            artist = program["artist"]
            reair = False
        except Exception as e:
            # データベースから取得できないときは暫定タグを設定
            title = "{date}_{kouzaname}".format(
                kouzaname=kouzaname, date=date.strftime("%Y_%m_%d")
            )
            artist = "NHK"
            reair = True
            if isinstance(e, TypeError):
                logger.warning("番組表データベースに番組が見つかりませんでした。再放送の可能性が高いため一時ディレクトリに保存します。")
            else:
                logger.error(e)

        tmpfile = TMPDIR / "{kouza}_{date}.m4a".format(
            kouza=kouzaname, date=date.strftime("%Y_%m_%d")
        )

        if reair:
            audiofile = TMPOUTDIR / "{kouza}_{date}.m4a".format(
                kouza=kouzaname, date=date.strftime("%Y_%m_%d")
            )
        else:
            audiofile = OUTDIR / "{kouza}_{date}.m4a".format(
                kouza=kouzaname, date=date.strftime("%Y_%m_%d")
            )

        logger.info(f"ダウンロード開始：{albumname}:{audiofile.name}")
        if audiofile in audio_file_list:
            audio_file_count = audio_file_count - 1
        if audiofile.is_file():
            if audiofile.stat().st_size > 3000000:
                logger.info(f"{audiofile.name} still exist. Skip")
                continue
        success = False
        try_count = 0
        while not success:
            try:
                try_count += 1
                cmd_args = [
                    ffmpeg,
                    "-y",
                    "-i",
                    mp4url,
                    "-vn",
                    "-acodec",
                    "copy",
                    str(tmpfile),
                ]
                check_call(cmd_args, stdout=FNULL, stderr=STDOUT, timeout=5 * 60)
                success = True
            except CalledProcessError as e:
                if tmpfile.exists():
                    tmpfile.unlink()
                if try_count >= 3:
                    # 3回失敗したらやめる
                    logger.error("ストリーミングファイルのダウンロードに失敗しました．")
                    raise CommandExecError(e)
                else:
                    # 失敗したら5秒待ってリトライ
                    logger.info("'{}'のダウンロードに失敗．リトライします．".format(title))
                    time.sleep(5)
            except TimeoutExpired as e:
                logger.error("タイムアウトのためダウンロードを中止しました．")
                raise CommandExecError(e)

        # ダウンロードが正常に完了しなかった場合はファイルを削除して中止
        if tmpfile.is_file():
            if kouzaname == "英会話タイムトライアル":
                # 英会話タイムトライアルは10分番組なのでサイズが小さい
                default_size = 3500000
            else:
                default_size = 5000000
            if tmpfile.stat().st_size < default_size:
                logger.error("ダウンロードが完了しませんでした．")
                tmpfile.unlink()
                continue

        # 保存先にコピー
        shutil.copyfile(tmpfile, audiofile)

        # タグを設定
        settag(
            audiofile,
            image=img_file,
            title=title,
            artist=artist,
            album=albumname,
            genre="Speech",
            track_num=None if reair else audio_file_count + 1,
            total_track_num=total_track_num,
            year=textbook_year,
            disc_num=1,
            total_disc_num=1,
        )

    con.close()


if __name__ == "__main__":
    if SENTRY_DSN_KEY is not None:
        sentry_logging = LoggingIntegration(
            level=logging.INFO,  # Capture info and above as breadcrumbs
            event_level=logging.ERROR,  # Send errors as events
        )
        sentry_sdk.init(dsn=SENTRY_DSN_KEY, integrations=[sentry_logging])
    for kouzaname, site_id, booknum in KOUZALIST:
        try:
            streamedump(kouzaname, site_id, booknum)
        except CommandExecError:
            logger.info(kouzaname + "のダウンロードを中止")
            pass
