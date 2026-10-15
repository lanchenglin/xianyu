"""Bounded decoding of the observed ordinary-text envelope; no decompression."""
import base64
import json


def unique_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError('duplicate key')
        result[key] = value
    return result


def reject_constant(value):
    raise ValueError('nonstandard JSON constant')


def decode_text(content):
    try:
        if not isinstance(content, dict) or type(content.get('contentType')) is not int or content['contentType'] != 101:
            return None
        custom = content['custom']
        if type(custom.get('type')) is not int or custom['type'] != 1:
            return None
        encoded = custom['data']
        if not isinstance(encoded, str) or len(encoded) > 24000:
            return None
        raw = base64.b64decode(encoded, validate=True)
        if len(raw) > 18000:
            return None
        value = json.loads(raw.decode('utf-8'), object_pairs_hook=unique_object, parse_constant=reject_constant)
        stack, count = [(value, 0)], 0
        while stack:
            node, depth = stack.pop()
            count += 1
            if depth > 12 or count > 2000:
                return None
            if isinstance(node, dict):
                stack.extend((v, depth + 1) for v in node.values())
            elif isinstance(node, list):
                stack.extend((v, depth + 1) for v in node)
        if type(value.get('contentType')) is not int or value['contentType'] != 1:
            return None
        text = value['text']['text']
        if not isinstance(text, str) or not text.strip() or len(text) > 4000:
            return None
        if any(ord(c) < 32 and c not in '\n\r\t' for c in text):
            return None
        return text
    except (ValueError, TypeError, KeyError, AttributeError, RecursionError):
        return None
