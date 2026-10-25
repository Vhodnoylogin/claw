"""Собирает женское тело вервольфа: пара по весу, шерсть на предплечьях и морфы.

Три вещи, которых у женского тела Elegant нет и которые здесь появляются.

**Пара по весу.** `femalebodywerewolf_0.nif` и `_1.nif` у Elegant совпадают
побайтово — это дубликат, а не пара, и вес самкам не даёт ничего. Половина `_0`
строится здесь убавлением обхвата: у людей прибавка от веса даёт 1–7 %, у зверя
берём вчетверо больше.

**Шерсть на предплечьях.** У самки нет формы `fur_arms` — единственное отличие
в наборе форм между полами. Она переносится с мужского тела и подгоняется полем
сдвига кожи, иначе провалилась бы в руку.

**Ползунок «к мужской груди».** Тела полов топологически одинаковы: совпадает
и число вершин, и их порядок. Поэтому целевые координаты для `CLAWChestFlat` —
это буквально вершины мужского тела с теми же номерами. Донор читается первым
проходом; двух тел в сцене держать нельзя, PyNifly при повторном импорте вливает
данные в существующие объекты вместо того, чтобы завести вторые.

  blender.exe --background --python build-female.py -- \\
      <мужское.nif> <женское.nif> <выход.nif> <full-body.json> <female.json> [--slim 0.90]
"""
import sys, os, json, bpy, addon_utils
from mathutils import Vector, kdtree

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import morphlib

_v = bpy.context.preferences.view
try:
    _v.use_translate_new_dataname = False
    _v.use_translate_interface = False
    _v.language = 'en_US'
except Exception:
    pass
addon_utils.enable("io_scene_nifly", default_set=False, persistent=True)

argv = sys.argv[sys.argv.index("--") + 1:]
COLLARS = None
COLLAR_REPORT = None
BREAST_SHAPE = None
DRY_COLLARS = '--dry-surface-collars' in argv
if DRY_COLLARS:
    argv.remove('--dry-surface-collars')
for flag in ('--surface-collars', '--surface-report', '--breast-shape'):
    if flag in argv:
        k = argv.index(flag)
        value = argv[k + 1]
        argv = argv[:k] + argv[k + 2:]
        if flag == '--surface-collars':
            COLLARS = value
        elif flag == '--surface-report':
            COLLAR_REPORT = value
        else:
            BREAST_SHAPE = value
SLIM = None
if '--slim' in argv:
    k = argv.index('--slim')
    SLIM = float(argv[k + 1])
    argv = argv[:k] + argv[k + 2:]
#: Ползунки, которые в этой сборке не заводить - см. тот же ключ у build-genitals.
SKIP_MORPHS = set()
while '--skip-morph' in argv:
    _k = argv.index('--skip-morph')
    SKIP_MORPHS.add(argv[_k + 1])
    argv = argv[:_k] + argv[_k + 2:]
MALE, FEMALE, OUT, FULL, FEM = argv[0], argv[1], argv[2], argv[3], argv[4]

# Optional shape profile changes only BreastSize semantics. Validate executable
# recipe inputs before importing/exporting anything; the default path is intact.
breast_profile = None
if BREAST_SHAPE:
    import breast_shape
    if not COLLARS:
        raise ValueError('--breast-shape requires --surface-collars')
    if breast_shape.PUBLIC_MORPH in SKIP_MORPHS:
        raise ValueError('--breast-shape requires the source BreastSize morph')
    with open(BREAST_SHAPE, encoding='utf-8-sig') as stream:
        breast_profile = json.load(stream)
    with open(FEM, encoding='utf-8-sig') as stream:
        source_female = json.load(stream)
    with open(FULL, encoding='utf-8-sig') as stream:
        source_full = json.load(stream)
    with open(COLLARS, encoding='utf-8-sig') as stream:
        source_collar = json.load(stream)
    breast_shape.validate_profile(breast_profile, source_female, source_full, source_collar, SLIM)


def wipe():
    for o in list(bpy.data.objects):
        bpy.data.objects.remove(o, do_unlink=True)


