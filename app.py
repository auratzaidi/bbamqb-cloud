#!/usr/bin/env python3
# BBAMQB Render + PostgreSQL Deployment App
# Login: pyra / admin123

import os, csv, io, hmac, hashlib, secrets
from datetime import datetime
from html import escape
from http import cookies
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse, parse_qs

import psycopg2
from psycopg2.extras import RealDictCursor

HOST = "0.0.0.0"
PORT = int(os.environ.get("PORT", "8090"))
DATABASE_URL = os.environ.get("DATABASE_URL")
SECRET = os.environ.get("BBAMQB_SECRET", "change-this-secret-in-render")
PRODUCTS = {"Hissa":1600, "Aqeeqa Girl":1600, "Aqeeqa Boy":3200}
PAYMENT_STATUS = ["Unpaid", "Partial", "Paid"]
ROLES = ["ROLE_ADMIN", "ROLE_OPERATOR"]

def now():
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")

def rupees(n):
    try: return "₹{:,.0f}".format(int(n or 0))
    except Exception: return "₹0"

def get_conn():
    if not DATABASE_URL:
        raise RuntimeError("DATABASE_URL is missing. Add Render PostgreSQL DATABASE_URL environment variable.")
    return psycopg2.connect(DATABASE_URL, cursor_factory=RealDictCursor)

def password_hash(password, salt=None):
    salt = salt or secrets.token_hex(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode(), salt.encode(), 120000).hex()
    return salt + "$" + digest

def password_ok(password, stored):
    try:
        salt, digest = stored.split("$", 1)
        return hmac.compare_digest(password_hash(password, salt).split("$", 1)[1], digest)
    except Exception:
        return False

def sign(value):
    return hmac.new(SECRET.encode(), value.encode(), hashlib.sha256).hexdigest()

def make_session(username):
    return username + "|" + sign(username)

def read_session(header):
    if not header: return None
    try:
        c = cookies.SimpleCookie(header)
        token = c.get("bbamqb_session")
        if not token: return None
        username, sig = token.value.split("|", 1)
        if not hmac.compare_digest(sig, sign(username)): return None
        with get_conn() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT * FROM users WHERE username=%s", (username,))
                return cur.fetchone()
    except Exception:
        return None

def receipt_no():
    return "BBQ-" + datetime.now().strftime("%Y%m%d%H%M%S")

