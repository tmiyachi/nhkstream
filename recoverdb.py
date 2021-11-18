import re
import sqlite3
from datetime import datetime

import pandas as pd
from dateutil.relativedelta import MO, relativedelta

from settings import DB_FILE


def get_func(nums):
    def func(rec):
        rec["date"] = pd.to_datetime(rec.date) + relativedelta(weeks=1)
        if rec.kouza == "英会話タイムトライアル":
            m = re.search(r"DAY(?P<day>[0-9]+)", rec.title)
            if m:
                rec.title = rec.title.replace(
                    "DAY{}".format(m.group("day")),
                    "DAY{}".format(int(m.group("day")) + nums),
                )
        elif rec.kouza == "高校生からはじめる「現代英語」":
            m = re.search(r"Lesson(?P<num>[0-9]+) Part(?P<part>[0-9+])", rec.title)
            if m:
                rec.title = rec.title.replace(
                    m.group("num"), str(int(m.group("num")) + 1)
                )
        else:
            m = re.search(r"\((?P<num>[0-9]+)\)", rec.title)
            if m:
                rec.title = rec.title.replace(
                    m.group("num"), str(int(m.group("num")) + nums)
                )
        return rec

    return func


def sql_one_week(mon: datetime) -> str:
    return 'SELECT * FROM programs WHERE date BETWEEN "{}" and "{}"'.format(
        mon.strftime("%Y-%m-%d"), (mon + relativedelta(days=6)).strftime("%Y-%m-%d")
    )


# 先々週放送された番組タイトルのリストを取得
with sqlite3.connect(DB_FILE) as conn:
    # 先週月曜日
    mon_last_week = datetime.today() + relativedelta(
        weeks=-1, weekday=MO(-1), hour=0, minute=0, second=0, microsecond=0
    )
    # 先々週の月曜日
    mon_the_week_befor_last = mon_last_week + relativedelta(weeks=-1)

    if len(pd.read_sql(sql_one_week(mon_last_week), conn)) > 0:
        print("先週放送された番組のレコードが残っています．削除してから実行してください．")
    else:
        df_bfrlstweek = pd.read_sql(sql_one_week(mon_the_week_befor_last), conn)

        # タイトルと日付を変更して取得できなかった先週分を強制的に追加
        # 英会話タイムトライアルと現代英語はタイトルの規則性が弱いので確認してDBを変更する
        for _, gr in df_bfrlstweek.groupby("kouza"):
            func = get_func(len(gr))
            gr = gr.apply(func, axis=1)
            gr.to_sql("programs", conn, index=False, if_exists="append")

        # 追加されたレコードの確認
        df_lstweek = pd.read_sql(sql_one_week(mon_last_week), conn)
        print(
            "追加されたレコード：{}, 追加された番組：{}".format(
                len(df_lstweek), len(df_lstweek.kouza.unique())
            )
        )
