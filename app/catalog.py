"""Realistic (fictional) lab incidents and explicit operation safety policy.

The benchmark labels in SCENARIOS are NOT provided to the LLM.
"""
from dataclasses import dataclass

@dataclass(frozen=True)
class Scenario:
    key: str
    title: str
    description: str
    log: str
    status: str
    operation: str
    category: str
    severity: str

SCENARIOS = {
    'web_stopped': Scenario('web_stopped', 'Serviço web interrompido', 'A aplicação deixou de responder e usuários recebem erro 503.', 'systemd[1]: demo-web.service: main process exited, code=exited, status=1/FAILURE; unit inactive', 'HTTP 503: backend process is not running', 'restart_demo_web', 'Aplicação', 'alta'),
    'maintenance_enabled': Scenario('maintenance_enabled', 'Modo de manutenção indevido', 'O portal está exibindo a página de manutenção sem janela planejada.', 'gateway: maintenance_mode=true, no active maintenance window; HTTP 503', 'HTTP 503: maintenance page served', 'disable_demo_maintenance', 'Configuração', 'média'),
    'dns_invalid': Scenario('dns_invalid', 'Resolução DNS incorreta', 'A aplicação não encontra seu serviço de autenticação interno.', 'resolver: NXDOMAIN for auth.demo.internal, nameserver record target=wrong.demo.internal', 'HTTP 503: upstream DNS lookup failed', 'restore_demo_dns', 'Rede/DNS', 'alta'),
    'db_pool_exhausted': Scenario('db_pool_exhausted', 'Pool de conexões esgotado', 'A API apresenta timeout ao consultar dados.', 'dbpool: available=0, pending=48; ConnectionPoolTimeout: queue exhausted', 'HTTP 503: database pool has no free slots', 'reset_demo_db_pool', 'Banco de dados', 'alta'),
    'queue_backlog': Scenario('queue_backlog', 'Fila de trabalhos congestionada', 'A resposta da aplicação está muito lenta.', 'worker: queue_depth=1250, processing_delay_ms=2800; traffic spike in demo workload', 'HTTP 503: latency SLO exceeded, simulated p95=2800ms', 'clear_demo_queue', 'Desempenho', 'média'),
    'config_missing': Scenario('config_missing', 'Variável de configuração ausente', 'Falha de inicialização após alteração de configuração.', 'startup: CONFIG_VALIDATION_ERROR: missing DEMO_SERVICE_TOKEN in test fixture', 'HTTP 503: demo service configuration invalid', 'restore_demo_config', 'Configuração', 'média'),
    'cert_expired': Scenario('cert_expired', 'Certificado de teste expirado', 'Integração interna apresenta falha TLS.', 'tls: CERTIFICATE_VERIFY_FAILED demo-gateway-test, expiry=2020-01-01 (fixture)', 'HTTP 503: simulated TLS handshake failed', 'renew_demo_certificate', 'Segurança', 'alta'),
    'unknown_failure': Scenario('unknown_failure', 'Falha com causa indeterminada', 'A aplicação está indisponível, mas ainda não há diagnóstico confiável.', 'observer: upstream probe failed; no stack trace, root cause or decisive signal available', 'HTTP 503: investigation pending, insufficient evidence', 'escalate', 'Indeterminada', 'média'),
    'disk_cache_full': Scenario('disk_cache_full', 'Cache de teste sem espaço', 'A aplicação não consegue gravar arquivos temporários.', 'filesystem: ENOSPC on /demo/cache; allocated=100%, quota reached in synthetic volume', 'HTTP 503: demo cache volume exhausted', 'clear_demo_cache', 'Armazenamento', 'média'),
}

# These actions operate ONLY on the dedicated fictional lab, not on the user's machine.
AUTO_ACTIONS = {'restart_demo_web', 'disable_demo_maintenance', 'restore_demo_dns', 'clear_demo_queue', 'restore_demo_config'}
APPROVAL_ACTIONS = {'reset_demo_db_pool', 'renew_demo_certificate', 'clear_demo_cache'}
ALLOWED_ACTIONS = AUTO_ACTIONS | APPROVAL_ACTIONS

# Free-form commands, host shell, file access and arbitrary networks are never allowed.
SAFE_TOOL_NAMES = ('check_health', 'read_logs', 'read_metrics', 'read_config')
