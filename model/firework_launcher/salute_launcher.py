# -*- coding: utf-8 -*-
"""
过山车提升顶旁的「垂柳塔」烟花发射架 —— 地标礼花的第 7 座发射架 (L7), 独立小资产, 不动 park_env.glb
Run: /e/blender/blender.exe --background --python model/firework_launcher/salute_launcher.py

为什么单独出资产: park_env.glb 按材质合并, 园内 6 座发射架只剩空锚点节点, 运行时无法克隆;
而过山车最高处离最近的现有发射架 L2 有 94m, 够不着。

造型 = park_env.py 已定稿的 B 型「垂柳塔」(_lw_B), 函数原样拷贝 (材质参数相同, 几何与园内 L3/L4 完全一致)。
炮口朝向该处的地标炸点: 过山车提升平顶中点沿前进方向 ANCHOR_OUT 米 (由 centerline.json 现算, 与
src/rides/coaster.js 的 crest 同一算法; ANCHOR_OUT 须与 src/fx/fw_director.js COASTER_OUT 一致)。

输出 (同目录):
  salute_launcher.glb            按材质合并, 世界坐标 (blender → glTF: app = (x, z, -y))
  colliders_salute_launcher.json app 坐标: launchers 发射架锚点 + circles 碰撞圆
"""
import bpy
import bmesh
import json
from math import radians, pi, cos, sin, atan2, hypot
from pathlib import Path
from mathutils import Vector

OUT = Path(__file__).resolve().parent
CENTERLINE = OUT.parent / "roller_coaster" / "centerline.json"

SITE = (46.0, 125.0)    # blender 坐标 = app (46, -125): 首跌外侧草坪, 离轨道约 6.5m, 离提升顶立柱基础 6m
LID, KIND = "L7", "B"
ANCHOR_OUT = 16.0       # 地标炸点离平顶中点的水平距离 (米)
MUZZLE_H = 2.92         # 管口离地高 (park_env.py MUZZLE_LOCAL["B"])
COLLIDE_R = 0.95        # 无限高阻挡圆 (park_env.py LW_COLLIDE["B"])

bpy.ops.wm.read_factory_settings(use_empty=True)   # -b 后台启动 ≠ 空场景: 先清掉默认立方体/灯/相机
sc = bpy.context.scene
col = bpy.data.collections.new("SaluteLauncher")
sc.collection.children.link(col)

# ----------------------------------------------------------------- utils (照抄 park_env.py) ---
HEX = {
    "red":     "#C43B3B",
    "warm":    "#FFE9C4",
    "iron":    "#23273A",
    "metal_d": "#1E2330",
    "wood":    "#4A3526",
    "violet":  "#9B5BFF",
}

def hex_lin(h, a=1.0):
    h = h.lstrip("#")
    out = []
    for i in (0, 2, 4):
        c = int(h[i:i+2], 16) / 255.0
        out.append(c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4)
    return (*out, a)

def sock(node, ident):
    for s in node.inputs:
        if s.identifier == ident:
            return s
    return None

def make_mat(name, color, rough=0.5, metal=0.0, emit=None, strength=0.0):
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    p = next(n for n in m.node_tree.nodes if n.type == "BSDF_PRINCIPLED")
    s = sock(p, "Base Color")
    if s: s.default_value = (*hex_lin(color)[:3], 1.0)
    s = sock(p, "Metallic")
    if s: s.default_value = metal
    s = sock(p, "Roughness")
    if s: s.default_value = rough
    if emit:
        s = sock(p, "Emission Color")
        if s: s.default_value = hex_lin(emit)
        s = sock(p, "Emission Strength")
        if s: s.default_value = strength
    return m

def _new_obj(name, verts, faces, mat, sm):
    me = bpy.data.meshes.new(name)
    me.from_pydata(verts, [], faces)
    me.validate(verbose=False)
    me.update()
    if mat: me.materials.append(mat)
    if sm:
        for p in me.polygons:
            p.use_smooth = True
    ob = bpy.data.objects.new(name, me)
    col.objects.link(ob)
    return ob

def add_cyl(name, r, depth, loc, rot=(0, 0, 0), mat=None, verts=12, sm=True):
    hz = depth / 2
    vs = []
    for i in range(verts):
        a = 2 * pi * i / verts
        vs.append((r * cos(a), r * sin(a), -hz))
    for i in range(verts):
        a = 2 * pi * i / verts
        vs.append((r * cos(a), r * sin(a), hz))
    fs = []
    for i in range(verts):
        j = (i + 1) % verts
        fs.append((i, j, verts + j, verts + i))
    fs.append(tuple(range(verts - 1, -1, -1)))
    fs.append(tuple(range(verts, verts * 2)))
    ob = _new_obj(name, vs, fs, mat, sm)
    ob.location = loc
    ob.rotation_euler = rot
    return ob

