#!/usr/bin/python
import os
import sys
import site

ROOT = os.path.dirname(__file__)
NAME = os.path.basename(ROOT)

DIRS = (
    # Add the path to your virtualenv's site-packages directory right here
    "/usr/local/share/python-environments/bot/lib/python2.7/site-packages",
)
for DIR in DIRS:
    if os.path.exists(DIR):
        site.addsitedir(DIR)

# Add the path to your application, too.
sys.path.insert(0, ROOT)

os.environ["PYTHON_EGG_CACHE"] = os.path.join(ROOT, "egg-cache/")

import bottle
import metalfrontend
application = bottle.default_app()
