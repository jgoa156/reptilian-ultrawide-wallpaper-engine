"""Apply rig v2 + cleaned author masks to the project scene."""
import copy, glob, json, os, shutil, sys

PROJ, TEX_DIR, REPORT = sys.argv[1:4]
scene_path = os.path.join(PROJ, 'scene.json')
scene = json.load(open(scene_path, encoding='utf-8'))
rep = json.load(open(REPORT))
layers = {o['name']: o for o in scene['objects']}

def all_ids(v, acc):
    if isinstance(v, dict):
        if isinstance(v.get('id'), int): acc.add(v['id'])
        for x in v.values(): all_ids(x, acc)
    elif isinstance(v, list):
        for x in v: all_ids(x, acc)
    return acc
nid = [max(all_ids(scene, set())) + 1]
def new_id():
    nid[0] += 1; return nid[0] - 1

fixed = {}                                   # 'masks/x' -> 'masks/fix_x'
for label, a in rep['author'].items():
    key = a.get('mask') or a.get('flow')
    fixed[key.replace('masks/fix_', 'masks/')] = key
balance = rep['author']['Balance (General)']
blur_center = rep['author']['Guelras (2)']['center_uv']

def rig_effect(key, label):
    r = rep['rig'][key]
    return {'file': 'effects/shake/effect.json', 'id': new_id(), 'name': label,
            'passes': [{'constantshadervalues': {'bounds': '0 1', 'friction': '1 1', 'speed': r['speed'], 'strength': r['strength']},
                        'id': new_id(), 'textures': [None, r['flow'], r['time']]}],
            'visible': True}

changes = {}
for L in scene['objects']:
    if L['name'] == 'BG':
        continue
    out, log = [], []
    for e in L.get('effects', []):
        if e.get('name', '').startswith('Rig: '):
            continue                                            # rig v1 is replaced below
        kind = e['file'].split('/')[-2]
        p = e['passes'][0]
        c = p.setdefault('constantshadervalues', {})
        if p.get('textures'):
            p['textures'] = [fixed.get(t, t) if isinstance(t, str) else t for t in p['textures']]
        if kind == 'shake' and e.get('name') == 'Balance (General)':
            c['strength'] = balance['strength']
        if kind == 'blurradial':
            c['center'] = f'{blur_center[0]:.5f} {blur_center[1]:.5f}'
        if kind == 'twirl':
            c['feather'] = round(float(c.get('size', 0.5)) * 0.9, 5)     # taper the rotation instead of a hard ring
        if 'lens_distortion' in e['file']:
            lens = e
            continue
        out.append(e)
    rig = [rig_effect('appendages', 'Rig: Hair & Tendrils'), rig_effect('tail', 'Rig: Tail'), rig_effect('body', 'Rig: Head & Body')]
    L['effects'] = out + rig + [lens]
    changes[L['name']] = len(L['effects'])

json.dump(scene, open(scene_path, 'w', encoding='utf-8'), indent='\t', ensure_ascii=False)

mdir = os.path.join(PROJ, 'materials', 'masks')
for f in glob.glob(os.path.join(mdir, 'rig_*.tex')):          # rig v1 maps are no longer referenced
    os.remove(f)
for f in glob.glob(os.path.join(TEX_DIR, '*.tex')):
    shutil.copy(f, mdir)
passes = sum(len(e['passes']) for o in scene['objects'] for e in o.get('effects', []))
print(json.dumps({'effects_per_layer': changes, 'total_passes': passes, 'mask_swaps': fixed}, indent=1))
