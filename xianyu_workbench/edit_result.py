"""Default-deny, strictly scalar Agent summaries of private edit audit results."""
import math
import re


def public_edit_result(raw, target_item_id):
    if not isinstance(raw, dict):
        return {}
    result = {}
    stage = raw.get('stage')
    if type(stage) is str and stage in {'submitting', 'verifying', 'verified'}:
        result['stage'] = stage
    item_id = raw.get('item_id')
    if type(item_id) is str and re.fullmatch(r'[0-9]{1,30}', item_id) and item_id == target_item_id:
        result['item_id'] = item_id
    for key in ('ownership_verified', 'status_verified', 'content_verified'):
        if type(raw.get(key)) is bool:
            result[key] = raw[key]
    timestamp = raw.get('verified_at')
    if type(timestamp) in (int, float) and timestamp >= 0:
        try:
            if math.isfinite(timestamp):
                result['verified_at'] = timestamp
        except OverflowError:
            pass
    notice = raw.get('notice')
    if type(notice) is str and notice == '编辑结果不确定，禁止重试；请人工核对同 ID 商品':
        result['notice'] = notice
    return result
