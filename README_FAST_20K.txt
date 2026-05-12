BBAMQB FAST 20K+ VERSION

Optimizations:
- PostgreSQL indexes for active rows, operator, receipt, mobile, name, timestamp.
- No full-table load on dashboard.
- Admin clients page uses pagination: 50 records per page.
- Search is limited and indexed-friendly.
- Operator dashboard only uses COUNT/SUM query.
- Soft delete does not remove database record.
- Trash/restore available for admin.
- Operator summary report available.
- Receipt page and exact timestamp included.
- Single entry and 7-name entry calculate amount automatically:
  Hissa = ₹1600
  Aqeeqa Girl = ₹1600
  Aqeeqa Boy = ₹3200

Upload to GitHub:
- app.py
- requirements.txt
- runtime.txt
- Procfile

Render:
Manual Deploy -> Clear build cache & deploy


Shares counter update:
- Admin dashboard now shows master Shares Entered counter.
- Operator dashboard now shows Shares Entered by that operator.
- Shares are counted using the quantity column.
- Single Entry quantity affects shares.
- 7 Name Entry saves each participant as quantity 1, so seven filled rows = seven shares.


SMS Export update:
- CSV export now contains only telephone numbers.
- File name: bbamqb_sms_numbers.csv
- Column: telephone
- Active entries only.
- Empty phone numbers ignored.
- Duplicate phone numbers removed using DISTINCT.


Master Search update:
- Added universal search page for both admin and operator.
- Search by:
  - Name
  - Telephone number
  - Receipt number
- Operators can search ONLY their own entries.
- Admin can search all entries.
- Search results allow:
  - Edit
  - Delete (soft delete)
  - Receipt recall
