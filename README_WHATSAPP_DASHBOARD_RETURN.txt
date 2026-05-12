WhatsApp dashboard-return safety update

Problem fixed:
- After saving an entry, WhatsApp opened and browser could return to the filled entry form.
- That could cause accidental duplicate entries.

New behavior:
- Save entry.
- App opens an intermediate WhatsApp page.
- WhatsApp opens using the client number and receipt template.
- The app page automatically redirects to Dashboard.
- Operator/admin does not return to the entry form.

For 7 Name Entry:
- The saved entries page shows WhatsApp buttons.
- Each button uses the same safe /wa/<id> flow.
