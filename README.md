# Arcana Sync — Telegram → Facebook

Independent Railway worker. Copies new text, photo, and photo-album posts from `@ArcanaLab_AI` to the Arcana Lab Facebook Page. No edits to the existing Arcana bot.

## Railway variables
- `TELEGRAM_BOT_TOKEN` — token of `@ArcanaFBReposter_bot`
- `FACEBOOK_PAGE_TOKEN` — Page Access Token (not the user token); ensure it is long-lived/renewable before unattended production use
- `FACEBOOK_PAGE_ID` — ID returned by Graph API Explorer
- `TELEGRAM_CHANNEL` — `@ArcanaLab_AI`
- `ARCANA_BOT_URL` — actual Telegram bot link (optional until known)
- `GRAPH_VERSION` — `v26.0` (optional)
- `DB_PATH` — persistence location, default `arcana_sync.sqlite3`

Deploy as a Railway **worker** with start command `python main.py`, one replica. Add the Telegram bot as channel admin (already done). **Do not run another instance using the same bot token**. Do not publish tokens in GitHub or chat.

## Important before production
- SQLite deduplication is local: attach a persistent Railway volume and set `DB_PATH` accordingly (e.g. `/data/arcana_sync.sqlite3`).
- Graph API Explorer tokens may expire. Configure a durable Page token/renewal process before leaving unattended.
- Current prototype retries neither failed posts automatically nor partial albums. On failure it logs an error; improve with a persistent retry queue before production. An album can leave unpublished photos if the final feed call fails.
- Supports text, single photos, photo albums; videos, animations, polls and edited/deleted posts are not mirrored.
- Photo captions are taken from the Telegram message; Facebook may impose different text and media limits.
- New posts only; no historical backfill.
