"""Pinned F1C100S reference inventory, ELF comparison and bounded ARM survey.

Never executes reference/device code. Zig is invoked only as a C cross compiler.
MMIO literals, branch edges and similarity results remain hypotheses. Approved
Ghidra labels additionally require prior original-byte execution evidence.
"""
from __future__ import annotations

import argparse
import difflib
import gzip
import hashlib
import io
import json
import os
import re
import struct
import subprocess
from pathlib import Path

from capstone import Cs, CS_ARCH_ARM, CS_MODE_ARM, CS_MODE_LITTLE_ENDIAN
from capstone.arm import ARM_OP_IMM, ARM_OP_MEM, ARM_OP_REG, ARM_REG_PC
from elftools.elf.elffile import ELFFile

BASE = 0x7fffffe0
CODE_START, CODE_END = 0x80000000, 0x80063800
PINS = {
    'mikljohansson/fnirsi-1013d-mcp': 'fa8377b2b1d148f8596a8befe638df79062c2bd8',
    'nminaylov/F1C100s_projects': 'c11422e99c9f33e8419a5ac4dcab6684c8d38296',
    'nminaylov/F1C100s_info': 'ec42b9b4147070b4277e86d12324d5cd0662cd1a',
    'minilogic/f1c_nonos': '73933dbb56d2cbdeb1f260a484bb7c525866616f',
}
KNOWN_HASHES = {
    'V3.6': '7523b2e91dd8627ffebfc7ac0525c0607a56df4cece04028a9c3a8ee558f6eb9',
    'V3.8': '7e7d7230155fe0790eb48531de2ef463bb122c0ae1a820ab6d10cf2e60f50290',
}


def digest(data):
    return hashlib.sha256(data).hexdigest()


def write(path, obj):
    path.write_text(json.dumps(obj, indent=2) + '\n', encoding='utf-8')


def run(args, **kwargs):
    return subprocess.run([str(x) for x in args], check=True, capture_output=True,
                          text=True, **kwargs).stdout.strip()


def inventory(root):
    result = []
    for repo, sha in PINS.items():
        path = root / repo.replace('/', '__')
        actual = run(['git', '-C', path, 'rev-parse', 'HEAD'])
        assert actual == sha, (repo, actual)
        assert not run(['git', '-C', path, 'status', '--porcelain']), repo
        licenses = [p for p in path.iterdir() if p.is_file() and
                    re.match(r'^(license|licence|copying)', p.name, re.I)]
        selected = []
        for rel in run(['git', '-C', path, 'ls-files']).splitlines():
            if (rel.endswith(('.h', '.c', '.S', '.s', '.ld', '.o')) and
                (rel.startswith(('f1c100s/', 'drv/', 'LIB_RE/', 'BROM/')) or
                 rel.startswith('firmware/scope/') and rel.count('/') == 2)) or rel == 'README.md' or (rel.startswith('BROM/') and rel.endswith('.bin')):
                p = path / rel
                selected.append({'path': rel, 'bytes': p.stat().st_size,
                                 'sha256': digest(p.read_bytes())})
        result.append({'repository': repo, 'commit': sha,
                       'url': f'https://github.com/{repo}/tree/{sha}',
                       'root_license': 'GPL-3.0 text' if licenses else 'no root license found; rights unresolved',
                       'licenses': [{'path': p.name, 'sha256': digest(p.read_bytes())} for p in licenses],
                       'files': selected})
    return result


