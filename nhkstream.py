# coding:utf-8
import glob
import os
import os.path
import shutil
import urllib.request
from datetime import datetime
from subprocess import STDOUT, check_call
import sqlite3

import requests
from dateutil.relativedelta import relativedelta, MO, FR

from bs4 import BeautifulSoup
from mutagen.id3 import APIC, ID3, TALB, TCON, TIT2, TPE1, TPE2, TPOS, TRCK, TYER
from mutagen.mp3 import MP3

from settings import KOUZALIST, OUTBASEDIR, TMPOUTDIR, TMPBASEDIR
from settings import XMLURL, MP4URL, IMGURL
from settings import USE_DB_TAG, DB_FILE
from settings import ffmpeg

from util import encodecmd, dict_factory


# mp3ファイルにタグを保存する
def setmp3tag(mp3file, image=None, title=None, album=None, artist=None, track_num=None,
              year=None, genre=None, total_track_num=None, disc_num=None, total_disc_num=None):
    audio = MP3(mp3file, ID3=ID3)
    try:
        audio.add_tag()
    except Exception:
        pass

    if image is not None:
        with open(image, 'rb') as f:
            audio.tags.add(APIC(
                encoding=3,
                mime='image/jpeg',
                type=3,
                desc='Cover Picture',
                data=f.read()))
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
            audio.tags.add(TRCK(encoding=3, text='{}/{}'.format(track_num, total_track_num)))
    if disc_num is not None:
        if total_disc_num is None:
            audio.tags.add(TPOS(encoding=3, text=str(disc_num)))
        else:
            audio.tags.add(TPOS(encoding=3, text='{}/{}'.format(disc_num, total_disc_num)))
    if genre is not None:
        audio.tags.add(TCON(encoding=3, text=genre))
    if year is not None:
        audio.tags.add(TYER(encoding=3, text=str(year)))
    audio.save(v2_version=3, v1=2)


