import botlib
import re
import mpd
import sqlite3
from time import sleep
import threading, signal, sys, socket
from select import select
import settings

# TODO: Eliminate DB hacks and duped code (SQLite base class is annoying), add votekicking/adding, queueing of full albums
class MetalBot(botlib.Bot):
    quit = False

    def __init__(self, server, channel, nick, password=None):
        botlib.Bot.__init__(self, server, 6667, channel, nick)
        self.mpc = mpd.MPDClient(use_unicode = True)
        self.db = sqlite3.connect(settings.DB)
        self._reconnect()
        self.mpc.update()
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
                    print "Inserting %s" % song["file"]
                    cur.execute("INSERT INTO songlist (filename, artist, album, title) VALUES (?,?,?,?)", \
                            (song["file"], song["artist"], song["album"], song["title"]))
        print "Commit all that stuff"
        self.db.commit()
        print "End initialize of DB"
        

    def _reconnect(self):
        self.mpc.connect(settings.MPD_SERVER, settings.MPD_PORT)

    def _process_cmd(self, data):
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
            try:
                self.mpc.status()
            except ConnectionError:
                self._reconnect()

            try:
                fn = getattr(self, self.command + "_action")
                fn(self.args)
            except AttributeError:
                self.protocol.privmsg(self.channel, u"Sorry, '{0}' means nothing to me".format(self.command))

    @staticmethod
    def getsongid(filename):
        db = sqlite3.connect(settings.DB)
        cur = db.cursor()
        cur.execute("SELECT id FROM songlist WHERE filename=?", (filename,))
        row = cur.fetchone()
        if row is not None:
            return row[0]

    def hello_action(self, args):
        self.protocol.privmsg(self.channel, u"Hello {0}!".format(self.username))

    def playing_action(self, args):
        s = self.player_status
        if s["state"] != "play":
            self.protocol.privmsg(self.channel, "Nothing's playing at the moment")
        else:
            s = self.mpc.currentsong()
            sid = MetalBot.getsongid(s["file"])
            self.protocol.privmsg(self.channel, u"Now playing [{0}]: {1} - {2}".format(sid, s["artist"], s["title"]))

    def next_action(self, args):
        s = self.player_status
        if "nextsong" in s:
            s = self.mpc.playlistinfo(int(s["nextsong"]))[0]
            sid = MetalBot.getsongid(s["file"])
            self.protocol.privmsg(self.channel, u"Next up [{0}]: {1} - {2}".format(sid, s["artist"], s["title"]))
        else:
            self.protocol.privmsg(self.channel, "Nothing appears to be up next")

    def downvote_action(self, args):
        self._vote(args, -1)

    def upvote_action(self, args):
        self._vote(args, 1)

    def undovote_action(self, args):
        self._vote(args, 0)

    def _vote(self, args, vote):
        if len(args) < 1:
            return

        cur = self.db.cursor()
        cur.execute("INSERT OR REPLACE INTO votes (id, username, val) VALUES (?, ?, ?)", (args[0], self.username, vote,))
        self.db.commit()
        cur.execute("SELECT artist, title FROM songlist WHERE id=?", (args[0],))
        row = cur.fetchone()
        if row is not None:
            if vote == -1:
                s = "a downvote"
            elif vote == 1:
                s = "an upvote"
            else:
                s = "an abstention"
            self.protocol.privmsg(self.channel, u"Recorded {0} from {1}, for [{2}]: {3} {4}".format(s, self.username, args[0], row[0], row[1]))

    def find_action(self, args):
        if len(args) < 2:
            return

        tag = args[0]
        if not any(tag in s for s in ["artist", "album", "song", "any"]):
            return

        tofind = " ".join(args[1:])
        songs = self.mpc.search(tag, tofind)
        cur = self.db.cursor()
        i = 0
        for s in songs:
            sid = MetalBot.getsongid(s["file"])
            self.protocol.privmsg(self.username, u"[{0}]: {1} - {2} - {3}".format(unicode(sid), s["artist"], s["album"], s["title"]))
            if i > 30:
                return
            # Anti-flood
            if i % 5 == 0 and i != 0:
                sleep(1)
            i += 1

    def queue_action(self, args):
        if len(args) < 1:
            return

        id = args[0]
        cur = self.db.cursor()
        cur.execute("SELECT COUNT(*) FROM songlist WHERE id=?", (id, ))
        if cur.fetchone()[0] > 0:
            cur.execute("INSERT INTO queue (songid, username) VALUES (?, ?)", (id, self.username, ));
            self.db.commit()
            self._requeue()


    def _requeue(self):
        cur = self.db.cursor()
        self._update_status()

        cur.execute("SELECT filename FROM queue INNER JOIN songlist ON songlist.id=queue.songid ORDER BY queue.id")
        queue = cur.fetchall()
        nextpos = int(self.mpc.status()["nextsong"])
        for queueentry in queue:
            filename = queueentry[0]
            songs = self.mpc.playlistfind("filename", filename)
            if len(songs) > 0:
                song = songs[0]
                #print "Queue entry is %s, song pos is %s, songid is %s" % (filename, song["id"], song["file"])
                self.mpc.moveid(song["id"], unicode(nextpos))
                #print "Requeued song %s to position %s\n" % (song["id"], nextpos)
                nextpos += 1

    def help_action(self, args):
            self.protocol.privmsg(self.username, "\m/ ANDY'S METAL BOT - THE QUICKEST WAY TO GO DEAF ON #parthenon_devs \m/")
            self.protocol.privmsg(self.username, "!metalbot playing - displays current track with ID")
            self.protocol.privmsg(self.username, "!metalbot next - displays next track")
            self.protocol.privmsg(self.username, "!metalbot <up|down|neutral>vote <songid> - adds your thumbs-up, down, neutral vote to this song")
            sleep(1) # Antiflood
            self.protocol.privmsg(self.username, "!metalbot find <artist|album|song|any> <title> - finds music and PMs you")
            self.protocol.privmsg(self.username, "!metalbot queue <songid> - queues the specified song for playing next")
            self.protocol.privmsg(self.username, "Stream URL ---> http://andy.internal:8000")

    # I make a new DB connection every time because you can't reuse the same one in multiple threads
    def _update_status(self):
        db = sqlite3.connect(settings.DB)
        cur = db.cursor()
        self.player_status = self.mpc.status()
        if self.player_status["state"] == "play":
            s = self.mpc.currentsong()
            self.currentsong = MetalBot.getsongid(s["file"])

            cur.execute("DELETE FROM queue WHERE songid = %d" % self.currentsong)
            db.commit()

    def thread_listener(self):
        mpc = mpd.MPDClient(use_unicode = True)
        mpc.connect(settings.MPD_SERVER, settings.MPD_PORT)
        mpc.idletimeout = 2
        mpc.send_idle()
        while not self.quit:
            (i, o, e) = select([mpc], [], [], 1)
            for sock in i:
                if sock == mpc:
                    event = mpc.fetch_idle()
                    mpc.send_idle()
                    if event[0] == "player":
                        self._update_status()

    def handle_controlc(self, signal, frame):
        self.quit = True
        sys.exit(0)

if __name__ == "__main__":
    bot = MetalBot(settings.SERVER, settings.CHANNEL, settings.NICK)
    signal.signal(signal.SIGINT, bot.handle_controlc)
    interface_thread = threading.Thread(target=bot.thread_listener)
    interface_thread.start()

    try:
        bot.run()
    except Exception as e:
        bot.quit = True
        raise e
