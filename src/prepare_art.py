"""Deterministic resize/encoding of supplied artwork; no redraw or device access."""
from pathlib import Path
import subprocess,hashlib,json
HERE=Path(__file__).resolve().parent
assert hashlib.sha256((HERE/'selected-original.png').read_bytes()).hexdigest()=='c5f82b1d523d49005737c8a1aa3c6f065319aa54fe570f84335fd1b965f20058'
def ff(*args):
    subprocess.run(['C:/ffmpeg/bin/ffmpeg.exe','-hide_banner','-loglevel','error','-y',*map(str,args)],check=True,cwd=HERE)
ff('-i','selected-original.png','-vf','scale=854:480:flags=lanczos','-frames:v','1','selected-preview-854x480.png')
ff('-i','selected-preview-854x480.png','-frames:v','1','-pix_fmt','rgb565le','-f','rawvideo','selected-full-854x480.rgb565le')
ff('-i','selected-preview-854x480.png','-vf','crop=304:120:530:340,transpose=clock','-frames:v','1','-pix_fmt','rgb565le','-f','rawvideo','selected-tile-120x304.rgb565le')
data=(HERE/'selected-full-854x480.rgb565le').read_bytes()
inside=outside=0
for y in range(480):
    for x in range(854):
        p=(y*854+x)*2
        if data[p:p+2]!=b'\0\0':
            if 530<=x<834 and 340<=y<460:inside+=1
            else:outside+=1
assert outside==0, 'Artwork outside tile would be cropped'
(HERE/'art-bounds-check.json').write_text(json.dumps(dict(nonblack_pixels_inside=inside,nonblack_pixels_outside=outside,passed=True),indent=2))
print('PASS: all nonblack RGB565 artwork retained within bottom-right tile')
