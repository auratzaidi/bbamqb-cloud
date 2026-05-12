#!/usr/bin/env python3
"""
BBAMQB FAST 20K+ Render PostgreSQL App
Optimized for large qurbani entry volume.
Login default: pyra / admin123
"""

import os, csv, io, hmac, hashlib, secrets
from datetime import datetime
from html import escape
from http import cookies
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse, parse_qs, unquote, urlencode
import pg8000.dbapi

HOST = "0.0.0.0"
PORT = int(os.environ.get("PORT", "8090"))
DATABASE_URL = os.environ.get("DATABASE_URL")
SECRET = os.environ.get("BBAMQB_SECRET", "change-this-secret")

PRICE_PER_SHARE = 1600
PRODUCTS = {
    "Hissa": 1600,
    "Aqeeqa Girl": 1600,
    "Aqeeqa Boy": 3200,
}
PAYMENT_STATUS = ["Paid", "Unpaid", "Partial"]
ROLES = ["ROLE_ADMIN", "ROLE_OPERATOR"]
PAGE_SIZE = 50

def now():
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")

def rupees(n):
    try:
        return "₹{:,.0f}".format(int(n or 0))
    except Exception:
        return "₹0"

def get_conn():
    if not DATABASE_URL:
        raise RuntimeError("DATABASE_URL is missing")
    u = urlparse(DATABASE_URL)
    return pg8000.dbapi.connect(
        user=unquote(u.username or ""),
        password=unquote(u.password or ""),
        host=u.hostname,
        port=u.port or 5432,
        database=(u.path or "/").lstrip("/"),
        ssl_context=True
    )

def dict_one(cur):
    row = cur.fetchone()
    if row is None:
        return None
    return dict(zip([d[0] for d in cur.description], row))

def dict_all(cur):
    rows = cur.fetchall()
    cols = [d[0] for d in cur.description]
    return [dict(zip(cols, r)) for r in rows]

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
    if not header:
        return None
    try:
        c = cookies.SimpleCookie(header)
        token = c.get("bbamqb_session")
        if not token:
            return None
        username, sig = token.value.split("|", 1)
        if not hmac.compare_digest(sig, sign(username)):
            return None
        conn = get_conn(); cur = conn.cursor()
        cur.execute("SELECT * FROM users WHERE username=%s", (username,))
        row = dict_one(cur)
        cur.close(); conn.close()
        return row
    except Exception:
        return None

def receipt_no():
    return "BBQ-" + datetime.now().strftime("%Y%m%d%H%M%S%f")