def init_db():
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id SERIAL PRIMARY KEY,
                username TEXT UNIQUE NOT NULL,
                password_hash TEXT NOT NULL,
                role TEXT NOT NULL DEFAULT 'ROLE_OPERATOR',
                mobile TEXT DEFAULT '',
                created_at TEXT NOT NULL
            );
            """)
            cur.execute("""
            CREATE TABLE IF NOT EXISTS clients (
                id SERIAL PRIMARY KEY,
                receipt_no TEXT UNIQUE NOT NULL,
                client_name TEXT NOT NULL,
                mobile TEXT DEFAULT '',
                city TEXT DEFAULT '',
                address TEXT DEFAULT '',
                product TEXT NOT NULL,
                quantity INTEGER NOT NULL DEFAULT 1,
                amount_due INTEGER NOT NULL DEFAULT 0,
                amount_paid INTEGER NOT NULL DEFAULT 0,
                payment_status TEXT NOT NULL DEFAULT 'Unpaid',
                names TEXT DEFAULT '',
                notes TEXT DEFAULT '',
                created_by TEXT DEFAULT '',
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );
            """)
            cur.execute("SELECT COUNT(*) AS c FROM users")
            if cur.fetchone()["c"] == 0:
                cur.execute(
                    "INSERT INTO users(username,password_hash,role,mobile,created_at) VALUES(%s,%s,%s,%s,%s)",
                    ("pyra", password_hash("admin123"), "ROLE_ADMIN", "9870057600", now())
                )
        conn.commit()

CSS = """
:root{--bg:#f7f3ea;--panel:#fffaf0;--ink:#15231d;--muted:#6d756f;--green:#063f35;--green2:#0e5a4a;--gold:#d7ad46;--line:#e8ddca;--danger:#a83a32;--ok:#1f7a55;--warn:#a46b00}
*{box-sizing:border-box}body{margin:0;background:radial-gradient(circle at top left,#fff7e6,#f5efe4 45%,#eee5d8);font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",Arial,sans-serif;color:var(--ink)}a{color:inherit;text-decoration:none}
.layout{display:flex;min-height:100vh}.sidebar{width:280px;background:linear-gradient(180deg,#062e28,#083e35);color:white;padding:22px;display:flex;flex-direction:column;gap:22px;position:fixed;inset:0 auto 0 0}.brand{display:flex;gap:12px;align-items:center;padding-bottom:18px;border-bottom:1px solid rgba(255,255,255,.15)}.brand-mark{width:44px;height:44px;border-radius:14px;background:linear-gradient(135deg,#e8c15a,#a47721);display:grid;place-items:center;color:#10251f;font-size:24px;font-weight:900}.brand small{display:block;color:#d8e4dc;margin-top:3px}nav{display:grid;gap:8px}nav a{padding:12px 14px;border-radius:12px;color:#eaf3ef;font-weight:700;font-size:14px}nav a:hover{background:rgba(255,255,255,.10)}.userbox{margin-top:auto;background:rgba(255,255,255,.09);border:1px solid rgba(255,255,255,.12);padding:12px;border-radius:16px;display:flex;gap:10px;align-items:center}.userbox span{width:38px;height:38px;border-radius:50%;background:white;color:#083e35;display:grid;place-items:center;font-weight:900}.userbox small{display:block;color:#d7e5df;font-size:12px;margin-top:2px}
.main{margin-left:280px;width:calc(100% - 280px);padding:32px}.top{display:flex;justify-content:space-between;align-items:flex-start;margin-bottom:22px}.top h1{margin:0;font-size:28px;letter-spacing:-.02em}.top p{margin:6px 0 0;color:var(--muted)}.badge{display:inline-flex;padding:9px 13px;border-radius:999px;background:#fffaf0;border:1px solid var(--line);color:var(--muted);font-size:13px}.card{background:rgba(255,250,240,.92);border:1px solid var(--line);border-radius:24px;padding:22px;box-shadow:0 18px 45px rgba(53,34,8,.08);margin-bottom:20px}.grid{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:14px}.stat{background:white;border:1px solid var(--line);border-radius:18px;padding:18px}.stat b{font-size:26px;display:block}.stat span{color:var(--muted);font-size:13px;font-weight:700;text-transform:uppercase;letter-spacing:.04em}
.btn{display:inline-flex;align-items:center;justify-content:center;background:var(--green2);color:white;border:0;border-radius:12px;padding:10px 14px;font-weight:800;cursor:pointer;margin:3px}.btn.secondary{background:#efe6d6;color:#23332c}.btn.danger{background:var(--danger)}.btn.gold{background:#b0832d;color:white}table{width:100%;border-collapse:separate;border-spacing:0 9px}th{font-size:12px;color:var(--muted);text-transform:uppercase;text-align:left;padding:0 10px;letter-spacing:.04em}td{background:white;border-top:1px solid var(--line);border-bottom:1px solid var(--line);padding:12px 10px;font-size:14px}td:first-child{border-left:1px solid var(--line);border-radius:12px 0 0 12px}td:last-child{border-right:1px solid var(--line);border-radius:0 12px 12px 0}
form .row{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:14px}label{display:grid;gap:6px;font-weight:800;font-size:13px;color:#314039;margin-bottom:12px}input,select,textarea{width:100%;border:1px solid var(--line);border-radius:13px;padding:12px;background:white;font:inherit}textarea{min-height:90px}.notice{padding:12px 14px;border-radius:14px;background:#fff4d7;border:1px solid #ead69f;color:#6b4b00;margin-bottom:15px}.status-paid{color:var(--ok);font-weight:900}.status-partial{color:var(--warn);font-weight:900}.status-unpaid{color:var(--danger);font-weight:900}
.login-wrap{min-height:100vh;display:grid;place-items:center;padding:25px}.login{width:min(440px,100%);background:#fffaf0;border:1px solid var(--line);border-radius:26px;padding:30px;box-shadow:0 22px 55px rgba(42,29,8,.12)}.login h1{margin:0 0 8px}.login p{color:var(--muted)}
@media(max-width:900px){.sidebar{position:relative;width:100%;inset:auto}.layout{display:block}.main{margin-left:0;width:100%;padding:14px}.grid,form .row{grid-template-columns:1fr}table{display:block;overflow-x:auto;white-space:nowrap}.top{display:block}.btn{width:100%;margin:5px 0}}
@media print{.sidebar,.top .badge,.btn{display:none}.main{margin:0;width:100%;padding:0}.card{box-shadow:none;border:0}body{background:white}}
"""

def html_page(title, body, user=None):
    nav = ""
    if user:
        nav = f"""
        <aside class="sidebar"><div class="brand"><div class="brand-mark">ب</div><div><b>BBAMQB</b><small>Operations Suite</small></div></div>
        <nav><a href="/">Dashboard</a><a href="/clients">Clients</a><a href="/client/new">New Entry</a><a href="/client/multi">7 Name Entry</a><a href="/report">Reports</a><a href="/export.csv">CSV Export</a><a href="/users">Users</a><a href="/logout">Logout</a></nav>
        <div class="userbox"><span>{escape(user['username'][0].upper())}</span><div><b>{escape(user['username'])}</b><small>{escape(user['role'])}</small></div></div></aside>
        """
    return f"""<!doctype html><html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1"><title>{escape(title)} · BBAMQB</title><style>{CSS}</style></head><body><div class="{'layout' if user else 'login-wrap'}">{nav}<main class="{'main' if user else ''}">{body}</main></div></body></html>"""

def redirect(path):
    return (302, {"Location": path}, b"")

class App(BaseHTTPRequestHandler):
    def sendx(self, status=200, headers=None, body=b""):
        self.send_response(status)
        for k,v in (headers or {}).items(): self.send_header(k,v)
        self.end_headers()
        if isinstance(body,str): body=body.encode("utf-8")
        self.wfile.write(body)

    def body(self):
        l=int(self.headers.get("Content-Length",0))
        return parse_qs(self.rfile.read(l).decode())

    def user(self):
        return read_session(self.headers.get("Cookie"))

    def need_user(self):
        u=self.user()
        if not u: self.sendx(*redirect("/login")); return None
        return u

    def do_GET(self):
        path=urlparse(self.path).path
        if path=="/login": return self.login_page()
        if path=="/logout":
            return self.sendx(302, {"Location":"/login","Set-Cookie":"bbamqb_session=; Path=/; Max-Age=0"}, b"")
        u=self.need_user()
        if not u: return
        if path=="/": return self.dashboard(u)
        if path=="/clients": return self.clients(u)
        if path=="/client/new": return self.client_form(u)
        if path=="/client/multi": return self.client_form(u, multi=True)
        if path.startswith("/client/edit/"): return self.client_form(u, client_id=path.split("/")[-1])
        if path.startswith("/client/delete/"): return self.delete_client(path.split("/")[-1])
        if path.startswith("/receipt/"): return self.receipt(u, path.split("/")[-1])
        if path=="/report": return self.report(u)
        if path=="/export.csv": return self.export_csv(u)
        if path=="/users": return self.users(u)
        if path=="/user/new": return self.user_form(u)
        if path.startswith("/user/delete/"): return self.delete_user(u, path.split("/")[-1])
        self.sendx(404, {"Content-Type":"text/html; charset=utf-8"}, html_page("404","<div class='card'><h1>404</h1></div>",u))

    def do_POST(self):
        path=urlparse(self.path).path
        if path=="/login": return self.login_post()
        u=self.need_user()
        if not u: return
        if path=="/client/save": return self.save_client(u)
        if path=="/user/save": return self.save_user(u)
        self.sendx(*redirect("/"))

    def login_page(self,msg=""):
        body=f"""<div class="login"><div class="brand" style="color:#12352d;border:0;padding:0 0 18px"><div class="brand-mark">ب</div><div><b>BBAMQB</b><small style="color:#65736c">Qurbani Operations</small></div></div><h1>Login</h1><p>Enter your operator credentials.</p>{f'<div class="notice">{escape(msg)}</div>' if msg else ''}<form method="post" action="/login"><label>Username<input name="username" value="pyra"></label><label>Password<input type="password" name="password" value="admin123"></label><button class="btn" style="width:100%">Login</button></form></div>"""
        self.sendx(200, {"Content-Type":"text/html; charset=utf-8"}, html_page("Login",body))

    def login_post(self):
        d=self.body(); username=d.get("username",[""])[0].strip(); password=d.get("password",[""])[0]
        with get_conn() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT * FROM users WHERE username=%s",(username,))
                row=cur.fetchone()
        if row and password_ok(password,row["password_hash"]):
            self.sendx(302, {"Location":"/","Set-Cookie":f"bbamqb_session={make_session(username)}; Path=/; HttpOnly; SameSite=Lax"}, b"")
        else: self.login_page("Invalid username or password.")

    def all_clients(self):
        with get_conn() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT * FROM clients ORDER BY id DESC")
                return cur.fetchall()

    def dashboard_stats(self):
        rows=self.all_clients()
        return {
            "rows":rows, "entries":len(rows), "shares":sum(int(r["quantity"] or 0) for r in rows),
            "amount_due":sum(int(r["amount_due"] or 0) for r in rows), "amount_paid":sum(int(r["amount_paid"] or 0) for r in rows),
            "paid":sum(1 for r in rows if r["payment_status"]=="Paid"),
            "partial":sum(1 for r in rows if r["payment_status"]=="Partial"),
            "unpaid":sum(1 for r in rows if r["payment_status"]=="Unpaid")
        }

    def client_head(self):
        return "<tr><th>Receipt</th><th>Name</th><th>Mobile</th><th>Product</th><th>Qty</th><th>Due</th><th>Paid</th><th>Status</th><th>Actions</th></tr>"

    def client_row(self,r):
        cls={"Paid":"status-paid","Partial":"status-partial","Unpaid":"status-unpaid"}.get(r["payment_status"],"")
        return f"<tr><td>{escape(r['receipt_no'])}</td><td><b>{escape(r['client_name'])}</b><br><small>{escape(r['city'] or '')}</small></td><td>{escape(r['mobile'] or '')}</td><td>{escape(r['product'])}</td><td>{r['quantity']}</td><td>{rupees(r['amount_due'])}</td><td>{rupees(r['amount_paid'])}</td><td class='{cls}'>{escape(r['payment_status'])}</td><td><a href='/receipt/{r['id']}'>Receipt</a> · <a href='/client/edit/{r['id']}'>Edit</a> · <a href='/client/delete/{r['id']}' onclick=\"return confirm('Delete entry?')\">Delete</a></td></tr>"

    def dashboard(self,u):
        s=self.dashboard_stats(); balance=max(0,s["amount_due"]-s["amount_paid"])
        recent="".join(self.client_row(r) for r in s["rows"][:8]) or "<tr><td colspan='9'>No entries yet.</td></tr>"
        body=f"""<div class="top"><div><h1>Dashboard</h1><p>Operational overview for qurbani entries, collections and reports.</p></div><span class="badge">Cloud Database · PostgreSQL</span></div><div class="grid"><div class="stat"><b>{s['entries']}</b><span>Total Entries</span></div><div class="stat"><b>{s['shares']}</b><span>Total Shares</span></div><div class="stat"><b>{rupees(s['amount_due'])}</b><span>Total Due</span></div><div class="stat"><b>{rupees(s['amount_paid'])}</b><span>Collected</span></div><div class="stat"><b>{rupees(balance)}</b><span>Balance</span></div><div class="stat"><b>{s['paid']}</b><span>Paid</span></div><div class="stat"><b>{s['partial']}</b><span>Partial</span></div><div class="stat"><b>{s['unpaid']}</b><span>Unpaid</span></div></div><div class="card"><a class="btn" href="/client/new">New Entry</a><a class="btn gold" href="/client/multi">7 Name Entry</a><a class="btn secondary" href="/report">Report</a><a class="btn secondary" href="/export.csv">CSV Export</a></div><div class="card"><h2>Recent Entries</h2><table>{self.client_head()}{recent}</table></div>"""
        self.sendx(200, {"Content-Type":"text/html; charset=utf-8"}, html_page("Dashboard",body,u))

    def clients(self,u):
        q=parse_qs(urlparse(self.path).query); search=q.get("q",[""])[0].strip(); status=q.get("status",[""])[0].strip()
        sql="SELECT * FROM clients WHERE 1=1"; args=[]
        if search:
            like="%"+search+"%"; sql+=" AND (client_name ILIKE %s OR mobile ILIKE %s OR receipt_no ILIKE %s OR city ILIKE %s)"; args += [like,like,like,like]
        if status:
            sql+=" AND payment_status=%s"; args.append(status)
        sql+=" ORDER BY id DESC"
        with get_conn() as conn:
            with conn.cursor() as cur:
                cur.execute(sql,args); rows=cur.fetchall()
        rows_html="".join(self.client_row(r) for r in rows) or "<tr><td colspan='9'>No matching entries.</td></tr>"
        status_options = '<option value="">All</option>' + ''.join(f'<option {"selected" if status==x else ""}>{x}</option>' for x in PAYMENT_STATUS)
        body=f"""<div class="top"><div><h1>Clients</h1><p>Search, filter and manage qurbani records.</p></div><a class="btn" href="/client/new">New Entry</a></div><div class="card"><form method="get" action="/clients"><div class="row"><label>Search<input name="q" value="{escape(search)}" placeholder="Name, mobile, receipt, city"></label><label>Status<select name="status">{status_options}</select></label></div><button class="btn">Apply Filter</button><a class="btn secondary" href="/clients">Clear</a></form></div><div class="card"><table>{self.client_head()}{rows_html}</table></div>"""
        self.sendx(200, {"Content-Type":"text/html; charset=utf-8"}, html_page("Clients",body,u))

    def client_form(self,u,client_id=None,multi=False):
        r=None
        if client_id:
            with get_conn() as conn:
                with conn.cursor() as cur:
                    cur.execute("SELECT * FROM clients WHERE id=%s",(client_id,)); r=cur.fetchone()
        def val(k,d=""): return escape(str(r[k] if r and r[k] is not None else d))
        title="Edit Entry" if r else ("7 Name Entry" if multi else "New Entry")
        names_default="\n".join([f"Name {i}" for i in range(1,8)]) if multi and not r else ""
        product_opts=''.join(f'<option value="{escape(p)}" {"selected" if (r and r["product"]==p) or ((not r) and p=="Hissa") else ""}>{escape(p)} — {rupees(price)}</option>' for p,price in PRODUCTS.items())
        status_opts=''.join(f'<option {"selected" if (r and r["payment_status"]==s) else ""}>{s}</option>' for s in PAYMENT_STATUS)
        names = escape((r["names"] if r else names_default) or "")
        body=f"""<div class="top"><div><h1>{title}</h1><p>Enter participant and payment details.</p></div></div><div class="card"><form method="post" action="/client/save"><input type="hidden" name="id" value="{val('id')}"><div class="row"><label>Client Name<input name="client_name" required value="{val('client_name')}"></label><label>Mobile<input name="mobile" value="{val('mobile')}"></label><label>City<input name="city" value="{val('city')}"></label><label>Product<select name="product">{product_opts}</select></label><label>Quantity<input type="number" min="1" name="quantity" value="{val('quantity',7 if multi else 1)}"></label><label>Amount Paid<input type="number" min="0" name="amount_paid" value="{val('amount_paid',0)}"></label><label>Payment Status<select name="payment_status">{status_opts}</select></label><label>Address<input name="address" value="{val('address')}"></label></div><label>Names / Share Holders<textarea name="names">{names}</textarea></label><label>Notes<textarea name="notes">{val('notes')}</textarea></label><button class="btn">Save Entry</button><a class="btn secondary" href="/clients">Cancel</a></form></div>"""
        self.sendx(200, {"Content-Type":"text/html; charset=utf-8"}, html_page(title,body,u))

    def save_client(self,u):
        d=self.body(); cid=d.get("id",[""])[0].strip(); product=d.get("product",["Hissa"])[0]; qty=max(1,int(d.get("quantity",["1"])[0] or 1)); paid=int(d.get("amount_paid",["0"])[0] or 0); due=PRODUCTS.get(product,0)*qty
        vals=(d.get("client_name",[""])[0].strip(),d.get("mobile",[""])[0].strip(),d.get("city",[""])[0].strip(),d.get("address",[""])[0].strip(),product,qty,due,paid,d.get("payment_status",["Unpaid"])[0],d.get("names",[""])[0].strip(),d.get("notes",[""])[0].strip(),now())
        with get_conn() as conn:
            with conn.cursor() as cur:
                if cid:
                    cur.execute("UPDATE clients SET client_name=%s,mobile=%s,city=%s,address=%s,product=%s,quantity=%s,amount_due=%s,amount_paid=%s,payment_status=%s,names=%s,notes=%s,updated_at=%s WHERE id=%s", vals+(cid,))
                else:
                    cur.execute("INSERT INTO clients(receipt_no,client_name,mobile,city,address,product,quantity,amount_due,amount_paid,payment_status,names,notes,created_by,created_at,updated_at) VALUES(%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)", (receipt_no(),)+vals[:11]+(u["username"],now(),now()))
            conn.commit()
        self.sendx(*redirect("/clients"))

    def delete_client(self,cid):
        with get_conn() as conn:
            with conn.cursor() as cur: cur.execute("DELETE FROM clients WHERE id=%s",(cid,))
            conn.commit()
        self.sendx(*redirect("/clients"))

    def receipt(self,u,cid):
        with get_conn() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT * FROM clients WHERE id=%s",(cid,)); r=cur.fetchone()
        if not r: return self.sendx(*redirect("/clients"))
        balance=max(0,int(r["amount_due"])-int(r["amount_paid"]))
        names="<br>".join(escape(x) for x in (r["names"] or "").splitlines() if x.strip())
        body=f"""<div class="top"><div><h1>Receipt</h1><p>{escape(r['receipt_no'])}</p></div><button class="btn" onclick="window.print()">Print</button></div><div class="card"><h2>Bazme Barkate Aley Mustafa Trust</h2><p><b>Receipt No:</b> {escape(r['receipt_no'])}<br><b>Date:</b> {escape(r['created_at'])}</p><table><tr><td><b>Name</b></td><td>{escape(r['client_name'])}</td></tr><tr><td><b>Mobile</b></td><td>{escape(r['mobile'] or '')}</td></tr><tr><td><b>Product</b></td><td>{escape(r['product'])} × {int(r['quantity'])}</td></tr><tr><td><b>Total Due</b></td><td>{rupees(r['amount_due'])}</td></tr><tr><td><b>Paid</b></td><td>{rupees(r['amount_paid'])}</td></tr><tr><td><b>Balance</b></td><td>{rupees(balance)}</td></tr><tr><td><b>Status</b></td><td>{escape(r['payment_status'])}</td></tr><tr><td><b>Names</b></td><td>{names}</td></tr></table><a class="btn secondary" href="/clients">Back</a></div>"""
        self.sendx(200, {"Content-Type":"text/html; charset=utf-8"}, html_page("Receipt",body,u))

    def report(self,u):
        s=self.dashboard_stats(); balance=max(0,s["amount_due"]-s["amount_paid"]); rows="".join(self.client_row(r) for r in s["rows"]) or "<tr><td colspan='9'>No data.</td></tr>"
        body=f"""<div class="top"><div><h1>Report</h1><p>Printable operational report.</p></div><button class="btn" onclick="window.print()">Print</button></div><div class="grid"><div class="stat"><b>{s['entries']}</b><span>Entries</span></div><div class="stat"><b>{s['shares']}</b><span>Shares</span></div><div class="stat"><b>{rupees(s['amount_paid'])}</b><span>Collected</span></div><div class="stat"><b>{rupees(balance)}</b><span>Balance</span></div></div><div class="card"><table>{self.client_head()}{rows}</table></div>"""
        self.sendx(200, {"Content-Type":"text/html; charset=utf-8"}, html_page("Report",body,u))

    def export_csv(self,u):
        rows=self.all_clients(); out=io.StringIO(); w=csv.writer(out); w.writerow(["receipt_no","client_name","mobile","city","product","quantity","amount_due","amount_paid","payment_status","names","notes","created_at"])
        for r in rows: w.writerow([r["receipt_no"],r["client_name"],r["mobile"],r["city"],r["product"],r["quantity"],r["amount_due"],r["amount_paid"],r["payment_status"],r["names"],r["notes"],r["created_at"]])
        self.sendx(200, {"Content-Type":"text/csv; charset=utf-8","Content-Disposition":"attachment; filename=bbamqb_report.csv"}, out.getvalue())

    def users(self,u):
        if u["role"]!="ROLE_ADMIN": return self.sendx(*redirect("/"))
        with get_conn() as conn:
            with conn.cursor() as cur: cur.execute("SELECT * FROM users ORDER BY id"); rows=cur.fetchall()
        rows_html="".join(f"<tr><td>{escape(r['username'])}</td><td>{escape(r['role'])}</td><td>{escape(r['mobile'] or '')}</td><td><a href='/user/delete/{r['id']}' onclick=\"return confirm('Delete user?')\">Delete</a></td></tr>" for r in rows)
        body=f"""<div class="top"><div><h1>Users</h1><p>Manage operators and admins.</p></div><a class="btn" href="/user/new">New User</a></div><div class="card"><table><tr><th>Username</th><th>Role</th><th>Mobile</th><th>Action</th></tr>{rows_html}</table></div>"""
        self.sendx(200, {"Content-Type":"text/html; charset=utf-8"}, html_page("Users",body,u))

    def user_form(self,u):
        if u["role"]!="ROLE_ADMIN": return self.sendx(*redirect("/"))
        role_opts=''.join(f'<option>{r}</option>' for r in ROLES)
        body=f"""<div class="top"><div><h1>New User</h1><p>Create admin/operator account.</p></div></div><div class="card"><form method="post" action="/user/save"><div class="row"><label>Username<input name="username" required></label><label>Password<input name="password" required></label><label>Mobile<input name="mobile"></label><label>Role<select name="role">{role_opts}</select></label></div><button class="btn">Save User</button></form></div>"""
        self.sendx(200, {"Content-Type":"text/html; charset=utf-8"}, html_page("New User",body,u))

    def save_user(self,u):
        if u["role"]!="ROLE_ADMIN": return self.sendx(*redirect("/"))
        d=self.body()
        with get_conn() as conn:
            with conn.cursor() as cur:
                try:
                    cur.execute("INSERT INTO users(username,password_hash,role,mobile,created_at) VALUES(%s,%s,%s,%s,%s)",(d.get("username",[""])[0].strip(),password_hash(d.get("password",[""])[0]),d.get("role",["ROLE_OPERATOR"])[0],d.get("mobile",[""])[0],now()))
                except Exception: pass
            conn.commit()
        self.sendx(*redirect("/users"))

    def delete_user(self,u,uid):
        if u["role"]!="ROLE_ADMIN": return self.sendx(*redirect("/"))
        with get_conn() as conn:
            with conn.cursor() as cur: cur.execute("DELETE FROM users WHERE id=%s AND username!='pyra'",(uid,))
            conn.commit()
        self.sendx(*redirect("/users"))

if __name__ == "__main__":
    init_db()
    print(f"BBAMQB Render PostgreSQL app running on {HOST}:{PORT}")
    ThreadingHTTPServer((HOST, PORT), App).serve_forever()
