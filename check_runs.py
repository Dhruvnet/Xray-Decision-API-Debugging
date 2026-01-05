from backend.db import get_conn

conn = get_conn()
rows = conn.execute("SELECT run_id, pipeline_name FROM runs ORDER BY rowid DESC LIMIT 10").fetchall()

for r in rows:
    print(r["run_id"], r["pipeline_name"])

from sdk.xray import XRay
print("SDK OK")

