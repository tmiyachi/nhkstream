import argparse
import re
from pathlib import Path

from mutagen import MutagenError
from mutagen.mp4 import MP4, MP4Cover


class MP4Tag:
    def __init__(self, file):
        self.mp4 = MP4(file)
        try:
            self.mp4.add_tags()
        except MutagenError:
            # tags already exist
            pass

    @property
    def title(self):
        return self.mp4.tags["\xa9nam"]

    @title.setter
    def title(self, title):
        self.mp4.tags["\xa9nam"] = title

    @property
    def album(self):
        return self.mp4.tags["\xa9alb"]

    @album.setter
    def album(self, album):
        self.mp4.tags["\xa9alb"] = album

    @property
    def artist(self):
        return self.mp4.tags["\xa9ART"]

    @artist.setter
    def artist(self, artist):
        self.mp4.tags["\xa9ART"] = artist

    @property
    def album_artist(self):
        return self.mp4.tags["aART"]

    @album_artist.setter
    def album_artist(self, artist):
        self.mp4.tags["aART"] = artist

    def set_track_num(self, track_num, total_track_num=None):
        if total_track_num is None:
            self.mp4.tags["trkn"] = [(track_num, track_num)]
        else:
            self.mp4.tags["trkn"] = [(track_num, total_track_num)]

    def set_disk_num(self, disk_num, total_disk_num=None):
        if total_disk_num is None:
            self.mp4.tags["disk"] = [(disk_num, disk_num)]
        else:
            self.mp4.tags["disk"] = [(disk_num, total_disk_num)]

    @property
    def genre(self):
        return self.mp4.tags["\xa9gen"]

    @genre.setter
    def genre(self, genre):
        self.mp4.tags["\xa9gen"] = genre

    @property
    def year(self):
        return int(self.mp4.tags["\xa9day"])

    @year.setter
    def year(self, year):
        self.mp4.tags["\xa9day"] = str(year)

    def save(self):
        self.mp4.save()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        prog="reset_mp4_tag",
        description=__doc__,
        formatter_class=argparse.RawTextHelpFormatter,
    )

    parser.add_argument("target_dir", help="対象ディレクトリ", type=Path)
    args = parser.parse_args()

    m = re.match("(?P<year>[0-9]{4})年(?P<month>[0-9]{2})月号", args.target_dir.name)
    if m is None:
        raise ValueError("ターゲットディレクトリ名が不正です")
    year = m.group("year")
    month = m.group("month")

    mp4list = sorted(args.target_dir.glob("*.m4a"))
    print(f"target directory: {args.target_dir.name}")
    print(f"year: {year}")
    print(f"total track num: {len(mp4list)}")
    for mp4file in mp4list:
        mp4 = MP4(mp4file)
        title = mp4.tags["\xa9nam"]
        album = mp4.tags["\xa9alb"]
        print(f"{album} {title}")

    mp4base = MP4(mp4list[int(len(mp4list) / 2)])
    album = mp4base.tags["\xa9alb"]
    artist = mp4base.tags["\xa9ART"]
    album_artist = mp4base.tags["aART"]
    genre = mp4base.tags["\xa9gen"]
    year = mp4base.tags["\xa9day"]
    image = mp4base.tags["covr"]
    print(f"{mp4base.filename} に合わせてタグを修正します(y/n)")
    print(f"  album: {album}")
    print(f"  artist: {artist}")
    print(f"  album_artist: {album_artist}")
    print(f"  genre: {genre}")
    print(f"  year: {year}")
    ret = input()
    if ret.strip() != "y":
        exit

    for i, mp4file in enumerate(mp4list):
        mp4 = MP4(mp4file)
        mp4.tags["\xa9alb"] = album
        mp4.tags["\xa9ART"] = artist
        mp4.tags["aART"] = album_artist
        mp4.tags["\xa9gen"] = genre
        mp4.tags["\xa9day"] = year
        mp4.tags["covr"] = image
        mp4.tags["trkn"] = [(i + 1, len(mp4list))]
        mp4.tags["disk"] = [(1, 1)]
        mp4.save()
