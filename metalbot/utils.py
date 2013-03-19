import os, re
import mpd
import sqlite3
from select import select
import settings
from subprocess import call
import time,calendar

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

                    m = re.search(r"(\d{4})", song["date"])
                    if m:
                        song["date"] = m.group(1)
                    m = re.search(r"^(\d+)", str(song["track"]))
                    if m:
                        song["track"] = m.group(1)

                    song["lastmodified"] = calendar.timegm(time.strptime(song["last-modified"], "%Y-%m-%dT%H:%M:%SZ"))
                    cur.execute("INSERT INTO songlist (filename, artist, album, title, track, date, lastmodified) VALUES (?,?,?,?,?,?,?)", \
                            (song["file"], song["artist"], song["album"], song["title"], str(song["track"]), str(song["date"]),
                            str(int(song["lastmodified"]))))

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

    def latest(self, num)
        try:
            num = int(num)
        except ValueError:
            return []

        cur = self.db.cursor()
        cur.execute("SELECT id AS sid, filename, title, artist FROM songlist ORDER BY lastmodified DESC LIMIT %s" % num)
        
        return self._to_dict_list(cur.fetchall())

    def _to_dict_list(self, rows):
        a = []
        for r in rows:
            d = {}
            for k in r.keys():
                d[k] = r[k]
            a.append(d)

        return a

