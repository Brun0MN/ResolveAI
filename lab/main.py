"""Isolated incident laboratory. Every call is a bounded HTTP API, no shell execution.

Each incident has its own SQLite-backed simulated service state. The service endpoint
really returns failing/success HTTP statuses; remediation changes only fixture state.
This is an honest emulated environment, NOT production incident automation.
"""
import sqlite3
import httpx
import time
from pathlib import Path
from uuid import UUID
from fastapi import FastAPI, Header, HTTPException
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from app.config import config
from app.catalog import SCENARIOS, ALLOWED_ACTIONS

app = FastAPI(title='ResolveAI / Sandbox Lab', docs_url=None, redoc_url=None)

# Only these fixtures operate genuine worker processes when Docker mode is enabled.
REAL_SCENARIOS = {'web_stopped', 'maintenance_enabled', 'config_missing'}
REAL_URL = getattr(config, 'real_lab_url', '').rstrip('/')

def _real(method, path, payload=None):
    if not REAL_URL:
        raise HTTPException(503, 'Laboratório real não está habilitado')
    try:
        with httpx.Client(timeout=8.0) as client:
            response = client.request(method, REAL_URL + path,
                headers={'X-Lab-Token': config.lab_token}, json=payload)
        if response.status_code >= 400:
            # Do not silently replace a failed real backend with emulation.
            raise HTTPException(503, f'Backend de processos reais não respondeu corretamente (HTTP {response.status_code})')
        return response.json()
    except (httpx.HTTPError, ValueError) as exc:
        raise HTTPException(503, 'Backend de processos reais indisponível; execute Docker Compose') from exc

def _backend(row):
    return row.get('backend', 'emulated')


def db():
    p = Path(config.lab_database_path)
    p.parent.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(p, timeout=20)
    con.row_factory = sqlite3.Row
    con.execute('PRAGMA busy_timeout=10000')
    con.execute('CREATE TABLE IF NOT EXISTS lab_incidents (id TEXT PRIMARY KEY, scenario TEXT NOT NULL, fixed INTEGER NOT NULL DEFAULT 0, attempts INTEGER NOT NULL DEFAULT 0, updated REAL NOT NULL, backend TEXT NOT NULL DEFAULT \"emulated\")')
    # One-way schema migration for existing deployments without deleting user data.
    cols = {r[1] for r in con.execute('PRAGMA table_info(lab_incidents)').fetchall()}
    if 'backend' not in cols:
        con.execute("ALTER TABLE lab_incidents ADD COLUMN backend TEXT NOT NULL DEFAULT 'emulated'")
    con.commit()
    return con

def auth(x_lab_token: str | None):
    if not x_lab_token or x_lab_token != config.lab_token:
        raise HTTPException(403, 'Laboratório isolado: token inválido')

def lookup(iid: str):
    try:
        UUID(iid)
    except (ValueError, TypeError):
        raise HTTPException(400, 'ID inválido')
    with db() as con:
        row = con.execute('SELECT * FROM lab_incidents WHERE id=?', (iid,)).fetchone()
    if not row:
        raise HTTPException(404, 'Incidente ausente no laboratório')
    return dict(row)

class CreateLab(BaseModel):
    id: str
    scenario: str

@app.get('/lab/ping')
def ping():
    return {'lab': 'ok', 'environment': 'mixed-isolated' if REAL_URL else 'isolated-emulation', 'real_scenarios': sorted(REAL_SCENARIOS) if REAL_URL else []}

@app.post('/lab/incidents', status_code=201)
def create_incident(request: CreateLab, x_lab_token: str | None = Header(None)):
    auth(x_lab_token)
    try:
        UUID(request.id)
    except ValueError:
        raise HTTPException(422, 'UUID inválido')
    if request.scenario not in SCENARIOS:
        raise HTTPException(422, 'Cenário desconhecido')
    backend = 'process-isolated' if REAL_URL and request.scenario in REAL_SCENARIOS else 'emulated'
    # Check duplicate BEFORE creating a real worker; creation is never silently downgraded.
    with db() as con:
        if con.execute('SELECT 1 FROM lab_incidents WHERE id=?', (request.id,)).fetchone():
            raise HTTPException(409, 'Esse incidente já existe')
    if backend == 'process-isolated':
        _real('POST', '/target/incidents', {'id': request.id, 'scenario': request.scenario})
    with db() as con:
        try:
            con.execute('INSERT INTO lab_incidents (id, scenario, backend, updated) VALUES (?,?,?,?)', (request.id, request.scenario, backend, time.time()))
            con.commit()
        except sqlite3.IntegrityError:
            raise HTTPException(409, 'Esse incidente já existe')
    return {'id': request.id, 'created': True, 'backend': backend}

