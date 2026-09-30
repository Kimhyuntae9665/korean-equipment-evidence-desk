"""Loopback only public-catalog desk. No factory integrations or write tools."""
from __future__ import annotations
import argparse
import json
import re
from http.server import BaseHTTPRequestHandler,ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs,urlsplit
from .core import Desk,DeskError
from .catalog import CatalogError
from .retrieval import RetrievalError

STATIC={"/":("index.html","text/html; charset=utf-8"),
        "/index.html":("index.html","text/html; charset=utf-8"),
        "/styles.css":("styles.css","text/css; charset=utf-8"),
        "/app.js":("app.js","text/javascript; charset=utf-8")}
MAX_BODY=8192
MAX_TARGET=4096

def make_server(desk:Desk,port=19090,static_dir=None):
    static_dir=Path(static_dir or Path(__file__).resolve().parents[1]/"static")
    class Handler(BaseHTTPRequestHandler):
        server_version="EquipmentEvidenceDesk"
        sys_version=""
        def log_message(self,fmt,*args):pass
        def send(self,status,value,content_type="application/json; charset=utf-8"):
            raw=value if isinstance(value,bytes) else json.dumps(value,ensure_ascii=False,
                allow_nan=False,separators=(",",":")).encode("utf-8")
            self.send_response(status)
            self.send_header("Content-Type",content_type)
            self.send_header("Content-Length",str(len(raw)))
            self.send_header("Cache-Control","no-store")
            self.send_header("X-Content-Type-Options","nosniff")
            self.send_header("X-Frame-Options","DENY")
            self.send_header("Referrer-Policy","no-referrer")
            self.send_header("Content-Security-Policy",
                "default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self'; connect-src 'self'; frame-ancestors 'none'; base-uri 'none'; form-action 'none'")
            self.end_headers()
            self.wfile.write(raw)
        def body(self):
            if self.headers.get("Transfer-Encoding"):
                raise DeskError("transfer_not_supported","Unsupported transfer encoding")
            lengths=self.headers.get_all("Content-Length",[])
            if len(lengths)!=1 or not lengths[0].isdigit():
                raise DeskError("length_required","Content-Length required")
            length=int(lengths[0])
            if length>MAX_BODY:raise DeskError("body_too_large","Request too large")
            if self.headers.get("Content-Type","").split(";",1)[0].strip().lower()!="application/json":
                raise DeskError("json_required","JSON required")
            try:body=json.loads(self.rfile.read(length))
            except (UnicodeDecodeError,json.JSONDecodeError) as exc:
                raise DeskError("invalid_json","Invalid JSON") from exc
            if not isinstance(body,dict):raise DeskError("invalid_json","JSON object required")
            return body
        def route(self,method):
            if len(self.path)>MAX_TARGET:
                self.send(414,{"code":"uri_too_long"});return
            hosts={f"127.0.0.1:{self.server.server_port}",f"localhost:{self.server.server_port}"}
            if self.headers.get("Host","").lower() not in hosts:
                self.send(403,{"code":"invalid_host"});return
            origin=self.headers.get("Origin")
            if origin and origin not in {"http://"+host for host in hosts}:
                self.send(403,{"code":"invalid_origin"});return
            parsed=urlsplit(self.path)
            path=parsed.path
            if parsed.scheme or parsed.netloc or "%" in path or "\\" in path:
                self.send(404,{"code":"not_found"});return
            query=parse_qs(parsed.query,keep_blank_values=True,max_num_fields=4)
            if any(len(v)!=1 for v in query.values()):
                raise DeskError("duplicate_query","Duplicate query field")
            query={k:v[0] for k,v in query.items()}
            if method=="GET" and path in STATIC:
                filename,ctype=STATIC[path]
                try:raw=(static_dir/filename).read_bytes()
                except OSError:self.send(404,{"code":"not_found"});return
                self.send(200,raw,ctype);return
            if method=="GET" and path=="/api/health":
                self.send(200,{"ok":True,"corpus":"real_public_catalog_preview",
                    "model_enabled":desk.model_client is not None,
                    "no_current_booking_or_visitor_access_authorization":True});return
            if method=="GET" and path=="/api/catalog":
                if set(query)-{"corpus","scope"}:
                    raise DeskError("unknown_query","Unknown query field")
                self.send(200,desk.catalog(query.get("corpus","small8"),query.get("scope","all")));return
            if method=="POST" and path=="/api/query":
                self.send(200,{"receipt":desk.query(self.body())});return
            if method=="GET" and re.fullmatch(r"/api/receipts/[a-f0-9]{24}",path):
                self.send(200,{"receipt":desk.get_receipt(path.rsplit("/",1)[1])});return
            self.send(404,{"code":"not_found"})
        def handle_method(self,method):
            try:self.route(method)
            except (DeskError,CatalogError,RetrievalError) as exc:
                self.send(400,{"code":exc.code,"error":str(exc)})
            except (BrokenPipeError,ConnectionError):self.close_connection=True
            except Exception:self.send(500,{"code":"internal_error"})
        def do_GET(self):self.handle_method("GET")
        def do_POST(self):self.handle_method("POST")
        def do_OPTIONS(self):self.send(405,{"code":"method_not_allowed"})
    class Server(ThreadingHTTPServer):
        daemon_threads=True
        def get_request(self):
            connection,address=super().get_request()
            connection.settimeout(15)
            return connection,address
    return Server(("127.0.0.1",port),Handler)

def main():
    root=Path(__file__).resolve().parents[1]
    parser=argparse.ArgumentParser(description="Public equipment preview evidence desk")
    parser.add_argument("--port",type=int,default=19090)
    parser.add_argument("--enable-model",action="store_true",
                        help="Enable actual local Qwen only after the CPU tokenizer check is installed")
    args=parser.parse_args()
    desk=Desk(root/"data")
    if args.enable_model:
        from .llm import Client
        desk.model_client=Client(desk.snapshots["small8"])
    server=make_server(desk,args.port)
    try:server.serve_forever()
    except KeyboardInterrupt:pass
    finally:server.server_close()

if __name__=="__main__":main()
