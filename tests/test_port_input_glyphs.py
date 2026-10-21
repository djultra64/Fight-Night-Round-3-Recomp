"""Native glyph derivative safety and physical-label contracts. Work: djultra64."""
import hashlib,importlib.util,json,shutil,tempfile,unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('glyphs',ROOT/'tools/port-input/build_glyph_overrides.py')
glyphs=importlib.util.module_from_spec(spec);spec.loader.exec_module(glyphs)
class GlyphContract(unittest.TestCase):
 @classmethod
 def setUpClass(cls):
  cls.temp=tempfile.TemporaryDirectory();cls.out=Path(cls.temp.name)/'output'
  cls.manifest=glyphs.build(cls.out,ROOT/'assets')
 @classmethod
 def tearDownClass(cls):cls.temp.cleanup()
 def texture(self,family,platform,name):
  data=(self.out/family/'gui/cafe/artAssets'/platform/'icons'/(name+'.big')).read_bytes()
  a,b=glyphs.arena_range(data,'str' if name=='back' else name);return data[a:b]
 def test_complete_hash_manifest_and_original_metadata(self):
  self.assertEqual(len(self.manifest['files']),96)
  for entry in self.manifest['files']:
   data=(self.out/entry['family']/entry['path']).read_bytes()
   self.assertEqual(hashlib.sha256(data).hexdigest(),entry['output_sha256'])
   path=Path(entry['path']);name=path.stem
   original=(ROOT/'assets'/path.with_name('str.big' if name=='back' else path.name)).read_bytes()
   self.assertEqual(hashlib.sha256(original).hexdigest(),entry['source_sha256'])
   a,b=glyphs.arena_range(original,'str' if name=='back' else name)
   self.assertEqual(data[:a],original[:a]);self.assertEqual(data[b:],original[b:])
 def test_switch_physical_abxy(self):
  for p in ['XBOX','XENON']:
   for dest,source in {'x':'t','t':'x','c':'s','s':'c'}.items():
    self.assertEqual(self.texture('switch',p,dest),self.texture('xbox',p,source))
 def test_ps_shapes_distinct_and_scaled(self):
  for p in ['XBOX','XENON']:
   textures=[self.texture('playstation',p,n) for n in ['x','t','c','s']]
   self.assertEqual(len(set(textures)),4)
   # Constant white BC2 RGB and explicit alpha: actual native textures rather
   # than changing labels or platform variables alone.
   self.assertTrue(all(len(t)==16384 for t in textures))
  self.assertNotEqual(self.texture('playstation','XBOX','x'),self.texture('playstation','XENON','x'))
 def test_bc2_explicit_alpha_background_and_shape(self):
  for platform,center in [('XBOX',16),('XENON',32)]:
   texture=self.texture('playstation',platform,'x')
   def alpha(x,y):
    offset=glyphs.tiled_offset(x//4,y//4,32,16)*16
    block=texture[offset:offset+16]
    block=b''.join(block[i:i+2][::-1] for i in range(0,16,2))
    bits=int.from_bytes(block[:8],'little')
    return ((bits>>(4*((y%4)*4+x%4)))&15)*17
   self.assertEqual(alpha(0,0),0)
   self.assertEqual(alpha(center,center),255)
   self.assertEqual(alpha(127,127),0)
 def test_corrupt_original_rejected_before_any_output(self):
  root=Path(self.temp.name)/'corrupt';target=Path(self.temp.name)/'rejected'
  pins=json.loads((ROOT/'tools/port-input/original-glyph-hashes.json').read_text())['sha256']
  for relative in pins:
   dest=root/relative;dest.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(ROOT/'assets'/relative,dest)
  first=root/next(iter(pins));data=bytearray(first.read_bytes());data[-1]^=1;first.write_bytes(data)
  with self.assertRaisesRegex(ValueError,'hash mismatch'):glyphs.build(target,root)
  self.assertFalse(target.exists())
if __name__=='__main__':unittest.main()
