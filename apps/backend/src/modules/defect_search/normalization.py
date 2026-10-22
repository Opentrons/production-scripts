"""Conservative display and action normalization; original records stay intact."""
from __future__ import annotations

import re
from typing import Any


# A P-prefixed pipette model (P50S, P1000S) must never become a duration.
SECOND_PATTERN = re.compile(
    r'(?<![p\d.])(\d+(?:\.\d+)?)\s*-?\s*(?:″|＂|”|"|秒|(?:seconds?|secs?|s)(?![a-z\d])(?!(?:\s*[-_－])))',
    re.IGNORECASE,
)
_PRODUCTS = (
    'P50M-G3', 'P1000M-G3', 'P1000S-G3', 'P50S-G3', 'P1000M-MINI',
    'P50M-MINI', 'P1000S-MINI', 'P50S-MINI', 'P1000M-D', 'P1000MPeek',
    'HS', 'OT2-R', 'OT3', 'OT3-MINI', 'OT3-Ultima', 'Plate stacker',
    'Plate Reader', 'Gripper', 'Gripper-MINI', '96H', '96H-200', '96H-200M',
    'TC2-R', 'Stacker电源', 'TD', 'HEPA UV',
)


def clean(value: Any) -> str:
    return re.sub(r'\s+', ' ', str(value or '')).strip()


def _product_key(value: str) -> str:
    value = clean(value).replace('－', '-').replace('_', '-')
    return re.sub(r'\s+', '', value).casefold()


_PRODUCT_LOOKUP = {_product_key(product): product for product in _PRODUCTS}


def canonical_product(value: str) -> str:
    """Normalize spelling of one model without merging its hardware variants."""
    value = clean(value)
    return _PRODUCT_LOOKUP.get(_product_key(value), value)


def product_aliases(value: str) -> tuple[str, ...]:
    canonical = canonical_product(value)
    aliases = (canonical, canonical.lower(), canonical.upper(), canonical.replace(' ', ''),
               canonical.replace('-', '_'), canonical.replace('-', '－'), canonical.replace('-', ' - '))
    return tuple(dict.fromkeys(alias for alias in aliases if alias))


def product_pattern(value: str) -> str:
    """Match the complete model with flexible, optional printed separators.

    Callers still supply ASCII boundaries and try longer model names first, so
    a spelling such as ``Gripper MINI`` cannot select the base Gripper model.
    """
    pieces = re.split(r'[\s_－-]+', canonical_product(value))
    return r'[\s_－-]*'.join(re.escape(piece) for piece in pieces if piece)


def normalize_seconds(value: str) -> str:
    return SECOND_PATTERN.sub(lambda match: f'{float(match[1]):g}秒', clean(value).lower())


def normalized_description(value: str) -> str:
    return re.sub(r'\s+', '', normalize_seconds(value))


def duration_values(value: str) -> set[float]:
    return {float(match[1]) for match in SECOND_PATTERN.finditer(value)}


