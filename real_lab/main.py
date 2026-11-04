"""One actual subprocess per incident, limited to three safe fault types.

The intended Docker deployment forbids this service host mounts, Docker socket,
network egress, shell commands, elevated privileges, and arbitrary actions.
"""
import os
import socket
import subprocess
import sys
import threading
import time
from contextlib import asynccontextmanager
from dataclasses import dataclass
from pathlib import Path
from uuid import UUID
import httpx
from fastapi import FastAPI, Header, HTTPException
from pydantic import BaseModel
from app.config import config

REAL_SCENARIOS={
 'web_stopped':('crash','restart_demo_web'),
 'maintenance_enabled':('maintenance','disable_demo_maintenance'),
 'config_missing':('bad_config','restore_demo_config')
}
LOG_DIR=Path('/tmp/resolveai-process-lab')
lock=threading.RLock()
@dataclass
class Worker:
    scenario: str
    log_path: Path
    process: subprocess.Popen | None = None
    port: int = 0
    touched: float = 0
    mode: str = "unknown"

workers:dict[str,Worker]={}

def verify_token(token):
    if not token or token!=config.lab_token:
        raise HTTPException(403,'Token de laboratório inválido')

def verify_id(iid):
    try: UUID(iid)
    except (TypeError,ValueError): raise HTTPException(422,'UUID inválido')

def stop(w):
    if w.process and w.process.poll() is None:
        w.process.terminate()
        try: w.process.wait(timeout=1)
        except subprocess.TimeoutExpired:
            w.process.kill()
            w.process.wait(timeout=1)
    w.process=None

def cleanup(force=False):
    with lock:
        now=time.monotonic()
        for iid,w in list(workers.items()):
            if force or now-w.touched>1200:
                stop(w)
                workers.pop(iid)
                w.log_path.unlink(missing_ok=True)

def spawn(w,mode):
    stop(w)
    w.mode = mode
    with socket.socket() as sock:
        sock.bind(('127.0.0.1',0))
        w.port=sock.getsockname()[1]
    with w.log_path.open('a',encoding='utf8') as log:
        log.write('controller: initiating actual subprocess in '+mode+' mode\n')
        log.flush()
        w.process=subprocess.Popen(
            [sys.executable,'-m','real_lab.worker','--port',str(w.port),'--mode',mode],
            cwd=str(Path(__file__).resolve().parents[1]),
            stdout=log,stderr=subprocess.STDOUT,stdin=subprocess.DEVNULL,
            env={**os.environ,'PYTHONDONTWRITEBYTECODE':'1'},
            start_new_session=True,close_fds=True)
    end=time.monotonic()+5
    while time.monotonic()<end:
        if w.process.poll() is not None: break
        try:
            with httpx.Client(timeout=.2) as c:
                r=c.get(f'http://127.0.0.1:{w.port}/health')
                if r.status_code in (200,503): return
        except httpx.HTTPError: time.sleep(.05)

def get(iid):
    verify_id(iid)
    with lock:
        cleanup()
        w=workers.get(iid)
        if not w: raise HTTPException(404,'Processo expirado ou reiniciado; crie um incidente novo')
        w.touched=time.monotonic()
        return w

def probe(w):
    start=time.monotonic()
    if w.process is None or w.process.poll() is not None:
        return {'healthy':False,'http_status':0,'process_alive':False,
                'exit_code':w.process.poll() if w.process else None,
                'probe_latency_ms':round((time.monotonic()-start)*1000,2),
                'detail':'Processo real do serviço encerrou'}
    try:
        with httpx.Client(timeout=1) as c:
            r=c.get(f'http://127.0.0.1:{w.port}/health')
        return {'healthy':r.status_code==200,'http_status':r.status_code,
                'process_alive':True,'exit_code':None,
                'probe_latency_ms':round((time.monotonic()-start)*1000,2),
                'detail':'Sonda HTTP em processo separado dentro do contêiner'}
    except httpx.HTTPError:
        return {'healthy':False,'http_status':0,
                'process_alive':w.process.poll() is None,'exit_code':w.process.poll(),
                'probe_latency_ms':round((time.monotonic()-start)*1000,2),
                'detail':'Sonda HTTP falhou ou excedeu o prazo'}

