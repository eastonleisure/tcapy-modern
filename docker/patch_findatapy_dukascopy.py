"""Fix error handling in the pinned findatapy 0.1.19's Dukascopy downloader.

tcapy pins findatapy 0.1.19 (newer releases pull in dependencies that no longer install on Python 3.7). Its Dukascopy
downloader mishandles failures. Fixed here, at image build time:
- `fetch_tick` never checked the HTTP status, so 403/404/5xx pages were treated as tick data, failed to decompress
  and that hour was silently dropped. Responses containing the text 'error' were retried, but that path never
  incremented the attempt counter, so it could loop forever.
- `download_tick`: if every multithreaded download attempt failed, `tick_list` was never assigned, raising
  UnboundLocalError instead of returning no data.
Note: Dukascopy's CDN currently answers findatapy's plain requests with 403 Forbidden. That is deliberately NOT worked
around here (upstream findatapy >= 0.1.37 sends a browser User-Agent); with these fixes a blocked download is reported
as a failed download instead of crashing or retrying forever.

The script checks the findatapy version and that each piece of code it changes is exactly as expected, so a different
findatapy fails the image build loudly instead of being patched incorrectly.
"""
import os
import sys

import findatapy

EXPECTED_VERSION = '0.1.19'

pkg = os.path.dirname(findatapy.__file__)
web_py = os.path.join(pkg, 'market', 'datavendorweb.py')
const_py = os.path.join(pkg, 'util', 'dataconstants.py')


def version():
    try:
        import importlib_metadata as md
    except ImportError:
        import importlib.metadata as md
    return md.version('findatapy')


def replace_once(text, old, new, label):
    n = text.count(old)
    if n != 1:
        sys.exit('patch_findatapy_dukascopy: expected exactly 1 match for %s, found %d - findatapy changed?' % (label, n))
    return text.replace(old, new)


if version() != EXPECTED_VERSION:
    sys.exit('patch_findatapy_dukascopy: written for findatapy %s, found %s' % (EXPECTED_VERSION, version()))

web = open(web_py).read()

# --- fetch_tick: check status codes, stop on refusals, count every attempt
old_fetch = """        # Try up to 5 times to download
        while i < 20:
            try:
                tick_request = requests.get(tick_url, timeout = 10)

                tick_request_content = tick_request.content
                tick_request.close()

                # Can sometimes get back an error HTML page, in which case retry
                if 'error' not in str(tick_request_content.decode("latin1")):
                    break
            except Exception as e:
                logger.warning("Problem downloading.. " + str(e))
                i = i + 1
                time.sleep(i * 3)

        if (tick_request_content is None):"""

new_fetch = """        # Try up to 20 times to download
        while i < 20:
            try:
                tick_request = requests.get(tick_url, timeout = 10)

                status_code = tick_request.status_code
                tick_request_content = tick_request.content
                tick_request.close()

                # patched: no file for this hour (eg. market closed) - don't retry
                if status_code == 404:
                    logger.warning("Error downloading.. " + tick_url + " returned 404 URL not found message! "
                                   "Are you sure Dukascopy has this asset?")
                    tick_request_content = None
                    break

                # patched: access refused - permanent, so retrying only delays the failure
                if status_code in (401, 403):
                    logger.error("Error downloading.. " + tick_url + " returned HTTP " + str(status_code) +
                                 " - Dukascopy refused the request")
                    tick_request_content = None
                    break

                # patched: only accept successful responses (a 403/5xx page is not tick data)
                if status_code == 200 and 'error' not in str(tick_request_content.decode("latin1")):
                    break

                logger.warning("Problem downloading.. " + tick_url + " returned HTTP " + str(status_code))
                tick_request_content = None
            except Exception as e:
                logger.warning("Problem downloading.. " + str(e))
                tick_request_content = None

            # patched: count every failed attempt (previously an error page retried forever)
            i = i + 1
            time.sleep(i * 3)

        if (tick_request_content is None):"""

web = replace_once(web, old_fetch, new_fetch, 'fetch_tick retry loop')

# --- download_tick: tick_list must exist even when every multithreaded attempt fails
web = replace_once(web,
"""        if multi_threaded:

            completed = False
""",
"""        if multi_threaded:

            completed = False
            tick_list = []  # patched: stays empty (-> no data) if every attempt below fails
""", 'download_tick multithreaded block')

open(web_py, 'w').write(web)

# Drop stale bytecode so the patched sources are what gets imported
for d in (os.path.join(pkg, 'market', '__pycache__'), os.path.join(pkg, 'util', '__pycache__')):
    if os.path.isdir(d):
        for f in os.listdir(d):
            if f.startswith(('datavendorweb.', 'dataconstants.')):
                os.remove(os.path.join(d, f))

print('patch_findatapy_dukascopy: patched findatapy %s' % EXPECTED_VERSION)
