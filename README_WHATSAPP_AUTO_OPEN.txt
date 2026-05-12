WhatsApp auto-open update

Behavior:
- After Single Entry save, app redirects directly to WhatsApp/wa.me for that client's number.
- WhatsApp opens with prefilled message:
  Aapka Qurbani ka Hissa Darj ho gaya hai-BBAMQB
  Receipt No: ...
  Amount: ...
- Operator still must tap Send inside WhatsApp. Browsers/WhatsApp do not allow silent send without Meta API.
- Search/results table has WhatsApp action link through /wa/<entry_id>.
- 10 digit numbers are converted to 91XXXXXXXXXX automatically.

Note:
- For 7 Name Entry, auto-opening seven WhatsApp windows at once is blocked by browsers. Use Master Search or receipt actions to send individual confirmations.
