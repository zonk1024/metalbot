import botlib
import re
import mpd
import sqlite3
from time import sleep

class MetalBot(botlib.Bot):
    def __init__(self, server, channel, nick, password=None):
       botlib.Bot.__init__(self, server, 6667, channel, nick)
       self.mpc = mpd.MPDClient(use_unicode = True)
       self.db = sqlite3.connect("bot.db")
       self._reconnect()
       self.mpc.update()
       self.initialize_db()

    def initialize_db(self):
        songs = self.mpc.listallinfo()
        cur = self.db.cursor()
        for song in songs:
            if "file" in song:
                cur.execute("SELECT COUNT(*) FROM songlist WHERE filename=?", (song["file"], ))
                if cur.fetchone()[0] == 0:
                    print "Inserting %s" % song["file"]
                    cur.execute("INSERT INTO songlist (filename, artist, album, title) VALUES (?,?,?,?)", \
                            (song["file"], song["artist"], song["album"], song["title"]))
        self.db.commit()
        

    def _reconnect(self):
        self.mpc.connect("localhost", 6600)

    def _process_cmd(self, data):
        m = re.search(r"^:([^!]+)!.*:!metalbot (\w+)(?: ([^\r\n]*))?", data)
        if m:
            self.username = m.group(1)
            self.command = m.group(2).lower()
            if m.group(3) is not None:
                self.args = m.group(3).split(" ")
            else:
                self.args = []
            return True
        else:
            return False

    def __actions__(self):
        botlib.Bot.__actions__(self)
 
        if botlib.check_found(self.data, "!metalbot"):
            if self._process_cmd(self.data):
                fn = getattr(self, self.command + "_action")
                try:
                    self.mpc.status()
                except ConnectionError:
                    self._reconnect()

                try:
                    fn(self.args)
                except AttributeError:
                    self.protocol.privmsg(self.channel, "Sorry, '{0}' means nothing to me".format(self.command))


    def hello_action(self, args):
        self.protocol.privmsg(self.channel, "Hello {0}!".format(self.username))

    def playing_action(self, args):
        s = self.mpc.status()
        if s["state"] != "play":
            self.protocol.privmsg(self.channel, "Nothing's playing at the moment")
        else:
            s = self.mpc.currentsong()
            cur = self.db.cursor()
            cur.execute("SELECT id FROM songlist WHERE filename=?", (s["file"],))
            sid = cur.fetchone()[0]

            self.protocol.privmsg(self.channel, "Now playing [{0}]: {1} - {2}".format(sid, s["artist"], s["title"]))

    def next_action(self, args):
        s = self.mpc.next()
        self.playing_action(args)

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

    def find_action(self, args):
        if len(args) < 2:
            return

        tag = args[0]
        tofind = " ".join(args[1:])
        songs = self.mpc.search(tag, tofind)
        cur = self.db.cursor()
        i = 0
        for s in songs:
            cur.execute("SELECT id FROM songlist WHERE filename=?", (s["file"],))
            sid = cur.fetchone()[0]
            self.protocol.privmsg(self.username, "[{0}]: {1} - {2} - {3}".format(sid, s["artist"], s["album"], s["title"]))
            if i > 30:
                return
            if i % 5 == 0 and i != 0:
                sleep(1)
            i = i + 1

    def queue_action(self, args):
        if len(args) < 1:
            return

        id = args[0]
        cur = self.db.cursor()
        cur.execute("INSERT INTO queue (songid, username) VALUES (?, ?)", (id, self.username));
        self.db.commit()

        self._requeue()


    def _requeue(self):
        cur.execute("SELECT filename FROM queue INNER JOIN songlist ON songlist.id=queue.songid ORDER BY queue.id")
        while 

        cur.execute("SELECT filename FROM songlist WHERE id=?", (id,))
        filename = cur.fetchone()[0]
        songs = self.mpc.playlistfind("filename", filename)
        if len(songs) > 0:
            song = songs[0]
            nextpos = self.mpc.status()["nextsong"]
            print "Found song {0} at pos {1}, moving to pos {2}\n".format(filename, song["pos"], nextpos)
            if song["pos"] != 1:
                self.mpc.move(song["pos"], nextpos)

    def help_action(self, args):
            self.protocol.privmsg(self.username, "\m/ ANDY'S METAL BOT - THE QUICKEST WAY TO GO DEAF ON #parthenon_devs \m/")
            self.protocol.privmsg(self.username, "!metalbot playing - displays current track with ID")
            self.protocol.privmsg(self.username, "!metalbot next - plays next track")
            self.protocol.privmsg(self.username, "!metalbot <up|down|neutral>vote <songid> - adds your thumbs-up, down, neutral vote to this song")
            sleep(1)
            self.protocol.privmsg(self.username, "!metalbot find <artist|album|song|any> <title> - finds music and PMs you")
            self.protocol.privmsg(self.username, "!metalbot queue <songid> - queues the specified song for playing next")
        
        

if __name__ == "__main__":
    bot = MetalBot("irc.freenode.net", "#parthenon_devs", "Metalbot")
    bot.run()

