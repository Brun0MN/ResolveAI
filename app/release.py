"""Single source of truth for release identification and report-policy compatibility."""
from hashlib import sha256
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def version() -> str:
    return (ROOT / 'VERSION').read_text(encoding='utf-8').strip()


def policy_digest() -> str:
    return sha256((ROOT / 'app' / 'policy.py').read_bytes()).hexdigest()[:16]


def policy_status(report: dict) -> str:
    """Compatibility of saved evaluation with current policy, not app release number."""
    old = report.get('policy_sha256_prefix')
    if not isinstance(old, str) or len(old) != 16:
        return 'unknown'
    return 'match' if old == policy_digest() else 'changed'
