# Backdrop character candidates

Cut automatically from each new comic's carousel pages (`store_design/characters.py`).
**None of these are live.** The cutter also picks up props (life rings, palm trees, headless
torsos), so each issue's `<NN>_sheet.png` is reviewed by eye first.

To put chosen figures live on that comic's page, run **Store Sync** (`store_sync.yml`) with
`approve_chars` = the keys printed on the sheet, e.g. `57_3_1,57_4_0`.
