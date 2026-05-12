# REPLACE ONLY THE export_csv FUNCTION IN YOUR EXISTING app.py WITH THIS

def export_csv(self):
    # ADMIN ONLY
    # CSV FORMAT:
    # Janwar Number, Mobile Numbers

    u = self.user()
    if not u or u.get("role") != "ROLE_ADMIN":
        return self.sendx(*redirect("/"))

    conn=get_conn()
    cur=conn.cursor()

    cur.execute("""
        SELECT
            COALESCE(janwar_no, '') AS janwar_no,
            COALESCE(mobile, '') AS mobile
        FROM clients
        WHERE deleted_at IS NULL
          AND TRIM(COALESCE(mobile,'')) <> ''
        ORDER BY janwar_no ASC, id ASC
    """)

    rows = dict_all(cur)

    cur.close()
    conn.close()

    grouped = {}

    for r in rows:
        janwar = (r.get("janwar_no") or "").strip()

        if not janwar:
            continue

        mobile = "".join(ch for ch in str(r.get("mobile") or "") if ch.isdigit())

        if not mobile:
            continue

        grouped.setdefault(janwar, []).append(mobile)

    out = io.StringIO()
    w = csv.writer(out)

    w.writerow(["Janwar Number", "Mobile Numbers"])

    for janwar, numbers in grouped.items():
        sms_line = ",".join(numbers) + ","
        w.writerow([janwar, sms_line])

    self.sendx(
        200,
        {
            "Content-Type":"text/csv; charset=utf-8",
            "Content-Disposition":"attachment; filename=bbamqb_janwar_sms.csv"
        },
        out.getvalue()
    )
