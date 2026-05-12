#!/usr/bin/env python3
import os, csv, io, hmac, hashlib, secrets
from datetime import datetime
from html import escape
from http import cookies
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse, parse_qs, unquote
import pg8000.dbapi

HOST = "0.0.0.0"
PORT = int(os.environ.get("PORT", "8090"))
DATABASE_URL = os.environ.get("DATABASE_URL")
SECRET = os.environ.get("BBAMQB_SECRET", "change-this-secret")
PRODUCTS = {"Hissa":1600, "Aqeeqa Girl":1600, "Aqeeqa Boy":3200}
PAYMENT_STATUS = ["Unpaid", "Partial", "Paid"]
ROLES = ["ROLE_ADMIN", "ROLE_OPERATOR"]

def now(): return datetime.now().strftime("%Y-%m-%d %H:%M:%S")
def rupees(n):
    try: return "₹{:,.0f}".format(int(n or 0))
    except Exception: return "₹0"

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
    if row is None: return None
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

def sign(value): return hmac.new(SECRET.encode(), value.encode(), hashlib.sha256).hexdigest()
def make_session(username): return username + "|" + sign(username)

def read_session(header):
    if not header: return None
    try:
        c = cookies.SimpleCookie(header)
        token = c.get("bbamqb_session")
        if not token: return None
        username, sig = token.value.split("|", 1)
        if not hmac.compare_digest(sig, sign(username)): return None
        conn = get_conn(); cur = conn.cursor()
        cur.execute("SELECT * FROM users WHERE username=%s", (username,))
        row = dict_one(cur)
        cur.close(); conn.close()
        return row
    except Exception:
        return None

def receipt_no(): return "BBQ-" + datetime.now().strftime("%Y%m%d%H%M%S")

def init_db():
    conn = get_conn(); cur = conn.cursor()
    cur.execute("""CREATE TABLE IF NOT EXISTS users (
        id SERIAL PRIMARY KEY, username TEXT UNIQUE NOT NULL, password_hash TEXT NOT NULL,
        role TEXT NOT NULL DEFAULT 'ROLE_OPERATOR', mobile TEXT DEFAULT '', created_at TEXT NOT NULL);""")
    cur.execute("""CREATE TABLE IF NOT EXISTS clients (
        id SERIAL PRIMARY KEY, receipt_no TEXT UNIQUE NOT NULL, client_name TEXT NOT NULL,
        mobile TEXT DEFAULT '', city TEXT DEFAULT '', address TEXT DEFAULT '', product TEXT NOT NULL,
        quantity INTEGER NOT NULL DEFAULT 1, amount_due INTEGER NOT NULL DEFAULT 0,
        amount_paid INTEGER NOT NULL DEFAULT 0, payment_status TEXT NOT NULL DEFAULT 'Unpaid',
        names TEXT DEFAULT '', notes TEXT DEFAULT '', created_by TEXT DEFAULT '',
        created_at TEXT NOT NULL, updated_at TEXT NOT NULL);""")
    cur.execute("SELECT COUNT(*) AS c FROM users")
    if dict_one(cur)["c"] == 0:
        cur.execute("INSERT INTO users(username,password_hash,role,mobile,created_at) VALUES(%s,%s,%s,%s,%s)",
                    ("pyra", password_hash("admin123"), "ROLE_ADMIN", "9870057600", now()))
    conn.commit(); cur.close(); conn.close()

