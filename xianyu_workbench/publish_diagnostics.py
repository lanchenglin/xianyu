"""Closed, local-only publish diagnostics. Never retain exception text or raw replies."""
from .provider import Problem

FAILURE_MESSAGES = {
    'risk_control': '平台要求安全验证',
    'auth_required': '登录态缺失或失效',
    'timeout': '执行超时',
    'uncertain': '上游执行或响应不确定',
    'upstream_error': '上游操作异常',
    'dependency_missing': '真实连接依赖缺失',
    'account_mismatch': '登录态所属账号不符',
    'account_paused': '账号已暂停',
    'human_takeover': '人工已接管',
    'publish_disabled': '发布开关关闭',
    'publish_stopped': '账号、模式或审批状态已改变',
    'integrity_error': '发布审批内容改变',
    'publish_snapshot_changed': '发布冻结快照已改变',
    'publish_defaults_missing': '发布默认快照缺失',
    'publish_location_reapproval_required': '发布地点需重新审批',
    'invalid_text_mode': '发布文本模式无效',
    'publish_evidence_required': '发布协议证据不足',
    'publish_readback_contract_required': '发布回读契约缺失',
    'publish_protocol_mismatch': '发布协议与冻结内容不一致',
    'daily_revoked': '每日授权已撤销或改变',
    'daily_code_changed': '每日生成码与冻结记录不一致',
    'daily_payload_changed': '每日授权内容已改变',
    'daily_unresolved': '每日发布存在未确定结果',
    'upload_contract_failed': '上传回执不符合契约',
    'ack_contract_failed': '发布 ACK 不符合契约',
    'readback_contract_failed': '发布回读不符合契约',
    'local_exception': '本地执行异常',
    'unknown_historical': '历史记录未保留可识别故障码，原因未知',
}
# Source codes are independent of display messages and locally generated diagnoses.
PROBLEM_CODES = frozenset({
    'risk_control', 'auth_required', 'timeout', 'uncertain', 'upstream_error',
    'dependency_missing', 'account_mismatch', 'account_paused', 'human_takeover',
    'publish_disabled', 'publish_stopped', 'integrity_error', 'publish_snapshot_changed',
    'publish_defaults_missing', 'publish_location_reapproval_required', 'invalid_text_mode',
    'publish_evidence_required', 'publish_readback_contract_required', 'publish_protocol_mismatch',
    'daily_revoked', 'daily_code_changed', 'daily_payload_changed', 'daily_unresolved',
})
CONTRACT_CODES = frozenset({'upload_contract_failed', 'ack_contract_failed', 'readback_contract_failed'})
EXECUTION_CODES = PROBLEM_CODES | CONTRACT_CODES | {'local_exception'}
HISTORICAL_CODES = frozenset({'unknown_historical'})
STAGES = frozenset({'prepared', 'uploading', 'submitting', 'verifying', 'verified', 'unknown'})


def known(value, allowed, fallback):
    return value if type(value) is str and value in allowed else fallback


def failure_summary(exc, stage, contract=None):
    if isinstance(exc, Problem):
        code = known(exc.code, PROBLEM_CODES, 'upstream_error')
    elif contract:
        code = known(contract, CONTRACT_CODES, 'local_exception')
    else:
        code = 'timeout' if isinstance(exc, TimeoutError) else 'local_exception'
    return {'code': code, 'stage': known(stage, STAGES, 'unknown')}


def execution_failure(value, stage):
    value = value if type(value) is dict else {}
    return {'code': known(value.get('code'), EXECUTION_CODES, 'upstream_error'),
            'stage': known(value.get('stage'), STAGES, known(stage, STAGES, 'unknown'))}


def public_failure(value, stage):
    value = value if type(value) is dict else {}
    return {'code': known(value.get('code'), EXECUTION_CODES | HISTORICAL_CODES, 'unknown_historical'),
            'stage': known(value.get('stage'), STAGES, known(stage, STAGES, 'unknown'))}


def failure_message(code):
    return FAILURE_MESSAGES[known(code, FAILURE_MESSAGES, 'upstream_error')] + '；结果待人工核对，禁止自动重试。'