def cyl_between(name, p1, p2, r, mat, verts=6, sm=True):
    p1, p2 = Vector(p1), Vector(p2)
    d = p2 - p1
    L = d.length
    ob = add_cyl(name, r, 1.0, ((p1.x + p2.x) / 2, (p1.y + p2.y) / 2, (p1.z + p2.z) / 2),
                 (0, 0, 0), mat, verts, sm)
    ob.scale = (1, 1, max(L, 1e-4))
    ob.rotation_euler = d.to_track_quat("Z", "Y").to_euler()
    return ob

def add_torus(name, R, tube, loc, rot=(0, 0, 0), mat=None, ms=64, ns=8, scale=(1, 1, 1)):
    vs = []
    for i in range(ms):
        a = 2 * pi * i / ms
        ca, sa = cos(a), sin(a)
        for j in range(ns):
            b = 2 * pi * j / ns
            cb, sb = cos(b), sin(b)
            vs.append(((R + tube * cb) * ca, (R + tube * cb) * sa, tube * sb))
    fs = []
    for i in range(ms):
        i2 = (i + 1) % ms
        for j in range(ns):
            j2 = (j + 1) % ns
            fs.append((i * ns + j, i2 * ns + j, i2 * ns + j2, i * ns + j2))
    ob = _new_obj(name, vs, fs, mat, True)
    ob.location = loc
    ob.rotation_euler = rot
    ob.scale = scale
    return ob

def torus_gap(ob, gap_half_deg, gap_center_deg):
    bm = bmesh.new()
    bm.from_mesh(ob.data)
    lo = radians(gap_center_deg - gap_half_deg) % (2 * pi)
    hi = radians(gap_center_deg + gap_half_deg) % (2 * pi)
    def in_gap(v):
        a = atan2(v.co.y, v.co.x) % (2 * pi)
        return lo <= a <= hi
    doomed = [v for v in bm.verts if in_gap(v)]
    bmesh.ops.delete(bm, geom=doomed, context="VERTS")
    bm.to_mesh(ob.data)
    bm.free()
    ob.data.update()
    return ob

def add_box(name, size, loc, rot=(0, 0, 0), mat=None):
    vs = [(-0.5, -0.5, -0.5), (0.5, -0.5, -0.5), (0.5, 0.5, -0.5), (-0.5, 0.5, -0.5),
          (-0.5, -0.5, 0.5), (0.5, -0.5, 0.5), (0.5, 0.5, 0.5), (-0.5, 0.5, 0.5)]
    fs = [(0, 3, 2, 1), (4, 5, 6, 7), (0, 1, 5, 4), (1, 2, 6, 5), (2, 3, 7, 6), (3, 0, 4, 7)]
    ob = _new_obj(name, vs, fs, mat, False)
    ob.location = loc
    ob.rotation_euler = rot
    ob.scale = size
    return ob

def add_cone(name, r, depth, loc, mat=None, verts=4, rot=(0, 0, 0)):
    hz = depth / 2
    vs = []
    for i in range(verts):
        a = 2 * pi * i / verts
        vs.append((r * cos(a), r * sin(a), -hz))
    vs.append((0, 0, hz))
    fs = []
    for i in range(verts):
        j = (i + 1) % verts
        fs.append((i, j, verts))
    fs.append(tuple(range(verts - 1, -1, -1)))
    ob = _new_obj(name, vs, fs, mat, True)
    ob.location = loc
    ob.rotation_euler = rot
    return ob

def add_sphere(name, r, loc, mat=None, seg=10, ring=6, scale=(1, 1, 1)):
    vs = [(0, 0, r)]
    for j in range(1, ring):
        phi = pi * j / ring
        sp, cp = sin(phi), cos(phi)
        for i in range(seg):
            th = 2 * pi * i / seg
            vs.append((r * sp * cos(th), r * sp * sin(th), r * cp))
    vs.append((0, 0, -r))
    top_i = 0
    bot_i = len(vs) - 1
    fs = []
    for i in range(seg):
        i2 = (i + 1) % seg
        fs.append((top_i, 1 + i, 1 + i2))
    for j in range(ring - 2):
        row0 = 1 + j * seg
        row1 = row0 + seg
        for i in range(seg):
            i2 = (i + 1) % seg
            fs.append((row0 + i, row1 + i, row1 + i2, row0 + i2))
    last_row = 1 + (ring - 2) * seg
    for i in range(seg):
        i2 = (i + 1) % seg
        fs.append((bot_i, last_row + i2, last_row + i))
    ob = _new_obj(name, vs, fs, mat, True)
    ob.location = loc
    ob.scale = scale
    return ob

