from __future__ import annotations
import re
import zipfile
from pathlib import Path, PurePosixPath
import xml.etree.ElementTree as ET

from core import ROOT, QAError, load_jsonish

POLICY_ROOT = ROOT / 'policies' / 'presentation-templates'


def load_template_policy(template_id: str | None = None, policy_path: str | None = None):
    if policy_path:
        rel = Path(policy_path)
        if rel.is_absolute() or '..' in rel.parts:
            raise QAError('unsafe presentation template policy path')
        path = ROOT / rel
    elif template_id:
        path = POLICY_ROOT / f'{template_id}.json'
    else:
        raise QAError('template_id or policy_path is required')
    if not path.is_file():
        raise QAError('presentation template policy not found: ' + str(path.relative_to(ROOT)))
    policy = load_jsonish(path)
    if template_id and policy.get('templateId') != template_id:
        raise QAError('presentation template policy id mismatch')
    return policy, path


def _part_num(name: str, stem: str):
    m = re.search(rf'/{re.escape(stem)}(\d+)\.xml$', name)
    return int(m.group(1)) if m else 10**9


def _custom_properties(z: zipfile.ZipFile):
    name = 'docProps/custom.xml'
    if name not in z.namelist():
        return {}
    root = ET.fromstring(z.read(name))
    out = {}
    for prop in list(root):
        key = prop.attrib.get('name')
        value = next(iter(prop), None)
        if key and value is not None:
            out[key] = value.text or ''
    return out


def _slide_text(z: zipfile.ZipFile, slide_no: int):
    name = f'ppt/slides/slide{slide_no}.xml'
    if name not in z.namelist():
        return ''
    root = ET.fromstring(z.read(name))
    return ' '.join((el.text or '') for el in root.iter() if el.tag.endswith('}t'))


def _layout_names(z: zipfile.ZipFile):
    names = sorted(
        [n for n in z.namelist() if re.fullmatch(r'ppt/slideLayouts/slideLayout\d+\.xml', n)],
        key=lambda n: _part_num(n, 'slideLayout'),
    )
    out = []
    for name in names:
        root = ET.fromstring(z.read(name))
        csld = next((el for el in root.iter() if el.tag.endswith('}cSld')), None)
        out.append(csld.attrib.get('name', '') if csld is not None else '')
    return names, out


def _relationship_targets(z: zipfile.ZipFile, rels_name: str, rel_type_suffix: str):
    if rels_name not in z.namelist():
        return []
    root = ET.fromstring(z.read(rels_name))
    out = []
    for rel in list(root):
        typ = rel.attrib.get('Type', '')
        if typ.endswith(rel_type_suffix):
            out.append(rel.attrib.get('Target', ''))
    return out


def _resolve(base: PurePosixPath, target: str):
    p = PurePosixPath(target)
    if p.is_absolute():
        return p.as_posix().lstrip('/')
    parts = []
    for part in (base / p).parts:
        if part in ('', '.'):
            continue
        if part == '..':
            if parts:
                parts.pop()
        else:
            parts.append(part)
    return PurePosixPath(*parts).as_posix()


