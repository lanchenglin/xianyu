"""Opt-in non-CAS editing with full, typed, independent response snapshots."""
import copy
import re
import secrets
import time
from decimal import Decimal
from typing import Literal

from pydantic import ConfigDict, Field, StrictStr, model_validator

from .edit_labels import LabelDependency, validate_dependency
from .edit_transforms import SnapshotInvariantMapping, transform_invariant
from .item_edit import EditIn, get, leaves
from .models import Model
from .security import canonical, digest

OBSERVATIONAL_FIELDS = {
    'browse_count': (('detail', 'itemDO', 'browseCnt'), int),
    'server_time': (('detail', 'serverTime'), str),
    'commerce_subtitle': (('detail', 'commerceDO', 'idleItemDetailFloatInfo', 'subTitleTextInfo', 'text'), str),
}


def projection(snapshot, protocol):
    """Only value-normalize three evidenced leaves; never remove structure or audit data."""
    value = copy.deepcopy(snapshot)
    mode = protocol.get('comparison_mode', 'full_snapshot')
    fields = protocol.get('observational_fields', [])
    if mode == 'full_snapshot':
        if fields:
            raise ValueError('full snapshot cannot exclude fields')
        return value
    if mode != 'observational_projection' or not fields or len(fields) != len(set(fields)):
        raise ValueError('explicit finite observational selection required')
    dependencies = [*protocol['identity_paths'].values(), protocol['status_path'],
                    *(m['path'] for m in protocol['content_mappings']),
                    *(m['before_path'] for m in protocol['invariant_mappings'])]
    for field in fields:
        if field not in OBSERVATIONAL_FIELDS:
            raise ValueError('unknown observational field')
        path, expected_type = OBSERVATIONAL_FIELDS[field]
        for dependency in dependencies:
            other = tuple(dependency)
            if path[:len(other)] == other or other[:len(path)] == path:
                raise ValueError('observational field overlaps protected mapping')
        if type(get(value, path)) is not expected_type:
            raise ValueError('observational field missing or wrong type')
        get(value, path[:-1])[path[-1]] = 0 if expected_type is int else ''
    return value


def equivalent(left, right, protocol):
    return canonical(projection(left, protocol)) == canonical(projection(right, protocol))


def follows_previous(before, after, protocol, previous):
    # Both contracts must accept the transition: changing selection cannot hide old drift.
    return equivalent(before, after, protocol) and equivalent(before, after, previous)


class ContentMapping(Model):
    path: list[StrictStr] = Field(min_length=2, max_length=10)
    field: Literal['title', 'desc', 'price']
    encoding: Literal['identity', 'yuan_string', 'cent_string']


def encoded(field, encoding, value):
    if field == 'price' and encoding == 'cent_string':
        return str(int(Decimal(value) * 100))
    return value


def distinct(paths):
    for i, path in enumerate(paths):
        if not 1 <= len(path) <= 10 or any(not k or len(k) > 100 for k in path):
            raise ValueError('invalid object path')
        if any(path[:len(p)] == p or p[:len(path)] == path for p in paths[i + 1:]):
            raise ValueError('overlapping snapshot paths')


