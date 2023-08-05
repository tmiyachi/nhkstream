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
from typing import Any, Dict, List, Optional, Union

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


# メイン関数
def streamedump(kouzaname: str, site_id: str, booknum: str) -> None:
    # ファイル名と放送日リストの取得
    oparser = ondemandParser(site_id)
    mp4url_list = oparser.get_mp4url_list()
    date_list = oparser.get_date_list()

    # 番組表データベースに接続
    con = sqlite3.connect(DB_FILE)
    con.row_factory = dict_factory

    # mp4ファイルをダウンロードする
    FNULL = open(os.devnull, "w")
    for mp4url, date in zip(mp4url_list, date_list):
        # ストリーミングの日付から何月号のテキストかを調べる
        this_week_monday = date + relativedelta(weekday=MO)
        this_week_tuesday = date + relativedelta(weekday=TU)
        this_week_friday = date + relativedelta(weekday=FR)
        # 月曜日の月号のファイルをカウントし1か月分以上あれば次放送とする
        text_year = this_week_monday.year
        text_month = this_week_monday.month

        filename = "{kouza}_{date}.m4a".format(
            kouza=kouzaname, date=date.strftime("%Y_%m_%d")
        )
        # 同名ファイルを除いたファイル数をカウント
        OUTDIR = OUTBASEDIR / kouzaname / f"{text_year:d}年{text_month:02d}月号"
        existed_file_list = [file.name for file in OUTDIR.glob("*.m4a")]
        if filename in existed_file_list:
            continue
        existed_track_num = len(
            [file for file in OUTDIR.glob("*.m4a") if file.name != filename]
        )
        # 4週分の講座数
        if "入門編" in kouzaname:
            max_kouzanum = 3 * 4
        elif "中級編" in kouzaname or "応用編" in kouzaname:
            max_kouzanum = 2 * 4
        else:
            max_kouzanum = (len(date_list) - 1) * 4
        if existed_track_num == 0:
            # ファイルがなければ新講座扱いで何週目かで判定（失敗する場合もある）
            if this_week_monday.month == this_week_friday:
                # 週のはじめと終わりが同じ月なら今号
                text_year = this_week_monday.year
                text_month = this_week_monday.month
            elif (this_week_tuesday.day - 1) // 7 + 1 == 5:
                # 火曜日が第5週なら次号
                text_year = this_week_friday.year
                text_month = this_week_friday.month
            else:
                # 第5週でなければ前号
                text_year = this_week_tuesday.year
                text_month = this_week_tuesday.month
        elif existed_track_num >= max_kouzanum:
            # 4週分既にあれば次号扱い
            text_year = (this_week_monday + relativedelta(months=1)).year
            text_month = (this_week_monday + relativedelta(months=1)).month
        else:
            text_year = this_week_monday.year
            text_month = this_week_monday.month

        # アルバム名
        albumname = f"{kouzaname}{text_year:d}年{text_month:02d}月号"

        # ディレクトリの作成
        TMPDIR = TMPBASEDIR / "nhkdump"
        # アルバム名のディレクトリに保存する
        OUTDIR = OUTBASEDIR / kouzaname / f"{text_year:d}年{text_month:02d}月号"

        if TMPDIR.is_dir():
            shutil.rmtree(TMPDIR, ignore_errors=True)
        os.makedirs(TMPDIR)
        if not OUTDIR.is_dir():
            os.makedirs(OUTDIR)

        # 同じ保存ディレクトリに存在するファイルの数からタグに付加するトラックナンバーの開始数を決定する
        existed_track_list = list(OUTDIR.glob("*.m4a"))
        existed_track_numbter = len(existed_track_list)

        # トータルトラック数を決定する
        if kouzaname == "英会話タイムトライアル" and text_month == 5:
            # 英会話タイムトライアルは5月は他講座より再放送が1週少ない
            total_track_num = 5 * 3
        else:
            total_track_num = 5 * 4

        # ジャケット画像ファイルを取得する
        imgfile: Optional[Path] = None
        try:
            if text_month in [1, 2, 3]:
                annual = text_year - 1
            else:
                annual = text_year
            if text_month == 1:
                # 1月号のテキストのサムネイルは前年の1月になる
                imgurl = IMGURL.format(
                    booknum=booknum.format(
                        month=text_month, year=text_year - 1, annual=annual
                    )
                )
            else:
                imgurl = IMGURL.format(
                    booknum=booknum.format(
                        month=text_month, year=text_year, annual=annual
                    )
                )
            imgfile = TMPDIR / os.path.basename(imgurl)
            imgdata = urllib.request.urlopen(imgurl)
            with open(imgfile, "wb") as f:
                f.write(imgdata.read())
            imgdata.close()
        except (urllib.error.HTTPError, urllib.error.URLError):
            logger.warning("ジャケット画像の取得に失敗しました。ジャケット画像なしで保存します。")
            imgfile = None

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
        if audiofile in existed_track_list:
            existed_track_numbter = existed_track_numbter - 1
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
                # print(" ".join(cmd_args))
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
            image=imgfile,
            title=title,
            artist=artist,
            album=albumname,
            genre="Speech",
            track_num=None if reair else existed_track_numbter + 1,
            total_track_num=total_track_num,
            year=text_year,
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
