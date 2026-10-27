"""Everything the server knows about Omio outside `omio/`: names, domains and the session cookie.

The rest of the package reads these values and never names the app itself.
"""

from __future__ import annotations

NAME = "Omio"
SLUG = "omio"
# The command and the prefix of every environment variable (OMIO_AUTH_TOKEN, OMIO_MCP_TOKEN ...).
CLI = "omio-mcp"
ENV = "OMIO"
# Requests may reach only these hosts and their subdomains. Their cookies are read from Chrome.
DOMAINS = ("omio.com",)
# Present only while signed in. The first is the cookie a pasted token sets.
SESSION_COOKIES = ("IamToken",)
COOKIE_DOMAIN = ".omio.com"
LOGIN_URL = "https://www.omio.com/"
# A final URL with one of these means the app signed the session out. Omio answers 204 instead (omio/auth.py).
LOGGED_OUT_MARKERS: tuple[str, ...] = ()
# An answer with one of these asks you to sign in again before a sensitive action. Omio has none.
RELOGIN_MARKERS: tuple[str, ...] = ()
# Paths of your Omio account that tools may read but never write. Common password, email and sign-in
# paths are refused for every app (core/account_guard.py); Omio adds none.
ACCOUNT_PATHS: tuple[str, ...] = ()
# REST routes live under this path, the same as on cotlet.dev.
API_PREFIX = "/api/v1/omio"
# Prepended to the MCP server's instructions: where an agent starts.
AGENT_START = (
    "Start with search_trips (city or station names work), then get_trip for its fares. "
    "start_booking never pays: it returns the checkout_url where the person pays on Omio."
)
