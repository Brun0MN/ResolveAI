"""SQLite incident and immutable audit journal; no API keys stored in database."""
import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from app.config import config

def now():
    return datetime.now(timezone.utc).isoformat(timespec='seconds')

def db():
    p=Path(config.database_path)
    p.parent.mkdir(parents=True, exist_ok=True)
    con=sqlite3.connect(p, timeout=20)
    con.row_factory=sqlite3.Row
    con.execute('PRAGMA busy_timeout=10000')
    con.execute('PRAGMA foreign_keys=ON')
    con.execute('''CREATE TABLE IF NOT EXISTS incidents (
      id TEXT PRIMARY KEY, title TEXT NOT NULL, description TEXT NOT NULL,
      scenario TEXT NOT NULL, status TEXT NOT NULL DEFAULT 'novo',
      severity TEXT NOT NULL DEFAULT 'não definida', diagnosis TEXT,
      recommended_action TEXT, confidence REAL, model TEXT,
      created_at TEXT NOT NULL, updated_at TEXT NOT NULL, resolved_at TEXT,
      resolution_seconds REAL, approved INTEGER NOT NULL DEFAULT 0,
      execution_mode TEXT
    )''')
    con.execute('''CREATE TABLE IF NOT EXISTS events (
      id INTEGER PRIMARY KEY AUTOINCREMENT, incident_id TEXT NOT NULL,
      stage TEXT NOT NULL, kind TEXT NOT NULL, detail TEXT NOT NULL,
      created_at TEXT NOT NULL, FOREIGN KEY(incident_id) REFERENCES incidents(id)
    )''')
    con.commit()
    return con

def create_incident(iid,title,description,scenario):
    stamp=now()
    with db() as con:
        con.execute('INSERT INTO incidents (id,title,description,scenario,status,created_at,updated_at) VALUES (?,?,?,?,?,?,?)', (iid,title,description,scenario,'novo',stamp,stamp))
        con.commit()
    add_event(iid,'entrada','created',{'message':'Incidente aberto; laboratório individual preparado'})
    return get_incident(iid)

def add_event(iid,stage,kind,detail):
    with db() as con:
        con.execute('INSERT INTO events (incident_id,stage,kind,detail,created_at) VALUES (?,?,?,?,?)', (iid,stage,kind,json.dumps(detail,ensure_ascii=False),now()))
        con.commit()

def patch_incident(iid,**fields):
    columns={'status','severity','diagnosis','recommended_action','confidence','model','resolved_at','resolution_seconds','approved','execution_mode'}
    if not fields or not set(fields).issubset(columns):
        raise ValueError('Campos inválidos')
    fields['updated_at']=now()
    with db() as con:
        con.execute('UPDATE incidents SET '+','.join(f'{k}=?' for k in fields)+' WHERE id=?', list(fields.values())+[iid])
        con.commit()

def get_incident(iid, include_events=True):
    with db() as con:
        row=con.execute('SELECT * FROM incidents WHERE id=?',(iid,)).fetchone()
        if not row:
            return None
        result=dict(row)
        if include_events:
            events=con.execute('SELECT * FROM events WHERE incident_id=? ORDER BY id',(iid,)).fetchall()
            result['events']=[dict(x)|{'detail':json.loads(x['detail'])} for x in events]
        return result

def list_incidents():
    with db() as con:
        return [dict(x) for x in con.execute('SELECT * FROM incidents ORDER BY created_at DESC, rowid DESC LIMIT 250')]

def stats():
    rows=list_incidents()
    resolved=[x for x in rows if x['status']=='resolvido']
    durations=[x['resolution_seconds'] for x in resolved if x['resolution_seconds'] is not None]
    return {'total':len(rows), 'resolved':len(resolved), 'pending_approval':sum(x['status']=='aguardando_aprovacao' for x in rows), 'escalated':sum(x['status']=='escalado' for x in rows), 'new':sum(x['status']=='novo' for x in rows), 'rate_pct':round(100*len(resolved)/len(rows),1) if rows else 0, 'avg_resolution_s':round(sum(durations)/len(durations),2) if durations else None}
