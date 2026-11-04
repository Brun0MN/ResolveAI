"""Read-only evaluation of newly frozen, author-defined synthetic cases."""
import json
from pathlib import Path
from app.config import config
from app.release import version, policy_status


def report_path():
    return Path(config.database_path).resolve().parent / 'reserved_latest.json'


def save(result):
    path = report_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix('.tmp')
    temp.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding='utf-8')
    temp.replace(path)


def latest():
    path = report_path()
    if not path.is_file():
        return {'available':False,'message':'Nenhum resultado da nova bateria congelada. O modo offline é gratuito.'}
    try:
        if path.stat().st_size > 1_000_000:
            raise ValueError('Arquivo muito grande')
        content = json.loads(path.read_text(encoding='utf-8'))
        if not isinstance(content,dict) or not isinstance(content.get('summary'),dict) or not isinstance(content.get('details'),list):
            raise ValueError('Arquivo inválido')
        return {'available':True,**content,'policy_status':policy_status(content),'running_version':version()}
    except (OSError,ValueError,UnicodeError,TypeError):
        return {'available':False,'message':'Não foi possível carregar o relatório da bateria congelada.'}
