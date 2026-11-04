"""Short-lived HTTP worker; started only inside the isolated target container."""
import argparse
import json
import sys
from http.server import ThreadingHTTPServer, BaseHTTPRequestHandler

p=argparse.ArgumentParser()
p.add_argument('--port', type=int, required=True)
p.add_argument('--mode', choices=['healthy','crash','maintenance','bad_config'],required=True)
a=p.parse_args()
if a.mode=='crash':
    print('demo-web.service: main process exited, code=exited, status=1/FAILURE',flush=True)
    sys.exit(1)
if a.mode=='bad_config':
    print('startup: CONFIG_VALIDATION_ERROR: missing DEMO_SERVICE_TOKEN in test fixture',flush=True)
    sys.exit(2)
if a.mode=='maintenance':
    print('gateway: maintenance_mode=true; HTTP 503',flush=True)
else:
    print('demo-web: service started successfully',flush=True)

class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path != '/health':
            self.send_error(404)
            return
        healthy=a.mode=='healthy'
        data=json.dumps({'healthy':healthy,'mode':a.mode}).encode()
        self.send_response(200 if healthy else 503)
        self.send_header('Content-Type','application/json')
        self.send_header('Content-Length',str(len(data)))
        self.end_headers()
        self.wfile.write(data)
    def log_message(self,fmt,*args):
        print('http: '+(fmt%args),flush=True)

ThreadingHTTPServer(('127.0.0.1',a.port),Handler).serve_forever()