def register_map(root):
    """Extract literals/enums; do not execute preprocessor expressions."""
    project = root / 'nminaylov__F1C100s_projects/f1c100s/drivers/inc'
    bases, groups = [], []
    for number, line in enumerate((project / 'f1c100s_periph.h').read_text().splitlines(), 1):
        m = re.match(r'#define\s+(\w+)_BASE\s+\((0x[0-9a-fA-F]+)\)', line)
        if m:
            bases.append({'name': m[1], 'base': int(m[2], 16), 'source':
                          'nminaylov/F1C100s_projects:f1c100s/drivers/inc/f1c100s_periph.h', 'line': number})
    for p in sorted(project.glob('*.h')):
        text = p.read_text()
        for match in re.finditer(r'typedef\s+enum\s*\{(.*?)\}\s*(\w*reg\w*)\s*;', text, re.S):
            values = []
            for m in re.finditer(r'(\w+)\s*=\s*(0x[0-9a-fA-F]+|[0-9]+)\s*[,\n]', match[1]):
                values.append({'name': m[1], 'offset': int(m[2], 0),
                               'line': text.count('\n', 0, match.start(1) + m.start()) + 1})
            groups.append({'enum': match[2], 'source': f'nminaylov/F1C100s_projects:f1c100s/drivers/inc/{p.name}',
                           'registers': values})
    # Extract explicitly annotated struct offsets as reference claims. They are
    # NOT used to synthesize C struct layouts: these headers contain known typos.
    p = root / 'minilogic__f1c_nonos/drv/f1c100s.h'
    annotations = []
    section = ''
    for number, line in enumerate(p.read_text().splitlines(), 1):
        m = re.match(r'/\* ([A-Z /]+) \*/', line)
        if m:
            section = m[1]
        m = re.search(r'\b(?:u32|u16|u8)\s+(\w+)(?:\[[^]]+\])?\s*;\s*//\s*(0x[0-9a-fA-F]+)', line)
        if m and not m[1].startswith('RES'):
            annotations.append({'section': section, 'name': m[1], 'offset': int(m[2], 16), 'line': number})
    return {'schema': 'ys4470.f1c100s.reference-registers.v1', 'bases': bases, 'register_enums': groups,
            'annotated_offsets': {'source': 'minilogic/f1c_nonos:drv/f1c100s.h', 'entries': annotations},
            'limits': ['Reference definitions are claims, not verified YS-4470 register accesses.',
                       'minilogic DRAM/PIO/DDMA definitions contain inconsistencies; annotations are not struct-offset validation.',
                       'Internal KEYADC/RTP do not identify the external measurement ADC.']}


def compile_sources(root, zig, out):
    project = root / 'nminaylov__F1C100s_projects/f1c100s'
    objects, logs = [], []
    cache = out / 'compiler-cache'
    env = dict(os.environ, ZIG_LOCAL_CACHE_DIR=str(cache / 'local'),
               ZIG_GLOBAL_CACHE_DIR=str(cache / 'global'), TEMP=str(cache / 'tmp'), TMP=str(cache / 'tmp'))
    (cache / 'tmp').mkdir(parents=True, exist_ok=True)
    flags = ['cc', '-target', 'arm-freestanding-eabi', '-mcpu=arm926ej_s', '-marm', '-O2',
             '-ffreestanding', '-fno-builtin', '-ffunction-sections', '-std=gnu99',
             '-I', str(project / 'drivers/inc'), '-I', str(project / 'arm926/inc')]
    for module in ('pwm', 'gpio', 'timer', 'uart', 'clock'):
        source = project / f'drivers/src/f1c100s_{module}.c'
        target = out / f'reference_{module}.o'
        run([zig, *flags, '-c', source, '-o', target], env=env)
        objects.append((target, 'compiled_source', f'nminaylov/F1C100s_projects:f1c100s/drivers/src/f1c100s_{module}.c'))
        logs.append({'source': source.name, 'source_sha256': digest(source.read_bytes()),
                     'object': target.name, 'object_sha256': digest(target.read_bytes()),
                     'flags': flags[:12]})
    return objects, {'compiler': 'Zig ' + run([zig, 'version']), 'compiler_sha256': digest(zig.read_bytes()), 'builds': logs}