# ----------------------------------------------------------------- 材质 (参数同 park_env.py, 名字加 FS_ 前缀防与园区材质串用) ---
m_wood     = make_mat("FS_Wood", HEX["wood"], rough=0.85)
m_iron     = make_mat("FS_Iron", HEX["iron"], rough=0.55, metal=0.8)
m_metal_d  = make_mat("FS_MetalDark", HEX["metal_d"], rough=0.6, metal=0.7)
m_steel    = make_mat("FS_Steel", "#3A4152", rough=0.35, metal=0.9)
m_wood_d   = make_mat("FS_WoodDark", "#3A2A1D", rough=0.9)
m_warm     = make_mat("FS_EmitWarm", HEX["warm"], emit=HEX["warm"], strength=2.6)
m_violet   = make_mat("FS_EmitViolet", HEX["violet"], emit=HEX["violet"], strength=2.2)
m_violet_s = make_mat("FS_EmitVioletSoft", HEX["violet"], emit=HEX["violet"], strength=1.2)
m_red      = make_mat("FS_EmitRed", HEX["red"], emit=HEX["red"], strength=2.2)

# ----------------------------------------------------------------- 造型 (park_env.py _lw_B 原样拷贝) ---
def _lw_fwd(elev, az=0.0):
    """局部旋转 (elev, 0, az) 下 +Z 轴方向 (炮口朝 -Y 仰起)"""
    return (sin(az) * sin(elev), -cos(az) * sin(elev), cos(elev))

def _lw_firebox(obs, tag, x, y, z, yaw=0.0):
    """家族基因: 点火箱 + 红蘑菇钮 + 推杆"""
    obs.append(add_box(f"{tag}_FBbody", (0.42, 0.3, 0.3), (x, y, z + 0.15), rot=(0, 0, yaw), mat=m_wood_d))
    obs.append(add_box(f"{tag}_FBlip", (0.46, 0.34, 0.04), (x, y, z + 0.31), rot=(0, 0, yaw), mat=m_wood))
    obs.append(add_cyl(f"{tag}_FBbtn", 0.06, 0.05, (x, y - 0.1, z + 0.36), mat=m_red, verts=10))
    obs.append(add_sphere(f"{tag}_FBcap", 0.055, (x, y - 0.1, z + 0.39), mat=m_red, seg=8, ring=5))
    obs.append(cyl_between(f"{tag}_FBlever", (x + 0.16, y + 0.05, z + 0.3), (x + 0.26, y + 0.12, z + 0.5), 0.014, m_iron))

