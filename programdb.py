import re
import sqlite3

import requests
import pandas as pd
from datetime import datetime
from dateutil.relativedelta import relativedelta
from dateutil.rrule import rrule, DAILY
import jaconv

from settings import DB_FILE, PROGRAMLIST, NHK_AREA, NHK_SERVICE, NHK_GENRE, NHK_APIKEY, NHK_PROGRAM_API


# 番組タイトル名に該当する講座名を取得する
def getKouza(title):
    for kouza_key, kouza in PROGRAMLIST:
        if kouza_key in title:
            return kouza
    return None


# 番組出演者情報をmp3タグに設定可能な形式に整形する
def getArtist(act):
    artist = '; '.join([a.split('…')[-1] if '…' in a else a for a in re.sub('【.{2,3}】', '', act).split('，')])
    return jaconv.z2h(artist, kana=False, ascii=True)


# 翌日から1週間分の番組表から番組データを取得する
json = []
for date in rrule(freq=DAILY, dtstart=datetime.today() + relativedelta(days=1), count=7):
    r = requests.get(NHK_PROGRAM_API.format(area=NHK_AREA, service=NHK_SERVICE,
                                            genre=NHK_GENRE, apikey=NHK_APIKEY, date=date.strftime('%Y-%m-%d')))
    json.extend(r.json()['list']['r2'])

df = pd.DataFrame(json)
df = df.loc[:, ['start_time', 'title', 'act']]

# 放送時間で並べ替えて同一タイトルの重複行を削除（再放送の削除）
df = df.sort_values(['start_time', 'title'])
df = df.drop_duplicates('title')

# NHK番組表では英数字も全角なので半角へ置換し、全角スペースも半角スペースに置換
df['title'] = df.title.apply(lambda s: jaconv.z2h(s, kana=False, ascii=True, digit=True).replace('　', ' '))

# 時刻情報は不要なので日付情報のみに変換
df['date'] = pd.to_datetime(df.start_time).apply(lambda d: datetime(d.year, d.month, d.day))

# 講座名とアーティスト名をmp3タグに設定する形式に変換する
df['kouza'] = df.title.apply(getKouza)
df['artist'] = df.act.apply(getArtist)

# PROGRAM_LISTで設定されていない番組を削除、講座名と日付が同じタイトルは最初に放送されるタイトルのみ残す（前週の再放送を削除）
df = df[df.kouza.notna()].drop_duplicates(['kouza', 'date']).reset_index()

# データベースファイルに追加する
df = df.loc[:, ['date', 'title', 'artist', 'kouza']]
conn = sqlite3.connect(DB_FILE)
df.to_sql('programs', conn, index=False, if_exists='append')
conn.close()
