import sqlite3
import re

import pandas as pd
from datetime import datetime
from dateutil.relativedelta import relativedelta, MO

from settings import DB_FILE


def get_func(nums):
    def func(rec):
        rec['date'] = pd.to_datetime(rec.date) + relativedelta(weeks=1)
        if rec.kouza == '英会話タイムトライアル':
            m = re.search(r'DAY(?P<day>[0-9]+)', rec.title)
            if m:
                rec.title = rec.title.replace('DAY{}'.format(m.group('day')),
                                              'DAY{}'.format(int(m.group('day')) + nums))
        elif rec.kouza == '高校生からはじめる「現代英語」':
            m = re.search(r'Lesson(?P<num>[0-9]+) Part(?P<part>[0-9+])', rec.title)
            if m:
                rec.title = rec.title.replace(m.group('num'), str(int(m.group('num')) + 1))
        else:
            m = re.search(r'\((?P<num>[0-9]+)\)', rec.title)
            if m:
                rec.title = rec.title.replace(m.group('num'), str(int(m.group('num')) + nums))
        return rec
    return func


# 先々週放送された番組タイトルのリストを取得
conn = sqlite3.connect(DB_FILE)
mon_bfrkstweek = datetime.today() + relativedelta(weeks=-2, weekday=MO(-1), hour=0, minute=0, second=0)
sql = 'SELECT * FROM programs WHERE date BETWEEN "{}" and "{}"'.format(
    mon_bfrkstweek.strftime('%Y-%m-%d'), (mon_bfrkstweek + relativedelta(days=6)).strftime('%Y-%m-%d'))
df_bfrlstweek = pd.read_sql(sql, conn)

# タイトルと日付を変更して取得できなかった先週分を強制的に追加
# 英会話タイムトライアルと現代英語はタイトルの規則性が弱いので確認してDBを変更する
for _, gr in df_bfrlstweek.groupby('kouza'):
    func = get_func(len(gr))
    gr = gr.apply(func, axis=1)
    gr.to_sql('programs', conn, index=False, if_exists='append')
conn.close()
