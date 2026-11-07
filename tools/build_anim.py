"""Rebuild the Reptilian effect stacks: tracked motion rig, synced across all art layers."""
import copy, glob, json, os, shutil, sys

PROJ, RIG_TEX, FIELDS, SPINS, LAYOUT_JS = sys.argv[1:6]
scene_path = os.path.join(PROJ, 'scene.json')
scene = json.load(open(scene_path, encoding='utf-8'))
fields = json.load(open(FIELDS))['fields']
spins = {s['id']: s for s in json.load(open(SPINS))['spins']}
layers = {o['name']: o for o in scene['objects']}
K = layers['K']
byid = {e['id']: e for e in K['effects']}

# ---- ids --------------------------------------------------------------------------------------
def all_ids(v, acc):
    if isinstance(v, dict):
        if isinstance(v.get('id'), int):
            acc.add(v['id'])
        for x in v.values():
            all_ids(x, acc)
    elif isinstance(v, list):
        for x in v:
            all_ids(x, acc)
    return acc
next_id = [max(all_ids(scene, set())) + 1]
def new_id():
    next_id[0] += 1
    return next_id[0] - 1
def clone(effect, name=None):
    e = copy.deepcopy(effect)
    e['id'] = new_id()
    for p in e['passes']:
        p['id'] = new_id()
    if name is not None:
        e['name'] = name
    return e

# ---- detail effects (UV-local; run on the undeformed drawing so their masks stay aligned) ------
spin_names = {553: 'Mini Eye #1', 555: 'Mini Eye #2'}
for sid, s in spins.items():
    if s['adopt'] and sid in byid:
        byid[sid]['passes'][0]['constantshadervalues']['center'] = f"{s['new_uv'][0]:.5f} {s['new_uv'][1]:.5f}"
for sid, nm in spin_names.items():
    byid[sid]['name'] = nm
byid[162]['name'] = 'Honeycomb'
byid[545]['name'] = 'Nose twirl'
byid[547]['name'] = 'Tail edge shimmer'
byid[543]['name'] = 'Ink edges'

DETAIL = [531, 533, 535, 537, 539, 541, 543, 545, 547, 551, 553, 555, 557, 559, 162]
K_ONLY = {539, 543}                     # looks (blur, edge detection), not motion
REMOVED = {549: 'shake with an empty direction map (no-op)',
           563: 'pulse with identical white tints (no-op)',
           565: 'swing hair (replaced by tracked hair)', 567: 'swing tail (replaced by tracked tail)',
           569: 'swing tail 2 (replaced by tracked tail)', 99: 'tail shake (replaced by tracked tail)'}
LENS = byid[169]

# ---- tracked motion rig ------------------------------------------------------------------------
def rig_effect(key, label):
    f = fields[key]
    tex = [None, f['flow']] + ([f['time']] if 'time' in f else [])
    return {'file': 'effects/shake/effect.json', 'id': 0, 'name': label,
            'passes': [{'constantshadervalues': {'bounds': '0 1', 'friction': '1 1', 'speed': f['speed'], 'strength': f['strength']},
                        'id': 0, 'textures': tex}],
            'visible': True}
RIG = [rig_effect('tendrils', 'Rig: Tendrils'), rig_effect('hair', 'Rig: Hair'),
       rig_effect('tail', 'Rig: Tail'), rig_effect('head', 'Rig: Head nod')]

def is_motion_swing(e):
    return e['file'].endswith('swing/effect.json')
def is_lens(e):
    return 'lens_distortion' in e['file']

summary = {}
# K: detail -> rig -> lens
K['effects'] = [byid[i] for i in DETAIL] + [clone(r) for r in RIG] + [LENS]
summary['K'] = [e['name'] or e['file'].split('/')[-2] for e in K['effects']]

# colour layers: their own colour/audio effects stay first, then the same motion stack as K
for name in ['C', 'M', 'C2']:
    L = layers[name]
    own = [e for e in L['effects'] if not is_motion_swing(e) and not is_lens(e)]
    lens = next(e for e in L['effects'] if is_lens(e))
    L['effects'] = own + [clone(byid[i]) for i in DETAIL if i not in K_ONLY] + [clone(r) for r in RIG] + [lens]
    summary[name] = [e['name'] or e['file'].split('/')[-2] for e in L['effects']]

# silhouette backing: only the large motions
W = layers['W']
wlens = next(e for e in W['effects'] if is_lens(e))
W['effects'] = [clone(r) for r in RIG] + [wlens]
summary['W'] = [e['name'] or e['file'].split('/')[-2] for e in W['effects']]

# layout script without the side option (Wallpaper Engine's flip handles mirroring)
K['visible'] = {'script': open(LAYOUT_JS, encoding='utf-8').read(), 'scriptproperties': {'heightPercent': 90}, 'value': True}

json.dump(scene, open(scene_path, 'w', encoding='utf-8'), indent='\t', ensure_ascii=False)

proj_path = os.path.join(PROJ, 'project.json')
proj = json.load(open(proj_path, encoding='utf-8'))
proj['general']['properties'].pop('side', None)
json.dump(proj, open(proj_path, 'w', encoding='utf-8'), indent='\t', ensure_ascii=False)

os.makedirs(os.path.join(PROJ, 'materials', 'masks'), exist_ok=True)
for f in glob.glob(os.path.join(RIG_TEX, '*.tex')):
    shutil.copy(f, os.path.join(PROJ, 'materials', 'masks'))

passes = sum(len(e['passes']) for o in scene['objects'] for e in o.get('effects', []))
print(json.dumps({'layers': {k: len(v) for k, v in summary.items()}, 'total_passes': passes, 'removed': REMOVED,
                  'spins_moved': {spin_names.get(i, i): s['shift_px'] for i, s in spins.items() if s['adopt']}}, indent=1, ensure_ascii=False))
json.dump(summary, open(os.path.join(os.path.dirname(FIELDS), 'stack_summary.json'), 'w'), indent=1, ensure_ascii=False)
