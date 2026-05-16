import os
import json
from http.server import HTTPServer, BaseHTTPRequestHandler
from supabase import create_client

SUPABASE_URL = os.environ["SUPABASE_URL"]
SUPABASE_KEY = os.environ["SUPABASE_KEY"]

supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        try:
            result = supabase.table("posts").select("*").order("fetched_at", desc=True).limit(200).execute()
            self.wfile.write(json.dumps(result.data).encode())
        except Exception as e:
            self.wfile.write(json.dumps([]).encode())

    def log_message(self, format, *args):
        pass

port = int(os.environ.get("PORT", 8765))
print(f"Nidus server running on port {port}")
HTTPServer(("0.0.0.0", port), Handler).serve_forever()