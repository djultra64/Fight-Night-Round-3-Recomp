#!/usr/bin/env python3
"""Build native glyph overrides without touching originals. Work: djultra64.

RW4 xb2 icons: 128x128 BC2, 32x32 tiled blocks, big-endian 16-bit words.
Only replace the 16384 texture bytes; retain BIG offsets and RW4 metadata.
"""
import argparse, hashlib, json, math, struct
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
# Resource identities were verified by decoding each original icon, NOT guessed
# from the misleading PS-style filenames: x=A, t=B, c=X, s=Y.
SLOTS={'x':'south','t':'east','c':'west','s':'north','l1':'L1','l2':'L2','l3':'L3','r1':'R1','r2':'R2','r3':'R3','str':'menu','up':'up','dwn':'down','lft':'left','rht':'right','back':'back'}
FONT={'L':['100','100','100','100','111'],'R':['110','101','110','101','101'],
'Z':['111','001','010','100','111'],'S':['111','100','111','001','111'],
'1':['010','110','010','010','111'],'2':['110','001','010','100','111'],
'3':['110','001','010','001','110'],'+':['000','010','111','010','000'],'-':['000','000','111','000','000']}
def tiled_offset(x,y,width=32,pitch=16):
    aw=(width+31)&~31;b=(pitch>>2)+((pitch>>1)>>(pitch>>2))
    macro=((x>>5)+(y>>5)*(aw>>5))<<(b+7)
    micro=((x&7)+((y&6)<<2))<<b
    o=macro+((micro&~15)<<1)+(micro&15)+((y&8)<<(3+b))+((y&1)<<4)
    return (((o&~511)<<3)+((o&448)<<2)+(o&63)+((y&16)<<7)+(((((y&8)>>2)+(x>>3))&3)<<6))>>b

def arena_range(data,name):
    if data[:4]!=b'BIGF':raise ValueError('Expected BIGF')
    count=struct.unpack_from('>I',data,8)[0];pos=16
    for _ in range(count):
        offset,size=struct.unpack_from('>II',data,pos);end=data.index(0,pos+8)
        entry=data[pos+8:end].decode('ascii');pos=end+1
        if entry==name+'.arena':
            if size!=0x5028 or data[offset:offset+8]!=b'\x89RW4xb2\0':raise ValueError('Unsupported RW4 icon layout')
            return offset+0x1000,offset+0x5000
    raise ValueError('Missing arena')

def ps_alpha(slot,x,y):
    # Native icon uses the first 32x32 texel cell; preserve its placement/UVs.
    dx=x-15.5;dy=y-15.5
    if abs(dx)>8 or abs(dy)>8:return False
    if slot not in ('south','east','west','north'):
        if slot=='back':return any(3<max(abs(dx-ox),abs(dy-oy))<4.3 for ox,oy in ((-2,-1),(2,1)))
        if slot=='menu':return abs(dx)<6 and any(abs(dy-line)<.7 for line in (-4,0,4))
        # Two small 3x5 glyphs, each 1.5 texels per cell.
        width=(len(slot)*4-1)*1.5;cx=int((dx+width/2)/1.5);cy=int((dy+3.75)/1.5)
        if dx < -width/2 or dy < -3.75 or cx<0 or cy<0 or cy>=5:return False
        char,px=divmod(cx,4)
        return char<len(slot) and px<3 and FONT[slot[char]][cy][px]=='1'
    if slot=='south':return abs(abs(dx)-abs(dy))<1.25 and max(abs(dx),abs(dy))<5.5
    if slot=='east':return 4.0<math.hypot(dx,dy)<6.0
    if slot=='west':return 4.0<max(abs(dx),abs(dy))<6.0
    # Outline triangle (three segment distances).
    vertices=[(0,-6.5),(-6,5),(6,5)]
    for a,b in zip(vertices,vertices[1:]+vertices[:1]):
        vx=b[0]-a[0];vy=b[1]-a[1]
        t=max(0,min(1,((dx-a[0])*vx+(dy-a[1])*vy)/(vx*vx+vy*vy)))
        if math.hypot(dx-a[0]-t*vx,dy-a[1]-t*vy)<1:return True
    return False

