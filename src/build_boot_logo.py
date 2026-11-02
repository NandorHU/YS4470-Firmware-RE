"""Keep selected artwork pixels; encode the bootloader's raw RGB565 BMP container."""
from pathlib import Path
import hashlib,struct,json
HERE=Path(__file__).resolve().parent;FACTORY=HERE.parent/'Project_March_V3.8_V02.26.6'
BOOT_HASH='cdecb2aa58beb830c0efceb77e9488dc91de328df64341c6191df8d042a6d132'
LOGO_HASH='8aa1fa72488b181e6059d2fa5b9b4ad357c4a38c9305e9babd9840b9f1882fc8'
def sha(b):return hashlib.sha256(b).hexdigest()
def checksum(data):
 n=struct.unpack_from('<I',data,16)[0];assert n==len(data) and n%4==0
 b=bytearray(data);struct.pack_into('<I',b,12,0x5f0a6c39)
 return sum(struct.unpack('<%dI'%(n//4),b))&0xffffffff
def build():
 original_boot=(FACTORY/'boot0_rgb480x854.bin').read_bytes();original_logo=(FACTORY/'logo.bin').read_bytes()
 assert sha(original_boot)==BOOT_HASH and sha(original_logo)==LOGO_HASH
 assert checksum(original_boot)==struct.unpack_from('<I',original_boot,12)[0]
 pixels=(HERE/'selected-tile-120x304.rgb565le').read_bytes();assert len(pixels)==120*304*2
 header=bytearray(original_logo[:40])
 for off in [0x1a,0x22]:struct.pack_into('<HH',header,off,120,304)
 length=(40+len(pixels)+511)//512*512;struct.pack_into('<I',header,16,length)
 logo=bytes(header)+pixels+bytes(length-40-len(pixels))
 assert len(logo)<=0x4a000 and logo[4:12]==b'eGON.BMP'
 # The existing logo checksum field is opaque. The actual loader never reads it;
 # preserve it rather than inventing a format/checksum algorithm.
 boot=bytearray(original_boot);edits=[]
 for off,old,new,why in [(0x45c,0xe1a010a0,0xe2401014,'native y=854-image_height-20'),(0x464,0xe1a000a0,0xe3a00014,'native x=20')]:
  assert struct.unpack_from('<I',boot,off)[0]==old
  struct.pack_into('<I',boot,off,new);edits.append(dict(offset=hex(off),original=hex(old),modified=hex(new),purpose=why))
 struct.pack_into('<I',boot,12,checksum(boot));assert checksum(boot)==struct.unpack_from('<I',boot,12)[0]
 assert len(boot)==len(original_boot)
 (HERE/'boot0-bottom-right-OFFLINE.bin').write_bytes(boot);(HERE/'logo-bottom-right-OFFLINE.bin').write_bytes(logo)
 r=dict(status='OFFLINE; not flashed; bootloader positioning change needs separate physical approval',source_art='selected-original.png',source_sha256=sha((HERE/'selected-original.png').read_bytes()),boot_sha256=sha(boot),logo_sha256=sha(logo),boot_length=len(boot),logo_length=len(logo),logo_capacity=0x4a000,logical_display=[854,480],logical_tile=[304,120],logical_tile_origin=[530,340],native_bitmap=[120,304],native_origin=[20,530],pixel_offset=40,format='RGB565 little endian, row-major',boot_checksum=hex(struct.unpack_from('<I',boot,12)[0]),boot_edits=edits,logo_checksum_note='Opaque original field preserved; not read by the emulated factory loader path')
 (HERE/'manifest.json').write_text(json.dumps(r,indent=2));return bytes(boot),logo,r
if __name__=='__main__':
 _,_,r=build();print(json.dumps(r,indent=2))