# ---- проход первый: донор ----------------------------------------------------
wipe()
bpy.ops.import_scene.pynifly(filepath=MALE)
male_co = {o.name: [v.co.copy() for v in o.data.vertices]
           for o in bpy.data.objects if o.type == 'MESH'}
src_arms = bpy.data.objects.get('fur_arms')
arms_mesh = src_arms.data if src_arms else None
arms_co, arms_weights = [], {}
if src_arms:
    arms_mesh.name = 'fur_arms'
    arms_co = [v.co.copy() for v in src_arms.data.vertices]
    gnames = {g.index: g.name for g in src_arms.vertex_groups}
    for v in src_arms.data.vertices:
        for g in v.groups:
            arms_weights.setdefault(gnames[g.group], []).append((v.index, g.weight))
print("FEM|донор прочитан: форм %d, fur_arms %d вершин"
      % (len(male_co), len(arms_co)))

# ---- проход второй: женское тело ---------------------------------------------
wipe()
bpy.ops.import_scene.pynifly(filepath=FEMALE)
arm = next(o for o in bpy.data.objects if o.type == 'ARMATURE')
body = bpy.data.objects['body']
if len(male_co['body']) != len(body.data.vertices):
    print("FEM|тела не родственные: %d вершин против %d"
          % (len(male_co['body']), len(body.data.vertices)))
    raise SystemExit(1)

# поле сдвига кожи: куда уехала каждая вершина при лепке самки из самца
skin_delta = [t.co - s for s, t in zip(male_co['body'], body.data.vertices)]
tree = kdtree.KDTree(len(male_co['body']))
for i, co in enumerate(male_co['body']):
    tree.insert(co, i)
tree.balance()

# ---- шерсть на предплечьях ---------------------------------------------------
if arms_mesh is not None and bpy.data.objects.get('fur_arms') is None:
    obj = bpy.data.objects.new('fur_arms', arms_mesh)
    bpy.context.collection.objects.link(obj)
    mx = 0.0
    for i, v in enumerate(obj.data.vertices):
        tot, acc = 0.0, Vector((0.0, 0.0, 0.0))
        for _c, j, dist in tree.find_n(arms_co[i], 8):
            w = 1.0 / max(dist, 1e-4)
            acc += skin_delta[j] * w
            tot += w
        d = acc / tot if tot else Vector((0, 0, 0))
        v.co = arms_co[i] + d
        mx = max(mx, d.length)
    for name, pairs in arms_weights.items():
        vg = obj.vertex_groups.new(name=name)
        for idx, w in pairs:
            vg.add([idx], w, 'REPLACE')
    obj.parent = arm
    obj.modifiers.new(name="Armature", type='ARMATURE').object = arm
    print("FEM|fur_arms перенесена: %d вершин, наибольшая подгонка %.3f"
          % (len(obj.data.vertices), mx))

meshes = {o.name: o for o in bpy.data.objects if o.type == 'MESH'}
collar_session = None
if COLLARS:
    with open(COLLARS, encoding='utf-8-sig') as stream:
        collar_recipe = json.load(stream)
    collar_session = morphlib.SurfaceCollarSession(meshes, collar_recipe, FEMALE)
if DRY_COLLARS:
    if collar_session is None:
        raise ValueError('--dry-surface-collars requires --surface-collars')
    print('COLLAR|configuration validated; no geometry or morphs exported')
    raise SystemExit(0)