def _lw_B(tag):
    """垂柳塔: 四腿收分木塔 (H2.3) + 单口粗臼炮 (仰角 76°) + 垂链紫灯笼 x4 + 弯月徽"""
    o = []
    g0, t0, H = 0.85, 0.5, 2.3
    for sx in (-1, 1):
        for sy in (-1, 1):
            o.append(cyl_between(f"{tag}_leg_{sx}{sy}", (sx * g0, sy * g0, 0.04), (sx * t0, sy * t0, H), 0.06, m_wood))
    for zz in (0.75, 1.5):
        w = g0 + (t0 - g0) * zz / H
        for sy in (-1, 1):
            o.append(cyl_between(f"{tag}_x1_{zz}_{sy}", (-w, sy * w, zz), (w, sy * w, zz + 0.55), 0.028, m_iron))
            o.append(cyl_between(f"{tag}_x2_{zz}_{sy}", (w, sy * w, zz), (-w, sy * w, zz + 0.55), 0.028, m_iron))
    o.append(add_box(f"{tag}_deck", (1.3, 1.3, 0.09), (0, 0, H + 0.045), mat=m_wood_d))
    for sx in (-1, 1):
        for sy in (-1, 1):
            o.append(add_cyl(f"{tag}_post_{sx}{sy}", 0.025, 0.3, (sx * 0.6, sy * 0.6, H + 0.24), mat=m_wood, verts=8))
    for sy in (-1, 1):
        o.append(cyl_between(f"{tag}_railX_{sy}", (-0.6, sy * 0.6, H + 0.36), (0.6, sy * 0.6, H + 0.36), 0.02, m_wood))
    for sx in (-1, 1):
        o.append(cyl_between(f"{tag}_railY_{sx}", (sx * 0.6, -0.6, H + 0.36), (sx * 0.6, 0.6, H + 0.36), 0.02, m_wood))
    elev = radians(76)
    fx, fy, fz = _lw_fwd(elev)
    bx, by, bz = 0.0, 0.1, H + 0.5
    o.append(add_cyl(f"{tag}_mortar", 0.27, 0.88, (bx, by, bz), rot=(elev, 0, 0), mat=m_steel, verts=14))
    o.append(add_torus(f"{tag}_band1", 0.285, 0.026, (bx - fx * 0.25, by - fy * 0.25, bz - fz * 0.25),
                       rot=(elev, 0, 0), mat=m_metal_d))
    o.append(add_torus(f"{tag}_band2", 0.29, 0.026, (bx + fx * 0.05, by + fy * 0.05, bz + fz * 0.05),
                       rot=(elev, 0, 0), mat=m_metal_d))
    o.append(add_cyl(f"{tag}_lip", 0.32, 0.12, (bx + fx * 0.42, by + fy * 0.42, bz + fz * 0.42),
                     rot=(elev, 0, 0), mat=m_steel, verts=14))
    o.append(add_torus(f"{tag}_rim", 0.32, 0.024, (bx + fx * 0.46, by + fy * 0.46, bz + fz * 0.46),
                       rot=(elev, 0, 0), mat=m_metal_d))
    o.append(add_torus(f"{tag}_muzzlering", 0.24, 0.03, (bx + fx * 0.5, by + fy * 0.5, bz + fz * 0.5),
                       rot=(elev, 0, 0), mat=m_violet_s))
    o.append(add_box(f"{tag}_mount", (0.72, 0.72, 0.22), (0, 0.1, H + 0.24), mat=m_iron))
    for (cx, cy, L) in ((-0.6, -0.6, 0.72), (0.6, -0.6, 0.5), (-0.6, 0.6, 0.4), (0.6, 0.6, 0.4)):
        lz = H + 0.34 - L
        o.append(cyl_between(f"{tag}_chain_{cx}{cy}", (cx, cy, H + 0.34), (cx, cy, lz), 0.011, m_iron))
        o.append(add_sphere(f"{tag}_lant_{cx}{cy}", 0.095, (cx, cy, lz - 0.11),
                            mat=m_violet, seg=10, ring=6, scale=(1, 1, 1.2)))
        o.append(add_cone(f"{tag}_cap_{cx}{cy}", 0.075, 0.08, (cx, cy, lz - 0.005), mat=m_metal_d, verts=12))
    moon = add_torus(f"{tag}_moon", 0.22, 0.026, (0, -0.72, 1.35), rot=(radians(90), 0, 0), mat=m_warm)
    torus_gap(moon, 48, 60)   # 缺口右上 = 新月
    o.append(moon)
    o.append(add_cyl(f"{tag}_barrel", 0.26, 0.5, (-1.0, 0.35, 0.25), mat=m_wood_d, verts=12))
    o.append(add_torus(f"{tag}_bbarrel", 0.265, 0.02, (-1.0, 0.35, 0.25), mat=m_iron))
    o.append(add_cyl(f"{tag}_barrel2", 0.22, 0.42, (-0.85, -0.6, 0.21), mat=m_wood, verts=12))
    o.append(add_torus(f"{tag}_bbarrel2", 0.225, 0.02, (-0.85, -0.6, 0.21), mat=m_iron))
    _lw_firebox(o, tag, 0.9, -0.55, 0.02, yaw=radians(15))
    return o

# ----------------------------------------------------------------- 地标炸点 → 炮口朝向 ---
# 平顶 = 与最高点同高 (±1cm) 的连续段 (判据须与 coaster.js crest 一致); 取段中点为「过山车最高处」, 沿前进方向 (blender +Y 北 = app -Z) 量 ANCHOR_OUT
cl = json.loads(CENTERLINE.read_text(encoding="utf-8"))
S, DS = cl["samples"], cl.get("ds", 0.5)
ymax = max(s["p"][2] for s in S)
i0 = next(i for i, s in enumerate(S) if s["p"][2] >= ymax - 0.01)
i1 = i0
while i1 + 1 < len(S) and S[i1 + 1]["p"][2] >= ymax - 0.01:
    i1 += 1
