"""Orchestrator: triage -> observe -> diagnose -> policy -> act -> verify.

Stages are separate, testable logical agents; ONE Gemini reasoning call per incident.
The lab owns the only mutable target; host execution is impossible by design.
"""
import time
from datetime import datetime, timezone
from uuid import uuid4
from app.catalog import SCENARIOS, AUTO_ACTIONS, APPROVAL_ACTIONS, ALLOWED_ACTIONS, SAFE_TOOL_NAMES
from app import storage
from app.lab_client import LabClient, LabError
from app.intelligence import diagnose
from app.policy import check_evidence
from app.config import config

class WorkflowError(Exception): pass

class TriageAgent:
    def create(self,title,description,scenario):
        if scenario not in SCENARIOS: raise WorkflowError('Cenário desconhecido')
        if not title.strip() or not description.strip(): raise WorkflowError('Chamado incompleto')
        iid=str(uuid4())
        LabClient().create(iid,scenario)
        storage.create_incident(iid,title.strip()[:160],description.strip()[:2000],scenario)
        return iid

class InvestigationAgent:
    def collect(self,iid):
        lab=LabClient()
        observations={name:lab.tool(iid,name) for name in SAFE_TOOL_NAMES}
        for name,value in observations.items():
            storage.add_event(iid,'investigação','tool_result',{'tool':name,'result':value})
        return observations

class ResolutionAgent:
    def execute_and_verify(self,iid,operation):
        if operation not in ALLOWED_ACTIONS:
            raise WorkflowError('Operação fora da allowlist')
        result=LabClient().operate(iid,operation)
        storage.add_event(iid,'resolução','operation',result)
        check=LabClient().tool(iid,'check_health')
        storage.add_event(iid,'verificação','post_check',check)
        if result.get('applied') and check.get('healthy'):
            created=storage.get_incident(iid,False)['created_at']
            elapsed=max(0,(datetime.now(timezone.utc)-datetime.fromisoformat(created)).total_seconds())
            storage.patch_incident(iid,status='resolvido',resolved_at=storage.now(),resolution_seconds=round(elapsed,2))
        else:
            storage.patch_incident(iid,status='escalado')
            storage.add_event(iid,'verificação','escalation',{'reason':'Correção não comprovada; encaminhado ao humano'})
        return storage.get_incident(iid)

class Workflow:
    def __init__(self):
        self.triage=TriageAgent()
        self.investigator=InvestigationAgent()
        self.resolver=ResolutionAgent()

    def run(self,iid):
        item=storage.get_incident(iid)
        if not item: raise WorkflowError('Incidente não encontrado')
        if item['status']!='novo': raise WorkflowError('O incidente já foi processado')
        storage.patch_incident(iid,status='analisando')
        storage.add_event(iid,'triagem','start',{'message':'Iniciando diagnóstico, sem executar comandos no host'})
        try:
            observations=self.investigator.collect(iid)
            if observations['check_health'].get('healthy'):
                storage.patch_incident(iid,status='resolvido',resolved_at=storage.now(),resolution_seconds=0)
                storage.add_event(iid,'verificação','already_healthy',{'message':'Serviço já está saudável'})
                return storage.get_incident(iid)
            plan,mode=diagnose(item['description'],observations)
            storage.patch_incident(iid,severity=plan.severity,diagnosis=plan.root_cause+' — '+plan.rationale,confidence=plan.confidence,recommended_action=plan.action,model=mode,execution_mode='ai' if mode.startswith('gemini:') else 'offline-rules')
            storage.add_event(iid,'diagnóstico','plan',plan.model_dump()|{'mode':mode,'api_usage':getattr(plan,'_usage',None)})
            # Never rely on the model's confidence alone to mutate even the lab.
            policy = check_evidence(plan.action, observations)
            storage.add_event(iid,'política','evidence_gate',{'proposed_action':plan.action,'permitted':policy.permitted,'reason':policy.reason})
            if not policy.permitted:
                storage.patch_incident(iid,status='escalado',recommended_action='escalate')
                storage.add_event(iid,'política','escalation',{'reason':'Porta de evidências bloqueou a operação; proposta original preservada na auditoria'})
                return storage.get_incident(iid)
            if plan.action not in ALLOWED_ACTIONS or plan.confidence<config.auto_min_confidence:
                storage.patch_incident(iid,status='escalado')
                storage.add_event(iid,'política','escalation',{'reason':'Baixa confiança, decisão humana ou ação desconhecida'})
                return storage.get_incident(iid)
            if plan.action in APPROVAL_ACTIONS:
                storage.patch_incident(iid,status='aguardando_aprovacao')
                storage.add_event(iid,'política','approval_required',{'operation':plan.action,'reason':'Ação exige aprovação humana explícita; o modelo não pode dispensá-la'})
                return storage.get_incident(iid)
            if plan.needs_human:
                storage.patch_incident(iid,status='escalado')
                storage.add_event(iid,'política','escalation',{'reason':'O modelo solicitou avaliação humana antes de qualquer ação automática'})
                return storage.get_incident(iid)
            return self.resolver.execute_and_verify(iid,plan.action)
        except Exception as exc:
            # Fail closed on provider/lab errors; do not leak credentials or raw provider output.
            storage.patch_incident(iid,status='escalado')
            storage.add_event(iid,'sistema','error',{'type':type(exc).__name__,'message':'Falha de infraestrutura/IA; nenhuma operação adicional foi autorizada'})
            return storage.get_incident(iid)

    def approve(self,iid):
        item=storage.get_incident(iid)
        if not item: raise WorkflowError('Incidente não encontrado')
        if item['status']!='aguardando_aprovacao': raise WorkflowError('Não há aprovação pendente')
        action=item['recommended_action']
        if action not in APPROVAL_ACTIONS: raise WorkflowError('Ação não aprovada pela política')
        storage.patch_incident(iid,approved=1,status='executando')
        storage.add_event(iid,'política','approved',{'operation':action,'approved_by':'local_operator'})
        try:
            return self.resolver.execute_and_verify(iid,action)
        except Exception as exc:
            storage.patch_incident(iid,status='escalado')
            storage.add_event(iid,'sistema','error',{'type':type(exc).__name__,'message':'Erro na execução autorizada; encaminhado ao humano'})
            return storage.get_incident(iid)

    def reject(self,iid):
        item=storage.get_incident(iid)
        if not item: raise WorkflowError('Incidente não encontrado')
        if item['status']!='aguardando_aprovacao': raise WorkflowError('Não há aprovação pendente')
        storage.patch_incident(iid,status='escalado')
        storage.add_event(iid,'política','rejected',{'reason':'Operador não autorizou a correção'})
        return storage.get_incident(iid)
