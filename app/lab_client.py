"""Approved lab tools. This client cannot execute host shell or arbitrary commands."""
import httpx
from app.config import config

class LabError(RuntimeError): pass

class LabClient:
    def __init__(self):
        self.base=config.lab_url
        self.headers={'X-Lab-Token':config.lab_token}
    def request(self,method,path,payload=None):
        try:
            with httpx.Client(timeout=5) as client:
                response=client.request(method,self.base+path,headers=self.headers,json=payload)
                response.raise_for_status()
                return response.json()
        except (httpx.HTTPError, ValueError) as exc:
            raise LabError(f'Laboratório indisponível: {type(exc).__name__}') from exc
    def create(self,iid,scenario):
        return self.request('POST','/lab/incidents',{'id':iid,'scenario':scenario})
    def tool(self,iid,name):
        endpoints={'check_health':'health','read_logs':'logs','read_metrics':'metrics','read_config':'config'}
        if name not in endpoints:
            raise ValueError('Ferramenta não permitida')
        return self.request('GET',f'/lab/incidents/{iid}/{endpoints[name]}')
    def operate(self,iid,operation):
        from app.catalog import ALLOWED_ACTIONS
        if operation not in ALLOWED_ACTIONS:
            raise ValueError('Operação não permitida')
        return self.request('POST',f'/lab/incidents/{iid}/operate',{'operation':operation})