class SnapshotProtocol(Model):
    model_config = ConfigDict(extra='forbid', str_strip_whitespace=False)
    schema_version: Literal[3]
    concurrency_mode: Literal['bounded_snapshot']
    external_race_acknowledged: Literal[True]
    complete_semantics_confirmed: Literal[True]
    evidence: StrictStr = Field(min_length=10, max_length=2000)
    item_id: str = Field(pattern=r'^\d{1,30}$')
    uid: str = Field(pattern=r'^\d{1,30}$')
    api_version: str = Field(pattern=r'^\d{1,2}\.\d{1,2}$')
    detail_api_version: str = Field(pattern=r'^\d{1,2}\.\d{1,2}$')
    text_mode: Literal['web_combined']
    before: dict
    before_content_hash: StrictStr = Field(pattern=r'^[a-f0-9]{64}$')
    comparison_mode: Literal['full_snapshot', 'observational_projection'] = 'full_snapshot'
    observational_fields: list[Literal['browse_count', 'server_time', 'commerce_subtitle']] = Field(default_factory=list, max_length=3)
    before_values: EditIn
    original_request: dict
    template: dict
    identity_paths: dict[str, list[StrictStr]]
    status_path: list[StrictStr] = Field(min_length=2, max_length=10)
    content_mappings: list[ContentMapping] = Field(min_length=5, max_length=20)
    invariant_mappings: list[SnapshotInvariantMapping] = Field(min_length=1, max_length=200)
    fixed_constants: dict
    label_dependency: LabelDependency | None = None
    unique_code_mode: Literal['timestamp_random']
    success_ret: list[StrictStr] = Field(min_length=1, max_length=4)
    read_success_ret: list[StrictStr] = Field(min_length=1, max_length=4)
    detail_success_ret: list[StrictStr] = Field(min_length=1, max_length=4)

    @model_validator(mode='after')
    def contract(self):
        if set(self.before) != {'detail', 'edit'} or any(not isinstance(v, dict) or not v for v in self.before.values()):
            raise ValueError('complete dual response data required')
        projection(self.before, self.model_dump())
        if digest(self.before) != self.before_content_hash:
            raise ValueError('content hash mismatch; not a platform version')
        if self.before_values.item_id != self.item_id:
            raise ValueError('before identity mismatch')
        distinct(list(self.identity_paths.values()))
        # These are independently evidenced seller/ID paths, not editDetail.userId.
        if (self.identity_paths.get('uid') != ['detail', 'sellerDO', 'sellerId']
                or self.identity_paths.get('item_id') != ['detail', 'itemDO', 'itemId']
                or set(self.identity_paths) != {'uid', 'item_id', 'edit_item_id'}
                or self.identity_paths['edit_item_id'][0] != 'edit'):
            raise ValueError('independent ordinary detail ownership required')
        for key, path in self.identity_paths.items():
            value = get(self.before, path)
            expected = self.uid if key == 'uid' else self.item_id
            if type(value) not in (str, int) or str(value) != expected:
                raise ValueError('snapshot identity mismatch')
        status = get(self.before, self.status_path)
        if self.status_path[0] != 'detail' or type(status) not in (str, int) or status == '':
            raise ValueError('independent evidenced status required')
        semantic_paths = [*self.identity_paths.values(), self.status_path]
        coverage = set()
        values = self.before_values.model_dump()
        for mapping in self.content_mappings:
            if mapping.path[0] not in {'detail', 'edit'}:
                raise ValueError('dual snapshot content path required')
            if (mapping.field == 'price') != (mapping.encoding in {'yuan_string', 'cent_string'}):
                raise ValueError('explicit bounded amount encoding required')
            if canonical(get(self.before, mapping.path)) != canonical(encoded(mapping.field, mapping.encoding, values[mapping.field])):
                raise ValueError('before content mismatch')
            semantic_paths.append(mapping.path)
            coverage.add((mapping.path[0], mapping.field))
        if not {('detail', 'title'), ('detail', 'desc'), ('detail', 'price'), ('edit', 'desc'), ('edit', 'price')} <= coverage:
            raise ValueError('independent complete content mapping required')
        distinct(semantic_paths)
        if canonical(self.original_request) != canonical(self.template):
            raise ValueError('complete original request mismatch')
        expected_text = {'title': values['desc'], 'desc': values['desc'], 'titleDescSeparate': False}
        if canonical(self.template.get('itemTextDTO')) != canonical(expected_text):
            raise ValueError('only evidenced web_combined text supported')
        if canonical(self.template.get('itemPriceDTO')) != canonical({'priceInCent': encoded('price', 'cent_string', values['price'])}):
            raise ValueError('only bounded single-price request supported')
        if self.template.get('itemId') != self.item_id:
            raise ValueError('same-ID request required')
        if (set(self.fixed_constants) != {'sourceId', 'bizcode', 'publishScene'}
                or any(type(v) is not str or not v or len(v) > 200 for v in self.fixed_constants.values())
                or self.fixed_constants['bizcode'] != 'pcMainPublish'
                or self.fixed_constants['publishScene'] != 'pcMainPublish'):
            raise ValueError('only evidenced wrapper constants allowed')
        for key, value in self.fixed_constants.items():
            if self.template.get(key) != value:
                raise ValueError('fixed constant mismatch')
        if not isinstance(self.template.get('uniqueCode'), str) or not re.fullmatch(r'\d{14,16}', self.template['uniqueCode']):
            raise ValueError('timestamp_random evidence required')
        paths = [('itemTextDTO',), ('itemPriceDTO',), ('uniqueCode',)] + [(k,) for k in self.fixed_constants]
        if self.label_dependency:
            validate_dependency(self.model_dump())
            paths.append(('itemLabelExtList',))
        covered = set().union(*(leaves(get(self.template, p), p) for p in paths))
        for mapping in self.invariant_mappings:
            path, source = tuple(mapping.request_path), mapping.before_path
            if source[0] != 'edit':
                raise ValueError('request invariants require editDetail evidence')
            transformed = transform_invariant(mapping, get(self.before, source))
            if canonical(get(self.template, path)) != canonical(transformed):
                raise ValueError('request must exactly match evidenced finite transform')
            # A fixed request value cannot be sourced from approved changing content.
            distinct([source, *(m.path for m in self.content_mappings)])
            paths.append(path)
            covered.update(leaves(get(self.template, path), path))
        distinct(paths)
        if not any(m.request_path == ['itemId'] and m.before_path == self.identity_paths['edit_item_id'] for m in self.invariant_mappings):
            raise ValueError('same-ID mapping required')
        if covered != leaves(self.template):
            raise ValueError('unmapped request fields')
        if any(not r.startswith('SUCCESS::') for r in self.success_ret + self.read_success_ret + self.detail_success_ret):
            raise ValueError('exact success ret required')
        if len(canonical(self.model_dump())) > 60000:
            raise ValueError('contract too large')
        return self


