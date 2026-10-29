"""Diagnose archive access without clearing caches or using account credentials."""
import argparse
import json
from pathlib import Path
import sys
from time import monotonic
from datetime import datetime, timezone
import requests

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from modules.storage.infrastructure.db import SessionLocal
from modules.session_domain.infrastructure.models import EventSessionRecord

parser = argparse.ArgumentParser()
parser.add_argument("session_id")
parser.add_argument("--output")
args = parser.parse_args()
with SessionLocal() as db:
    session = db.get(EventSessionRecord,args.session_id)
    if session is None or not session.api_path or not session.api_path.startswith("/static/"):
        raise SystemExit("An imported FastF1 session with an archive path is required")
    path = session.api_path
results = []
for host in ("https://livetiming.formula1.com","https://livetiming-mirror.fastf1.dev"):
    for file in ("CarData.z.jsonStream","Position.z.jsonStream"):
        url = host+path.rstrip("/")+"/"+file
        started = monotonic()
        try:
            with requests.get(url,stream=True,timeout=(5,10)) as response:
                results.append({"url":url,"status":response.status_code,"seconds":round(monotonic()-started,3),
                                "edge_cache":response.headers.get("x-cache")})
        except requests.RequestException as error:
            results.append({"url":url,"error":type(error).__name__,"seconds":round(monotonic()-started,3)})
result = {"checked_at":datetime.now(timezone.utc).isoformat(),"session_id":args.session_id,
          "credentials_used":False,"caches_modified":False,"responses":results}
encoded = json.dumps(result,indent=2)
print(encoded)
if args.output:
    Path(args.output).write_text(encoded+"\n",encoding="utf-8")
