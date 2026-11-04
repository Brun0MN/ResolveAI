"""Web interface and API; localhost only in supported demo deployment."""
from contextlib import asynccontextmanager
from pathlib import Path
from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field
from app import storage
from app.catalog import SCENARIOS, AUTO_ACTIONS, APPROVAL_ACTIONS
from app.config import config
from app.workflow import Workflow, WorkflowError
from app.lab_client import LabError, LabClient
from app.evaluation import latest_evaluation
from app.challenge_eval import latest_challenge
from app.holdout_eval import latest as latest_holdout
from app.reserved_eval import latest as latest_reserved
from app.release import version, policy_digest

BASE=Path(__file__).resolve().parent

@asynccontextmanager
async def lifespan(application:FastAPI):
    with storage.db(): pass
    yield

app=FastAPI(title='ResolveAI', version=version(), lifespan=lifespan, docs_url=None,redoc_url=None)
app.mount('/static',StaticFiles(directory=str(BASE/'static')),name='static')
workflow=Workflow()

class NewIncident(BaseModel):
    title: str=Field(min_length=3,max_length=160)
    description: str=Field(min_length=8,max_length=2000)
    scenario: str

@app.get('/')
def index():
    return FileResponse(BASE/'static'/'index.html')

@app.get('/api/config')
def info():
    try:
        ping=LabClient().request('GET','/lab/ping')
        active_real=ping.get('real_scenarios',[])
    except LabError:
        active_real=[]
    return {'model':config.gemini_model if config.gemini_key else 'Regras locais (sem IA)',
        'mode':'gemini' if config.gemini_key else 'offline',
        'lab':'processos reais isolados + cenários emulados' if active_real else 'simulação isolada (sem Docker)',
        'real_scenarios':active_real,'version':version(),'policy_sha256_prefix':policy_digest()}

@app.get('/api/scenarios')
def scenarios():
    return [{'id':k,'title':v.title,'description':v.description,
             'real_when_docker': k in {'web_stopped','maintenance_enabled','config_missing'}}
            for k,v in SCENARIOS.items()]

@app.get('/api/metrics')
def metrics():
    return storage.stats()

@app.get('/api/evaluation/latest')
def evaluation():
    return latest_evaluation()

@app.get('/api/challenge/latest')
def challenge_evaluation():
    return latest_challenge()

@app.get('/api/holdout/latest')
def holdout_evaluation():
    return latest_holdout()

@app.get('/api/reserved/latest')
def reserved_evaluation():
    return latest_reserved()

@app.get('/api/incidents')
def incidents():
    return storage.list_incidents()

@app.post('/api/incidents',status_code=201)
def create_incident(payload:NewIncident):
    try:
        iid=workflow.triage.create(payload.title,payload.description,payload.scenario)
        return storage.get_incident(iid)
    except WorkflowError as exc:
        raise HTTPException(422,str(exc))
    except LabError as exc:
        raise HTTPException(503,'Laboratório não responde. Confirme se o serviço lab está rodando.')

@app.get('/api/incidents/{iid}')
def incident(iid:str):
    result=storage.get_incident(iid)
    if not result: raise HTTPException(404,'Incidente não encontrado')
    return result

def mutate(call,iid):
    try:
        return call(iid)
    except WorkflowError as exc:
        raise HTTPException(409,str(exc))

@app.post('/api/incidents/{iid}/run')
def run(iid:str):
    return mutate(workflow.run,iid)

@app.post('/api/incidents/{iid}/approve')
def approve(iid:str):
    return mutate(workflow.approve,iid)

@app.post('/api/incidents/{iid}/reject')
def reject(iid:str):
    return mutate(workflow.reject,iid)
