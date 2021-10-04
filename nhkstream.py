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
from subprocess import STDOUT, CalledProcessError, check_call
from typing import Any, Dict, List, Optional, Union

import requests
import sentry_sdk
from dateutil import parser
from dateutil.relativedelta import FR, MO, TU, relativedelta
from mutagen.id3 import APIC, ID3, TALB, TCON, TIT2, TPE1, TPE2, TPOS, TRCK, TYER
from mutagen.mp3 import MP3
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


# mp3ファイルにタグを保存する
def setmp3tag(
    mp3file,
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
    audio = MP3(mp3file, ID3=ID3)
    try:
        audio.add_tag()
    except Exception:
        pass

    if image is not None:
        with open(image, "rb") as f:
            audio.tags.add(
                APIC(
                    encoding=3,
                    mime="image/jpeg",
                    type=3,
                    desc="Cover Picture",
                    data=f.read(),
                )
            )
    if title is not None:
        audio.tags.add(TIT2(encoding=3, text=title))
    if album is not None:
        audio.tags.add(TALB(encoding=3, text=album))
    if artist is not None:
        audio.tags.add(TPE1(encoding=3, text=artist))
        audio.tags.add(TPE2(encoding=3, text=artist))
    if track_num is not None:
        if total_track_num is None:
            audio.tags.add(TRCK(encoding=3, text=str(track_num)))
        else:
            audio.tags.add(
                TRCK(encoding=3, text="{}/{}".format(track_num, total_track_num))
            )
    if disc_num is not None:
        if total_disc_num is None:
            audio.tags.add(TPOS(encoding=3, text=str(disc_num)))
        else:
            audio.tags.add(
                TPOS(encoding=3, text="{}/{}".format(disc_num, total_disc_num))
            )
    if genre is not None:
        audio.tags.add(TCON(encoding=3, text=genre))
    if year is not None:
        audio.tags.add(TYER(encoding=3, text=str(year)))
    audio.save(v2_version=3, v1=2)


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

    # ストリーミングの日付から何月号のテキストかを調べる
    this_week_monday = date_list[0] + relativedelta(weekday=MO)
    this_week_tuesday = date_list[0] + relativedelta(weekday=TU)
    this_week_friday = date_list[0] + relativedelta(weekday=FR)
    if this_week_monday.month == this_week_friday.month:
        # 週のはじめと終わりが同じ場合は初日と同じ月が該当月
        text_year = this_week_monday.year
        text_month = this_week_monday.month
    else:
        # 週のはじめと終わりが違う場合は月曜日の月号のファイルをカウントし1か月分以上あれば次放送とする
        text_year = this_week_monday.year
        text_month = this_week_monday.month

        # 同名ファイルを除いたファイル数をカウント
        mp3file_list = [
            "{kouza}_{date}.mp3".format(kouza=kouzaname, date=date.strftime("%Y_%m_%d"))
            for date in date_list
        ]
        OUTDIR = OUTBASEDIR / kouzaname / f"{text_year:d}年{text_month:02d}月号"
        existed_track_num = len(
            [
                mp3file
                for mp3file in OUTDIR.glob("*.mp3")
                if mp3file.name not in mp3file_list
            ]
        )
        # 4週分の講座数
        if "入門編" in kouzaname:
            max_kouzanum = 3 * 4
        elif "中級編" in kouzaname or "応用編" in kouzaname:
            max_kouzanum = 2 * 4
        else:
            max_kouzanum = len(date_list) * 4

        if existed_track_num == 0:
            # ファイルがなければ新講座扱いで何週目かで判定（失敗する場合もある）
            if (this_week_tuesday.day - 1) // 7 + 1 == 5:
                # 火曜日が第5週なら次号
                text_year = this_week_friday.year
                text_month = this_week_friday.month
            else:
                # 第5週でなければ前号
                text_year = this_week_tuesday.year
                text_month = this_week_tuesday.month
        elif existed_track_num >= max_kouzanum:
            # 4週分既にあれば次号扱い
            text_year = this_week_friday.year
            text_month = this_week_friday.month
        else:
            text_year = this_week_monday.year
            text_month = this_week_monday.month
    # アルバム名
    albumname = f"{kouzaname}{text_year:d}年{text_month:02d}月号"
    logger.info("ダウンロード開始：" + albumname)

    # ディレクトリの作成
    TMPDIR = TMPBASEDIR / "nhkdump"
    # アルバム名のディレクトリに保存する
    OUTDIR = OUTBASEDIR / kouzaname / f"{text_year:d}年{text_month:02d}月号"

    if TMPDIR.is_dir():
        shutil.rmtree(TMPDIR, ignore_errors=True)
    os.makedirs(TMPDIR)
    if not OUTDIR.is_dir():
        os.makedirs(OUTDIR)

    # 同じ保存ディレクトリに存在するmp3ファイルの数からタグに付加するトラックナンバーの開始数を決定する
    existed_track_list = list(OUTDIR.glob("*.mp3"))
    existed_track_numbter = len(existed_track_list)

    # トータルトラック数を決定する
    if kouzaname == "英会話タイムトライアル" and text_month == 5:
        # 英会話タイムトライアルは5月は他講座より再放送が1週少ない
        total_track_num = len(date_list) * 3
    else:
        total_track_num = len(date_list) * 4

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
                booknum=booknum.format(month=text_month, year=text_year, annual=annual)
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

    # mp4ファイルをダウンロードしてmp3にファイルに変換する
    FNULL = open(os.devnull, "w")
    for number_on_week, (mp4url, date) in enumerate(zip(mp4url_list, date_list)):
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

        tmpfile = TMPDIR / "{kouza}_{date}.mp4".format(
            kouza=kouzaname, date=date.strftime("%Y_%m_%d")
        )

        if reair:
            mp3file = TMPOUTDIR / "{kouza}_{date}.mp3".format(
                kouza=kouzaname, date=date.strftime("%Y_%m_%d")
            )
        else:
            mp3file = OUTDIR / "{kouza}_{date}.mp3".format(
                kouza=kouzaname, date=date.strftime("%Y_%m_%d")
            )

        if mp3file in existed_track_list:
            existed_track_numbter = existed_track_numbter - 1

        if mp3file.is_file():
            if mp3file.stat().st_size > 3000000:
                logger.info(
                    "{} still exist. Skip {} {}".format(
                        mp3file.name, albumname, mp3file.name
                    )
                )
                continue
        else:
            logger.info("download " + mp3file.name)
        success = False
        try_count = 0
        while not success:
            try:
                try_count = 1
                cmd_args = [
                    ffmpeg,
                    "-y",
                    "-i",
                    mp4url,
                    "-vn",
                    "-bsf",
                    "aac_adtstoasc",
                    "-acodec",
                    "copy",
                    str(tmpfile),
                ]
                check_call(cmd_args, stdout=FNULL, stderr=STDOUT)
                success = True
            except CalledProcessError as e:
                logger.error("ストリーミングファイルのダウンロードに失敗しました．")
                if try_count >= 3:
                    # 3回失敗したらやめる
                    raise CommandExecError(e)
                else:
                    # 失敗したら5秒待ってリトライ
                    time.sleep(5)
        try:
            cmd_args = [
                ffmpeg,
                "-i",
                str(tmpfile),
                "-vn",
                "-acodec",
                "libmp3lame",
                "-ar",
                "22050",
                "-ac",
                "1",
                "-ab",
                "48k",
                str(mp3file),
            ]
            check_call(cmd_args, stdout=FNULL, stderr=STDOUT)
        except CalledProcessError as e:
            logger.error("MP3ファイルへの変換に失敗しました．")
            raise CommandExecError(e)
        logger.info("完了: {} {}".format(albumname, os.path.basename(mp3file)))
        time.sleep(1)

        # mp3タグを設定
        setmp3tag(
            mp3file,
            image=imgfile,
            title=title,
            artist=artist,
            album=albumname,
            genre="Speech",
            track_num=None if reair else existed_track_numbter + number_on_week + 1,
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
            event_level=logging.WARN,  # Send errors as events
        )
        sentry_sdk.init(dsn=SENTRY_DSN_KEY, integrations=[sentry_logging])
    for kouzaname, site_id, booknum in KOUZALIST:
        try:
            streamedump(kouzaname, site_id, booknum)
        except CommandExecError as e:
            logger.error(e)
