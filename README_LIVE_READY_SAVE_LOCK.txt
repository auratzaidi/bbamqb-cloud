LIVE READY PATCH — Save Button Lock + Loading Spinner

Added:
- All form submit buttons disable immediately after click.
- Button changes to Saving... with spinner.
- Prevents double-tap/double-submit duplicate entries.
- Applies to:
  - Login
  - Single Entry
  - 7 Name Entry
  - Search forms
  - User creation

This patch is important for live qurbani operations where operators may tap repeatedly during internet lag.

Upload/replace on GitHub:
- app.py
- requirements.txt
- runtime.txt
- Procfile

Then Render:
Manual Deploy -> Clear build cache & deploy
