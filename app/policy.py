"""Independent evidence gate for a *fictional* incident laboratory.

This is intentionally conservative and uses structural state plus multiple
corroborating signals, not self-reported LLM confidence. It is a safety control
for a sandbox, NOT a replacement for production incident approvals.
"""
from dataclasses import dataclass
from datetime import date
from app.catalog import ALLOWED_ACTIONS

@dataclass(frozen=True)
class PolicyDecision:
    permitted: bool
    reason: str


def _logs(observations):
    raw = observations.get('read_logs') or {}
    return [str(line).lower()[:500] for line in raw.get('lines', []) if isinstance(line, str)]


def _current(lines):
    # An old, explicitly resolved event is not evidence of a *current* failure.
    markers = ('yesterday', 'historical', 'recovered', 'resolved at', 'anteontem', 'ontem', 'corrigido')
    return '\n'.join(line for line in lines if not any(marker in line for marker in markers))


def _number(value):
    try:
        return float(value) if value is not None and not isinstance(value, bool) else None
    except (ValueError, TypeError):
        return None


def _positive(value):
    n = _number(value)
    return n is not None and n > 0


def check_evidence(action: str, observations: dict) -> PolicyDecision:
    """Deny mutations unless current evidence supports the exact action.

    Synthetic fixture logs are accepted only as corroboration; future systems
    must replace them with authenticated typed telemetry (not raw LLM logs).
    """
    if action == 'escalate':
        return PolicyDecision(True, 'Encaminhamento sem operação permitido.')
    if action not in ALLOWED_ACTIONS:
        return PolicyDecision(False, 'Ação não está na allowlist.')
    health = observations.get('check_health') or {}
    metrics = observations.get('read_metrics') or {}
    settings = observations.get('read_config') or {}
    if not isinstance(health, dict) or not isinstance(metrics, dict) or not isinstance(settings, dict):
        return PolicyDecision(False, 'Telemetria obrigatória incompleta.')
    if health.get('healthy') is True or health.get('http_status') == 200:
        return PolicyDecision(False, 'Serviço já responde normalmente.')
    lines = _current(_logs(observations))
    def has(*words): return any(word in lines for word in words)

    if action == 'restart_demo_web':
        # Require current, structured telemetry. Logs are only corroboration:
        # arbitrary log text must never authorize a restart by itself.
        config_error = (has('config_validation_error', 'missing demo_service_token',
                            'required key demo_service_token', 'missing required environment')
                        or ('DEMO_SERVICE_TOKEN' in settings and
                            settings['DEMO_SERVICE_TOKEN'] in (None, '<absent>', '')))
        high_errors = _number(metrics.get('error_rate_5xx'))
        process_failed = health.get('process_alive') is False
        probe_failed = health.get('http_status') in (0, 500, 502, 503, 504)
        corroborated = (has('main pid', 'main process exited', 'process terminated',
                            'entered failed state') or
                        (high_errors is not None and high_errors >= .8))
        valid = (process_failed and probe_failed and corroborated
                 and settings.get('maintenance_mode') is not True
                 and settings.get('maintenance') is not True and not config_error)
        # Legacy emulation uses trusted fixture state only in the lab.
        valid = valid or (health.get('backend') == 'emulated' and
                          has('main process exited') and not config_error)
        reason = 'Processo inativo, health check falhando e telemetria atual corroborada.'
    elif action == 'disable_demo_maintenance':
        # User-supplied logs cannot flip this flag, even with convincing prose.
        valid = (settings.get('maintenance_mode') is True or
                 settings.get('maintenance') is True or
                 (health.get('backend') == 'emulated' and has('maintenance_mode=true')))
        reason = 'Configuração estruturada ou fixture interna de laboratório confirma manutenção ativa.'
    elif action == 'restore_demo_dns':
        failures = metrics.get('failed_dns_lookups', metrics.get('failed_dns_lookups_last_5m',
                           metrics.get('dns_failures_last_5m')))
        bad_config = (str(settings.get('dns_record', '')).lower().startswith('obsolete') or
                      str(settings.get('dns_target', '')).lower().startswith('wrong'))
        synthetic = health.get('backend') == 'emulated' and has('nxdomain')
        valid = (_positive(failures) and bad_config) or synthetic
        reason = 'Falhas DNS atuais e destino inválido confirmados por telemetria estruturada.'
    elif action == 'reset_demo_db_pool':
        available = _number(metrics.get('database_pool_available'))
        waiting = metrics.get('database_pool_waiting')
        valid = (available == 0 and _positive(waiting)) or (
            health.get('backend') == 'emulated' and has('connectionpooltimeout'))
        reason = 'Pool esgotado comprovado; ainda exige aprovação humana.'
    elif action == 'clear_demo_queue':
        depth = _number(metrics.get('queue_depth'))
        latency = _number(metrics.get('p95_latency_ms'))
        valid = (depth is not None and depth > 500 and latency is not None and latency > 1000) or (
            health.get('backend') == 'emulated' and has('queue_depth=1250'))
        reason = 'Fila congestionada comprovada por contagem e latência.'
    elif action == 'restore_demo_config':
        absent = ('DEMO_SERVICE_TOKEN' in settings and
                  settings['DEMO_SERVICE_TOKEN'] in (None, '<absent>', ''))
        valid = (has('config_validation_error', 'missing demo_service_token',
                     'required key demo_service_token', 'missing required environment')
                 and (absent or health.get('process_alive') is False or health.get('backend') == 'emulated'))
        reason = 'Erro de inicialização por configuração ausente.'
    elif action == 'renew_demo_certificate':
        expiry = settings.get('certificate_expires')
        try: expired = date.fromisoformat(expiry) < date.today()
        except (ValueError, TypeError): expired = False
        valid = ((expired and _positive(metrics.get('tls_handshake_failures')) and
                 has('expired', 'certificate has expired')) or
                 (health.get('backend') == 'emulated' and has('certificate_verify_failed')))
        reason = 'Certificado vencido e falhas TLS presentes; aprovação obrigatória.'
    elif action == 'clear_demo_cache':
        usage = _number(metrics.get('cache_usage_pct'))
        valid = ((usage is not None and usage >= 99 and has('quota exceeded', 'no space left')) or
                 (health.get('backend') == 'emulated' and has('enospc')))
        reason = 'Volume de cache esgotado; aprovação obrigatória.'
    else:
        valid = False
        reason = 'Sem política de evidência para esta ação.'
    return PolicyDecision(bool(valid), reason if valid else 'Evidência atual insuficiente/contraditória para '+action+'.')
