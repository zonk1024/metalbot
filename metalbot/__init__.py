import botlib
from time import sleep
import threading, signal, sys, socket
import settings
import re
from utils import MPDInterface

class MetalBot(botlib.Bot):
    quit = False
    msg_counter = 0

    def __init__(self, server, channel, nick, password=None):
        botlib.Bot.__init__(self, server, 6667, channel, nick)
        self.mpdi = MPDInterface()
        self.mpdi.initialize_db()

    def _process_cmd(self, data):
        # Little mod for Jon H :)
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

    def kick_action(self, args):
        if len(args) < 1:
            return

        for admin in settings.ADMINS:
            if args[0].lower() == admin.lower():
                self._privmsg(self.channel, "{0}: {1}".format(self.username, settings.GO_TO_HELL_MSG))
                return

        if len(args) == 2:
            comment = " ".join(args[1:])
        else:
            comment = "Bye"

        self.protocol.send("KICK {0} {1} {2}".format(self.channel, args[0], comment))

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

    def showqueue_action(self, args):
        queue = self.mpdi.get_queue()
        for qe in queue:
            self._privmsg(self.channel, u"[{0}]: {1} - {2} - {3}".format(qe["sid"], qe["artist"], qe["album"], qe["title"]))
        
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
        self._privmsg(self.username, "!metalbot latest - shows the top 50 latest songs")
        self._privmsg(self.username, "!metalbot kick <nick> [comment] - kicks out the riffraff")
        self._privmsg(self.username, "Stream URL ---> http://andy.internal:8000")
        self._privmsg(self.username, "Station URL ---> http://andy.internal:8080")

    def linkload_action(self, args):
        if self.username in settings.ADMINS:
            self.mpdi.load_links()

    def faves_action(self, args):
        self._privmsg(self.channel, "The top upvotes are as follows:")
        for f in self.mpdi.top_upvotes(10):
            self._privmsg(self.channel, u"[{0}]: {1} - {2} - {3}".format(s["sid"], s["artist"], s["album"], s["title"]))

    def latest_action(self, args):
        self._privmsg(self.username, "The latest available songs are as follows:")
        for s in self.mpdi.latest(50):
            self._privmsg(self.username, u"[{0}]: {1} - {2} - {3}".format(s["sid"], s["artist"], s["album"], s["title"]))

    def say_action(self, args):
        tosay = " ".join(args)
        self._privmsg(self.channel, tosay)
        
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
