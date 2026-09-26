# Who may read the call. Any website open in Chrome can connect to localhost, so without this a page you happen to
# have open could read the call as it happens. The engine's WebSocket (subtitles.py) and the Weave server only
# answer our own pages: the overlay extension, and pages served from this Mac (overlay.html, the Weave app,
# extension/dev.html). Programs on this Mac send no Origin header (garden/relay.py, the iPhone app) and are fine.
import re

OURS = re.compile(r"^(chrome-extension://[a-p]{32}|https?://(localhost|127\.0\.0\.1|\[::1\])(:\d+)?)$")


def allowed(origin):
    return origin is None or bool(OURS.match(origin))
