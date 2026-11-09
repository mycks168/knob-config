#!/usr/bin/env python3
"""x86_64 Mach-O を静的解析する簡易ツール（実行はしない）。

使い方:
  macho.py BIN syms PATTERN       シンボル一覧（正規表現で絞り込み）
  macho.py BIN dis SYMBOL         関数を逆アセンブル（スタブ呼び出しを名前解決）
  macho.py BIN xref TARGET        TARGET（シンボル名）を call している関数一覧
"""
import re
import struct
import sys

from capstone import CS_ARCH_X86, CS_MODE_64, Cs


class MachO:
    """Mach-O のセグメント・シンボル・スタブ情報を保持する。"""

    def __init__(self, path):
        """ファイルを読み込んでロードコマンドを解析する。"""
        self.d = open(path, 'rb').read()
        d = self.d
        magic, _, _, _, ncmds, _, _, _ = struct.unpack_from('<IiiIIIII', d, 0)
        assert magic == 0xfeedfacf, 'x86_64 Mach-O ではない'
        off = 32
        self.sections = []
        symoff = nsyms = stroff = 0
        indoff = nind = 0
        for _ in range(ncmds):
            cmd, size = struct.unpack_from('<II', d, off)
            if cmd == 0x19:  # LC_SEGMENT_64
                nsect = struct.unpack_from('<I', d, off + 64)[0]
                so = off + 72
                for _ in range(nsect):
                    sect = d[so:so + 16].split(b'\0')[0].decode()
                    seg = d[so + 16:so + 32].split(b'\0')[0].decode()
                    addr, sz, foff = struct.unpack_from('<QQI', d, so + 32)
                    reserved1, reserved2 = struct.unpack_from('<II', d, so + 68)
                    self.sections.append(dict(seg=seg, sect=sect, addr=addr, size=sz,
                                              off=foff, r1=reserved1, r2=reserved2))
                    so += 80
            elif cmd == 0x2:  # LC_SYMTAB
                symoff, nsyms, stroff, _ = struct.unpack_from('<IIII', d, off + 8)
            elif cmd == 0xb:  # LC_DYSYMTAB
                indoff, nind = struct.unpack_from('<II', d, off + 56)
            off += size
        # シンボル表
        self.syms = []
        for i in range(nsyms):
            strx, ntype, sect, _, val = struct.unpack_from('<IBBhQ', d, symoff + i * 16)
            name = d[stroff + strx:d.index(b'\0', stroff + strx)].decode('latin1')
            self.syms.append((name, ntype, sect, val))
        self.addr2name = {v: n for n, t, s, v in self.syms if s != 0 and v}
        self.name2addr = {n: v for n, t, s, v in self.syms if s != 0 and v}
        # スタブ（外部関数呼び出し口）の名前解決
        ind = [struct.unpack_from('<I', d, indoff + i * 4)[0] for i in range(nind)]
        for s in self.sections:
            if s['sect'] == '__stubs' and s['r2']:
                for k in range(s['size'] // s['r2']):
                    idx = ind[s['r1'] + k]
                    if idx < len(self.syms):
                        self.addr2name[s['addr'] + k * s['r2']] = self.syms[idx][0] + '@stub'
        self.text = next(s for s in self.sections if s['sect'] == '__text')
        self.funcs = sorted(v for n, t, s, v in self.syms
                            if s == self.text_index() and v)

    def text_index(self):
        """__text セクションの番号（1始まり）を返す。"""
        return self.sections.index(self.text) + 1

    def read_addr(self, addr, n):
        """仮想アドレスから n バイト読む。"""
        for s in self.sections:
            if s['addr'] <= addr < s['addr'] + s['size'] and s['off']:
                o = s['off'] + addr - s['addr']
                return self.d[o:o + n]
        return b''

    def cstring(self, addr):
        """仮想アドレスの C 文字列を読む（無ければ None）。"""
        b = self.read_addr(addr, 200)
        if not b:
            return None
        b = b.split(b'\0')[0]
        if len(b) >= 2 and all(32 <= c < 127 for c in b):
            return b.decode()
        return None

    def func_range(self, start):
        """関数の開始アドレスから終了アドレス（次の関数の先頭）を求める。"""
        import bisect
        i = bisect.bisect_right(self.funcs, start)
        end = self.funcs[i] if i < len(self.funcs) else self.text['addr'] + self.text['size']
        return start, end

    def disasm(self, start):
        """関数を逆アセンブルして命令列を返す。"""
        s, e = self.func_range(start)
        md = Cs(CS_ARCH_X86, CS_MODE_64)
        return list(md.disasm(self.read_addr(s, e - s), s))

    def annotate(self, ins):
        """命令に呼び出し先名や参照文字列の注釈を付ける。"""
        note = ''
        m = re.search(r'0x([0-9a-f]+)', ins.op_str)
        if ins.mnemonic.startswith(('call', 'j')) and m:
            note = self.addr2name.get(int(m.group(1), 16), '')
        m = re.search(r'\[rip ([+-]) 0x([0-9a-f]+)\]', ins.op_str)
        if m:
            tgt = ins.address + ins.size + (1 if m.group(1) == '+' else -1) * int(m.group(2), 16)
            note = self.addr2name.get(tgt, '') or (repr(self.cstring(tgt)) if self.cstring(tgt) else hex(tgt))
        return note


def main():
    """コマンドライン引数に応じて処理する。"""
    mo = MachO(sys.argv[1])
    mode, arg = sys.argv[2], sys.argv[3]
    if mode == 'syms':
        for n, t, s, v in mo.syms:
            if re.search(arg, n):
                print(hex(v), n)
    elif mode == 'dis':
        addr = int(arg, 16) if arg.startswith('0x') else mo.name2addr[arg]
        for ins in mo.disasm(addr):
            note = mo.annotate(ins)
            print(f'{ins.address:x}: {ins.mnemonic:6} {ins.op_str}' + (f'   ; {note}' if note else ''))
    elif mode == 'xref':
        md = Cs(CS_ARCH_X86, CS_MODE_64)
        targets = {a for a, n in mo.addr2name.items() if re.search(arg, n)}
        t = mo.text
        hits = set()
        for ins in md.disasm(mo.read_addr(t['addr'], t['size']), t['addr']):
            if ins.mnemonic == 'call':
                m = re.match(r'0x([0-9a-f]+)$', ins.op_str)
                if m and int(m.group(1), 16) in targets:
                    import bisect
                    f = mo.funcs[bisect.bisect_right(mo.funcs, ins.address) - 1]
                    hits.add((f, mo.addr2name.get(f, '?')))
        for f, n in sorted(hits):
            print(hex(f), n)


if __name__ == '__main__':
    main()
