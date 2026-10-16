"""Explicit existing-conversation binding; no automatic FAQ or first contact."""
import re
import time

from .provider import Problem
from .security import digest


def binding(service, account):
    settings = service.s
    if not settings.message_send_enabled:
        raise Problem('message_send_disabled', '管理员尚未启用单条消息发送', 409)
    if (not settings.browser_cdp_endpoint or account['id'] != settings.browser_cdp_account_id
            or account['uid'] != settings.browser_cdp_uid):
        raise Problem('cdp_binding_mismatch', '消息账号与管理员 CDP 绑定不符', 409)
    if not account['secret']:
        raise Problem('auth_required', '发送需要管理员独立导入同账号 Cookie；不会从浏览器提取', 409)
    cookies = service.vault.open(account['secret'])
    if cookies.get('unb') != account['uid']:
        raise Problem('account_mismatch', '独立发送登录态账号不符', 409)
    state = service.db.one('SELECT revision FROM message_observation WHERE account_id=?', (account['id'],))
    return {'uid': account['uid'], 'source': 'independent_cookie_ws',
            'observation_revision': state['revision'] if state else 0,
            'credential_digest': digest(cookies), 'endpoint': settings.browser_cdp_endpoint}


def verify_pair(service, account, payload):
    service.observation.guard(account['id'])
    if (not re.fullmatch(r'[0-9]{1,30}', payload['cid'])
            or not re.fullmatch(r'[0-9]{1,30}', payload['toid'])
            or payload['toid'] == account['uid']):
        raise Problem('recipient_unverified', '仅支持已核验数字 CID 与不同的单聊收件人', 409)
    result = service.provider.call(account['id'], 'messages', {})
    matches = [item for item in result.get('items', []) if item.get('cid') == payload['cid']]
    if (not matches or any(item.get('recipient_verified') is not True
                           or item.get('peer_uid') != payload['toid'] for item in matches)):
        raise Problem('recipient_unverified', '本次只读样本无法确认会话双方，停止发送', 409)
    return matches


def prepare(service, account, payload):
    frozen = binding(service, account)
    verify_pair(service, account, payload)
    return {**payload, '_binding': frozen}


def preflight(service, account, payload):
    if payload.get('_binding') != binding(service, account):
        raise Problem('send_binding_changed', '发送登录态或绑定已改变，请重新申请审批', 409)
    return verify_pair(service, account, payload)


def observe(service, account, payload, before):
    """Read-only evidence, never a delivery receipt or permission to replay."""
    result = {'verification': 'unconfirmed', 'delivery_confirmed': False,
              'notice': '发送尝试结果待核实；不会自动重发，不代表送达或已读。'}
    try:
        current = service.provider.account(account['id'])
        wait = max(0, current['last_call'] + service.s.read_interval - time.time())
        if wait > 10 or service.stop.wait(wait):
            raise Problem('readback_deferred', '只读核对等待超过预算', 409)
        after = verify_pair(service, account, payload)
        old_ids = {item.get('message_id') for item in before}
        observed = [item for item in after if item.get('message_id') not in old_ids
                    and item.get('direction') == 'outgoing' and item.get('sender_uid') == account['uid']
                    and item.get('body_status') == 'available' and item.get('body') == payload['text']]
        result['matching_new_outgoing_observed'] = bool(observed)
        # Matching text alone cannot correlate a particular send request to a platform ACK.
        result['notice'] = ('只读观察到新增同文消息，但无法关联发送请求；仍待人工核实，非送达证明。'
                            if observed else result['notice'])
    except Exception:
        result['readback_failed'] = True
    return result
