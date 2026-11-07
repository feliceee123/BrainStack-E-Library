"""Create (or promote) an administrator account.

    python create_admin.py admin@example.com "MyStrongPass123" "Admin Name"
"""
import sys

from app.db import connect, ensure_admin, init_db

if len(sys.argv) < 3:
    sys.exit(__doc__)
init_db()
conn = connect()
ensure_admin(conn, sys.argv[1], sys.argv[2], sys.argv[3] if len(sys.argv) > 3 else "Administrator")
conn.commit()
conn.close()
print("Administrator ready:", sys.argv[1].lower())