# ---- половина по весу --------------------------------------------------------
# Убавление обхвата делается ГЕОМЕТРИЕЙ, а не морфом: пара _0/_1 - это встроенное
# смешивание движка, оно про два разных меша, а не про именованный сдвиг.
if SLIM is not None:
    slim = {"mode": "region", "axis": [0.0, -2.0], "zRange": [56.0, 116.0],
            "zFade": 12.0, "amount": SLIM,
            "includeContains": ["NPC Pelvis", "NPC Spine", "NPC Neck"]}
    d = morphlib.deltas_for(body, slim, arm)
    fields = {'body': d} if collar_session else {}
    legacy_source = None
    if collar_session:
        # Preserve out-of-scope fur/tail behavior without mutating the true donor
        # used by the collar. Breast-local followers are replaced by skin bindings.
        legacy_source = [(body.matrix_world @ v.co) + d.get(i, Vector((0, 0, 0)))
                         for i, v in enumerate(body.data.vertices)]
    if not collar_session:
        # Keep the published legacy build reproducible until the opt-in candidate
        # is selected by a new versioned build recipe.
        morphlib.apply_neutral_fields(meshes, {'body': d})
    for name in ('fur_belly', 'fur_chest', 'fur_back', 'fur_shoulders', 'ChestBlend'):
        o = meshes.get(name)
        if o is None:
            continue
        # The opt-in candidate samples the frozen source, before its Basis moves.
        fields[name] = morphlib.carry_field(body, d, o, source_positions=legacy_source)
    if collar_session:
        fields = collar_session.neutral_fields(fields)
    morphlib.apply_neutral_fields(meshes, fields)
    print("FEM|половина по весу: обхват %.2f, сдвинуто %d вершин кожи" % (SLIM, len(d)))

# ---- ползунки ----------------------------------------------------------------
# Общий рецепт держит ползунки обоих полов: у ползунка «к форме другого пола»
# знак у самца и самки разный, поэтому запись помечена полом и чужая пропускается.
full = [it for it in json.load(open(FULL, encoding='utf-8'))
        if it.get('sex', 'any') in ('any', 'female')
        and it.get('morph') not in SKIP_MORPHS]
for it in full:
    if it.get('mode') == 'toShape':
        morphlib.apply_to_shape(it, meshes, {'body': male_co.get('body')}, print)
morphlib.apply_recipe([it for it in full if it.get('mode') != 'toShape'], meshes, arm)

fem = [it for it in json.load(open(FEM, encoding='utf-8'))
       if it.get('morph') not in SKIP_MORPHS]
if SKIP_MORPHS:
    print("FEM|пропущены по --skip-morph: %s" % ", ".join(sorted(SKIP_MORPHS)))
plain = [it for it in fem if it.get('mode') != 'toShape']
morphlib.apply_recipe(plain, meshes, arm)

# Ползунки «к форме другого тела» считает morphlib: то же самое нужно и сборщику
# самца, и второй копии этой логики быть не должно.
for it in fem:
    if it.get('mode') == 'toShape':
        morphlib.apply_to_shape(it, meshes, {'body': male_co.get('body')}, print)

if collar_session:
    collar_session.reconcile_morphs()
if breast_profile:
    collar_session.report['breastShape'] = breast_shape.apply_profile(collar_session, breast_profile)

morphlib.export_clean(OUT)
if breast_profile:
    # PyNifly can omit all-subthreshold keys; only the written TRI establishes
    # the public contract. A failed export leaves candidate files, no success report.
    collar_session.report['breastShape']['serializedContract'] = breast_shape.verify_serialized_morphs(
        OUT, collar_session.report['breastShape']['publicMorphs'])
if collar_session:
    import hashlib
    report = collar_session.report
    report['status'] = 'exported-candidate-visual-and-runtime-acceptance-pending'
    report['blenderVersion'] = bpy.app.version_string
    report['recipeSha256'] = hashlib.sha256(open(COLLARS, 'rb').read()).hexdigest()
    report['maleInputSha256'] = hashlib.sha256(open(MALE, 'rb').read()).hexdigest()
    report['sourceSha256'] = {name: hashlib.sha256(open(os.path.join(
        os.path.dirname(__file__), name), 'rb').read()).hexdigest()
        for name in ('build-female.py', 'morphlib.py', 'surface_collar.py')}
    if breast_profile:
        report['breastShapeRecipeSha256'] = hashlib.sha256(open(BREAST_SHAPE, 'rb').read()).hexdigest()
        report['sourceSha256']['breast_shape.py'] = hashlib.sha256(open(os.path.join(
            os.path.dirname(__file__), 'breast_shape.py'), 'rb').read()).hexdigest()
    report_path = COLLAR_REPORT or OUT + '.surface-collars.json'
    os.makedirs(os.path.dirname(os.path.abspath(report_path)), exist_ok=True)
    with open(report_path, 'w', encoding='utf-8') as stream:
        json.dump(report, stream, indent=2)
print("FEM|экспорт ok ->", OUT)
