import botlib
import re
import mpd
import sqlite3
from time import sleep
import threading, signal, sys, socket, os
from select import select
import settings
from subprocess import call

class MPDInterface():
    def __init__(self):
        self.mpc = mpd.MPDClient(use_unicode = True)
        self.db = sqlite3.connect(settings.DB)
        self.db.row_factory = sqlite3.Row
        self.reconnect()
        self.idling = False

    def load_links(self):
        for mydir in settings.LINK_DIRS:
            os.system("cp -as " + mydir + "/* " + settings.MPD_SOURCE)
        self.mpc.update()
        os.system("mpc crop")
        os.system("mpc ls | mpc add")
        self.mpc.shuffle()
        self.mpc.play()
        self.initialize_db()
        self._requeue()
        
    def initialize_db(self):
        print "Start initialize of DB...getting songs"
        songs = self.mpc.listallinfo()
        loaded_songs = []

        cur = self.db.cursor()
        cur.execute("SELECT filename FROM songlist")
        while True:
            row = cur.fetchone()
            if row is None:
                break

            loaded_songs.append(row[0])
        
        print "Start iteration..."
        for song in songs:
            if "file" in song and "title" in song:
                if song["file"] not in loaded_songs:
                    if "date" not in song:
                        song["date"] = ""
                    if "track" not in song:
                        song["track"] = ""

                    cur.execute("INSERT INTO songlist (filename, artist, album, title, track, date) VALUES (?,?,?,?,?,?)", \
                            (song["file"], song["artist"], song["album"], song["title"], str(song["track"]), str(song["date"])))

        print "Commit all that stuff"
        self.db.commit()
        print "End initialize of DB"

        print "Requeuing..."
        self._requeue()
        print "End requeue"

    def reconnect(self): 
        try:
            self.mpc.status()
        except:
            self.mpc.connect(settings.MPD_SERVER, settings.MPD_PORT)

    def getsongid(self, filename):
        cur = self.db.cursor()
        cur.execute("SELECT id FROM songlist WHERE filename=?", (filename,))
        row = cur.fetchone()
        if row is not None:
            return row[0]
        return None

    def currentsong(self):
        s = self.mpc.status()
        if s["state"] == "play":
            song = self.mpc.currentsong()
            song["sid"] = self.getsongid(song["file"])
            return song
        else:
            return None

    def nextsong(self, number = 1):
        s = self.mpc.status()
        nextsongs = []
        if "nextsong" in s:
            for songpos in range(int(s["nextsong"]), int(s["nextsong"]) + number):
                song = self.mpc.playlistinfo(songpos)[0]
                song["sid"] = self.getsongid(song["file"])
                nextsongs.append(song)
            return nextsongs
        else:
            return None
    
    def vote(self, songid, username, vote):
        cur = self.db.cursor()
        cur.execute("SELECT * FROM songlist WHERE id=?", (songid,))
        row = cur.fetchone()
        if row is not None:
            cur.execute("INSERT OR REPLACE INTO votes (id, username, val) VALUES (?, ?, ?)", (songid, username, vote,))
            self.db.commit()
            return row
        else:
            return None

    def search(self, tag, tofind):
        songs = self.mpc.search(tag, tofind)
        for song in songs:
            song["sid"] = self.getsongid(song["file"])
        return songs

    def add_to_queue(self, username, id):
        cur = self.db.cursor()
        cur.execute("SELECT COUNT(*) FROM songlist WHERE id=?", (id, ))
        if cur.fetchone()[0] > 0:
            cur.execute("SELECT COUNT(*) FROM queue WHERE songid=?", (id, ))
            if cur.fetchone()[0] == 0:
                cur.execute("INSERT INTO queue (songid, username) VALUES (?, ?)", (id, username, ));
                self.db.commit()
                self._requeue()

    def add_album_to_queue(self, username, artist, album):
        cur = self.db.cursor()
        cur.execute("SELECT * FROM songlist WHERE artist=? AND album=? ORDER BY track", (artist, album,))
        rows = self._to_dict_list(cur.fetchall())
        for row in rows:
            cur.execute("SELECT COUNT(*) FROM queue WHERE songid=?", (row["id"], ))
            if cur.fetchone()[0] == 0:
                cur.execute("INSERT INTO queue (songid, username) VALUES (?, ?)", (row["id"], username, ));
                self.db.commit()
                self._requeue()

    def get_queue(self):
        cur = self.db.cursor()
        cur.execute("SELECT songid AS sid, filename, title, artist FROM queue INNER JOIN songlist ON songlist.id=queue.songid ORDER BY queue.id")
        
        return self._to_dict_list(cur.fetchall())

    def _requeue(self):
        cur = self.db.cursor()
        self._update_status()

        cur.execute("SELECT filename FROM queue INNER JOIN songlist ON songlist.id=queue.songid ORDER BY queue.id")
        queue = cur.fetchall()
        status = self.mpc.status()
        nextpos = -1
        for queueentry in queue:
            filename = queueentry[0]
            songs = self.mpc.playlistfind("filename", filename)
            if len(songs) > 0:
                song = songs[0]
                self.mpc.moveid(song["id"], unicode(nextpos))
                nextpos -= 1
    
    def listen_for_events(self):
        if not self.idling:
            self.mpc.idletimeout = 2
            self.mpc.send_idle()
            self.idling = True

        (i, o, e) = select([self.mpc], [], [], 1)
        for sock in i:
            if sock == self.mpc:
                event = self.mpc.fetch_idle()
                if event[0] == "player":
                    self._update_status()
                self.mpc.send_idle()

    def _update_status(self):
        cur = self.db.cursor()
        try:
            self.mpc.status()
        except mpd.ConnectionError:
            self.reconnect()
        self.player_status = self.mpc.status()
        if self.player_status["state"] == "play":
            s = self.mpc.currentsong()
            sid = self.getsongid(s["file"])
            cur.execute("DELETE FROM queue WHERE songid = %d" % sid)
            self.db.commit()
            cur.execute("SELECT SUM(val) FROM votes WHERE id=%d" % sid)
            row = cur.fetchone()
            if row is not None and row[0] is not None:
                if row[0] < -5:
                    self.mpc.next()

    def artists(self):
        cur = self.db.cursor()
        cur.execute("SELECT DISTINCT artist FROM songlist ORDER BY artist")

        return self._to_dict_list(cur.fetchall())

    def albums(self, artist):
        cur = self.db.cursor()
        cur.execute("SELECT DISTINCT date, album FROM songlist WHERE artist=? ORDER BY date", (artist,))

        return self._to_dict_list(cur.fetchall())

    def songs(self, artist, album):
        cur = self.db.cursor()
        cur.execute("SELECT * FROM songlist WHERE artist=? AND album=? ORDER BY track", (artist, album, ))
        
        return self._to_dict_list(cur.fetchall())

    def top_upvotes(self, num):
        try:
            num = int(num) 
        except ValueError:
            return []

        cur = self.db.cursor()
        cur.execute("SELECT id AS sid, filename, title, artist FROM votes INNER JOIN songlist USING (id) WHERE val > 0 ORDER BY val DESC LIMIT %s" % num)
        
        return self._to_dict_list(cur.fetchall())

    def move_to_next(self):
        self.mpc.next()

    def _to_dict_list(self, rows):
        a = []
        for r in rows:
            d = {}
            for k in r.keys():
                d[k] = r[k]
            a.append(d)

        return a