def presentation_template_qa(path: Path, policy: dict):
    issues = []
    detail = {'templateId': policy.get('templateId')}
    expected_props = policy.get('candidatePptxCustomProperties', {})
    fp = policy.get('structuralFingerprint', {})
    with zipfile.ZipFile(path) as z:
        names = set(z.namelist())
        props = _custom_properties(z)
        detail['customProperties'] = props
        for key, expected in expected_props.items():
            actual = props.get(key)
            if actual is None:
                issues.append('TEMPLATE_CUSTOM_PROPERTY_MISSING:' + key)
            elif actual != expected:
                issues.append('TEMPLATE_CUSTOM_PROPERTY_MISMATCH:' + key)

        try:
            pres = ET.fromstring(z.read('ppt/presentation.xml'))
        except KeyError:
            issues.append('TEMPLATE_PRESENTATION_XML_MISSING')
            pres = None
        slide_size = None
        if pres is not None:
            size = next((el for el in pres.iter() if el.tag.endswith('}sldSz')), None)
            if size is not None:
                try:
                    slide_size = (int(size.attrib.get('cx', '0')), int(size.attrib.get('cy', '0')))
                except ValueError:
                    slide_size = None
        detail['slideSizeEmu'] = list(slide_size) if slide_size else None
        expected_size = (fp.get('slideWidthEmu'), fp.get('slideHeightEmu'))
        if all(isinstance(x, int) for x in expected_size) and slide_size != expected_size:
            issues.append('TEMPLATE_SLIDE_SIZE_MISMATCH')

        masters = sorted([n for n in names if re.fullmatch(r'ppt/slideMasters/slideMaster\d+\.xml', n)])
        layouts, layout_names = _layout_names(z)
        slides = sorted(
            [n for n in names if re.fullmatch(r'ppt/slides/slide\d+\.xml', n)],
            key=lambda n: _part_num(n, 'slide'),
        )
        detail.update({
            'slideCount': len(slides),
            'slideMasterCount': len(masters),
            'slideLayoutCount': len(layouts),
            'layoutNames': layout_names,
        })
        if isinstance(fp.get('slideMasterCount'), int) and len(masters) != fp['slideMasterCount']:
            issues.append('TEMPLATE_MASTER_COUNT_MISMATCH')
        if isinstance(fp.get('slideLayoutCount'), int) and len(layouts) != fp['slideLayoutCount']:
            issues.append('TEMPLATE_LAYOUT_COUNT_MISMATCH')
        expected_layout_names = fp.get('layoutNames')
        if isinstance(expected_layout_names, list) and layout_names != expected_layout_names:
            issues.append('TEMPLATE_LAYOUT_NAMES_MISMATCH')

        known_layouts = set(layouts)
        for slide in slides:
            n = _part_num(slide, 'slide')
            rels = f'ppt/slides/_rels/slide{n}.xml.rels'
            targets = _relationship_targets(z, rels, '/slideLayout')
            if len(targets) != 1:
                issues.append(f'TEMPLATE_SLIDE_LAYOUT_BINDING_INVALID:S{n}')
                continue
            resolved = _resolve(PurePosixPath('ppt/slides'), targets[0])
            if resolved not in known_layouts:
                issues.append(f'TEMPLATE_SLIDE_LAYOUT_TARGET_UNKNOWN:S{n}')

        known_masters = set(masters)
        for layout in layouts:
            n = _part_num(layout, 'slideLayout')
            rels = f'ppt/slideLayouts/_rels/slideLayout{n}.xml.rels'
            targets = _relationship_targets(z, rels, '/slideMaster')
            if len(targets) != 1:
                issues.append(f'TEMPLATE_LAYOUT_MASTER_BINDING_INVALID:L{n}')
                continue
            resolved = _resolve(PurePosixPath('ppt/slideLayouts'), targets[0])
            if resolved not in known_masters:
                issues.append(f'TEMPLATE_LAYOUT_MASTER_TARGET_UNKNOWN:L{n}')

        if slides:
            cover = _slide_text(z, _part_num(slides[0], 'slide'))
            closing = _slide_text(z, _part_num(slides[-1], 'slide'))
            detail['coverText'] = cover
            detail['closingText'] = closing
            for token in fp.get('coverTextMustContain', []) or []:
                if token not in cover:
                    issues.append('TEMPLATE_COVER_TEXT_MISSING:' + token)
            for token in fp.get('closingTextMustContain', []) or []:
                if token not in closing:
                    issues.append('TEMPLATE_CLOSING_TEXT_MISSING:' + token)

    return {
        'status': 'FAIL' if issues else 'PASS',
        'pass': not issues,
        'issues': sorted(set(issues)),
        'detail': detail,
    }
