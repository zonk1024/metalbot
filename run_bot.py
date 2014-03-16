#!/usr/bin/python

from metalbot import settings
from metalbot.ircbot import MetalBot

if __name__ == "__main__":
    bot = MetalBot(settings.SERVER, settings.CHANNEL, settings.NICK)
    bot.run()