@app.get('/lab/incidents/{iid}/health')
def health(iid: str, x_lab_token: str | None = Header(None)):
    auth(x_lab_token)
    row = lookup(iid)
    if _backend(row) == 'process-isolated':
        return _real('GET', f'/target/incidents/{iid}/health')
    ok = bool(row['fixed'])
    return {'healthy': ok, 'http_status': 200 if ok else 503, 'service': 'demo-portal', 'backend': 'emulated', 'detail': 'HTTP 200 — verificação de saúde concluída' if ok else SCENARIOS[row['scenario']].status}

@app.get('/lab/incidents/{iid}/logs')
def logs(iid: str, x_lab_token: str | None = Header(None)):
    auth(x_lab_token)
    row = lookup(iid)
    if _backend(row) == 'process-isolated':
        return _real('GET', f'/target/incidents/{iid}/logs')
    return {'source': 'synthetic incident journal', 'backend': 'emulated', 'lines': ['lab-service: startup diagnostic fixture', 'lab-service: system health probe failed' if not row['fixed'] else 'lab-service: remediation verified, health probe successful', SCENARIOS[row['scenario']].log if not row['fixed'] else 'lab-service: healthy after allowed intervention']}

@app.get('/lab/incidents/{iid}/metrics')
def metrics(iid: str, x_lab_token: str | None = Header(None)):
    auth(x_lab_token)
    row = lookup(iid)
    if _backend(row) == 'process-isolated':
        return _real('GET', f'/target/incidents/{iid}/metrics')
    return {'backend': 'emulated', 'http_5xx_rate_pct': 0 if row['fixed'] else 97, 'availability_pct': 100 if row['fixed'] else 3, 'probe_latency_ms': 32 if row['fixed'] else 2800 if row['scenario']=='queue_backlog' else 420, 'simulated': True}

@app.get('/lab/incidents/{iid}/config')
def safe_config(iid: str, x_lab_token: str | None = Header(None)):
    auth(x_lab_token)
    row = lookup(iid)
    if _backend(row) == 'process-isolated':
        return _real('GET', f'/target/incidents/{iid}/config')
    return {'backend': 'emulated', 'environment': 'sandbox', 'demo_service': 'portal', 'config_validation': 'passed' if row['fixed'] else 'check logs', 'credential_values': '[never returned]'}

class Action(BaseModel):
    operation: str

@app.post('/lab/incidents/{iid}/operate')
def operate(iid: str, request: Action, x_lab_token: str | None = Header(None)):
    auth(x_lab_token)
    if request.operation not in ALLOWED_ACTIONS:
        raise HTTPException(403, 'Operação não autorizada (allowlist)')
    row = lookup(iid)
    scenario = SCENARIOS[row['scenario']]
    if _backend(row) == 'process-isolated':
        result = _real('POST', f'/target/incidents/{iid}/operate', {'operation': request.operation})
        with db() as con:
            con.execute('UPDATE lab_incidents SET attempts=attempts+1, fixed=?, updated=? WHERE id=?',
                        (int(bool(result.get('applied'))), time.time(), iid))
            con.commit()
        return result
    success = scenario.operation == request.operation
    with db() as con:
        con.execute('UPDATE lab_incidents SET attempts=attempts+1, fixed=CASE WHEN ? THEN 1 ELSE fixed END, updated=? WHERE id=?', (success, time.time(), iid))
        con.commit()
    return {'operation': request.operation, 'applied': success, 'backend': 'emulated', 'scope': 'fictional-lab-only', 'explanation': 'Alterou estado da simulação, sem tocar no sistema operacional'}

@app.get('/demo/incidents/{iid}/service')
def demo_service(iid: str, x_lab_token: str | None = Header(None)):
    """A real HTTP response (503 while broken, 200 after correction) for lab probes."""
    auth(x_lab_token)
    row=lookup(iid)
    if _backend(row) == 'process-isolated':
        check = _real('GET', f'/target/incidents/{iid}/health')
        ok = bool(check.get('healthy'))
        return JSONResponse(status_code=200 if ok else 503,
            content={'demo_service': 'portal', 'healthy': ok, 'backend': 'process-isolated', 'probe': check})
    ok=bool(row['fixed'])
    return JSONResponse(status_code=200 if ok else 503, content={'demo_service':'portal','healthy':ok,'backend':'emulated','note':'Isolated emulated service; not an external system'})