def elf_functions(path):
    elf = ELFFile(io.BytesIO(path.read_bytes()))
    assert elf.header.e_machine == 'EM_ARM' and elf.elfclass == 32 and elf.little_endian
    symbols = elf.get_section_by_name('.symtab')
    for sym in symbols.iter_symbols():
        section_id, size, start = sym['st_shndx'], sym['st_size'], sym['st_value']
        if sym['st_info']['type'] != 'STT_FUNC' or not isinstance(section_id, int) or size < 28 or start & 1:
            continue
        section = elf.get_section(section_id)
        data = section.data()[start:start + size]
        relocs = []
        for s in elf.iter_sections():
            if s['sh_type'] in ('SHT_REL', 'SHT_RELA') and s['sh_info'] == section_id:
                for r in s.iter_relocations():
                    if start <= r['r_offset'] < start + size:
                        relocs.append({'offset': r['r_offset'] - start, 'type': r['r_info_type']})
        # Mapping symbols separate code from embedded constants.
        maps = sorted((s['st_value'], s.name[:2]) for s in symbols.iter_symbols()
                      if s['st_shndx'] == section_id and s.name.startswith(('$a', '$t', '$d')))
        yield {'name': sym.name, 'data': data, 'relocations': relocs,
               'mapping_symbols': maps, 'section_offset': start}


def masked_matches(raw, f):
    data, mask = f['data'], bytearray(b'\x01' * len(f['data']))
    # We conservatively mask whole relocation words, including branch opcode.
    # The candidate retains the complete relocation list for manual inspection.
    for r in f['relocations']:
        mask[r['offset']:r['offset'] + 4] = b'\x00' * min(4, len(mask) - r['offset'])
    runs, start = [], None
    for i, val in enumerate(mask + b'\x00'):
        if val and start is None:
            start = i
        elif not val and start is not None:
            runs.append((start, data[start:i])); start = None
    if not runs or sum(mask) < 24:
        return []
    anchor_offset, anchor = max(runs, key=lambda x: len(x[1]))
    if len(anchor) < 16:
        return []
    result, pos = [], 0
    while True:
        found = raw.find(anchor, pos)
        if found < 0:
            break
        offset, pos = found - anchor_offset, found + 1
        if offset >= 0 and offset + len(data) <= len(raw) and (offset + BASE) % 4 == 0:
            if all(not mask[k] or raw[offset + k] == value for k, value in enumerate(data)):
                result.append({'address': hex(BASE + offset), 'unmasked_bytes': sum(mask),
                               'body_bytes': len(data), 'confidence': 0.90 if not f['relocations'] else 0.80,
                               'status': 'candidate_full_body_bytes_except_relocations',
                               'relocation_targets_verified': not bool(f['relocations'])})
    return result


def tokens(data, address):
    md = Cs(CS_ARCH_ARM, CS_MODE_ARM | CS_MODE_LITTLE_ENDIAN)
    md.detail = True
    result = []
    for ins in md.disasm(data, address):
        values = []
        for op in ins.operands:
            if op.type == ARM_OP_REG:
                values.append(ins.reg_name(op.reg))
            elif op.type == ARM_OP_IMM:
                values.append('target' if ins.mnemonic.startswith(('b', 'cb')) and ins.mnemonic not in ('bic', 'bics') else str(op.imm))
            elif op.type == ARM_OP_MEM:
                values.append('pc-literal' if op.mem.base == ARM_REG_PC else
                              f'{ins.reg_name(op.mem.base)}:{ins.reg_name(op.mem.index)}:{op.mem.disp}')
        result.append(ins.mnemonic + ':' + ','.join(values))
    return result