def unique_code():
    return str(int(time.time() * 1000)) + str(secrets.randbelow(1000))


def read_pair(call, protocol):
    detail = call('edit.detail', {'item_id': protocol['item_id'], 'api_version': protocol['detail_api_version']})
    edit = call('edit.read', {'item_id': protocol['item_id'], 'api_version': protocol['api_version']})
    if detail.get('ret') != protocol['detail_success_ret'] or edit.get('ret') != protocol['read_success_ret']:
        raise ValueError('dual read success mismatch')
    return {'detail': detail['data'], 'edit': edit['data']}


def expected_after(protocol, payload):
    expected = copy.deepcopy(protocol['before'])
    for mapping in protocol['content_mappings']:
        path = mapping['path']
        get(expected, path[:-1])[path[-1]] = encoded(mapping['field'], mapping['encoding'], payload[mapping['field']])
    return expected


def request_template(protocol, payload, code):
    if not isinstance(code, str) or not re.fullmatch(r'\d{14,16}', code) or code == protocol['template']['uniqueCode']:
        raise ValueError('invalid frozen uniqueCode')
    template = copy.deepcopy(protocol['template'])
    template['itemTextDTO'].update(title=payload['desc'], desc=payload['desc'])
    template['itemPriceDTO']['priceInCent'] = encoded('price', 'cent_string', payload['price'])
    template['uniqueCode'] = code
    unchanged = copy.deepcopy(template)
    for key in ('itemTextDTO', 'itemPriceDTO', 'uniqueCode'):
        unchanged[key] = protocol['original_request'][key]
    if canonical(unchanged) != canonical(protocol['original_request']):
        raise ValueError('unapproved request mutation')
    return template