def init_db():
    conn = get_conn(); cur = conn.cursor()
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
        payment_status TEXT NOT NULL DEFAULT 'Paid',
        names TEXT DEFAULT '',
        notes TEXT DEFAULT '',
        created_by TEXT DEFAULT '',
        created_at TEXT NOT NULL,
        updated_at TEXT NOT NULL,
        deleted_at TEXT DEFAULT NULL,
        deleted_by TEXT DEFAULT NULL,
        delete_reason TEXT DEFAULT ''
    );
    """)
    # Lightweight migrations for older deployed DBs
    for col_sql in [
        "ALTER TABLE clients ADD COLUMN IF NOT EXISTS deleted_at TEXT DEFAULT NULL",
        "ALTER TABLE clients ADD COLUMN IF NOT EXISTS deleted_by TEXT DEFAULT NULL",
        "ALTER TABLE clients ADD COLUMN IF NOT EXISTS delete_reason TEXT DEFAULT ''"
    ]:
        cur.execute(col_sql)

    # Indexes matter for 20k+ records.
    cur.execute("CREATE INDEX IF NOT EXISTS idx_clients_active_created ON clients(deleted_at, created_at DESC)")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_clients_created_by_active ON clients(created_by, deleted_at)")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_clients_receipt ON clients(receipt_no)")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_clients_mobile ON clients(mobile)")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_clients_name_lower ON clients(LOWER(client_name))")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_clients_created_at ON clients(created_at DESC)")

    cur.execute("SELECT COUNT(*) AS c FROM users")
    if dict_one(cur)["c"] == 0:
        cur.execute(
            "INSERT INTO users(username,password_hash,role,mobile,created_at) VALUES(%s,%s,%s,%s,%s)",
            ("pyra", password_hash("admin123"), "ROLE_ADMIN", "9870057600", now())
        )
    conn.commit(); cur.close(); conn.close()

CSS = """
*{box-sizing:border-box}
body{margin:0;font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Arial,sans-serif;background:#f6efe3;color:#15231d}
a{text-decoration:none;color:#0e5a4a;font-weight:800}
.layout{display:flex;min-height:100vh}
.sidebar{width:260px;background:#073b34;color:white;padding:22px;position:fixed;top:0;bottom:0}
.brand{font-size:22px;font-weight:900;margin-bottom:22px}
.brand small{display:block;font-size:12px;color:#cfe2dd}
nav a{display:block;color:white;padding:12px;border-radius:12px;margin:5px 0}
nav a:hover{background:rgba(255,255,255,.13)}
.userbox{position:absolute;bottom:20px;left:20px;right:20px;background:rgba(255,255,255,.12);padding:12px;border-radius:14px}
.main{margin-left:260px;padding:28px;width:calc(100% - 260px)}
.top{display:flex;justify-content:space-between;align-items:flex-start;margin-bottom:20px}
.top h1{margin:0;font-size:30px}.top p{color:#6d756f;margin:6px 0 0}
.card{background:#fffaf0;border:1px solid #e8ddca;border-radius:22px;padding:22px;margin-bottom:18px;box-shadow:0 12px 35px rgba(0,0,0,.06)}
.grid{display:grid;grid-template-columns:repeat(4,1fr);gap:14px}
.stat{background:white;border:1px solid #e8ddca;border-radius:18px;padding:18px}
.stat b{font-size:26px;display:block}.stat span{color:#6d756f;font-size:12px;text-transform:uppercase;font-weight:800}
.btn{display:inline-block;background:#0e5a4a;color:white;border:0;border-radius:12px;padding:10px 14px;font-weight:900;margin:3px;cursor:pointer;text-align:center}
.btn.secondary{background:#efe6d6;color:#15231d}.btn.gold{background:#b0832d;color:white}.btn.danger{background:#a83a32;color:white}
table{width:100%;border-collapse:collapse;background:white;border-radius:14px;overflow:hidden}
th,td{text-align:left;padding:12px;border-bottom:1px solid #eee;font-size:14px;vertical-align:top}
th{background:#fbf6ed;color:#6d756f;text-transform:uppercase;font-size:12px}
label{font-weight:800;font-size:13px;color:#314039;display:block;margin-bottom:12px}
input,select,textarea{width:100%;padding:12px;border:1px solid #e0d5c4;border-radius:12px;font:inherit;margin-top:6px;background:white}
textarea{min-height:90px}.row{display:grid;grid-template-columns:repeat(2,1fr);gap:14px}
.login-wrap{min-height:100vh;display:grid;place-items:center}.login{width:min(430px,94%);background:#fffaf0;border:1px solid #e8ddca;border-radius:24px;padding:30px}
.notice{background:#fff4d7;padding:12px;border-radius:12px;margin:10px 0}
.status-paid{color:#1f7a55;font-weight:900}.status-partial{color:#a46b00;font-weight:900}.status-unpaid{color:#a83a32;font-weight:900}
.pager{display:flex;gap:8px;align-items:center;justify-content:flex-end;flex-wrap:wrap}
.small{font-size:12px;color:#6d756f}
@media(max-width:850px){
.layout{display:block}.sidebar{position:relative;width:100%}.main{margin:0;width:100%;padding:14px}
.grid,.row{grid-template-columns:1fr}.top{display:block}table{display:block;overflow-x:auto;white-space:nowrap}
.btn{width:100%;margin:5px 0}.sidebar .userbox{position:static;margin-top:20px}
}
@media print{.sidebar,.btn,.pager,.no-print{display:none}.main{margin:0;width:100%;padding:0}.card{box-shadow:none;border:0}body{background:white}}
"""

def page(title, body, user=None):
    nav = ""
    if user:
        if user.get("role") == "ROLE_OPERATOR":
            menu = "<a href='/'>Dashboard</a><a href='/client/new'>Single Entry</a><a href='/client/multi'>7 Name Entry</a><a href='/logout'>Logout</a>"
        else:
            menu = "<a href='/'>Dashboard</a><a href='/clients'>Clients</a><a href='/client/new'>Single Entry</a><a href='/client/multi'>7 Name Entry</a><a href='/operator-summary'>Operator Summary</a><a href='/trash'>Deleted Entries</a><a href='/report'>Report</a><a href='/export.csv'>CSV Export</a><a href='/users'>Users</a><a href='/logout'>Logout</a>"
        nav = f"""<aside class="sidebar"><div class="brand">BBAMQB<small>Fast Operations Suite</small></div>
<nav>{menu}</nav>
<div class="userbox"><b>{escape(user['username'])}</b><br><small>{escape(user['role'])}</small></div></aside>"""
    return f"<!doctype html><html><head><meta charset='utf-8'><meta name='viewport' content='width=device-width, initial-scale=1'><title>{escape(title)}</title><style>{CSS}</style></head><body><div class='{'layout' if user else 'login-wrap'}'>{nav}<main class='{'main' if user else ''}'>{body}</main></div></body></html>"

def redirect(path):
    return (302, {"Location": path}, b"")

def qint(qs, key, default=1):
    try:
        return max(1, int(qs.get(key, [str(default)])[0] or default))
    except Exception:
        return default

class App(BaseHTTPRequestHandler):
    def sendx(self, status=200, headers=None, body=b""):
        self.send_response(status)
        for k,v in (headers or {}).items():
            self.send_header(k,v)
        self.end_headers()
        if isinstance(body,str):
            body=body.encode("utf-8")
        self.wfile.write(body)

    def form(self):
        l=int(self.headers.get("Content-Length",0))
        return parse_qs(self.rfile.read(l).decode("utf-8"))

    def user(self):
        return read_session(self.headers.get("Cookie"))

    def need_user(self):
        u=self.user()
        if not u:
            self.sendx(*redirect("/login"))
            return None
        return u

    def do_GET(self):
        path=urlparse(self.path).path
        if path=="/login": return self.login()
        if path=="/logout": return self.sendx(302, {"Location":"/login","Set-Cookie":"bbamqb_session=; Path=/; Max-Age=0"}, b"")
        u=self.need_user()
        if not u: return
        if path=="/": return self.dashboard(u)
        if u.get("role") == "ROLE_OPERATOR":
            if path=="/client/new": return self.client_form(u)
            if path=="/client/multi": return self.client_form(u, multi=True)
            return self.sendx(*redirect("/"))
        if path=="/clients": return self.clients(u)
        if path=="/client/new": return self.client_form(u)
        if path=="/client/multi": return self.client_form(u, multi=True)
        if path.startswith("/client/edit/"): return self.client_form(u, path.split("/")[-1])
        if path.startswith("/client/delete/"): return self.delete_client(u, path.split("/")[-1])
        if path.startswith("/client/restore/"): return self.restore_client(path.split("/")[-1])
        if path.startswith("/receipt/"): return self.receipt(u, path.split("/")[-1])
        if path=="/operator-summary": return self.operator_summary(u)
        if path=="/trash": return self.trash(u)
        if path=="/report": return self.report(u)
        if path=="/export.csv": return self.export_csv()
        if path=="/users": return self.users(u)
        if path=="/user/new": return self.user_form(u)
        if path.startswith("/user/delete/"): return self.delete_user(u, path.split("/")[-1])
        self.sendx(404, {"Content-Type":"text/html"}, page("404","<div class='card'><h1>404</h1></div>",u))

    def do_POST(self):
        path=urlparse(self.path).path
        if path=="/login": return self.login_post()
        u=self.need_user()
        if not u: return
        if path=="/client/save": return self.save_client(u)
        if path=="/user/save": return self.save_user(u)
        self.sendx(*redirect("/"))

    def login(self,msg=""):
        body=f"<div class='login'><h1>BBAMQB Login</h1>{f'<div class=notice>{escape(msg)}</div>' if msg else ''}<form method='post' action='/login'><label>Username<input name='username'></label><label>Password<input type='password' name='password'></label><button class='btn' style='width:100%'>Login</button></form></div>"
        self.sendx(200, {"Content-Type":"text/html; charset=utf-8"}, page("Login", body))

    def login_post(self):
        d=self.form(); username=d.get("username",[""])[0].strip(); password=d.get("password",[""])[0]
        conn=get_conn(); cur=conn.cursor()
        cur.execute("SELECT * FROM users WHERE username=%s",(username,))
        row=dict_one(cur); cur.close(); conn.close()
        if row and password_ok(password,row["password_hash"]):
            self.sendx(302, {"Location":"/","Set-Cookie":f"bbamqb_session={make_session(username)}; Path=/; HttpOnly; SameSite=Lax"}, b"")
        else:
            self.login("Invalid username or password.")

    def summary_for_user(self, username=None):
        conn=get_conn(); cur=conn.cursor()
        if username:
            cur.execute("SELECT COUNT(*) AS entries, COALESCE(SUM(amount_due),0) AS total FROM clients WHERE deleted_at IS NULL AND created_by=%s", (username,))
        else:
            cur.execute("SELECT COUNT(*) AS entries, COALESCE(SUM(amount_due),0) AS total FROM clients WHERE deleted_at IS NULL")
        row=dict_one(cur); cur.close(); conn.close()
        return row

    def dashboard(self,u):
        if u.get("role") == "ROLE_OPERATOR":
            s = self.summary_for_user(u["username"])
            body=f"""<div class='top'><div><h1>Dashboard</h1></div></div>
            <div class='grid' style='grid-template-columns:repeat(2,minmax(0,1fr));'>
              <div class='stat'><b>{s['entries']}</b><span>Total Entries</span></div>
              <div class='stat'><b>{rupees(s['total'])}</b><span>Amount Collected</span></div>
            </div>
            <div class='card'><a class='btn' href='/client/new'>Single Entry</a><a class='btn gold' href='/client/multi'>7 Name Entry</a></div>"""
            self.sendx(200, {"Content-Type":"text/html; charset=utf-8"}, page("Dashboard",body,u))
            return
        s = self.summary_for_user()
        conn=get_conn(); cur=conn.cursor()
        cur.execute("SELECT COUNT(*) AS deleted FROM clients WHERE deleted_at IS NOT NULL")
        deleted=dict_one(cur)["deleted"]
        cur.execute("SELECT COUNT(*) AS operators FROM users WHERE role='ROLE_OPERATOR'")
        ops=dict_one(cur)["operators"]
        cur.close(); conn.close()
        body=f"""<div class='top'><div><h1>Dashboard</h1><p>Admin overview</p></div></div>
        <div class='grid'>
          <div class='stat'><b>{s['entries']}</b><span>Active Entries</span></div>
          <div class='stat'><b>{rupees(s['total'])}</b><span>Total Collection</span></div>
          <div class='stat'><b>{ops}</b><span>Operators</span></div>
          <div class='stat'><b>{deleted}</b><span>Deleted Entries</span></div>
        </div>
        <div class='card'><a class='btn' href='/clients'>Search Entries</a><a class='btn gold' href='/operator-summary'>Operator Summary</a><a class='btn secondary' href='/export.csv'>CSV Export</a></div>"""
        self.sendx(200, {"Content-Type":"text/html; charset=utf-8"}, page("Dashboard",body,u))

    def client_head(self):
        return "<tr><th>Receipt</th><th>Name</th><th>Mobile</th><th>Product</th><th>Qty</th><th>Amount</th><th>Time</th><th>Operator</th><th>Actions</th></tr>"

    def client_row(self,r, trash=False):
        actions = f"<a href='/receipt/{r['id']}'>Receipt</a> · <a href='/client/edit/{r['id']}'>Edit</a> · <a class='danger-link' href='/client/delete/{r['id']}' onclick=\"return confirm('Move this entry to trash?')\">🗑</a>"
        if trash:
            actions = f"<a href='/client/restore/{r['id']}'>Restore</a>"
        return f"<tr><td>{escape(r['receipt_no'])}</td><td><b>{escape(r['client_name'])}</b><br><small>{escape(r['city'] or '')}</small></td><td>{escape(r['mobile'] or '')}</td><td>{escape(r['product'])}</td><td>{r['quantity']}</td><td>{rupees(r['amount_due'])}</td><td><span class='small'>{escape(r['created_at'])}</span></td><td>{escape(r['created_by'] or '')}</td><td>{actions}</td></tr>"

    def clients_query(self, include_deleted=False):
        qs=parse_qs(urlparse(self.path).query)
        search=qs.get("q",[""])[0].strip()
        page_no=qint(qs,"page",1)
        offset=(page_no-1)*PAGE_SIZE
        where = "WHERE deleted_at IS NOT NULL" if include_deleted else "WHERE deleted_at IS NULL"
        args=[]
        if search:
            like="%"+search.lower()+"%"
            where += " AND (LOWER(client_name) LIKE %s OR mobile LIKE %s OR receipt_no LIKE %s)"
            args += [like, "%"+search+"%", "%"+search+"%"]
        conn=get_conn(); cur=conn.cursor()
        cur.execute(f"SELECT COUNT(*) AS c FROM clients {where}", tuple(args))
        total=dict_one(cur)["c"]
        cur.execute(f"SELECT * FROM clients {where} ORDER BY id DESC LIMIT %s OFFSET %s", tuple(args+[PAGE_SIZE, offset]))
        rows=dict_all(cur); cur.close(); conn.close()
        return rows,total,page_no,search

    def pager(self, base, page_no, total, search=""):
        pages=max(1, (int(total)+PAGE_SIZE-1)//PAGE_SIZE)
        prev_q=urlencode({"q":search,"page":max(1,page_no-1)})
        next_q=urlencode({"q":search,"page":min(pages,page_no+1)})
        return f"<div class='pager'><span class='small'>Page {page_no} of {pages} · {total} records</span><a class='btn secondary' href='{base}?{prev_q}'>Previous</a><a class='btn secondary' href='{base}?{next_q}'>Next</a></div>"

    def clients(self,u):
        rows,total,page_no,search=self.clients_query(False)
        rows_html="".join(self.client_row(r) for r in rows) or "<tr><td colspan=9>No data</td></tr>"
        body=f"""<div class='top'><div><h1>Clients</h1><p>Fast paginated search. Showing {PAGE_SIZE} records per page.</p></div><a class='btn' href='/client/new'>Single Entry</a></div>
        <div class='card no-print'><form method='get' action='/clients'><div class='row'><label>Search Name / Phone / Receipt<input name='q' value='{escape(search)}'></label><label>&nbsp;<button class='btn'>Search</button></label></div></form></div>
        <div class='card'>{self.pager('/clients',page_no,total,search)}<table>{self.client_head()}{rows_html}</table>{self.pager('/clients',page_no,total,search)}</div>"""
        self.sendx(200, {"Content-Type":"text/html; charset=utf-8"}, page("Clients",body,u))

    def client_form(self,u,client_id=None,multi=False):
        r=None
        if client_id:
            conn=get_conn(); cur=conn.cursor()
            cur.execute("SELECT * FROM clients WHERE id=%s",(client_id,))
            r=dict_one(cur); cur.close(); conn.close()
        def val(k,d=""): return escape(str(r[k] if r and r[k] is not None else d))
        title="Edit Entry" if r else ("7 Name Entry" if multi else "Single Entry")
        if multi and not r:
            product_options=''.join(f'<option value="{escape(p)}">{escape(p)} — {rupees(price)}</option>' for p,price in PRODUCTS.items())
            rows=""
            for i in range(1,8):
                rows += f"""<div class='row' style='border:1px solid #e8ddca;border-radius:14px;padding:12px;margin-bottom:10px;background:#fff;'>
                    <label>Name {i}<input name='name_{i}' placeholder='Enter name'></label>
                    <label>Telephone {i}<input name='phone_{i}' placeholder='Enter phone'></label>
                    <label>Product {i}<select name='product_{i}'>{product_options}</select></label>
                    <label>Remarks {i}<input name='note_{i}' placeholder='Optional'></label>
                </div>"""
            body=f"""<div class='top'><div><h1>7 Name Entry</h1><p>Seven separate participant records. Each saved row counts as one entry.</p></div></div>
            <div class='card'><form method='post' action='/client/save'><input type='hidden' name='multi_mode' value='1'>
            <div class='row'><label>Common City<input name='city'></label><label>Common Address<input name='address'></label></div>
            {rows}<button class='btn'>Save 7 Entries</button></form></div>"""
            self.sendx(200, {"Content-Type":"text/html; charset=utf-8"}, page(title,body,u)); return
        product_opts=''.join(f'<option value="{escape(p)}" {"selected" if (r and r["product"]==p) or ((not r) and p=="Hissa") else ""}>{escape(p)} — {rupees(price)}</option>' for p,price in PRODUCTS.items())
        body=f"""<div class='top'><div><h1>{title}</h1></div></div><div class='card'><form method='post' action='/client/save'><input type='hidden' name='id' value='{val('id')}'>
        <div class='row'><label>Client Name<input name='client_name' required value='{val('client_name')}'></label><label>Mobile<input name='mobile' value='{val('mobile')}'></label>
        <label>City<input name='city' value='{val('city')}'></label><label>Product<select name='product'>{product_opts}</select></label>
        <label>Quantity<input type='number' min='1' name='quantity' value='{val('quantity',1)}'></label><label>Address<input name='address' value='{val('address')}'></label></div>
        <label>Notes<textarea name='notes'>{val('notes')}</textarea></label><button class='btn'>Save Entry</button></form></div>"""
        self.sendx(200, {"Content-Type":"text/html; charset=utf-8"}, page(title,body,u))

    def save_client(self,u):
        d=self.form()
        if d.get("multi_mode", [""])[0] == "1":
            city=d.get("city",[""])[0].strip(); address=d.get("address",[""])[0].strip()
            conn=get_conn(); cur=conn.cursor()
            for i in range(1,8):
                name=d.get(f"name_{i}",[""])[0].strip()
                phone=d.get(f"phone_{i}",[""])[0].strip()
                product=d.get(f"product_{i}",["Hissa"])[0]
                note=d.get(f"note_{i}",[""])[0].strip()
                if not name and not phone:
                    continue
                due=PRODUCTS.get(product, PRICE_PER_SHARE)
                cur.execute("INSERT INTO clients(receipt_no,client_name,mobile,city,address,product,quantity,amount_due,amount_paid,payment_status,names,notes,created_by,created_at,updated_at) VALUES(%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)",
                    (receipt_no(), name or f"Participant {i}", phone, city, address, product, 1, due, due, "Paid", name, note, u["username"], now(), now()))
            conn.commit(); cur.close(); conn.close(); self.sendx(*redirect("/")); return
        cid=d.get("id",[""])[0].strip()
        product=d.get("product",["Hissa"])[0]
        qty=max(1,int(d.get("quantity",["1"])[0] or 1))
        due=PRODUCTS.get(product, PRICE_PER_SHARE)*qty
        vals=(d.get("client_name",[""])[0].strip(),d.get("mobile",[""])[0].strip(),d.get("city",[""])[0].strip(),d.get("address",[""])[0].strip(),product,qty,due,due,"Paid",d.get("client_name",[""])[0].strip(),d.get("notes",[""])[0].strip(),now())
        conn=get_conn(); cur=conn.cursor()
        if cid:
            cur.execute("UPDATE clients SET client_name=%s,mobile=%s,city=%s,address=%s,product=%s,quantity=%s,amount_due=%s,amount_paid=%s,payment_status=%s,names=%s,notes=%s,updated_at=%s WHERE id=%s", vals+(cid,))
        else:
            cur.execute("INSERT INTO clients(receipt_no,client_name,mobile,city,address,product,quantity,amount_due,amount_paid,payment_status,names,notes,created_by,created_at,updated_at) VALUES(%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)",
                (receipt_no(),)+vals[:11]+(u["username"],now(),now()))
        conn.commit(); cur.close(); conn.close(); self.sendx(*redirect("/"))

    def delete_client(self,u,cid):
        conn=get_conn(); cur=conn.cursor()
        cur.execute("UPDATE clients SET deleted_at=%s, deleted_by=%s, delete_reason=%s WHERE id=%s", (now(), u["username"], "Operator/admin trash", cid))
        conn.commit(); cur.close(); conn.close(); self.sendx(*redirect("/clients"))

    def restore_client(self,cid):
        conn=get_conn(); cur=conn.cursor()
        cur.execute("UPDATE clients SET deleted_at=NULL, deleted_by=NULL, delete_reason='' WHERE id=%s", (cid,))
        conn.commit(); cur.close(); conn.close(); self.sendx(*redirect("/trash"))

    def receipt(self,u,cid):
        conn=get_conn(); cur=conn.cursor()
        cur.execute("SELECT * FROM clients WHERE id=%s",(cid,))
        r=dict_one(cur); cur.close(); conn.close()
        if not r: return self.sendx(*redirect("/clients"))
        body=f"""<div class='top'><div><h1>Receipt</h1><p>{escape(r['receipt_no'])}</p></div><button class='btn' onclick='window.print()'>Print</button></div>
        <div class='card'><h2>Bazme Barkate Aley Mustafa Trust</h2><table>
        <tr><td>Receipt</td><td>{escape(r['receipt_no'])}</td></tr><tr><td>Date/Time</td><td>{escape(r['created_at'])}</td></tr>
        <tr><td>Name</td><td>{escape(r['client_name'])}</td></tr><tr><td>Mobile</td><td>{escape(r['mobile'] or '')}</td></tr>
        <tr><td>Product</td><td>{escape(r['product'])} × {r['quantity']}</td></tr><tr><td>Amount</td><td>{rupees(r['amount_due'])}</td></tr>
        <tr><td>Operator</td><td>{escape(r['created_by'] or '')}</td></tr></table></div>"""
        self.sendx(200, {"Content-Type":"text/html; charset=utf-8"}, page("Receipt",body,u))

    def operator_summary(self,u):
        conn=get_conn(); cur=conn.cursor()
        cur.execute("""SELECT created_by, COUNT(*) AS entries, COALESCE(SUM(amount_due),0) AS total
                       FROM clients WHERE deleted_at IS NULL GROUP BY created_by ORDER BY total DESC""")
        rows=dict_all(cur); cur.close(); conn.close()
        trs="".join(f"<tr><td>{escape(r['created_by'] or 'Unknown')}</td><td>{r['entries']}</td><td>{rupees(r['total'])}</td></tr>" for r in rows)
        body=f"<div class='top'><div><h1>Operator Summary</h1><p>Fast reconciliation by operator.</p></div></div><div class='card'><table><tr><th>Operator</th><th>Entries</th><th>Amount</th></tr>{trs}</table></div>"
        self.sendx(200, {"Content-Type":"text/html; charset=utf-8"}, page("Operator Summary",body,u))

    def trash(self,u):
        rows,total,page_no,search=self.clients_query(True)
        trs="".join(self.client_row(r, trash=True) for r in rows) or "<tr><td colspan=9>No deleted entries.</td></tr>"
        body=f"""<div class='top'><div><h1>Deleted Entries</h1><p>Soft-deleted records remain auditable.</p></div></div>
        <div class='card no-print'><form method='get' action='/trash'><div class='row'><label>Search<input name='q' value='{escape(search)}'></label><label>&nbsp;<button class='btn'>Search</button></label></div></form></div>
        <div class='card'>{self.pager('/trash',page_no,total,search)}<table>{self.client_head()}{trs}</table>{self.pager('/trash',page_no,total,search)}</div>"""
        self.sendx(200, {"Content-Type":"text/html; charset=utf-8"}, page("Deleted Entries",body,u))

    def report(self,u):
        return self.operator_summary(u)

    def export_csv(self):
        conn=get_conn(); cur=conn.cursor()
        cur.execute("SELECT receipt_no,client_name,mobile,city,product,quantity,amount_due,created_by,created_at FROM clients WHERE deleted_at IS NULL ORDER BY id DESC")
        rows=dict_all(cur); cur.close(); conn.close()
        out=io.StringIO(); w=csv.writer(out)
        w.writerow(["receipt_no","client_name","mobile","city","product","quantity","amount","operator","created_at"])
        for r in rows:
            w.writerow([r["receipt_no"],r["client_name"],r["mobile"],r["city"],r["product"],r["quantity"],r["amount_due"],r["created_by"],r["created_at"]])
        self.sendx(200, {"Content-Type":"text/csv; charset=utf-8","Content-Disposition":"attachment; filename=bbamqb_report.csv"}, out.getvalue())

    def users(self,u):
        if u["role"]!="ROLE_ADMIN": return self.sendx(*redirect("/"))
        conn=get_conn(); cur=conn.cursor(); cur.execute("SELECT * FROM users ORDER BY id"); rows=dict_all(cur); cur.close(); conn.close()
        html="".join(f"<tr><td>{escape(r['username'])}</td><td>{escape(r['role'])}</td><td>{escape(r['mobile'] or '')}</td><td><a href='/user/delete/{r['id']}'>Delete</a></td></tr>" for r in rows)
        body=f"<div class='top'><div><h1>Users</h1></div><a class='btn' href='/user/new'>New User</a></div><div class='card'><table><tr><th>Username</th><th>Role</th><th>Mobile</th><th>Action</th></tr>{html}</table></div>"
        self.sendx(200, {"Content-Type":"text/html; charset=utf-8"}, page("Users",body,u))

    def user_form(self,u):
        if u["role"]!="ROLE_ADMIN": return self.sendx(*redirect("/"))
        body=f"<div class='top'><div><h1>New User</h1></div></div><div class='card'><form method='post' action='/user/save'><div class='row'><label>Username<input name='username' required></label><label>Password<input name='password' required></label><label>Mobile<input name='mobile'></label><label>Role<select name='role'>{''.join(f'<option>{r}</option>' for r in ROLES)}</select></label></div><button class='btn'>Save User</button></form></div>"
        self.sendx(200, {"Content-Type":"text/html; charset=utf-8"}, page("New User",body,u))

    def save_user(self,u):
        if u["role"]!="ROLE_ADMIN": return self.sendx(*redirect("/"))
        d=self.form(); conn=get_conn(); cur=conn.cursor()
        try:
            cur.execute("INSERT INTO users(username,password_hash,role,mobile,created_at) VALUES(%s,%s,%s,%s,%s)",(d.get("username",[""])[0].strip(),password_hash(d.get("password",[""])[0]),d.get("role",["ROLE_OPERATOR"])[0],d.get("mobile",[""])[0],now()))
        except Exception:
            pass
        conn.commit(); cur.close(); conn.close(); self.sendx(*redirect("/users"))

    def delete_user(self,u,uid):
        if u["role"]!="ROLE_ADMIN": return self.sendx(*redirect("/"))
        conn=get_conn(); cur=conn.cursor(); cur.execute("DELETE FROM users WHERE id=%s AND username!='pyra'",(uid,)); conn.commit(); cur.close(); conn.close(); self.sendx(*redirect("/users"))

if __name__ == "__main__":
    init_db()
    print(f"BBAMQB FAST 20K app running on {HOST}:{PORT}")
    ThreadingHTTPServer((HOST, PORT), App).serve_forever()