class MetalBot(botlib.Bot):
    quit = False
    msg_counter = 0

    def __init__(self, server, channel, nick, password=None):
        botlib.Bot.__init__(self, server, 6667, channel, nick)
        self.mpdi = MPDInterface()
        self.mpdi.initialize_db()

    def _process_cmd(self, data):
        if data.lower().find("shopigniter") != -1:
            self._privmsg(self.channel, u"Fuck Shopigniter \m/")

        for reg in [r"^:([^!]+)!.*:!metalbot (\w+)(?: ([^\r\n]*))?", 
                    r"^:([^!]+)!.*PRIVMSG {0} :(\w+)(?: ([^\r\n]*))?".format(settings.NICK),
                    ]:
            m = re.search(reg, data)
            if m:
                self.username = m.group(1)
                self.command = m.group(2).lower()
                if m.group(3) is not None:
                    self.args = m.group(3).split(" ")
                else:
                    self.args = []
                return True
        return False

    def __actions__(self):
        botlib.Bot.__actions__(self)
 
        if self._process_cmd(self.data):
            self.mpdi.reconnect()

            try:
                fn = getattr(self, self.command + "_action")
                fn(self.args)
            except AttributeError:
                self._privmsg(self.channel, u"Sorry, '{0}' means nothing to me".format(self.command))

    def hello_action(self, args):
        self._privmsg(self.channel, u"Hello {0}!".format(self.username))

    def playing_action(self, args):
        song = self.mpdi.currentsong()
        if song is None:
            self._privmsg(self.channel, "Nothing's playing at the moment")
        else:
            self._privmsg(self.channel, u"Now playing [{0}]: {1} - {2}".format(song["sid"], song["artist"], song["title"]))

    def next_action(self, args):
        songs = self.mpdi.nextsong()
        if songs is None:
            self_privmsg(self.channel, "Nothing appears to be up next")
        else:
            song = songs[0]
            self._privmsg(self.channel, u"Next up [{0}]: {1} - {2}".format(song["sid"], song["artist"], song["title"]))

    def downvote_action(self, args):
        self._vote(args, -1)

    def upvote_action(self, args):
        self._vote(args, 1)

    def undovote_action(self, args):
        self._vote(args, 0)

    # Andy can do this, no one else.
    def nuclearstrike_action(self, args):
        if self.username in settings.ADMINS:
            self._vote(args, -999)
        else:
            self._privmsg(self.username, u"Sorry, only configured admins can perform nuclear strikes")

    def _vote(self, args, vote):
        if len(args) < 1:
            return

        song = self.mpdi.vote(args[0], self.username, vote)
        if song is not None:
            if vote == -1:
                s = "a downvote"
            elif vote == 1:
                s = "an upvote"
            elif vote < 100:
                self._sendnuke()
                s = "a nuclear strike"
            else:
                s = "an abstention"
            self._privmsg(self.channel, u"Recorded {0} from {1}, for [{2}]: {3} - {4}".format(s, self.username, args[0], song["artist"], song["title"]))

    def _sendnuke(self):
        nuke = """
              ..-^~~~^-..
            .~           ~.
           (;:           :;)
            (:           :)
              ':._   _.:'
                  | |
                (=====)
                  | |
                  | |
                  | |
               ((/   \))
"""
        for line in nuke.split("\n"):
            self._privmsg(self.channel, line)

    def find_action(self, args):
        if len(args) < 2:
            return

        tag = args[0]
        if not any(tag in s for s in ["artist", "album", "title", "any"]):
            return

        tofind = " ".join(args[1:])
        songs = self.mpdi.search(tag, tofind)
        i = 0
        for s in songs:
            self._privmsg(self.username, u"[{0}]: {1} - {2} - {3}".format(s["sid"], s["artist"], s["album"], s["title"]))
            if i > 50:
                return
            i += 1

    def queue_action(self, args):
        if len(args) < 1:
            return

        id = args[0]
        self.mpdi.add_to_queue(self.username, id)

    def showqueue_action(self):
        queue = self.mpdi.get_queue()
        for qe in queue:
            self._privmsg(self.channel, u"[{0}]: {1} - {2} - {3}".format(s["sid"], s["artist"], s["album"], s["title"]))
        
    # Messaging with antiflood protection
    def _privmsg(self, username, message):
        if self.msg_counter % 5 == 0 and self.msg_counter != 0:
            sleep(1)

        self.protocol.privmsg(username, message)
        self.msg_counter += 1
        
    def help_action(self, args):
        self._privmsg(self.username, "\m/ ANDY'S METAL BOT - THE QUICKEST WAY TO GO DEAF ON #parthenon_devs \m/")
        self._privmsg(self.username, "!metalbot playing - displays current track with ID")
        self._privmsg(self.username, "!metalbot next - displays next track")
        self._privmsg(self.username, "!metalbot <up|down|undo>vote <songid> - adds your thumbs-up, down, neutral vote to this song")
        self._privmsg(self.username, "!metalbot find <artist|album|title|any> <title> - finds music and PMs you")
        self._privmsg(self.username, "!metalbot queue <songid> - queues the specified song for playing next")
        self._privmsg(self.username, "!metalbot showqueue - shows everything queued up")
        self._privmsg(self.username, "!metalbot faves - shows the top 10 upvoted songs")
        self._privmsg(self.username, "Stream URL ---> http://andy.internal:8000")
        self._privmsg(self.username, "Station URL ---> http://andy.internal:8080")

    def linkload_action(self, args):
        if self.username in settings.ADMINS:
            self.mpdi.load_links()

    def faves_action(self, args):
        self._privmsg(self.channel, "The top upvotes are as follows:")
        for f in self.mpdi.top_upvotes(10):
            self._privmsg(self.channel, u"[{0}]: {1} - {2} - {3}".format(s["sid"], s["artist"], s["album"], s["title"]))

    def thread_listener(self):
        mpdi = MPDInterface()
        while not self.quit:
            mpdi.listen_for_events()

    def handle_controlc(self, signal, frame):
        self.quit = True
        sys.exit(0)

if __name__ == "__main__":
    bot = MetalBot(settings.SERVER, settings.CHANNEL, settings.NICK)
    signal.signal(signal.SIGINT, bot.handle_controlc)
    interface_thread = threading.Thread(target=bot.thread_listener)
    interface_thread.start()

#    try:
    bot.run()
#    except Exception as e:
#    bot.quit = True
#    raise e