def encode_ps(slot,scale=1):
    result=bytearray(16384)
    # BC2 constant white color with explicit4-bit alpha for eachtexel.
    for by in range(32):
        for bx in range(32):
            bits=0
            for y in range(4):
                for x in range(4):
                    a=round(sum(ps_alpha(slot,(bx*4+x+sx)/scale,(by*4+y+sy)/scale) for sx in (.125,.375,.625,.875) for sy in (.125,.375,.625,.875))*255/16)
                    bits|=(round(a/17)&15)<<(4*(y*4+x))
            block=bits.to_bytes(8,'little')+struct.pack('<HHI',0xffff,0,0)
            block=b''.join(block[i:i+2][::-1] for i in range(0,16,2))
            pos=tiled_offset(bx,by)*16;result[pos:pos+16]=block
    return result

def build(output,game_data_root=None):
    game_data_root=Path(game_data_root) if game_data_root is not None else ROOT/'assets'
    pins=json.loads((Path(__file__).parent/'original-glyph-hashes.json').read_text())['sha256']
    # Validate the entire original set before producing any derivatives.
    for relative,expected in pins.items():
        path=game_data_root/relative
        if not path.is_file() or hashlib.sha256(path.read_bytes()).hexdigest()!=expected:
            raise ValueError(f'Original glyph hash mismatch: {path}')
    manifest={'author':'djultra64','format':'RW4 xb2 BC2 tiled/16-bit swapped','files':[]}
    for platform in ('XBOX','XENON'):
        base=game_data_root/'gui/cafe/artAssets'/platform/'icons'
        originals={name:(base/(('str' if name=='back' else name)+'.big')).read_bytes() for name in SLOTS}
        textures={name:data[slice(*arena_range(data,'str' if name=='back' else name))] for name,data in originals.items()}
        for family in ('xbox','playstation','switch'):
            for name,slot in SLOTS.items():
                data=bytearray(originals[name]);a,b=arena_range(data,'str' if name=='back' else name)
                if slot in ('up','down','left','right'):pass
                elif family=='playstation':data[a:b]=encode_ps(slot,2 if platform=='XENON' else 1)
                elif family=='switch':
                    if name in ('x','t','c','s'):data[a:b]=textures[{'x':'t','t':'x','c':'s','s':'c'}[name]]
                    else:
                        label={'l1':'L','l2':'ZL','l3':'LS','r1':'R','r2':'ZR','r3':'RS','str':'+','back':'-'}[name]
                        data[a:b]=encode_ps(label,2 if platform=='XENON' else 1)
                relative=Path('gui/cafe/artAssets')/platform/'icons'/(name+'.big')
                if family=='xbox' and name=='back':data[a:b]=encode_ps('back',2 if platform=='XENON' else 1)
                target=output/family/relative;target.parent.mkdir(parents=True,exist_ok=True);target.write_bytes(data)
                # Strong invariant: only texture bytes changed; every original
                # archive entry offset and all native UI/RW4 metadata survive.
                assert data[:a]==originals[name][:a] and data[b:]==originals[name][b:]
                manifest['files'].append({'family':family,'path':str(relative),'source_sha256':hashlib.sha256(originals[name]).hexdigest(),'output_sha256':hashlib.sha256(data).hexdigest()})
    output.mkdir(parents=True,exist_ok=True);(output/'manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')
    return manifest
if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--output',type=Path,default=ROOT/'runtime/input-glyphs');parser.add_argument('--game-data-root',type=Path,default=ROOT/'assets');args=parser.parse_args()
    manifest=build(args.output,args.game_data_root);print(f"Built {len(manifest['files'])} native glyph BIG overrides in {args.output}")
