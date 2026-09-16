# Backdrop character candidates

Cut automatically from each new comic's carousel pages (`store_design/characters.py`) and sent to
Telegram as `<NN>_sheet.jpg`. **None of these are live yet.**

- **Owner picks:** run **Store Sync** (`store_sync.yml`) with `approve_chars` = the codes on the
  sheet, e.g. `57_3_1,57_4_0` (or ask Claude). The rest of that comic's candidates are dropped.
- **No pick:** once the comic is published, the next hourly Store Sync puts the top 3 live itself
  (`<NN>_pending.json` lists them best first).
