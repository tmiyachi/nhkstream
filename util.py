import sys


# UTF-8以外の環境で生じるユニコード問題への対処関数
def encodecmd(cmd):
    systemcode = sys.getfilesystemencoding()
    if isinstance(cmd, list):
        encodedcmd = [s.encode(systemcode) for s in cmd]
    else:
        encodedcmd = cmd.encode(systemcode)
    return encodedcmd


def dict_factory(cursor, row):
    d = {}
    for idx, col in enumerate(cursor.description):
        d[col[0]] = row[idx]
    return d
