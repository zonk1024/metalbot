import os, re
from bottle import route, run, debug, request, validate, static_file, error, abort
from bottle import jinja2_view as view, jinja2_template as template
from metalbot import MPDInterface
import settings

# only needed when you run Bottle on mod_wsgi
from bottle import default_app

@route('/')
@view('index.html')
def main_page():
    mpdi = MPDInterface()

    nextsongs = mpdi.nextsong(number = 10)
    nowplaying = mpdi.currentsong()
    if nowplaying is not None:
        if os.path.isfile(os.path.join(settings.MPD_SOURCE, os.path.dirname(nowplaying["file"]), "cover.jpg")):
            nowplaying["coverpath"] = u"/covers/{0}/cover.jpg".format(os.path.dirname(nowplaying["file"]))

    queue = mpdi.get_queue()

    return dict(nextup = nextsongs, nowplaying = nowplaying, queue = queue)

@route("/covers/<coverpath:path>")
def covers(coverpath):
    if re.match(r".*cover\.jpg", coverpath) is None:
        abort(404, "Cover file not found")

    return static_file(coverpath, root=settings.MPD_SOURCE)

run(host='0.0.0.0', port=8080)
