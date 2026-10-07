#!/usr/bin/env python3
"""Virtual endpoints for localhost NGINX experiments. No external dependencies."""
import argparse, time, json
from http.server import ThreadingHTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs
class Handler(BaseHTTPRequestHandler):
    protocol_version = 'HTTP/1.1'
    def do_GET(self):
        u = urlparse(self.path); q = parse_qs(u.query)
        if u.path.startswith('/slow'):
            gap = min(5.0, max(0.0, float(q.get('gap',['0.2'])[0])))
            chunks = [f'chunk={i}\n'.encode() for i in range(6)]
            self.send_response(200); self.send_header('Content-Type','text/plain')
            self.send_header('Content-Length',str(sum(map(len,chunks)))); self.end_headers()
            try:
                for chunk in chunks:
                    self.wfile.write(chunk); self.wfile.flush(); time.sleep(gap)
            except (BrokenPipeError,ConnectionResetError): pass
            return
        if u.path.startswith('/blob'):
            size = min(16*1024*1024,max(1,int(q.get('size',['1048576'])[0])))
            self.reply(b'x'*size); return
        self.reply(json.dumps({'path':self.path,'port':self.server.server_port,'time_ns':time.time_ns(),'client':self.client_address},ensure_ascii=False).encode(), cache=u.path.startswith('/cache'))
    def do_POST(self):
        # This simple lab intentionally supports Content-Length only, not chunked decoding.
        n = int(self.headers.get('Content-Length','0'))
        if n > 16*1024*1024: self.reply(b'body too large',status=413); return
        body = self.rfile.read(n)
        self.reply(json.dumps({'received_bytes':len(body),'port':self.server.server_port}).encode())
    def reply(self, body, cache=False, status=200):
        self.send_response(status); self.send_header('Content-Type','application/json')
        self.send_header('Content-Length',str(len(body)))
        if cache: self.send_header('Cache-Control','public, max-age=2')
        self.end_headers()
        try: self.wfile.write(body)
        except (BrokenPipeError,ConnectionResetError): pass
    def log_message(self, fmt, *args): print(self.client_address, fmt % args, flush=True)
if __name__ == '__main__':
    p=argparse.ArgumentParser();p.add_argument('--port',type=int,default=18081);a=p.parse_args()
    server=ThreadingHTTPServer(('127.0.0.1',a.port), Handler)
    try:server.serve_forever()
    except KeyboardInterrupt:pass
    finally:server.server_close()
