BBAMQB Render + PostgreSQL

Deploy files:
- app.py
- requirements.txt
- runtime.txt
- Procfile

Render settings:
Build Command:
pip install -r requirements.txt

Start Command:
python app.py

Environment variables:
DATABASE_URL = paste Internal Database URL from Render PostgreSQL
BBAMQB_SECRET = any long random secret text

Login:
pyra / admin123