def survey(raw, bases):
    md = Cs(CS_ARCH_ARM, CS_MODE_ARM | CS_MODE_LITTLE_ENDIAN)
    md.detail = True
    base_map = sorted((r['base'], r['name']) for r in bases)
    refs, edges, cpu = [], [], []
    for addr in range(CODE_START, min(CODE_END, BASE + len(raw)) - 3, 4):
        offset = addr - BASE
        word = struct.unpack_from('<I', raw, offset)[0]
        # Only ordinary ARM condition fields; unconditional space is not ARM BL.
        if word >> 28 < 15 and (word & 0x0f000000) == 0x0b000000:
            delta = (word & 0xffffff) << 2
            if delta & 0x2000000:
                delta -= 0x4000000
            target = addr + 8 + delta
            if CODE_START <= target < CODE_END:
                edges.append((addr, target))
        # PC-relative immediate LDR word: P=1, W=0, L=1, Rn=PC.
        if word >> 28 < 15 and (word & 0x0f7f0000) == 0x051f0000:
            literal = addr + 8 + ((word & 0xfff) if word & 0x800000 else -(word & 0xfff))
            lo = literal - BASE
            if not 0 <= lo <= len(raw) - 4:
                continue
            value = struct.unpack_from('<I', raw, lo)[0]
            block = next(((b, n) for b, n in reversed(base_map) if b <= value < b + 0x400), None)
            if block:
                ins = next(md.disasm(raw[offset:offset + 4], addr), None)
                refs.append({'instruction': hex(addr), 'literal_address': hex(literal),
                             'value': hex(value), 'block': block[1], 'block_offset': value - block[0],
                             'assembly': '' if ins is None else f'{ins.mnemonic} {ins.op_str}',
                             'status': 'literal_reference_candidate', 'confidence': 0.65})
        if (word & 0x0f000010) == 0x0e000010 and (word >> 8) & 15 == 15:
            ins = next(md.disasm(raw[offset:offset + 4], addr), None)
            if ins and ins.mnemonic in ('mcr', 'mrc'):
                cpu.append({'address': hex(addr), 'assembly': f'{ins.mnemonic} {ins.op_str}',
                            'status': 'CP15_candidate_in_linear_ARM_survey'})
    # Raw linear BL edges do not establish function boundaries. Grouping uses
    # target addresses as candidate entries, with bounded windows only.
    entries = sorted(set(t for _, t in edges))
    functions = []
    for i, entry in enumerate(entries):
        end = min(entry + 256, entries[i + 1] if i + 1 < len(entries) else CODE_END)
        functions.append({'entry': entry, 'end': end,
                          'tokens': tokens(raw[entry - BASE:end - BASE], entry)})
    return refs, edges, cpu, functions


def follow_literal(raw, ref, maximum=12):
    """Straight-line constant propagation; stop at any control transfer.

    No MMIO values are guessed. All destinations reported by Capstone are
    invalidated, so loading through a known pointer cannot invent a new one.
    Conditional accesses remain path candidates, never executed observations.
    """
    md = Cs(CS_ARCH_ARM, CS_MODE_ARM | CS_MODE_LITTLE_ENDIAN)
    md.detail = True
    start = int(ref['instruction'], 16)
    seed = next(md.disasm(raw[start - BASE:start - BASE + 4], start))
    constants = {seed.operands[0].reg: int(ref['value'], 16)}
    result = []
    data = raw[start + 4 - BASE:start + 4 - BASE + maximum * 4]
    for ins in md.disasm(data, start + 4):
        if ins.group(1) or ins.group(2) or ins.group(3) or ins.group(4):
            break
        read, written = ins.regs_access()
        for op in ins.operands:
            if op.type == ARM_OP_MEM and op.mem.base in constants and not op.mem.index:
                address = (constants[op.mem.base] + op.mem.disp) & 0xffffffff
                if 0x01c00000 <= address < 0x02000000 and ins.mnemonic.startswith(('ldr', 'str')):
                    result.append({'instruction': hex(ins.address), 'address': hex(address),
                                   'operation': 'read' if ins.mnemonic.startswith('ldr') else 'write',
                                   'assembly': f'{ins.mnemonic} {ins.op_str}',
                                   'status': 'straight_line_path_candidate_not_execution', 'confidence': 0.75})
        new = {}
        ops = ins.operands
        if ins.mnemonic in ('add', 'sub') and len(ops) == 3 and ops[0].type == ARM_OP_REG and ops[1].type == ARM_OP_REG and ops[2].type == ARM_OP_IMM and ops[1].reg in constants:
            new[ops[0].reg] = (constants[ops[1].reg] + (ops[2].imm if ins.mnemonic == 'add' else -ops[2].imm)) & 0xffffffff
        if ins.mnemonic == 'mov' and len(ops) == 2 and ops[0].type == ARM_OP_REG:
            if ops[1].type == ARM_OP_IMM:
                new[ops[0].reg] = ops[1].imm & 0xffffffff
            elif ops[1].type == ARM_OP_REG and ops[1].reg in constants:
                new[ops[0].reg] = constants[ops[1].reg]
        for reg in written:
            constants.pop(reg, None)
        # Conditional assignments cannot replace a known constant on both paths.
        if ins.cc == 15:  # ARM_CC_AL
            constants.update(new)
        if not constants:
            break
    return result


