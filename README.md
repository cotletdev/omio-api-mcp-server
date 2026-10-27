# Omio API and MCP server, self-hosted

<!-- mcp-name: dev.cotlet/omio -->

An **Omio API** and an **Omio MCP server** you run on your own computer, in Python, on the session of your own Google Chrome. All 16 Omio tools we run in production at [Cotlet](https://cotlet.dev/integrations/omio-api-mcp-server): places, train, bus, flight and ferry search, the cheapest day of a route, fares with their refund and exchange conditions, round trips, a booking up to the checkout link, Your Bookings and saved travelers.

Omio has no public API for your own account. Its Search API sits in the affiliate programme, for partners, and Your Bookings, saved travelers and checkout exist only on omio.com and in the Omio app. This repo gives you:

- **MCP server** for Claude Code, Claude Desktop, Cursor, Codex and any MCP client, over stdio or HTTP. [Setup](#mcp-server)
- **REST API** on `http://127.0.0.1:8787/api/v1/omio`, with OpenAPI docs at `/docs`. [Setup](#rest-api)
- **Python**: `call("search_trips", {"from": "Berlin", "to": "Munich", "date": "2026-11-19"})`, plus 8 ready scripts in [`examples/`](https://github.com/cotletdev/omio-api-mcp-server/blob/main/examples/).

Nothing here pays. `start_booking` reserves the fare and returns a `checkout_url`, and you pay on omio.com yourself.

It is for technical people who want to run it themselves, **for noncommercial use only** ([license](#license)). If you want it running 24/7 on a server, kept working when Omio changes its site, for a team or a business, use the [hosted version at cotlet.dev](https://cotlet.dev/integrations/omio-api-mcp-server).

[![Omio MCP server](https://img.shields.io/badge/Omio%20MCP-16%20tools-6d4aef)](#all-16-tools)
[![Python 3.11+](https://img.shields.io/badge/python-3.11%2B-141318)](#requirements)
[![License: PolyForm Noncommercial 1.0.0](https://img.shields.io/badge/license-PolyForm%20Noncommercial-141318)](https://github.com/cotletdev/omio-api-mcp-server/blob/main/LICENSE)

```bash
git clone https://github.com/cotletdev/omio-api-mcp-server.git && cd omio-api-mcp-server
python3 -m venv .venv && . .venv/bin/activate && pip install -e .
omio-mcp connect                                   # reads your Omio session from Chrome
omio-mcp call search_trips from=Berlin to=Munich date=2026-11-19 limit=5
claude mcp add omio -- "$PWD/.venv/bin/omio-mcp" mcp
```

## Contents

- [How it works](#how-it-works)
- [Requirements](#requirements)
- [Install](#install)
- [Connect your Chrome](#connect-your-chrome)
- [MCP server](#mcp-server)
- [REST API](#rest-api)
- [Python and the example scripts](#python-and-the-example-scripts)
- [All 16 tools](#all-16-tools)
- [Configuration](#configuration)
- [Security and your Omio account](#security-and-your-omio-account)
- [Errors](#errors)
- [Self-hosted or hosted](#self-hosted-or-hosted)
- [FAQ](#faq)
- [License](#license)

## How it works

```text
AI agent (MCP) / script (REST, Python) ──▶ omio-mcp on your computer ──your Omio cookies──▶ www.omio.com
                                                  ▲
                          omio-mcp connect ───────┘ reads them once from your Chrome (DevTools Protocol)
```

1. You sign in to Omio in your own Chrome, the way you always do (Omio mails you a 6-digit code).
2. `omio-mcp connect` attaches to that Chrome through the Chrome DevTools Protocol, reads the omio.com cookies and saves them to `~/.config/omio-api-mcp/session.json`, readable by your user only. Omio has no password, and this code never sees your mailbox.
3. Every tool call is a request to the endpoints Omio's own web app calls on `www.omio.com` (search, GraphQL, bookings, passengers) with those cookies, sent with [curl_cffi](https://github.com/lexiforest/curl_cffi), which copies Chrome's TLS fingerprint. No headless browser runs.

Cloudflare guards www.omio.com. Its `cf_clearance` cookie, which `connect` reads along with the session, belongs to your Chrome and your network. So run the server on the same computer and connection as the Chrome you connected. If Omio shows a bot check, open omio.com in that Chrome and run `omio-mcp connect` again.

Omio's sign-in cookie lasts about a year. When Omio signs you out, the server reads the cookies from Chrome again, if Chrome is open with remote debugging on.

## Requirements

- Python 3.11 or newer.
- Google Chrome 144 or newer, signed in to Omio. Any Chrome or Chromium works with a [debugging port](#option-b-a-chrome-with-a-debugging-port).
- macOS, Linux or Windows.
- An Omio account. A free traveler account is all the tools need.

## Install

```bash
git clone https://github.com/cotletdev/omio-api-mcp-server.git
cd omio-api-mcp-server
python3 -m venv .venv
. .venv/bin/activate              # Windows: .venv\Scripts\activate
pip install -e .
omio-mcp --version
```

With [uv](https://docs.astral.sh/uv/): `uv venv && uv pip install -e .`, then `uv run omio-mcp ...`.

Setting it up with an AI agent (Claude Code, Codex, Cursor)? Open it in this folder and ask it to set up the repo: [`AGENTS.md`](https://github.com/cotletdev/omio-api-mcp-server/blob/main/AGENTS.md) tells it every step, and it asks you only for the steps in Chrome.

To update: `git pull && pip install -e .`. We copy every change of the hosted Omio tools into this repo.

## Connect your Chrome

### Option A: your everyday Chrome (recommended)

1. Open `chrome://inspect/#remote-debugging` in Chrome and switch **remote debugging** on. Chrome then accepts DevTools connections from programs on this computer, and asks you before each one.
2. Make sure you are signed in at [omio.com](https://www.omio.com) (your name shows in the top right).
3. Run:

   ```bash
   omio-mcp connect
   ```

4. Chrome asks whether to allow the connection. Click **Allow**.

```text
Saved 40 Omio cookies to /Users/you/.config/omio-api-mcp/session.json
Signed in to Omio as Ana Lopez (ana.lopez@example.com)
```

You can switch remote debugging off again afterwards. Leave it on if you want the server to pick up a new session by itself after Omio signs you out.

`connect` looks for Chrome's `DevToolsActivePort` file in the default profile folder. For Chrome Beta, Canary or a custom profile folder, pass `--profile-dir "<folder>"`.

### Option B: a Chrome with a debugging port

Chrome does not open a debugging port on your default profile, so start a separate one, sign in to Omio there once, and connect to it:

```bash
# macOS
"/Applications/Google Chrome.app/Contents/MacOS/Google Chrome" --remote-debugging-port=9222 --user-data-dir="$HOME/.chrome-omio"
# Linux
google-chrome --remote-debugging-port=9222 --user-data-dir="$HOME/.chrome-omio"
# Windows
"C:\Program Files\Google\Chrome\Application\chrome.exe" --remote-debugging-port=9222 --user-data-dir="%USERPROFILE%\.chrome-omio"

omio-mcp connect --cdp http://127.0.0.1:9222
```

`--cdp` also takes a `ws://` DevTools URL, for example of a Chrome on another machine reached over an SSH tunnel. Requests still leave from the machine that runs `omio-mcp`, and Cloudflare may give that machine a bot check.

### Option C: paste the cookie by hand

In Chrome open DevTools on omio.com, **Application > Cookies > https://www.omio.com**, copy the value of `IamToken`, then:

```bash
omio-mcp connect --token          # paste it, input is hidden
# or, without a session file:
export OMIO_AUTH_TOKEN=...
```

A pasted token is not refreshed on its own, and it carries no Cloudflare cookie, so Omio may answer with a bot check. Options A and B work better.

Check the session at any time:

```bash
omio-mcp status
```

## MCP server

The MCP server lists every tool with its input schema, a description written for agents, and hints. Read tools are marked read-only. The tools that reserve a fare or change saved travelers are marked so your client asks before running them.

### Claude Code

```bash
claude mcp add omio -- /path/to/omio-api-mcp-server/.venv/bin/omio-mcp mcp
# read only:
claude mcp add omio -- /path/to/omio-api-mcp-server/.venv/bin/omio-mcp mcp --read-only
```

### Claude Desktop

`~/Library/Application Support/Claude/claude_desktop_config.json` (macOS) or `%APPDATA%\Claude\claude_desktop_config.json` (Windows):

```json
{
  "mcpServers": {
    "omio": {
      "command": "/path/to/omio-api-mcp-server/.venv/bin/omio-mcp",
      "args": ["mcp"]
    }
  }
}
```

### Cursor

`~/.cursor/mcp.json`, the same block as Claude Desktop. A ready copy is in [`mcp.json`](https://github.com/cotletdev/omio-api-mcp-server/blob/main/mcp.json).

### Codex

`~/.codex/config.toml`:

```toml
[mcp_servers.omio]
command = "/path/to/omio-api-mcp-server/.venv/bin/omio-mcp"
args = ["mcp"]
```

### Over HTTP

`omio-mcp serve` also serves MCP over streamable HTTP at `http://127.0.0.1:8787/mcp`, for clients that take a URL:

```bash
omio-mcp serve
claude mcp add --transport http omio http://127.0.0.1:8787/mcp
```

Then ask your agent things like:

> *Compare train, bus and flight from Berlin to Munich next Thursday by price and travel time.*
>
> *Which day in the next three weeks is cheapest from Berlin to Munich, and what is the cheapest train that day?*
>
> *Price a round trip Berlin to Munich, out on Friday morning and back on Sunday evening, with my BahnCard 50.*
>
> *Reserve the cheapest refundable train from Berlin to Munich next Thursday for me and my saved companion, and send me the total and the checkout link.*

## REST API

```bash
omio-mcp serve                    # http://127.0.0.1:8787, MCP at /mcp, docs at /docs
```

Each tool has its own route under `/api/v1/omio`, the same paths as the hosted API at cotlet.dev, so code written against one works with the other. Path parts and the query string are arguments, and a JSON body adds the rest.

```bash
curl 'http://127.0.0.1:8787/api/v1/omio/places?query=Munich'
curl 'http://127.0.0.1:8787/api/v1/omio/trips/search?from=Berlin&to=Munich&date=2026-11-19&limit=5'
curl 'http://127.0.0.1:8787/api/v1/omio/trips/<trip_id>'
```

Any tool by name, body as its arguments:

```bash
curl -X POST http://127.0.0.1:8787/api/v1/omio/tools/get_price_calendar \
  -d '{"from": "Berlin", "to": "Munich", "start_date": "2026-11-10", "modes": ["train"]}'
```

- `GET /api/v1/omio/tools`: every tool with its route, input schema and an example answer.
- `GET /docs`: interactive OpenAPI docs, `GET /openapi.json` the schema, for n8n, Postman or a generated client.
- Answers are JSON. Prices are `{"amount": 86.0, "currency": "EUR"}`.

The server listens on `127.0.0.1` only. To reach it from another device of yours, set a token, and every request then needs `Authorization: Bearer <token>`:

```bash
OMIO_MCP_TOKEN=$(openssl rand -hex 24) omio-mcp serve --host 0.0.0.0
```

## Python and the example scripts

Straight from Python, no server needed:

```python
from omio_api_mcp import call
from omio_api_mcp.scripting import write_rows

found = call("search_trips", {"from": "Berlin", "to": "Munich", "date": "2026-11-19", "modes": ["train"]})
write_rows(found["trips"], "trains.csv")
trip = call("get_trip", {"trip_id": found["trips"][0]["trip_id"]})
print([(f["name"], f["price"], f["refundable"]) for f in trip["fares"]])
```

Or one tool from the shell: `omio-mcp call search_places query=Munich`, or with a JSON object.

Ready scripts in [`examples/`](https://github.com/cotletdev/omio-api-mcp-server/blob/main/examples/). Each takes `--help`:

| Script | What it does |
|---|---|
| [`search_places.py`](https://github.com/cotletdev/omio-api-mcp-server/blob/main/examples/search_places.py) | Cities, stations, airports and ports by name, with their place id. |
| [`compare_trips.py`](https://github.com/cotletdev/omio-api-mcp-server/blob/main/examples/compare_trips.py) | Cheapest and fastest train, bus and flight between two places on one day. `--out` saves every trip. |
| [`cheapest_day.py`](https://github.com/cotletdev/omio-api-mcp-server/blob/main/examples/cheapest_day.py) | Cheapest price per day for up to a month, then the cheapest trips on the best day. |
| [`trip_fares.py`](https://github.com/cotletdev/omio-api-mcp-server/blob/main/examples/trip_fares.py) | Fares of one trip with class, price and refund and exchange conditions. `--refundable`. |
| [`round_trip.py`](https://github.com/cotletdev/omio-api-mcp-server/blob/main/examples/round_trip.py) | Cheapest outbound leg and its return legs with the round-trip price, with a discount card if you have one. |
| [`book_to_checkout.py`](https://github.com/cotletdev/omio-api-mcp-server/blob/main/examples/book_to_checkout.py) | Reserves the cheapest (or cheapest refundable) fare for your saved travelers and prints the total and the checkout link. Pays nothing. `--dry-run` first. |
| [`export_bookings.py`](https://github.com/cotletdev/omio-api-mcp-server/blob/main/examples/export_bookings.py) | Your Bookings to CSV or JSON: route, departure, operator, status, total. |
| [`saved_travelers.py`](https://github.com/cotletdev/omio-api-mcp-server/blob/main/examples/saved_travelers.py) | Saved travelers with their discount cards, or `--cards bahncard` to find a card to add. |

```bash
python examples/cheapest_day.py Berlin Munich --start 2026-11-10 --modes train
python examples/book_to_checkout.py <trip_id> --refundable --dry-run
```

On a schedule, cron on your own computer works while it is on: `0 8 * * 1 cd ~/omio-api-mcp-server && .venv/bin/python examples/cheapest_day.py Berlin Munich --start 2026-12-01`.

## All 16 tools

Places take a name (`Berlin`) or a `place_id` from `search_places`. A search returns `trip_id` values, which `get_trip`, `list_return_trips` and `start_booking` take. `omio-mcp tools` prints this list, `omio-mcp tools --json` adds the input schemas.

### Places, trips and fares

| Tool | Access | REST route | What it does |
|---|---|---|---|
| `search_places` | read | `GET /places` | Cities, train and bus stations, airports and ferry ports Omio knows, by name. |
| `list_discount_cards` | read | `GET /discount-cards` | Rail and coach discount cards Omio prices in, such as BahnCard or Railcards, by operator. |
| `get_price_calendar` | read | `GET /price-calendar` | Cheapest one-way price per day and mode between two places, for up to a month. |
| `search_trips` | read | `GET /trips/search` | Trains, buses, flights and ferries between two places on a date, with times, duration, changes, operator and price. |
| `list_more_trips` | read | `GET /searches/{search_id}/more-trips` | Load later or earlier departures of a search's trains beyond the time window search_trips returned. |
| `list_return_trips` | read | `GET /trips/{trip_id}/return-trips` | Return legs Omio offers with one outbound leg of a round-trip search, with the round-trip price. |
| `get_trip` | read | `GET /trips/{trip_id}` | Legs of one trip and its fare options with their conditions: class, price, refundable, exchangeable. |

### Bookings

| Tool | Access | REST route | What it does |
|---|---|---|---|
| `start_booking` | write | `POST /bookings` | Reserve fares with the travelers' names and get the price breakdown and a checkout link. Pays nothing: the person finishes payment at checkout_url. |
| `get_booking` | read | `GET /bookings/{booking_id}` | Journey, travelers, fare conditions, status and price of one booking, paid or not yet paid. |
| `list_bookings` | read | `GET /bookings` | Bookings from Your Bookings with route, departure, operator and status. |

### Account and saved travelers

| Tool | Access | REST route | What it does |
|---|---|---|---|
| `get_account` | read | `GET /account` | The signed-in Omio account: name, email, when it was made and its marketing email setting. |
| `list_payment_methods` | read | `GET /payment-methods` | Payment methods saved on the account, by type and brand. Never card numbers. |
| `list_passengers` | read | `GET /passengers` | Travelers saved on the account, the account holder first, with their details and discount cards. |
| `add_passenger` | write | `POST /passengers` | Save a traveler on the account so bookings can use their details. |
| `update_passenger` | write | `PATCH /passengers/{passenger_id}` | Change a saved traveler's details or discount cards, including the account holder's own. |
| `delete_passenger` | write | `DELETE /passengers/{passenger_id}` | Remove a saved traveler from the account. The account holder cannot be removed. |

Never built, on purpose: paying, changing or cancelling a booking, your Omio sign-in and email, and anything else that moves money. `start_booking` stops before payment, and `list_payment_methods` shows type and brand only, never card numbers. Every request passes a guard that refuses common password, email and sign-in paths.

## Configuration

| Variable | Default | What it does |
|---|---|---|
| `OMIO_MCP_HOME` | `~/.config/omio-api-mcp` | Folder of `session.json`. |
| `OMIO_AUTH_TOKEN` | | Omio `IamToken` cookie, instead of `omio-mcp connect`. |
| `OMIO_PROXY` | | Proxy for every request to Omio, e.g. `http://user:pass@host:port`. |
| `OMIO_MCP_READ_ONLY` | | `1` hides and refuses every tool that changes Omio (same as `--read-only`). |
| `OMIO_MCP_TOKEN` | | Bearer token required by `serve`; needed to listen beyond `127.0.0.1`. |
| `OMIO_MCP_HOST`, `OMIO_MCP_PORT` | `127.0.0.1`, `8787` | Address of `serve`. |

## Security and your Omio account

- **No password involved.** Omio signs you in with a code by email. Only cookies are read, and only those of omio.com.
- **The session file is yours.** `session.json` is created with mode 0600. Anyone who has it can act as you on Omio, see your bookings and reserve fares, so keep it out of git and shared folders.
- **Local by default.** `serve` binds to `127.0.0.1` and refuses another address without `OMIO_MCP_TOKEN`.
- **omio.com only.** Requests and redirects outside omio.com are refused.
- **Read-only mode.** `--read-only` or `OMIO_MCP_READ_ONLY=1` exposes the 12 read tools only.
- **No payment.** Omio holds a reserved fare for a short time, and it lapses unpaid. You pay on omio.com at `checkout_url`, or not at all.
- **Keep to normal use.** Searches go out one at a time, as you would click. Hundreds of searches in a loop can get your network a bot check or a block from Cloudflare.

## Errors

The REST API answers `{"error": "<code>", "message": "..."}`. The MCP server returns the same code and message as a tool error.

| Status | Code | What to do |
|---|---|---|
| 401 | `auth_required`, `auth_expired` | No session, or Omio signed you out. Sign in to Omio in Chrome and run `omio-mcp connect`. |
| 403 | `scope_denied` | The server runs read-only. |
| 403 | `target_blocked` | Cloudflare showed a bot check. Open omio.com in the Chrome you connected, then run `omio-mcp connect` again. |
| 409 | `captcha_required` | Omio asks for a CAPTCHA. Solve it in Chrome. |
| 422 | `invalid_input` | An argument is missing or wrong; the message names it. |
| 429 | `rate_limited` | Omio is limiting requests. Wait a few minutes. |
| 502 | `target_error` | Omio answered with an error, or changed its site. `git pull` for the latest tools, or [open an issue](https://github.com/cotletdev/omio-api-mcp-server/issues). |

## Self-hosted or hosted

| | This repo | [Cotlet, hosted](https://cotlet.dev/integrations/omio-api-mcp-server) |
|---|---|---|
| Tools | the same 16 | the same 16 |
| Runs | on your computer, while it is on | in the cloud, 24/7 |
| Omio session | your Chrome, cookies in a local file | your own Cloud Browser in the EU, profile encrypted with AES-256-GCM |
| Cloudflare bot checks | your Chrome and your network | passed in your Cloud Browser |
| When Omio changes its site | `git pull` once we have fixed it | fixed for you, every tool tested daily |
| Approvals | your MCP client asks per call | writes wait for your OK, switchable per tool |
| Works with | MCP clients on your machine, local scripts | Claude.ai and ChatGPT connectors, n8n, Make, Zapier, any HTTP client |
| Who may use it | you, for noncommercial use | teams, businesses, agencies |
| Price | free | free 7-day trial with 2,000 credits, no card; then one-time packs from $29 for 5,000 credits |

On the hosted version a successful call uses 10 credits, failed calls are free, and the Cloud Browser uses 50 credits a day while it has an app enabled for agents. [Full pricing](https://cotlet.dev/pricing).

## FAQ

**Does Omio have an API?**
Not for your own account. Omio's affiliate programme lists a Search API for partners, and its app in ChatGPT searches trips. Your Bookings, saved travelers, fare conditions and checkout work only on omio.com and in the Omio app. Details: [cotlet.dev/integrations/omio-api-mcp-server](https://cotlet.dev/integrations/omio-api-mcp-server).

**Is there an Omio MCP server for Claude, ChatGPT or Cursor?**
Yes, this one runs on your machine: `omio-mcp mcp` for Claude Code, Claude Desktop, Cursor and Codex. ChatGPT and Claude.ai connectors need a public HTTPS URL, which the [hosted Omio MCP server](https://cotlet.dev/integrations/omio-api-mcp-server) gives you.

**Can it buy tickets?**
No. `start_booking` reserves the fare with your travelers' names and returns the price breakdown and `checkout_url`. You open that link in a browser signed in to the same Omio account and pay there. Nothing is charged until you do.

**Is this an Omio scraper?**
It does what people want a scraper for (prices, timetables, the cheapest day, an export of bookings) but does not parse HTML in a headless browser. It calls the same JSON endpoints the Omio web app calls, in your own account.

**Can I use my BahnCard or Railcard?**
Yes. `list_discount_cards` finds the card, and `search_trips` takes it per traveler, so the prices include the discount. Saved travelers keep their cards on the account.

**Why does it need my Chrome?**
To read your Omio session and Cloudflare's cookie without a password. Chrome is used once per sign-in, not for each call.

**What happens when Omio signs me out?**
Calls fail with `auth_expired`. With Chrome remote debugging on, the server reads the new cookies on the next call (click Allow when Chrome asks); otherwise run `omio-mcp connect` again.

**Can it run on a VPS or in Docker?**
Not well. Cloudflare checks requests to www.omio.com, and a datacenter IP without a browser gets a bot check. For an always-on setup the hosted version keeps your session in your own Cloud Browser, which passes those checks.

**Can I use it at work or for my clients?**
No, the license allows noncommercial use only. Booking travel for a company or for clients is commercial use. Use [Cotlet](https://cotlet.dev) or write to [contact@cotlet.dev](mailto:contact@cotlet.dev).

**Is it open source?**
The source is public, the license is not an open source license: noncommercial use only, no business use.

**A tool broke or I need another one.**
[Open an issue](https://github.com/cotletdev/omio-api-mcp-server/issues) with the tool name and the error message.

## License

[PolyForm Noncommercial License 1.0.0](https://github.com/cotletdev/omio-api-mcp-server/blob/main/LICENSE). In short:

- **Allowed:** noncommercial use: you, for your own personal purposes with your own Omio account, or a charity, school, public research or government body. Changing the code, and sharing it under the same license.
- **Not allowed:** any commercial use, your own business included; client work; selling or offering it, or a service built on it.

---

<p>
  <a href="https://cotlet.dev">
    <picture>
      <source media="(prefers-color-scheme: dark)" srcset="assets/logo-white.svg">
      <img src="https://raw.githubusercontent.com/cotletdev/omio-api-mcp-server/main/assets/logo.svg" alt="Cotlet" width="120">
    </picture>
  </a>
</p>

Maintained by [Cotlet](https://cotlet.dev) ([@cotletdev](https://x.com/cotletdev)). Omio is a trademark of its owner. This project is unofficial and not affiliated with, endorsed or sponsored by Omio.
