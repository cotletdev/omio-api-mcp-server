# AGENTS.md

You are an AI agent in a clone of this repo. It is a self-hosted Omio API and MCP server: 16 tools that work in the user's own Omio account, through the session of their own Google Chrome. Your usual job is one of three: set it up for the user, use its tools for them, or change its code. Human docs: `README.md`.

## Before you start

- The license allows noncommercial use only (PolyForm Noncommercial 1.0.0, `LICENSE`). If the user is setting this up for a company, a team or clients, say so and point to the hosted version at https://cotlet.dev/integrations/omio-api-mcp-server. Do not continue the setup for that use.
- Every tool acts as the user on Omio. Tools with access `write` reserve fares or change the saved travelers on the account. No tool pays: `start_booking` returns a `checkout_url`, and the user pays there in their own browser.

## Set it up for the user

Do the steps yourself. Ask the user only for what needs their hands in Chrome.

1. Check Python: `python3 --version` must be 3.11 or newer.
2. Install in the repo root:

   ```bash
   python3 -m venv .venv && .venv/bin/pip install -e .
   .venv/bin/omio-mcp --version
   ```

   On Windows the path is `.venv\Scripts\omio-mcp`. With uv: `uv venv && uv pip install -e .`.
3. Ask the user to do two things in Chrome. You cannot open `chrome://` pages for them.
   - Open `chrome://inspect/#remote-debugging` and switch remote debugging on.
   - Be signed in at https://www.omio.com. Omio signs in with a 6-digit code by email, so the user does this step.
4. Run `.venv/bin/omio-mcp connect`. Tell the user to click **Allow** when Chrome asks about the connection. Success prints `Signed in to Omio as <name> (<email>)`.
5. Check: `.venv/bin/omio-mcp status`, then `.venv/bin/omio-mcp call search_places query=Berlin`.
6. Add the MCP server to the user's client. Use the absolute path of `.venv/bin/omio-mcp`:
   - Claude Code: `claude mcp add omio -- <abs path>/.venv/bin/omio-mcp mcp`
   - Claude Desktop, Cursor, Codex: the config blocks in `README.md`, section "MCP server".
   - Add `--read-only` after `mcp` if the user only wants to read.
   The client loads new MCP servers on its next start. Tell the user.

Run the server on the same computer as the Chrome you connected. Cloudflare guards www.omio.com, and its cookie works only from the network that Chrome uses.

If step 4 or 5 fails:

| Message | What to do |
|---|---|
| `Chrome remote debugging is off` | Step 3 is not done, or Chrome is Beta, Canary or a custom profile: pass `--profile-dir "<profile folder>"`. |
| `Could not connect to Chrome` | The user did not click Allow, or Chrome is closed. Run `connect` again. |
| `This Chrome is not signed in to Omio` | The user signs in at omio.com in that Chrome, then run `connect` again. |
| `target_blocked: Omio showed a bot check` | The user opens omio.com in the same Chrome and passes the check if one shows. Then run `connect` again. |
| No Chrome on this machine (a server) | Omio's Cloudflare blocks most servers. Point the user to the hosted version. A pasted cookie (`omio-mcp connect --token`, cookie `IamToken`) is for the user to run themselves; never ask them to paste it into the chat. |

## Use the tools

- With the MCP server added, call its tools. Without it: `.venv/bin/omio-mcp call <tool> key=value ...`, or one JSON object as the argument.
- `.venv/bin/omio-mcp tools` lists every tool with access and route. `tools --json` adds the input schemas.
- Start with `search_trips` (`from`, `to` as city or station names, `date` as YYYY-MM-DD). Its `trip_id` values go to `get_trip`, which lists the fares with their `fare_id`. A round trip: `search_trips` with `return_date`, then `list_return_trips` with an outbound `trip_id`.
- Discount cards change the price: find them with `list_discount_cards` and pass them per traveler in `passengers`.
- Before `start_booking`, show the user the trip, the fare with its conditions and the travelers, and get their OK. Give them the `checkout_url` it returns and the total. Never open or pay the checkout for them.
- Before `add_passenger`, `update_passenger` or `delete_passenger`, show what changes and get the user's OK.
- For a script or a cron job, use `omio_api_mcp.scripting` (`call`, `write_rows`) and the scripts in `examples/` as models.
- For a REST API (n8n, other languages): `.venv/bin/omio-mcp serve`, routes under `http://127.0.0.1:8787/api/v1/omio`, docs at `/docs`.

Errors come as `<code>: <message>`. `auth_expired` means Omio signed the session out: the user signs in again in Chrome and you run `connect`. `target_blocked` is a Cloudflare bot check: see the table above. More codes: `README.md`, section "Errors".

## Keep secrets out

- `~/.config/omio-api-mcp/session.json` and `OMIO_AUTH_TOKEN` give full access to the user's Omio account. Never print, log, commit or copy their content.
- `serve` listens on 127.0.0.1. Never start it on another address without `OMIO_MCP_TOKEN`.

## Change the code

| Path | What | Edit? |
|---|---|---|
| `omio_api_mcp/omio/` | the Omio tools, one file per tool in `tools/`, shared request code in `client.py` | Yes for a local fix, but the next `git pull` brings our version of these files. Report the bug at https://github.com/cotletdev/omio-api-mcp-server/issues |
| `omio_api_mcp/app.py` | app name, domains, session cookie, REST prefix | Rarely |
| `omio_api_mcp/core/` | `@tool` declaration, errors, the HTTP client with the session (`context.py`) | Yes |
| `omio_api_mcp/session.py` | reading cookies from Chrome over CDP, the session file | Yes |
| `omio_api_mcp/runner.py`, `api.py`, `mcp_server.py`, `mcp_context.py`, `cli.py` | tool registry, REST API, MCP server, its prompts and resources, command line | Yes |
| `examples/` | scripts for common jobs | Yes |

A new tool is a new file in `omio_api_mcp/omio/tools/` with a `@tool(...)` declaration (name, access, input schema, `route`). The registry finds it, and the REST API, the MCP server and the CLI show it without other changes.

There is no test suite. After a change, run `.venv/bin/omio-mcp tools` and one read tool against the user's account.