def compare(raw, objects, funcs):
    all_matches, summaries = [], []
    for path, kind, source in objects:
        count, matched = 0, 0
        for f in elf_functions(path):
            count += 1
            exact = masked_matches(raw, f)
            # Similarity is only a ranking aid; never a naming proof. Require
            # >=12 instructions and >=16 shared tokens, not a short prologue.
            maps = f['mapping_symbols']
            code_end = min((a - f['section_offset'] for a, mode in maps
                            if mode != '$a' and f['section_offset'] < a < f['section_offset'] + len(f['data'])),
                           default=len(f['data']))
            ft = tokens(f['data'][:code_end], 0)
            ranked = []
            if not exact and len(ft) >= 12:
                for candidate in funcs:
                    ct = candidate['tokens']
                    if not 0.5 <= len(ct) / len(ft) <= 2:
                        continue
                    sm = difflib.SequenceMatcher(None, ft, ct, autojunk=False)
                    if sm.quick_ratio() < 0.70:
                        continue
                    blocks = sm.get_matching_blocks()
                    shared = sum(b.size for b in blocks)
                    ratio = sm.ratio()
                    if ratio >= 0.70 and shared >= 16:
                        ranked.append({'address': hex(candidate['entry']), 'similarity': round(ratio, 5),
                                       'shared_instruction_tokens': shared, 'confidence': min(0.60, round(ratio * 0.6, 3)),
                                       'status': 'hypothesis_normalized_instruction_similarity',
                                       'boundary': 'unverified direct-BL target and bounded window'})
                ranked = sorted(ranked, key=lambda x: x['similarity'], reverse=True)[:3]
            if exact or ranked:
                matched += 1
                all_matches.append({'reference': source, 'origin': kind, 'symbol': f['name'],
                                    'object_sha256': digest(path.read_bytes()), 'function_sha256': digest(f['data']),
                                    'relocations': f['relocations'], 'exact_masked': exact, 'similarity_candidates': ranked})
        summaries.append({'reference': source, 'origin': kind, 'eligible_functions': count,
                          'functions_with_candidates': matched, 'object_sha256': digest(path.read_bytes())})
    return all_matches, summaries