# Corrections observed in the imported descriptions. They change spelling,
# never the axis, component, operating stage or an additional symptom.
_SYMPTOM_SPELLINGS = {
    'homung': 'homing',
    'hstogram': 'histogram',
    'empey': 'empty',
    'functonal': 'functional',
}
_STATUS_STEMS = (
    'force', 'width', 'latch', 'general', 'cycling', 'cycle', 'cying',
    'doorswitch', 'door', 'switch',
)
_STATUS_COMPOUND = re.compile(
    r'(?<![a-z])(' + '|'.join(_STATUS_STEMS) + r')(?:failure|failed|fail|ng)(?![a-z])',
    re.IGNORECASE,
)
_STATUS_WORD = re.compile(r'(?<![a-z])(?:failure|failed|fail|ng)(?![a-z])', re.IGNORECASE)
_SYMPTOM_TOKEN = re.compile(
    r'\d+(?:\.\d+)?秒|[a-z]+\d+(?:[a-z]+\d*)*|\d+(?:\.\d+)?[a-z]+|'
    r'[a-z]+|\d+(?:\.\d+)?|[\u3400-\u9fff]+', re.IGNORECASE,
)
_ORDERED_SYMPTOM = re.compile(
    r'前|后|先|再|又|时|导致|过程中|之前|之后|→|->|'
    r'(?<![a-z])(?:before|after|then|while|during)(?![a-z])', re.IGNORECASE,
)
_COMPARISONS = (
    (r'>=|≥|≧|大于等于|不少于|至少', '不小于'),
    (r'<=|≤|≦|小于等于|不超过|至多', '不大于'),
    (r'!=|≠', '不等于'),
    (r'±|\+\s*/\s*-', '正负'),
    (r'>|＞|超过|高于', '大于'),
    (r'<|＜|低于', '小于'),
    (r'(?<![<>=!])=(?!=)', '等于'),
)
_MEASUREMENT_NUMBER = re.compile(r'(?<![\d.])(?:[+\-−－负]\s*)?\d+(?:\.\d+)?(?![\d.])')
_COMPARISON_VALUE = re.compile(
    r'(不小于|不大于|不等于|大于|小于|等于|正负)\s*'
    r'((?:[+\-−－负]\s*)?\d+(?:\.\d+)?)?'
)
_POSITION = re.compile(r'(?<![a-z])([a-h])\s*(1[0-2]|[1-9])(?!\d)')
_CHANNEL_RANGE = re.compile(
    r'(?<!\d)(\d{1,2})\s*[-~～至到]\s*(\d{1,2})\s*(?:ch|通道)(?![a-z])|'
    r'(?<![a-z\d])(?:ch|通道)\s*(\d{1,2})\s*[-~～至到]\s*(\d{1,2})(?!\d)'
)
_CHANNEL_COUNT = re.compile(r'(?<!\d)(\d{1,2})\s*个\s*(?:ch|通道)(?![a-z])')
_CHANNEL_POSITION = re.compile(
    r'(?<!\d)(\d{1,2})\s*(?:ch|通道)(?![a-z])|'
    r'(?<![a-z\d])(?:ch|通道)\s*(\d{1,2})(?!\d)'
)


def _comparison_text(value: str) -> str:
    text = clean(value)
    for pattern, replacement in _COMPARISONS:
        text = re.sub(pattern, replacement, text)
    text = re.sub(r'(?<![a-z\d.])\.(?=\d)', '0.', text, flags=re.IGNORECASE)
    return text


def _number_value(match: re.Match[str], text: str) -> str:
    value = re.sub(r'\s+', '', match[0]).replace('−', '-').replace('－', '-')
    prefix = text[match.start() - 1:match.start()] if match.start() else ''
    # A hyphen attached to an ASCII label is a delimiter (speed-180); a
    # standalone minus or Chinese temperature label remains a negative value.
    if value.startswith('-') and prefix and re.fullmatch(r'[a-z]', prefix, re.I):
        left, right = text[:match.start()], text[match.end():].lstrip()
        temperature = (bool(re.search(r'(?:temp(?:erature)?|温度)\s*$', left, re.I))
                       or bool(re.match(r'℃|°\s*c|度', right, re.I)))
        if not temperature:
            value = value[1:]
    elif value.startswith('负'):
        value = value[1:] if prefix == '正' else '-' + value[1:]
    if value.startswith('+'):
        value = value[1:]
    return value


def _symptom_conditions(value: str) -> set[str]:
    text = normalize_seconds(_comparison_text(value))
    conditions = {'number:' + _number_value(match, text) for match in _MEASUREMENT_NUMBER.finditer(text)}
    conditions.update('position:' + match[1] + match[2]
                      for match in _POSITION.finditer(text))
    axis_text = _symptom_value(value)
    conditions.update('axis:' + match[1]
                      for match in re.finditer(
                          r'(?<![a-z\d])([xyz])(?=[\s_-]*(?:轴|axis|tof|speed|histogram|current))', axis_text))
    conditions.update('axis:' + match[1]
                      for match in re.finditer(
                          r'(?<![a-z\d])tof[\s_-]*([xyz])(?=[\s_-]*(?:失败|fail|failure|ng|$))', axis_text))
    for match in _CHANNEL_RANGE.finditer(text):
        conditions.add('channel-range:' + (match[1] or match[3]) + '-' + (match[2] or match[4]))
    channel_text = _CHANNEL_RANGE.sub(' ', text)
    conditions.update('channel-count:' + match[1]
                      for match in _CHANNEL_COUNT.finditer(channel_text))
    for match in _CHANNEL_POSITION.finditer(channel_text):
        conditions.add('channel:' + str(int(match[1] or match[2])))
    conditions.update(f'duration:{duration:g}' for duration in duration_values(text))
    for match in _COMPARISON_VALUE.finditer(text):
        operator, number = match[1], match[2]
        if number:
            number_match = _MEASUREMENT_NUMBER.search(number)
            number = _number_value(number_match, number) if number_match else number
        conditions.add('comparison:' + operator + (':' + number if number else ''))
    return conditions


