"""Static/isolated FMV tests. Unicorn executes bounded byte-reader/wrapper code,
not rayne2.exe as a process; no graphics, Bink playback, or game initialization.
"""
import argparse
import csv
import json
import struct
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent / '_deps'))
from build_fmv_probe import ROOT, OUT, TEXTS, cues, sha
from x86_iat_xrefs import Pe32
from unicorn import Uc, UC_ARCH_X86, UC_MODE_32, UC_HOOK_CODE
from unicorn.x86_const import UC_X86_REG_EAX, UC_X86_REG_ECX, UC_X86_REG_EIP, UC_X86_REG_ESP, UC_X86_REG_EBP

MAP_ROWS = list(csv.DictReader((ROOT / '_cn_project/build/full_translation/character_map.tsv').open(encoding='utf-8-sig'), delimiter='\t'))
DECODE = {bytes.fromhex(r['carrier']): r['character'] for r in MAP_ROWS}

def decode(blob):
    result = ''
    i = 0
    while i < len(blob):
        if blob[i] < 128:
            result += chr(blob[i]); i += 1
        else:
            pair = blob[i:i+2]
            if pair not in DECODE:
                raise ValueError(f'invalid carrier at byte {i}: {pair.hex().upper()}')
            result += DECODE[pair]; i += 2
    return result

class NativeFixture:
    STACK = 0x10000000
    FONT = 0x11000000
    INPUT = 0x11008000
    OUTPUT = 0x11009000
    STOP = 0x20000000
    WIDTH = 0x20000020
    GETC = 0x20000040

    def __init__(self):
        self.uc = Uc(UC_ARCH_X86, UC_MODE_32)
        p = Pe32(ROOT / 'rayne2.exe')
        for address, size in [(0x4E5000, 0x2000), (0x64C000, 0x1000), (0x69A000, 0x2000)]:
            self.uc.mem_map(address, size)
            offset = p.va_to_offset(address)
            self.uc.mem_write(address, p.data[offset:offset+size])
        for address, size in [(self.STACK, 0x10000), (self.FONT, 0x10000), (self.STOP, 0x1000)]:
            self.uc.mem_map(address, size)
        # The real bit-font virtual width method sums each byte's record width.
        # Emulate that boundary with exact v12 FNT widths and per-frame scale.
        self.widths = {}
        for line in (ROOT / '_cn_project/build/full_translation/assets/DATA/GOTHICTITLE_RU.FNT').read_bytes().splitlines():
            if len(line) > 2 and line[1:2] == b':':
                self.widths[line[0]] = int(line[2:].strip().split(b',')[2])
        self.uc.mem_write(self.FONT, struct.pack('<I', self.FONT + 0x3000))
        self.uc.mem_write(self.FONT + 0x3004, struct.pack('<I', self.WIDTH))
        # fld dword [scratch]; ret 4: preserves the x87 return convention.
        self.uc.mem_write(self.WIDTH, b'\xd9\x05' + struct.pack('<I', self.FONT+0x4000) + b'\xc2\x04\x00')
        self.uc.mem_write(self.GETC, b'\xc3')
        # Local x87 float-to-int helper, balanced stack; no host CRT calls.
        self.uc.mem_write(0x69B920, bytes.fromhex('83EC04DB1C2458C3'))
        self.scale = 1.0
        self.stream = b''
        self.position = 0
        self.uc.hook_add(UC_HOOK_CODE, self.hook)

    def u32(self, address):
        return struct.unpack('<I', self.uc.mem_read(address,4))[0]

    def cstr(self, address):
        result = bytearray()
        for i in range(4096):
            value = self.uc.mem_read(address+i,1)[0]
            if not value:
                return bytes(result)
            result.append(value)
        raise AssertionError('Unterminated native string')

    def ret(self, value):
        sp = self.uc.reg_read(UC_X86_REG_ESP)
        self.uc.reg_write(UC_X86_REG_EAX, value & 0xFFFFFFFF)
        self.uc.reg_write(UC_X86_REG_EIP, self.u32(sp))
        self.uc.reg_write(UC_X86_REG_ESP, sp+4)

    def hook(self, uc, address, size, _):
        sp = uc.reg_read(UC_X86_REG_ESP)
        if address == self.WIDTH:
            value = sum(self.widths.get(b,0) for b in self.cstr(self.u32(sp+4))) * self.scale
            uc.mem_write(self.FONT+0x4000, struct.pack('<f',value))
        elif address == 0x69A800:
            dst,val,count = [self.u32(sp+i) for i in (4,8,12)]
            assert count <= 4096
            uc.mem_write(dst, bytes([val & 255])*count)
            self.ret(dst)
        elif address == 0x69AF41:
            # C-locale isspace. Carrier bytes are deliberately all non-space.
            self.ret(int(self.u32(sp+4) in (9,10,11,12,13,32)))
        elif address == self.GETC:
            if self.position == len(self.stream):
                self.ret(-1)
            else:
                value = self.stream[self.position]
                self.position += 1
                self.ret(value)

    def call(self, address, args):
        sp = self.STACK+0xF000
        self.uc.mem_write(sp, struct.pack('<'+'I'*(len(args)+1), self.STOP, *args))
        self.uc.reg_write(UC_X86_REG_ESP,sp)
        self.uc.reg_write(UC_X86_REG_EBP,0)
        self.uc.reg_write(UC_X86_REG_ECX,self.FONT)
        self.uc.emu_start(address,self.STOP,count=1000000)
        assert self.uc.reg_read(UC_X86_REG_EIP) == self.STOP, 'Native fixture timed out'
        assert self.uc.reg_read(UC_X86_REG_ESP) == sp+4+len(args)*4
        return self.uc.reg_read(UC_X86_REG_EAX)

    def read_lines(self, blob):
        self.stream, self.position = blob, 0
        self.uc.mem_write(self.FONT+0x3004,struct.pack('<I',self.GETC))
        lines=[]
        while self.position < len(blob):
            result = self.call(0x64CE30,[self.OUTPUT,1023])
            assert result < 1023
            lines.append(self.cstr(self.OUTPUT))
        self.uc.mem_write(self.FONT+0x3004,struct.pack('<I',self.WIDTH))
        return lines

    def wrap(self,text,width,height):
        self.scale = height/480.0*0.5
        self.uc.mem_write(self.INPUT,text+b'\0')
        self.uc.mem_write(self.OUTPUT,b'\xCC'*400)
        count=self.call(0x4E5A90,[self.INPUT,self.OUTPUT,5,64,width])
        assert 0 < count <= 5
        assert bytes(self.uc.mem_read(self.OUTPUT+320,80)) == b'\xCC'*80
        return [self.cstr(self.OUTPUT+i*64) for i in range(count)]

