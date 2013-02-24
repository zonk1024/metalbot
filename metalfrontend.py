import sqlite3
from bottle import route, run, debug, request, validate, static_file, error
from bottle import jinja2_view as view, jinja2_template as template
import mpd
from metalbot import MetalBot
import settings

# only needed when you run Bottle on mod_wsgi
from bottle import default_app

@route('/')
@view('index.html')
def main_page():
    mpc = mpd.MPDClient(use_unicode = True)
    mpc.connect(settings.MPD_SERVER, settings.MPD_PORT)
    s = mpc.status()
    nextsongs = []
    if "nextsong" in s:
        for songpos in range(int(s["nextsong"]), int(s["nextsong"]) + 10):
            song = mpc.playlistinfo(songpos)[0]
            song["sid"] = MetalBot.getsongid(song["file"])
            nextsongs.append(song)

    if s["state"] == "play":
        nowplaying = mpc.currentsong()
        nowplaying["sid"] = MetalBot.getsongid(song["file"])

    db = sqlite3.connect(settings.DB)
    cur = db.cursor()
    cur.execute("SELECT filename, title, artist FROM queue INNER JOIN songlist ON songlist.id=queue.songid ORDER BY queue.id")
    queuerows = cur.fetchall()
    queue = []
    for qr in queuerows:
        qe = {}
        qe["sid"] = MetalBot.getsongid(qr[0])
        qe["title"] = qr[1]
        qe["artist"] = qr[2]
        queue.append(qe)

    return dict(nextup = nextsongs, nowplaying = nowplaying, queue = queue)


run(host='localhost', port=8080)