def symptom_conditions_match(query: str, description: str) -> bool:
    """Require every explicit number, position, axis and comparison condition.

    No unit conversion or approximate numeric match is inferred. A query can
    leave the channel unspecified, but naming H1, X轴, 18 or ±1 constrains it.
    """
    return _symptom_conditions(query).issubset(_symptom_conditions(description))


def ordered_symptom(value: str) -> bool:
    """Keep sequence language and multiple numeric parameters in printed order.

    With several values, word order also binds each value to its label:
    speed-180/current-0.8 must not become speed-0.8/current-180.
    """
    if _ORDERED_SYMPTOM.search(value):
        return True
    text = normalize_seconds(_comparison_text(value))
    # These numbers already carry independent identities, so "60s 4CH" and
    # "4CH 60秒" retain their established equivalence in either word order.
    for pattern in (SECOND_PATTERN, _CHANNEL_RANGE, _CHANNEL_COUNT, _CHANNEL_POSITION, _POSITION):
        text = pattern.sub(' ', text)
    return len(list(_MEASUREMENT_NUMBER.finditer(text))) > 1


def _symptom_value(value: str) -> str:
    text = _comparison_text(value)
    for original, canonical in _SYMPTOM_SPELLINGS.items():
        text = re.sub(r'(?<![a-z])' + original + r'(?![a-z])', canonical, text, flags=re.IGNORECASE)
    # Raw CamelCase is useful evidence of a status suffix. In particular this
    # is case-sensitive: the final letters of "homing" are never an NG token.
    text = re.sub(r'(?<=[a-z])(?:Failure|Failed|Fail|NG)(?![a-zA-Z])', '失败', text)
    text = _STATUS_COMPOUND.sub(lambda match: match[1] + '失败', text)
    text = _STATUS_WORD.sub('失败', text)
    text = normalize_seconds(text)
    # Shop-floor descriptions use Chinese status words after the same named
    # tests. Keep the component/stage, only normalize its failure suffix.
    text = re.sub(
        r'(?<![a-z])(latch|force|width|homing|general|cycling|cycle|histogram|tof)'
        r'[\s_-]*(?:故障|异常|报错)', r'\1失败', text,
    )
    text = re.sub(r'(?<![a-z])width(?![a-z])', '宽度', text)
    text = re.sub(r'(?<![a-z])leak(?:age)?(?![a-z])', '漏液', text)
    text = text.replace('漏水', '漏液').replace('噪音', '异响').replace('噪声', '异响')
    # These two recorded phrases differ only by an optional test wrapper.
    # Other words remain, e.g. 二次, homing, 亮黄灯, 过程中 and Z轴掉落.
    text = re.sub(r'协议(?:\s*测试)?(?:\s*运行)?\s*(?:失败|报错)', '协议失败', text)
    text = re.sub(r'老化(?:\s*测试)?(?:\s*运行)?\s*失败', '老化失败', text)
    if re.search(r'force[\s_-]*失败', text):
        text = text.replace('夹爪', '')
    return text


def normalize_symptom(value: str) -> str:
    """Conservative symptom spelling used for matching, not stored payloads."""
    # Keep decimal points inside measurements; 0.5 seconds is not 05 seconds.
    return re.sub(r'[^\w.]|_|(?<!\d)\.|\.(?!\d)', '', _symptom_value(value), flags=re.UNICODE)


def symptom_terms(value: str) -> list[str]:
    """Keep all requested conditions, allowing harmless word order changes."""
    return [match[0] for match in _SYMPTOM_TOKEN.finditer(_symptom_value(value))]


