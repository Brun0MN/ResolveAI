from types import SimpleNamespace
import pytest
from app.intelligence import _generate_with_retry

class ServerError(Exception): pass
class ClientError(Exception): pass

class FailOnce:
    def __init__(self): self.calls=0
    def generate_content(self, **kwargs):
        self.calls+=1
        if self.calls==1: raise ServerError('transient')
        return 'ok'

class InvalidToken:
    def __init__(self): self.calls=0
    def generate_content(self, **kwargs):
        self.calls+=1
        raise ClientError('invalid key')

def test_one_retry_only_for_server_error(monkeypatch):
    from app import intelligence
    sleeps=[]
    monkeypatch.setattr(intelligence.time, 'sleep',lambda x:sleeps.append(x))
    model=FailOnce()
    result=_generate_with_retry(SimpleNamespace(models=model),model='test')
    assert result=='ok' and model.calls==2 and sleeps==[1]

def test_no_retry_for_client_error(monkeypatch):
    from app import intelligence
    sleeps=[]
    monkeypatch.setattr(intelligence.time, 'sleep',lambda x:sleeps.append(x))
    model=InvalidToken()
    with pytest.raises(ClientError):
        _generate_with_retry(SimpleNamespace(models=model),model='test')
    assert model.calls==1 and sleeps==[]