CSS = """
*{box-sizing:border-box}body{margin:0;font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Arial,sans-serif;background:#f6efe3;color:#15231d}a{text-decoration:none;color:#0e5a4a;font-weight:700}
.layout{display:flex;min-height:100vh}.sidebar{width:260px;background:#073b34;color:white;padding:22px;position:fixed;top:0;bottom:0}.brand{font-size:22px;font-weight:900;margin-bottom:22px}.brand small{display:block;font-size:12px;color:#cfe2dd}
nav a{display:block;color:white;padding:12px;border-radius:12px;margin:5px 0}nav a:hover{background:rgba(255,255,255,.13)}.userbox{position:absolute;bottom:20px;left:20px;right:20px;background:rgba(255,255,255,.12);padding:12px;border-radius:14px}
.main{margin-left:260px;padding:28px;width:calc(100% - 260px)}.top{display:flex;justify-content:space-between;align-items:flex-start;margin-bottom:20px}.top h1{margin:0;font-size:30px}.top p{color:#6d756f}
.card{background:#fffaf0;border:1px solid #e8ddca;border-radius:22px;padding:22px;margin-bottom:18px;box-shadow:0 12px 35px rgba(0,0,0,.06)}.grid{display:grid;grid-template-columns:repeat(4,1fr);gap:14px}.stat{background:white;border:1px solid #e8ddca;border-radius:18px;padding:18px}.stat b{font-size:26px;display:block}.stat span{color:#6d756f;font-size:12px;text-transform:uppercase;font-weight:800}
.btn{display:inline-block;background:#0e5a4a;color:white;border:0;border-radius:12px;padding:10px 14px;font-weight:800;margin:3px;cursor:pointer}.btn.secondary{background:#efe6d6;color:#15231d}.btn.gold{background:#b0832d;color:white}
table{width:100%;border-collapse:collapse;background:white;border-radius:14px;overflow:hidden}th,td{text-align:left;padding:12px;border-bottom:1px solid #eee;font-size:14px}th{background:#fbf6ed;color:#6d756f;text-transform:uppercase;font-size:12px}
label{font-weight:800;font-size:13px;color:#314039;display:block;margin-bottom:12px}input,select,textarea{width:100%;padding:12px;border:1px solid #e0d5c4;border-radius:12px;font:inherit;margin-top:6px}textarea{min-height:90px}.row{display:grid;grid-template-columns:repeat(2,1fr);gap:14px}
.login-wrap{min-height:100vh;display:grid;place-items:center}.login{width:min(430px,94%);background:#fffaf0;border:1px solid #e8ddca;border-radius:24px;padding:30px}.notice{background:#fff4d7;padding:12px;border-radius:12px;margin:10px 0}
.status-paid{color:#1f7a55;font-weight:900}.status-partial{color:#a46b00;font-weight:900}.status-unpaid{color:#a83a32;font-weight:900}
@media(max-width:850px){.layout{display:block}.sidebar{position:relative;width:100%}.main{margin:0;width:100%;padding:14px}.grid,.row{grid-template-columns:1fr}table{display:block;overflow-x:auto;white-space:nowrap}.btn{width:100%;text-align:center}}
"""

def page(title, body, user=None):
    nav = ""
    if user:
        nav = f"""<aside class="sidebar"><div class="brand">BBAMQB<small>Operations Suite</small></div>
<nav><a href="/">Dashboard</a><a href="/clients">Clients</a><a href="/client/new">New Entry</a><a href="/client/multi">7 Name Entry</a><a href="/report">Reports</a><a href="/export.csv">CSV Export</a><a href="/users">Users</a><a href="/logout">Logout</a></nav>
<div class="userbox"><b>{escape(user['username'])}</b><br><small>{escape(user['role'])}</small></div></aside>"""
    return f"<!doctype html><html><head><meta charset='utf-8'><meta name='viewport' content='width=device-width, initial-scale=1'><title>{escape(title)}</title><style>{CSS}</style></head><body><div class='{'layout' if user else 'login-wrap'}'>{nav}<main class='{'main' if user else ''}'>{body}</main></div></body></html>"

def redirect(path): return (302, {"Location": path}, b"")