def complete_symptom(query: str, description: str) -> bool:
    """Require the complete normalized description, including qualifiers.

    Word order may differ, but every query token is consumed once and nothing
    may remain. A duration, channel, axis, homing stage or second defect can
    therefore never disappear merely to manufacture a complete match.
    """
    if not symptom_conditions_match(query, description) or not symptom_conditions_match(description, query):
        return False
    wanted, remaining = normalize_symptom(query), normalize_symptom(description)
    if not wanted or not remaining:
        return False
    if wanted == remaining:
        return True
    # Ordering/conditional language is part of the reported failure. The two
    # operations in "开机后复位失败" must not be swapped to match a new fault.
    if ordered_symptom(query) or ordered_symptom(description):
        return False
    terms = symptom_terms(query)
    if not terms:
        return False
    for term in sorted(terms, key=len, reverse=True):
        if term not in remaining:
            return False
        remaining = remaining.replace(term, '', 1)
    return not remaining


def _unique(values: list[str]) -> list[str]:
    return list(dict.fromkeys(values))


def normalize_action(action: str, serial_number: str = '') -> dict[str, Any]:
    """Remove identifiable historical serials, retaining parts, position and order.

    This deliberately does not collapse repairs solely because they mention the
    same part: before/after wording, revision, channel and operation order remain
    part of the normalized description and therefore its grouping key.
    """
    value = clean(action)
    value = re.sub(r'XWS-?\d{5,8}[A-Z]\d{3,8}', '', value, flags=re.IGNORECASE)
    serial = clean(serial_number)
    if len(serial) >= 7 and re.search(r'[a-z]', serial, re.IGNORECASE) and re.search(r'\d', serial):
        value = re.sub(re.escape(serial), '', value, flags=re.IGNORECASE)
    value = re.sub(r'(?:\bS\s*/?\s*N\s*[:：]?|序列号\s*[:：]?)\s*[A-Z][A-Z0-9-]{7,}', '', value, flags=re.IGNORECASE)
    value = value.translate(str.maketrans({'（': '(', '）': ')', '，': '、', '；': ';', '：': ':', '－': '-'}))
    value = re.sub(r'\s*([、;:])\s*', r'\1', value)
    value = re.sub(r'(?<=\d)\.(?=\d{3}-\d{5})', '、', value)
    value = re.sub(r'\s+', ' ', value).strip(' 、;,')
    if value.casefold() in {'sw update', '软件更新', '更新软件'}:
        value = '软件升级'
    operations = re.findall(r'重新烧录|重新烧|烧录|烧|重新安装|重新组装|重装|复装|拆机|更换|返修|调整|校准|复测|升级|清洁|清理|紧固|换', value)
    components = re.findall(r'(?<!\d)\d{3}-\d{5}(?!\d)', value)
    components += re.findall(r'(?:更换|换|电机|齿轮)\s*(\d{4})(?![a-z\d.])', value, re.IGNORECASE)
    versions = re.findall(r'(?<![a-z])(?:\d{4})?[A-Z]\d+(?:\.\d+)+(?![\d.])|\bV\d+(?:\.\d+)*\b|[A-Z]\d+(?=版本)', value, re.IGNORECASE)
    positions = re.findall(r'(?<![a-z\d])\d{1,2}\s*ch(?![a-z\d])|(?<![a-z])[A-H](?:1[0-2]|[1-9])(?![\d.])|(?:第?\d+(?:、\d+)*)(?:通道|轴)|[XYZ]轴|左(?:边|侧)?|右(?:边|侧)?|上面|下面|朝上|朝下|正向|反向|前端|后端', value, re.IGNORECASE)
    revision_tokens = {item.upper() for item in versions}
    positions = [item for item in positions if item.upper() not in revision_tokens]
    return {
        'normalized_action': value,
        'operation': ' → '.join(operations),
        'components': _unique(components),
        'versions': _unique([item.upper() for item in versions]),
        'positions': _unique(positions),
    }


def normalized_action(action: str, serial_number: str = '') -> str:
    return str(normalize_action(action, serial_number)['normalized_action'])


def positive_verification(value: str) -> bool:
    """Only explicit positive validation is evidence; a part name is not."""
    value = clean(value).casefold()
    if not value or re.search(r'不通过|未通过|失败|未解决|未验证|待验证|待确认|待复测|未复测|未确认|仍有|仍然|依旧|复发|但是|但|后又|之后又|再次异常|不ok|not\s+ok|异常|复现|(?<![a-z])ng(?![a-z])|(?<![a-z])fail(?:ed|ure)?(?![a-z])', value.replace('无异常', '')):
        return False
    return bool(re.search(r'\bok\b|(?<=[\u4e00-\u9fff])ok\b|通过|无异常|验证正常|测试正常|复测正常', value))