def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--baseline',action='store_true')
    args=parser.parse_args()
    original=cues((OUT/'original/A1S01P01_RU.srt').read_bytes())
    if args.baseline:
        for number,_,text in original:
            try:
                decode(text)
            except ValueError as error:
                print(f'BASELINE_FAIL cue={number.decode()} {error}')
                return 1
        raise AssertionError('Expected invalid baseline carrier')
    manifest=json.loads((OUT/'manifest.json').read_text(encoding='utf-8'))
    for name,digest in manifest['required_files'].items():
        assert sha(ROOT/name)==digest
    target=OUT/'payload/video/A1S01P01_RU.srt'
    data=target.read_bytes()
    assert sha(target)==manifest['payload_sha256']
    modified=cues(data)
    assert [(n,t) for n,t,_ in original]==[(n,t) for n,t,_ in modified]
    assert [decode(text) for _,_,text in modified]==TEXTS
    native=NativeFixture()
    assert b'\n'.join(native.read_lines(data))+b'\n' == data.replace(b'\r\n',b'\n')
    scenarios=[(640,480),(800,600),(1280,1024),(1920,1080),(2560,1440),(3840,2160),(7680,4320)]
    for _,_,text in modified:
        for width,height in scenarios:
            lines=native.wrap(text,width,height)
            # Ignore only whitespace discarded by the native wrapping routine.
            assert ''.join(decode(line) for line in lines).replace(' ','') == decode(text).replace(' ','')
    # Negative control: a dangling first byte must not validate as a character.
    try: decode(b'\x81')
    except ValueError: pass
    else: raise AssertionError('Dangling-byte control unexpectedly passed')
    print('MODIFIED_PASS cues=6 timing=exact carrier_roundtrip=exact glyphs=covered')
    print('NATIVE_FIXTURE_PASS raw_reader=exact wrap_cases=42 split_pairs=0 buffer_overruns=0')
    print('GAME_NOT_LAUNCHED visual_and_audio_confirmation=pending')
    return 0

if __name__=='__main__':
    sys.exit(main())
