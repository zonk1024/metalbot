import os, re
from bottle import route, run, debug, request, validate, static_file, error, abort,response
from bottle import jinja2_view as view, jinja2_template as template
from utils import MPDInterface
import json
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

    return dict(nextup = nextsongs, nowplaying = nowplaying, mpdurl = settings.MPD_URL)

@route("/covers/<coverpath:path>")
def covers(coverpath):
    if re.match(r".*cover\.jpg", coverpath) is None:
        abort(404, "Cover file not found")

    return static_file(coverpath, root=settings.MPD_SOURCE)

@route('/static/<filename:re:.*\.(?:js|css|jpg|png)$>')
def static(filename):
    return static_file(filename, root='static')

@route('/api/artists')
def api_artists():
    mpdi = MPDInterface()
    artists = mpdi.artists()
    for artist in artists:
        artist["albums"] = mpdi.albums(artist["artist"])

    response.content_type = "application/json"
    return json.dumps(artists)

@route('/api/songs/<artist>/<album>')
def api_songs(artist, album):
    mpdi = MPDInterface()
    songs = mpdi.songs(unicode(artist, "utf-8"), unicode(album, "utf-8"))

    response.content_type = "application/json"
    return json.dumps(songs)

@route("/api/queue/<id:int>")
def api_queue_add(id):
    mpdi = MPDInterface()
    mpdi.add_to_queue("WebUser", id)

@route("/api/queue")
def api_queue():
    mpdi = MPDInterface()
    queue = mpdi.get_queue()

    response.content_type = "application/json"
    return json.dumps(queue)

@route("/api/queue/<artist>/<album>")
def api_queue_album(artist, album):
    mpdi = MPDInterface()
    mpdi.add_album_to_queue("WebUser", unicode(artist, "utf-8"), unicode(album, "utf-8"))

@route("/api/upcoming/<numsongs:int>")
def api_upcoming(numsongs):
    mpdi = MPDInterface()
    nextsongs = mpdi.nextsong(number = numsongs)

    response.content_type = "application/json"
    return json.dumps(nextsongs)
    
@route("/api/currentsong")
def api_currentsong():
    mpdi = MPDInterface()
    nowplaying = mpdi.currentsong()
    if nowplaying is not None:
        if os.path.isfile(os.path.join(settings.MPD_SOURCE, os.path.dirname(nowplaying["file"]), "cover.jpg")):
            nowplaying["coverpath"] = u"/covers/{0}/cover.jpg".format(os.path.dirname(nowplaying["file"]))

    return nowplaying

def _check_secret(secret):
    if settings.SECRET == secret:
        return
    raise Exception("Secret is not correct, preventing load!")

@route("/initialize/<secret>")
def initialize_db(secret):
    _check_secret(secret)

    mpdi = MPDInterface()
    mpdi.initialize_db()

    return "Done!"

@route("/loadlinks/<secret>")
def initialize_db(secret):
    _check_secret(secret)

    mpdi = MPDInterface()
    mpdi.load_links()

    return "Done!"

if __name__ == "__main__":
    run(host='0.0.0.0', port=8080)