# メイン関数
def streamedump(kouzaname, language, kouza, kouzano):
    # XMLからストリーミングファイルの情報を取得する
    xmlfile = urllib.request.urlopen(XMLURL.format(language=language, kouza=kouza))
    soup = BeautifulSoup(xmlfile.read().decode('utf-8').replace('\n', ''), features='lxml')

    # ファイル名と放送日リストの取得
    file_list = []
    date_list = []
    today = datetime.today()
    for item in soup.findAll('music'):
        file_list.append(item.get('file'))
        file_date = datetime.strptime(item.get('hdate'), '%m月%d日放送分')
        if file_date.month == 12 and today.month == 1:
            file_date = file_date + relativedelta(year=today.year - 1)
        else:
            file_date = file_date + relativedelta(year=today.year)
        date_list.append(file_date)

    # ストリーミングの日付から何月号のテキストかを調べる
    this_week_monday = date_list[0] + relativedelta(weekday=MO(-1))
    this_week_friday = date_list[0] + relativedelta(weekday=FR)
    if this_week_monday.month == this_week_friday.month:
        # 週のはじめと終わりが同じ場合は初日と同じ月が該当月
        text_year = this_week_monday.year
        text_month = this_week_monday.month
    else:
        # 週のはじめと終わりが違う場合は前週か次週の月のテキスト
        if (this_week_monday.day - 1) // 7 + 1 == 5:
            # 月曜日が第5週なら次号
            text_year = this_week_friday.year
            text_month = this_week_friday.month
        else:
            # 第5週でなければ前号
            text_year = this_week_monday.year
            text_month = this_week_monday.month

    # アルバム名
    albumname = '{kouzaname}{year:d}年{month:02d}月号'.format(kouzaname=kouzaname, year=text_year, month=text_month)

    # 再放送週かどうかの確認
    reair = False
    try:
        r = requests.get('https://www2.nhk.or.jp/gogaku/topics.cgi')
        bs = BeautifulSoup(r.content.decode('utf-8'), 'lxml')

        for div in bs.find('div', class_='ct1').find('dd').find_all('div', recursive=False):
            if kouzaname in div.find('p').text:
                p = div.find('p')
                if '再放送' in p.text and date_list[0].strftime('%-m月%-d日') in p.text:
                    reair = True
    except Exception:
        reair = True

    # ディレクトリの作成
    TMPDIR = os.path.join(TMPBASEDIR, 'nhkdump')
    if reair:
        # 再放送週なら一時保存ディレクトリに念のため保存して後で削除
        OUTDIR = TMPOUTDIR
    else:
        # 通常放送週ならアルバム名のディレクトリに保存する
        OUTDIR = os.path.join(OUTBASEDIR, kouzaname, '{year:d}年{month:02d}月号'.format(year=text_year, month=text_month))
    if os.path.isdir(TMPDIR):
        shutil.rmtree(TMPDIR, ignore_errors=True)
    os.makedirs(TMPDIR)
    if not os.path.isdir(OUTDIR):
        os.makedirs(OUTDIR)

    # 同じ保存ディレクトリに存在するmp3ファイルの数からタグに付加するトラックナンバーの開始数を決定する
    if not reair:
        existed_track_list = list(glob.glob(os.path.join(OUTDIR, '*.mp3')))
    else:
        existed_track_list = []
    existed_track_numbter = len(existed_track_list)

    # ジャケット画像ファイルを取得する
    # REVIEW: 2020年1月号のテキストのURLが...012019...になり規則通りではなかった。NHK側のミスの可能性高いが注意が必要
    imgurl = IMGURL.format(kouzano=kouzano, date=('{:02d}{:04d}'.format(text_month, text_year)))
    imgfile = os.path.join(TMPDIR, os.path.basename(imgurl))
    imgdata = urllib.request.urlopen(imgurl)
    with open(imgfile, 'wb') as f:
        f.write(imgdata.read())
    imgdata.close()

    if USE_DB_TAG:
        con = sqlite3.connect(DB_FILE)
        con.row_factory = dict_factory

    # mp4ファイルをダウンロードしてmp3にファイルに変換する
    FNULL = open(os.devnull, 'w')
    for number_on_week, (mp4file, date) in enumerate(zip(file_list, date_list)):
        mp4url = MP4URL.format(mp4file=mp4file)
        tmpfile = os.path.join(TMPDIR, '{kouza}_{date}.mp4'.format(kouza=kouzaname, date=date.strftime('%Y_%m_%d')))
        mp3file = os.path.join(OUTDIR, '{kouza}_{date}.mp3'.format(kouza=kouzaname, date=date.strftime('%Y_%m_%d')))

        if mp3file in existed_track_list:
            existed_track_numbter = existed_track_numbter - 1

        if os.path.isfile(mp3file):
            if os.path.getsize(mp3file) > 3000000:
                print(mp3file + ' still exist. skip.')
                continue
        else:
            print('download ' + mp3file)

        check_call(encodecmd([ffmpeg, '-y', '-i', mp4url, '-vn', '-bsf', 'aac_adtstoasc', '-acodec', 'copy', tmpfile]), stdout=FNULL, stderr=STDOUT)
        check_call(encodecmd([ffmpeg, '-i', tmpfile, '-vn', '-acodec', 'libmp3lame', '-ar', '22050', '-ac', '1', '-ab', '48k', mp3file]),
                   stdout=FNULL, stderr=STDOUT)

        # MP3ファイルにタグを設定 (mutagen)
        title = '{date}_{kouzaname}'.format(kouzaname=kouzaname, date=date.strftime('%Y_%m_%d'))
        artist = 'NHK'
        if USE_DB_TAG:
            # 番組表データベースからタイトルと出演者情報を取得
            try:
                cur = con.cursor()
                cur.execute('SELECT * FROM programs WHERE kouza=? and date=?', (kouzaname, date))
                program = cur.fetchone()
                title = program['title']
                artist = program['artist']
            except Exception:
                print('cannot find program in database. use default title and artist')

        setmp3tag(mp3file,
                  image=imgfile,
                  title=title,
                  artist=artist,
                  album=albumname,
                  genre='Speech',
                  track_num=None if reair else existed_track_numbter + number_on_week + 1,
                  total_track_num=None,
                  year=text_year,
                  disc_num=1,
                  total_disc_num=1
                  )

    if USE_DB_TAG:
        con.close()


if __name__ == '__main__':
    for kouzaname, language, kouza, kouzano in KOUZALIST:
        streamedump(kouzaname, language, kouza, kouzano)