a, b = S[i0]["p"], S[i1]["p"]
crest_b = ((a[0] + b[0]) / 2, (a[1] + b[1]) / 2)
tn = hypot(b[0] - a[0], b[1] - a[1])
tan_app = ((b[0] - a[0]) / tn, -(b[1] - a[1]) / tn)
target_app = (crest_b[0] + tan_app[0] * ANCHOR_OUT, -crest_b[1] + tan_app[1] * ANCHOR_OUT)
dx, dz = target_app[0] - SITE[0], target_app[1] + SITE[1]     # app 坐标: 站点 → 炸点
dn = hypot(dx, dz) or 1.0
dx, dz = round(dx / dn, 3), round(dz / dn, 3)
print(f"crest s={((i0 + i1) / 2) * DS:.1f} app=({crest_b[0]:.2f},{-crest_b[1]:.2f}) tan_app=({tan_app[0]:.3f},{tan_app[1]:.3f})")
print(f"site app=({SITE[0]:.1f},{-SITE[1]:.1f}) target app=({target_app[0]:.2f},{target_app[1]:.2f}) aim=({dx},{dz})")

# ----------------------------------------------------------------- 建发射架 ---
# 本地 -Y (炮口) 绕 Z 转 theta 后指向 (sinθ, -cosθ); blender 方向 = (dx, -dz) → θ = atan2(dx, -(-dz)) = atan2(dx, dz)
# (对照 park_env.py 朝园心的写法 atan2(-sx, sy): 那里 dx=-sx/r, dz=sy/r, 代入同一式)
theta = atan2(dx, dz)
anchor = bpy.data.objects.new(f"PE_LW_{LID}_anchor", None)
col.objects.link(anchor)
anchor.location = (SITE[0], SITE[1], 0.0)
anchor.rotation_euler = (0.0, 0.0, theta)
parts = _lw_B(f"PE_LW_{LID}")
for ob in parts:
    ob.parent = anchor
bpy.context.view_layer.update()   # 父子变换要过一次依赖图, matrix_world 才是位姿后的值

# ----------------------------------------------------------------- 按材质合并 (bpy.data 直合, 同 park_env.py; 世界坐标) ---
groups = {}
for ob in list(bpy.context.scene.objects):
    if ob.type != "MESH":
        continue
    groups.setdefault(ob.data.materials[0].name if ob.data.materials else "NONE", []).append(ob)
bbox = None
for mat_name, obs in groups.items():
    vs_all, fs_all, offset = [], [], 0
    for ob in obs:
        me = ob.data
        mw = ob.matrix_world
        for v in me.vertices:
            w = mw @ v.co
            vs_all.append((w.x, w.y, w.z))
            if bbox is None:
                bbox = [[w.x, w.y, w.z], [w.x, w.y, w.z]]
            else:
                for k in range(3):
                    bbox[0][k] = min(bbox[0][k], w[k])
                    bbox[1][k] = max(bbox[1][k], w[k])
        for poly in me.polygons:
            fs_all.append(tuple(i + offset for i in poly.vertices))
        offset = len(vs_all)
        bpy.data.objects.remove(ob, do_unlink=True)
    me_new = bpy.data.meshes.new(mat_name)
    me_new.from_pydata(vs_all, [], fs_all)
    me_new.validate(verbose=False)
    me_new.update()
    for m in bpy.data.materials:
        if m.name == mat_name:
            me_new.materials.append(m)
            break
    ob_new = bpy.data.objects.new(mat_name, me_new)
    col.objects.link(ob_new)
    print(f"  {mat_name}: verts={len(vs_all)} faces={len(fs_all)} parts={len(obs)}")
bpy.data.objects.remove(anchor, do_unlink=True)   # 锚点空节点只用于摆位, 不进 glb

# ----------------------------------------------------------------- 导出 ---
try:
    bpy.ops.export_scene.gltf(filepath=str(OUT / "salute_launcher.glb"),
                              export_format="GLB", export_apply=True)
except (TypeError, RuntimeError):
    bpy.ops.export_scene.gltf(filepath=str(OUT / "salute_launcher.glb"),
                              export_format="GLB")
print("GLB_EXPORTED", (OUT / "salute_launcher.glb").stat().st_size, "bytes")

# colliders (app 坐标: app_x = blender_x, app_z = -blender_y)
manifest = {
    "version": 1,
    "note": "过山车提升顶旁的垂柳塔发射架 L7 (app 坐标; salute_launcher.py 生成)。launchers 条目并入 colliders.json 的 launchers, circles = 无限高阻挡圆; dx/dz = 炮口水平朝向 (指向过山车顶地标炸点)",
    "launchers": [{"id": LID, "kind": KIND, "x": SITE[0], "z": -SITE[1], "dx": dx, "dz": dz, "mz": MUZZLE_H}],
    "circles": [{"x": SITE[0], "z": -SITE[1], "r": COLLIDE_R}],
}
(OUT / "colliders_salute_launcher.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=1) + "\n",
                                                     encoding="utf-8")
print("bbox blender", [[round(v, 2) for v in bbox[0]], [round(v, 2) for v in bbox[1]]])
print("COLLIDERS_WRITTEN")