class App(BaseHTTPRequestHandler):
    def sendx(self, status=200, headers=None, body=b""):
        self.send_response(status)
        for k,v in (headers or {}).items(): self.send_header(k,v)
        self.end_headers()
        if isinstance(body,str): body=body.encode()
        self.wfile.write(body)
    def form(self):
        l=int(self.headers.get("Content-Length",0))
        return parse_qs(self.rfile.read(l).decode())
    def user(self): return read_session(self.headers.get("Cookie"))
    def need_user(self):
        u=self.user()
        if not u: self.sendx(*redirect("/login")); return None
        return u
    def do_GET(self):
        path=urlparse(self.path).path
        if path=="/login": return self.login()
        if path=="/logout": return self.sendx(302, {"Location":"/login","Set-Cookie":"bbamqb_session=; Path=/; Max-Age=0"}, b"")
        u=self.need_user()
        if not u: return
        if path=="/": return self.dashboard(u)
        if path=="/clients": return self.clients(u)
        if path=="/client/new": return self.client_form(u)
        if path=="/client/multi": return self.client_form(u, multi=True)
        if path.startswith("/client/edit/"): return self.client_form(u, path.split("/")[-1])
        if path.startswith("/client/delete/"): return self.delete_client(path.split("/")[-1])
        if path.startswith("/receipt/"): return self.receipt(u, path.split("/")[-1])
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
        body=f"<div class='login'><h1>BBAMQB Login</h1>{f'<div class=notice>{escape(msg)}</div>' if msg else ''}<form method='post' action='/login'><label>Username<input name='username' value=''></label><label>Password<input type='password' name='password' value=''></label><button class='btn' style='width:100%'>Login</button></form></div>"
        self.sendx(200, {"Content-Type":"text/html; charset=utf-8"}, page("Login", body))
    def login_post(self):
        d=self.form(); username=d.get("username",[""])[0].strip(); password=d.get("password",[""])[0]
        conn=get_conn(); cur=conn.cursor(); cur.execute("SELECT * FROM users WHERE username=%s",(username,)); row=dict_one(cur); cur.close(); conn.close()
        if row and password_ok(password,row["password_hash"]):
            self.sendx(302, {"Location":"/","Set-Cookie":f"bbamqb_session={make_session(username)}; Path=/; HttpOnly; SameSite=Lax"}, b"")
        else: self.login("Invalid username or password.")
    def all_clients(self):
        conn=get_conn(); cur=conn.cursor(); cur.execute("SELECT * FROM clients ORDER BY id DESC"); rows=dict_all(cur); cur.close(); conn.close(); return rows
    def client_head(self): return "<tr><th>Receipt</th><th>Name</th><th>Mobile</th><th>Product</th><th>Qty</th><th>Due</th><th>Paid</th><th>Status</th><th>Actions</th></tr>"
    def client_row(self,r):
        cls={"Paid":"status-paid","Partial":"status-partial","Unpaid":"status-unpaid"}.get(r["payment_status"],"")
        return f"<tr><td>{escape(r['receipt_no'])}</td><td><b>{escape(r['client_name'])}</b><br><small>{escape(r['city'] or '')}</small></td><td>{escape(r['mobile'] or '')}</td><td>{escape(r['product'])}</td><td>{r['quantity']}</td><td>{rupees(r['amount_due'])}</td><td>{rupees(r['amount_paid'])}</td><td class='{cls}'>{escape(r['payment_status'])}</td><td><a href='/receipt/{r['id']}'>Receipt</a> · <a href='/client/edit/{r['id']}'>Edit</a> · <a href='/client/delete/{r['id']}'>Delete</a></td></tr>"
    def stats(self):
        rows=self.all_clients()
        due=sum(int(r["amount_due"] or 0) for r in rows); paid=sum(int(r["amount_paid"] or 0) for r in rows)
        return rows,due,paid
    def dashboard(self,u):
        rows,due,paid=self.stats(); recent="".join(self.client_row(r) for r in rows[:8]) or "<tr><td colspan=9>No entries yet.</td></tr>"
        body=f"<div class='top'><div><h1>Dashboard</h1><p>Cloud PostgreSQL Operations Suite</p></div></div><div class='grid'><div class='stat'><b>{len(rows)}</b><span>Entries</span></div><div class='stat'><b>{sum(int(r['quantity'] or 0) for r in rows)}</b><span>Shares</span></div><div class='stat'><b>{rupees(due)}</b><span>Total Due</span></div><div class='stat'><b>{rupees(paid)}</b><span>Collected</span></div></div><div class='card'><a class='btn' href='/client/new'>New Entry</a><a class='btn gold' href='/client/multi'>7 Name Entry</a><a class='btn secondary' href='/report'>Report</a></div><div class='card'><h2>Recent Entries</h2><table>{self.client_head()}{recent}</table></div>"
        self.sendx(200, {"Content-Type":"text/html; charset=utf-8"}, page("Dashboard",body,u))
    def clients(self,u):
        rows=self.all_clients(); body=f"<div class='top'><div><h1>Clients</h1><p>Manage records</p></div><a class='btn' href='/client/new'>New Entry</a></div><div class='card'><table>{self.client_head()}{''.join(self.client_row(r) for r in rows) or '<tr><td colspan=9>No data</td></tr>'}</table></div>"
        self.sendx(200, {"Content-Type":"text/html; charset=utf-8"}, page("Clients",body,u))
    def client_form(self,u,client_id=None,multi=False):
        r=None
        if client_id:
            conn=get_conn(); cur=conn.cursor(); cur.execute("SELECT * FROM clients WHERE id=%s",(client_id,)); r=dict_one(cur); cur.close(); conn.close()
        def val(k,d=""): return escape(str(r[k] if r and r[k] is not None else d))
        title="Edit Entry" if r else ("7 Name Entry" if multi else "New Entry")
        product_opts=''.join(f'<option value="{escape(p)}" {"selected" if (r and r["product"]==p) or ((not r) and p=="Hissa") else ""}>{escape(p)} — {rupees(price)}</option>' for p,price in PRODUCTS.items())
        status_opts=''.join(f'<option {"selected" if (r and r["payment_status"]==s) else ""}>{s}</option>' for s in PAYMENT_STATUS)

        if multi and not r:
            product_options_plain = ''.join(f'<option value="{escape(p)}">{escape(p)} — {rupees(price)}</option>' for p,price in PRODUCTS.items())
            seven_rows = ""
            for i in range(1,8):
                seven_rows += f"""
                <div class='row' style='border:1px solid #e8ddca;border-radius:14px;padding:12px;margin-bottom:10px;background:#fff;'>
                  <label>Name {i}<input name='name_{i}' placeholder='Enter name {i}'></label>
                  <label>Telephone {i}<input name='phone_{i}' placeholder='Enter phone number {i}'></label>
                  <label>Product {i}<select name='product_{i}'>{product_options_plain}</select></label>
                  <label>Amount Paid {i}<input type='number' min='0' name='paid_{i}' placeholder='Amount paid'></label>
                </div>
                """
            body=f"""
            <div class='top'><div><h1>7 Name Entry</h1><p>Enter seven separate participant records. Each row creates one client entry.</p></div></div>
            <div class='card'>
              <form method='post' action='/client/save'>
                <input type='hidden' name='multi_mode' value='1'>
                <div class='row'>
                  <label>Common City<input name='city' placeholder='City / location'></label>
                  <label>Common Address<input name='address' placeholder='Address if same for all'></label>
                  <label>Common Payment Status<select name='payment_status'>{status_opts}</select></label>
                  <label>Common Notes<input name='notes' placeholder='Optional notes'></label>
                </div>
                <h2>Seven Participants</h2>
                {seven_rows}
                <button class='btn'>Save 7 Entries</button>
                <a class='btn secondary' href='/clients'>Cancel</a>
              </form>
            </div>
            """
            self.sendx(200, {"Content-Type":"text/html; charset=utf-8"}, page(title,body,u))
            return

        names_value = escape((r["names"] if r else "") or "")
        body=f"<div class='top'><div><h1>{title}</h1></div></div><div class='card'><form method='post' action='/client/save'><input type='hidden' name='id' value='{val('id')}'><div class='row'><label>Client Name<input name='client_name' required value='{val('client_name')}'></label><label>Mobile<input name='mobile' value='{val('mobile')}'></label><label>City<input name='city' value='{val('city')}'></label><label>Product<select name='product'>{product_opts}</select></label><label>Quantity<input type='number' min='1' name='quantity' value='{val('quantity',1)}'></label><label>Amount Paid<input type='number' min='0' name='amount_paid' value='{val('amount_paid','')}'></label><label>Payment Status<select name='payment_status'>{status_opts}</select></label><label>Address<input name='address' value='{val('address')}'></label></div><label>Names / Share Holders<textarea name='names'>{names_value}</textarea></label><label>Notes<textarea name='notes'>{val('notes')}</textarea></label><button class='btn'>Save Entry</button></form></div>"
        self.sendx(200, {"Content-Type":"text/html; charset=utf-8"}, page(title,body,u))

    def save_client(self,u):
        d=self.form()

        # 7 Name Entry mode: creates seven separate client records
        if d.get("multi_mode", [""])[0] == "1":
            city=d.get("city",[""])[0].strip()
            address=d.get("address",[""])[0].strip()
            status=d.get("payment_status",["Unpaid"])[0]
            notes=d.get("notes",[""])[0].strip()
            conn=get_conn(); cur=conn.cursor()
            saved = 0
            for i in range(1,8):
                name=d.get(f"name_{i}",[""])[0].strip()
                phone=d.get(f"phone_{i}",[""])[0].strip()
                product=d.get(f"product_{i}",["Hissa"])[0]
                paid=int(d.get(f"paid_{i}",["0"])[0] or 0)
                if not name and not phone:
                    continue
                qty = 1
                due = PRODUCTS.get(product,0) * qty
                cur.execute(
                    "INSERT INTO clients(receipt_no,client_name,mobile,city,address,product,quantity,amount_due,amount_paid,payment_status,names,notes,created_by,created_at,updated_at) VALUES(%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)",
                    (receipt_no()+f"-{i}", name or f"Participant {i}", phone, city, address, product, qty, due, paid, status, name, notes, u["username"], now(), now())
                )
                saved += 1
            conn.commit(); cur.close(); conn.close()
            self.sendx(*redirect("/clients"))
            return

        cid=d.get("id",[""])[0].strip(); product=d.get("product",["Hissa"])[0]; qty=max(1,int(d.get("quantity",["1"])[0] or 1)); paid=int(d.get("amount_paid",["0"])[0] or 0); due=PRODUCTS.get(product,0)*qty
        vals=(d.get("client_name",[""])[0].strip(),d.get("mobile",[""])[0].strip(),d.get("city",[""])[0].strip(),d.get("address",[""])[0].strip(),product,qty,due,paid,d.get("payment_status",["Unpaid"])[0],d.get("names",[""])[0].strip(),d.get("notes",[""])[0].strip(),now())
        conn=get_conn(); cur=conn.cursor()
        if cid: cur.execute("UPDATE clients SET client_name=%s,mobile=%s,city=%s,address=%s,product=%s,quantity=%s,amount_due=%s,amount_paid=%s,payment_status=%s,names=%s,notes=%s,updated_at=%s WHERE id=%s", vals+(cid,))
        else: cur.execute("INSERT INTO clients(receipt_no,client_name,mobile,city,address,product,quantity,amount_due,amount_paid,payment_status,names,notes,created_by,created_at,updated_at) VALUES(%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)", (receipt_no(),)+vals[:11]+(u["username"],now(),now()))
        conn.commit(); cur.close(); conn.close(); self.sendx(*redirect("/clients"))

    def delete_client(self,cid):
        conn=get_conn(); cur=conn.cursor(); cur.execute("DELETE FROM clients WHERE id=%s",(cid,)); conn.commit(); cur.close(); conn.close(); self.sendx(*redirect("/clients"))
    def receipt(self,u,cid):
        conn=get_conn(); cur=conn.cursor(); cur.execute("SELECT * FROM clients WHERE id=%s",(cid,)); r=dict_one(cur); cur.close(); conn.close()
        if not r: return self.sendx(*redirect("/clients"))
        body=f"<div class='top'><div><h1>Receipt</h1><p>{escape(r['receipt_no'])}</p></div><button class='btn' onclick='window.print()'>Print</button></div><div class='card'><h2>Bazme Barkate Aley Mustafa Trust</h2><table><tr><td>Name</td><td>{escape(r['client_name'])}</td></tr><tr><td>Product</td><td>{escape(r['product'])} × {r['quantity']}</td></tr><tr><td>Due</td><td>{rupees(r['amount_due'])}</td></tr><tr><td>Paid</td><td>{rupees(r['amount_paid'])}</td></tr><tr><td>Status</td><td>{escape(r['payment_status'])}</td></tr></table></div>"
        self.sendx(200, {"Content-Type":"text/html; charset=utf-8"}, page("Receipt",body,u))
    def report(self,u):
        return self.clients(u)
    def export_csv(self):
        rows=self.all_clients(); out=io.StringIO(); w=csv.writer(out); w.writerow(["receipt_no","client_name","mobile","city","product","quantity","amount_due","amount_paid","payment_status","names","notes","created_at"])
        for r in rows: w.writerow([r["receipt_no"],r["client_name"],r["mobile"],r["city"],r["product"],r["quantity"],r["amount_due"],r["amount_paid"],r["payment_status"],r["names"],r["notes"],r["created_at"]])
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
        try: cur.execute("INSERT INTO users(username,password_hash,role,mobile,created_at) VALUES(%s,%s,%s,%s,%s)",(d.get("username",[""])[0].strip(),password_hash(d.get("password",[""])[0]),d.get("role",["ROLE_OPERATOR"])[0],d.get("mobile",[""])[0],now()))
        except Exception: pass
        conn.commit(); cur.close(); conn.close(); self.sendx(*redirect("/users"))
    def delete_user(self,u,uid):
        if u["role"]!="ROLE_ADMIN": return self.sendx(*redirect("/"))
        conn=get_conn(); cur=conn.cursor(); cur.execute("DELETE FROM users WHERE id=%s AND username!='pyra'",(uid,)); conn.commit(); cur.close(); conn.close(); self.sendx(*redirect("/users"))

if __name__ == "__main__":
    init_db()
    print(f"BBAMQB app running on {HOST}:{PORT}")
    ThreadingHTTPServer((HOST, PORT), App).serve_forever()