def validate_watchdog(raw):
    """Execute two newly located helpers against inert RAM register shadows."""
    from unicorn import Uc, UC_ARCH_ARM, UC_MODE_ARM, UC_MODE_LITTLE_ENDIAN
    from unicorn import UC_PROT_READ, UC_PROT_WRITE, UC_PROT_EXEC, UC_HOOK_MEM_READ, UC_HOOK_MEM_WRITE, UC_MEM_READ
    from unicorn.arm_const import UC_CPU_ARM_926, UC_ARM_REG_CPSR, UC_ARM_REG_LR, UC_ARM_REG_R0, UC_ARM_REG_PC
    result = []
    seeds = [0, 1, 0xffffffff, 0x5555aaaa, 0xaaaaaaaa, 0x12345678, 0x14af, 0x80000000]
    for entry, register, mask, name in ((0x800085c4, 0x01c20cb0, 0x14af, 'RE_WatchdogKeyedControlUpdate'),
                                        (0x800085e0, 0x01c20cb8, 1, 'RE_WatchdogModeEnable')):
        cases = []
        for seed in seeds:
            uc = Uc(UC_ARCH_ARM, UC_MODE_ARM | UC_MODE_LITTLE_ENDIAN)
            uc.ctl_set_cpu_model(UC_CPU_ARM_926)
            uc.mem_map(0x80008000, 0x1000, UC_PROT_READ | UC_PROT_WRITE)
            uc.mem_write(0x80008000, raw[0x80008000 - BASE:0x80009000 - BASE])
            uc.mem_protect(0x80008000, 0x1000, UC_PROT_READ | UC_PROT_EXEC)
            uc.mem_map(0x01c20000, 0x1000, UC_PROT_READ | UC_PROT_WRITE)
            uc.mem_map(0x10000000, 0x1000, UC_PROT_READ | UC_PROT_EXEC)
            uc.mem_write(register, struct.pack('<I', seed))
            accesses = []
            def memory_hook(emu, access, address, size, value, user):
                if 0x80008000 <= address < 0x80009000:
                    assert access == UC_MEM_READ
                    return
                assert address == register and size == 4, (hex(address), size)
                accesses.append((access, address, value))
            uc.hook_add(UC_HOOK_MEM_READ | UC_HOOK_MEM_WRITE, memory_hook)
            uc.reg_write(UC_ARM_REG_CPSR, 0x13)
            uc.reg_write(UC_ARM_REG_LR, 0x10000000)
            uc.reg_write(UC_ARM_REG_R0, 0xa5a5a5a5)
            uc.emu_start(entry, 0x10000000, count=30)
            actual = struct.unpack('<I', uc.mem_read(register, 4))[0]
            assert uc.reg_read(UC_ARM_REG_PC) == 0x10000000
            assert actual == seed | mask and len(accesses) == 2, (hex(entry), hex(seed), actual, accesses)
            cases.append({'before': seed, 'after': actual})
        end = 0x800085dc if entry == 0x800085c4 else 0x800085f4
        md = Cs(CS_ARCH_ARM, CS_MODE_ARM)
        result.append({'address': hex(entry), 'name': name, 'register': hex(register), 'or_mask': hex(mask),
                       'cpu': 'UC_CPU_ARM_926', 'passed': len(cases), 'cases': cases,
                       'status': 'confirmed_bounded_original_ARM926_execution',
                       'assembly': [f'{i.address:08x} {i.mnemonic} {i.op_str}' for i in
                                    md.disasm(raw[entry - BASE:end - BASE], entry)],
                       'limit': 'Inert RAM shadows, not a watchdog model; no real reset/feed/timeout observed.'})
    return result


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--references', type=Path, required=True)
    ap.add_argument('--zig', type=Path, required=True)
    ap.add_argument('--input', action='append', required=True, metavar='VERSION=PATH')
    ap.add_argument('--sound-evidence', type=Path)
    ap.add_argument('--out-dir', type=Path, required=True)
    args = ap.parse_args()
    root, out = args.references.resolve(), args.out_dir.resolve()
    out.mkdir(parents=True, exist_ok=True)
    inv = inventory(root)
    regs = register_map(root)
    write(out / 'reference-lock.json', {'schema': 'ys4470.reference-lock.v1', 'repositories': inv})
    write(out / 'reference-register-map.json', regs)
    objects, build = compile_sources(root, args.zig.resolve(), out)
    for module in ('pwm', 'gpio', 'timer', 'uart', 'clock', 'interrupt', 'cache', 'dma'):
        p = root / f'nminaylov__F1C100s_info/LIB_RE/sys_{module}.o'
        if p.exists():
            objects.append((p, 'upstream_prebuilt_unlicensed_sdk_object', f'nminaylov/F1C100s_info:LIB_RE/sys_{module}.o'))
    sound = json.loads(args.sound_evidence.read_text()) if args.sound_evidence else None
    versions = []
    for inp in args.input:
        version, path = inp.split('=', 1)
        raw = Path(path).read_bytes()
        sha = digest(raw)
        assert sha == KNOWN_HASHES[version], (version, sha)
        refs, edges, cpu, funcs = survey(raw, regs['bases'])
        for ref in refs:
            ref['following_access_candidates'] = follow_literal(raw, ref)
        matches, summaries = compare(raw, objects, funcs)
        graph = {'schema': 'ys4470.arm-linear-call-candidates.v1', 'input_sha256': sha,
                 'survey_start': hex(CODE_START), 'survey_end_exclusive': hex(CODE_END),
                 'status': 'linear ARM hypotheses; embedded data may decode as calls; no Thumb/indirect coverage',
                 'edges': [{'call_site': hex(a), 'target_candidate': hex(t)} for a, t in edges]}
        graph_bytes = json.dumps(graph, separators=(',', ':')).encode()
        (out / f'{version}-call-candidates.json.gz').write_bytes(gzip.compress(graph_bytes, mtime=0))
        watchdog = validate_watchdog(raw)
        approved = []
        if sound:
            tested = next(v for v in sound['versions'] if v['version'] == version)
            assert tested['input_sha256'] == sha and tested['failed'] == 0 and tested['gate_cases_passed'] == 396
            for addr, name in ((0x8000302c, 'RE_PinMuxPull'), (0x800060d0, 'RE_SoundPWMOutput'),
                               (0x80006e4c, 'RE_SoundControlGate'), (0x80042d40, 'RE_PWMConfigure')):
                approved.append({'address': hex(addr), 'name': name, 'confidence': 1.0,
                                 'proof': 'prior_bounded_original_ARM926_execution',
                                 'evidence': 'evidence/2026-11-07-sound-pwm-path.json',
                                 'guard_bytes': 64, 'guard_sha256': digest(raw[addr - BASE:addr - BASE + 64])})
        for experiment in watchdog:
            addr = int(experiment['address'], 16)
            approved.append({'address': hex(addr), 'name': experiment['name'], 'confidence': 1.0,
                             'proof': 'bounded_original_ARM926_execution',
                             'evidence': 'evidence/2026-11-07-f1c100s-reference/reference-analysis.json',
                             'guard_bytes': 64, 'guard_sha256': digest(raw[addr - BASE:addr - BASE + 64])})
        versions.append({'version': version, 'input_sha256': sha, 'reference_function_comparisons': summaries,
                         'matches': matches, 'mmio_literal_candidates': refs, 'cp15_candidates': cpu,
                         'direct_bl_candidate_count': len(edges), 'candidate_entry_count': len(funcs),
                         'call_graph': {'file': f'{version}-call-candidates.json.gz', 'uncompressed_sha256': digest(graph_bytes)},
                         'watchdog_experiments': watchdog, 'approved_labels': approved})
        print(version, 'MMIO literals', len(refs), 'call edges', len(edges), 'reference matches', len(matches))
    write(out / 'reference-analysis.json', {'schema': 'ys4470.f1c100s.reference-analysis.v1', 'build': build,
          'survey': {'start': hex(CODE_START), 'end_exclusive': hex(CODE_END), 'mode': 'ARM aligned linear candidates'},
          'versions': versions, 'limits': ['No physical device access; no reference firmware is loaded.',
          'Masked relocations are not verified semantic equivalence; candidates never authorize labels.',
          'Normalized candidates ignore branch targets/PC literal displacement but do not prove literal values or callee identity.',
          'Full Thumb/indirect calls, state machines, scheduler and whole-firmware function recovery remain open.',
          'Approved RE labels require separate original-byte execution evidence and exact image/window guards.']})


if __name__ == '__main__':
    main()