@asynccontextmanager
async def lifespan(app):
    LOG_DIR.mkdir(parents=True,exist_ok=True)
    try: yield
    finally: cleanup(force=True)

app=FastAPI(title='ResolveAI / Real Sandbox', docs_url=None,redoc_url=None,lifespan=lifespan)
class New(BaseModel):
    id:str
    scenario:str
class Action(BaseModel):
    operation:str

@app.get('/target/ping')
def ping(): return {'target':'ok','backend':'process-isolated','supported':sorted(REAL_SCENARIOS)}

@app.post('/target/incidents',status_code=201)
def create(body:New,x_lab_token:str|None=Header(None)):
    verify_token(x_lab_token)
    verify_id(body.id)
    if body.scenario not in REAL_SCENARIOS: raise HTTPException(422,'Cenário não suportado')
    with lock:
        cleanup()
        if body.id in workers: raise HTTPException(409,'ID já existe')
        if len(workers)>=32: raise HTTPException(429,'Laboratório cheio; reinicie real-target')
        w=Worker(body.scenario,LOG_DIR/(body.id+'.log'),touched=time.monotonic())
        workers[body.id]=w
        try: spawn(w,REAL_SCENARIOS[body.scenario][0])
        except Exception:
            workers.pop(body.id,None)
            stop(w)
            raise
        return {'created':True,'id':body.id,'backend':'process-isolated'}

@app.get('/target/incidents/{iid}/health')
def health(iid:str,x_lab_token:str|None=Header(None)):
    verify_token(x_lab_token)
    with lock: return {**probe(get(iid)),'service':'demo-web-process','backend':'process-isolated'}

@app.get('/target/incidents/{iid}/logs')
def logs(iid:str,x_lab_token:str|None=Header(None)):
    verify_token(x_lab_token)
    with lock:
        w=get(iid)
        return {'source':'actual process stdout/stderr','backend':'process-isolated',
                'lines':w.log_path.read_text(encoding='utf8',errors='replace').splitlines()[-60:] if w.log_path.exists() else []}

@app.get('/target/incidents/{iid}/metrics')
def metrics(iid:str,x_lab_token:str|None=Header(None)):
    verify_token(x_lab_token)
    with lock:
        x=probe(get(iid))
        return {'http_status':x['http_status'],'process_alive':x['process_alive'],
                'probe_latency_ms':x['probe_latency_ms'],'simulated':False,
                'backend':'process-isolated', 'note':'Uma observação real, não histórico sintético'}

@app.get('/target/incidents/{iid}/config')
def config_view(iid:str,x_lab_token:str|None=Header(None)):
    verify_token(x_lab_token)
    with lock:
        w=get(iid)
        return {'backend':'process-isolated','environment':'isolated Docker target',
                'maintenance_mode': w.mode == 'maintenance',
                'DEMO_SERVICE_TOKEN': '<absent>' if w.mode == 'bad_config' else '[redacted]',
                'secrets':'[redacted]'}

@app.post('/target/incidents/{iid}/operate')
def operate(iid:str,body:Action,x_lab_token:str|None=Header(None)):
    verify_token(x_lab_token)
    with lock:
        w=get(iid)
        if body.operation!=REAL_SCENARIOS[w.scenario][1]:
            return {'operation':body.operation,'applied':False,'backend':'process-isolated',
                    'reason':'Ação não corresponde à falha'}
        spawn(w,'healthy')
        check=probe(w)
        return {'operation':body.operation,'applied':check['healthy'],'backend':'process-isolated',
                'scope':'genuine HTTP worker inside sandbox container',
                'verification':check,
                'explanation':'Reiniciado processo HTTP real dentro do contêiner, sem executar comandos no host'}
