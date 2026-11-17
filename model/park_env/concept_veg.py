# 植被全家桶 v3 概念稿 — 草/南瓜/树/花/蘑菇/干草堆/稻草人 重构图渲染
# 独立脚本: 只产 preview/concept_*.png, 不产出/不覆盖 park_env.glb
# 确认后把本文件的生成器移植回 park_env.py (见会话内重构方案)
#
# 运行: E:/blender/blender.exe -b -P model/park_env/concept_veg.py
# 材质语义严格对齐 glTF→three.js: 顶点色 Col 乘 Base Color (COLOR_0 linear 直乘),
# 自发光走 Emission Color/Strength (KHR_emissive_strength), 保证概念图=游戏观感。

import bpy
import random
from math import pi, radians, sin, cos, hypot
from mathutils import Vector, Quaternion
from pathlib import Path

random.seed(20261117)
OUT = Path(__file__).resolve().parent / "preview"
OUT.mkdir(exist_ok=True)

# 清空默认启动场景 (Cube/灯光/相机): 默认 Cube 会以白方块污染原点簇 (踩坑)
for _o in list(bpy.data.objects):
    bpy.data.objects.remove(_o, do_unlink=True)

sc = bpy.context.scene
col = bpy.data.collections.new("CONCEPT")
sc.collection.children.link(col)


def tmark(label):
    print(f"[concept] {label}", flush=True)


# ---------------- 基础 helper (照抄 park_env.py) ----------------
def hex_lin(h, a=1.0):
    h = h.lstrip("#")
    r, g, b = (int(h[i:i + 2], 16) / 255 for i in (0, 2, 4))
    def f(c):
        return c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4
    return (f(r), f(g), f(b), a)


def _new_obj(name, verts, faces, mat, sm):
    me = bpy.data.meshes.new(name)
    me.from_pydata(verts, [], faces)
    me.validate(verbose=False)
    me.update()
    if mat:
        me.materials.append(mat)
    if sm:
        for p in me.polygons:
            p.use_smooth = True
    ob = bpy.data.objects.new(name, me)
    col.objects.link(ob)
    return ob


def set_vcol(ob, colors):
    """colors: 每顶点 (r,g,b) LINEAR 值 → COLOR_0"""
    me = ob.data
    flat = []
    for c in colors:
        flat += [c[0], c[1], c[2], 1.0]
    attr = me.color_attributes.new("Col", 'FLOAT_COLOR', 'POINT')
    attr.data.foreach_set("color", flat)
    try:
        me.color_attributes.active_color = attr
    except Exception:
        pass
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


def add_box(name, size, loc, rot=(0, 0, 0), mat=None):
    vs = [(-0.5, -0.5, -0.5), (0.5, -0.5, -0.5), (0.5, 0.5, -0.5), (-0.5, 0.5, -0.5),
          (-0.5, -0.5, 0.5), (0.5, -0.5, 0.5), (0.5, 0.5, 0.5), (-0.5, 0.5, 0.5)]
    fs = [(0, 3, 2, 1), (4, 5, 6, 7), (0, 1, 5, 4), (1, 2, 6, 5), (2, 3, 7, 6), (3, 0, 4, 7)]
    ob = _new_obj(name, vs, fs, mat, False)
    ob.location = loc
    ob.rotation_euler = rot
    ob.scale = size
    return ob


def add_sphere(name, r, loc, mat=None, seg=10, ring=6, scale=(1, 1, 1), sm=True):
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
    ob = _new_obj(name, vs, fs, mat, sm)
    ob.location = loc
    ob.scale = scale
    return ob


def look_at(ob, target):
    d = Vector(target) - ob.location
    ob.rotation_euler = d.to_track_quat("-Z", "Y").to_euler()


# ---------------- v3 专用 helper ----------------
def make_mat(name, color, rough=0.5, metal=0.0, emit=None, strength=0.0):
    """普通材质 (颜色走 Base Color, 顶点色不参与) — 与 glTF 一致"""
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    p = next(n for n in m.node_tree.nodes if n.type == "BSDF_PRINCIPLED")
    def sock(ident):
        for s in p.inputs:
            if s.identifier == ident:
                return s
        return None
    s = sock("Base Color")
    if s:
        s.default_value = hex_lin(color)
    s = sock("Metallic")
    if s:
        s.default_value = metal
    s = sock("Roughness")
    if s:
        s.default_value = rough
    if emit:
        s = sock("Emission Color")
        if s:
            s.default_value = hex_lin(emit)
        s = sock("Emission Strength")
        if s:
            s.default_value = strength
    return m


def make_vcol_mat(name, color, rough=0.5, emit=None, strength=0.0):
    """顶点色材质: Base = 颜色 × Attribute(Col) — 复刻 three.js vertexColors 乘法"""
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    nt = m.node_tree
    p = next(n for n in nt.nodes if n.type == "BSDF_PRINCIPLED")
    attr = nt.nodes.new("ShaderNodeAttribute")
    attr.attribute_name = "Col"
    if color.upper() in ("#FFFFFF", "WHITE"):
        nt.links.new(attr.outputs["Color"], p.inputs["Base Color"])
    else:
        mix = nt.nodes.new("ShaderNodeMix")
        mix.data_type = 'RGBA'
        mix.blend_type = 'MULTIPLY'
        mix.inputs[6].default_value = hex_lin(color)   # Factor B
        nt.links.new(attr.outputs["Color"], mix.inputs[7])  # A
        nt.links.new(mix.outputs[2], p.inputs["Base Color"])
    for s in p.inputs:
        if s.identifier == "Roughness":
            s.default_value = rough
    if emit:
        for s in p.inputs:
            if s.identifier == "Emission Color":
                s.default_value = hex_lin(emit)
            if s.identifier == "Emission Strength":
                s.default_value = strength
    return m


def tube_frustum(name, pts, radii, mat, sides=8, sm=True, cap_end_fan=True):
    """平行输运标架的变径管: pts 控制点序列, radii 对应半径 → 有机弯曲枝干"""
    pts = [Vector(p) for p in pts]
    rings = []
    up0 = Vector((0, 0, 1))
    d0 = (pts[1] - pts[0]).normalized()
    dcur = d0
    n = up0 if abs(d0.z) > 0.93 else up0.cross(d0).normalized()
    n = (n - d0 * n.dot(d0)).normalized()
    for i, p in enumerate(pts):
        if i > 0:
            dprev = (pts[i] - pts[i - 1]).normalized()
            dcur = (pts[min(i + 1, len(pts) - 1)] - pts[i]).normalized() if i < len(pts) - 1 else dprev
            q = dprev.rotation_difference(dcur)
            n = q @ n
        nn = (n - dcur * n.dot(dcur)).normalized()
        r = radii[i]
        ring = []
        for k in range(sides):
            a = 2 * pi * k / sides
            ring.append(p + (nn * cos(a) + dcur.cross(nn) * sin(a)) * r)
        rings.append(ring)
    vs = [v for ring in rings for v in ring]
    fs = []
    for i in range(len(rings) - 1):
        b0, b1 = i * sides, (i + 1) * sides
        for k in range(sides):
            k2 = (k + 1) % sides
            fs.append((b0 + k, b0 + k2, b1 + k2, b1 + k))
    if cap_end_fan:
        tip = pts[-1] + (pts[-1] - pts[-2]).normalized() * radii[-1] * 2.2
        vs.append(tuple(tip))
        ti = len(vs) - 1
        b = (len(rings) - 1) * sides
        for k in range(sides):
            fs.append((b + k, b + (k + 1) % sides, ti))
    return _new_obj(name, vs, fs, mat, sm)


def blade(prefix, base, length, width, yaw, bend, mat,
          root_c, tip_c, segs=5, lean=0.2, twist=0.0):
    """弯曲锥形草叶: 弧线积分 + 尖部收窄 + 顶点色渐变。返回 (ob, 顶点数)"""
    base = Vector(base)
    d0 = Vector((cos(yaw) * lean, sin(yaw) * lean, 1.0)).normalized()
    outw = Vector((cos(yaw), sin(yaw), 0.0))
    axis = d0.cross(Vector((0, 0, 1))).normalized()   # 水平弯折轴
    if (Quaternion(axis, 0.2) @ d0).dot(outw) < d0.dot(outw):
        axis = -axis
    lft = axis.copy()
    p = base.copy()
    rows = []
    step = length / segs
    for i in range(segs + 1):
        t = i / segs
        th = bend * (t ** 1.3)
        d = (Quaternion(axis, th) @ d0).normalized()
        if twist:
            lft2 = Quaternion(d, twist * t) @ lft
        else:
            lft2 = lft
        w = width * (1 - t) ** 1.15 * 0.5 + 0.0012
        rows.append((p - lft2 * w, p + lft2 * w, t))
        p = p + d * step
    vs = []
    vcol = []
    for l, r, t in rows:
        vs += [tuple(l), tuple(r)]
        tt = t ** 0.85
        c = [root_c[k] + (tip_c[k] - root_c[k]) * tt for k in range(3)]
        vcol += [c, c]
    fs = []
    for i in range(segs):
        a, b = i * 2, i * 2 + 1
        fs.append((a, b, b + 2))
        fs.append((a, b + 2, a + 2))
    ob = _new_obj(prefix, vs, fs, mat, False)
    set_vcol(ob, vcol)
    return ob


def blade_tone():
    """随机草色系: 常规 / 偏暗 / 枯黄 — 线性色"""
    kind = random.random()
    root = hex_lin("#0B1D14")[:3]
    if kind < 0.62:
        tip = hex_lin("#41602C")[:3]
    elif kind < 0.85:
        tip = hex_lin("#2E4A24")[:3]
    else:
        tip = hex_lin("#7A6F35")[:3]
    return root, tip


# ---------------- v3 生成器 ----------------
m_tuft = make_vcol_mat("PE_GrassTuft", "#FFFFFF", rough=1.0)
m_trunk = make_mat("PE_Trunk", "#332A24", rough=0.9)
m_twig = make_mat("PE_Twig", "#2E2620", rough=0.9)
m_pinefol = make_vcol_mat("PE_PineFoliage", "#1B3830", rough=0.9)
m_willow = make_vcol_mat("PE_WillowFiber", "#FFFFFF", rough=0.95)
m_pump = make_vcol_mat("PE_Pumpkin", "#C87419", rough=0.42)
m_pump_deep = make_vcol_mat("PE_PumpkinDeep", "#A8541E", rough=0.42)
m_pump_pale = make_vcol_mat("PE_PumpkinPale", "#D9C9A8", rough=0.5)
m_cavity = make_mat("PE_PumpCavity", "#100A06", rough=1.0)
m_glow = make_mat("PE_PumpGlow", "#2A1608", rough=0.8, emit="#FFC46B", strength=7.0)
m_stem = make_mat("PE_PumpStem", "#4A4030", rough=0.9)
m_leaf = make_vcol_mat("PE_VineLeaf", "#FFFFFF", rough=0.75)
m_petal = make_vcol_mat("PE_Petal", "#FFFFFF", rough=0.55)
m_core = make_mat("PE_Core", "#2A1608", rough=0.8, emit="#FFE9C4", strength=1.4)
m_mushcap = make_mat("PE_MushCap", "#6E5AA6", rough=0.75)
m_mushgill = make_mat("PE_MushGill", "#6B4FA8", rough=0.8, emit="#B08BFF", strength=0.25)
m_mushspot = make_mat("PE_MushSpot", "#6B4FA8", rough=0.8, emit="#B08BFF", strength=0.35)
m_mushstem = make_mat("PE_MushStem", "#D8CFE2", rough=0.85)
m_straw = make_vcol_mat("PE_StrawV", "#FFFFFF", rough=0.95)
m_hay = make_vcol_mat("PE_Hay", "#8A6A2E", rough=0.95)   # 稻草本色 × 灰阶vcol (白底会渲成发光白团, 踩坑)
m_moss = make_vcol_mat("PE_GroundMoss", "#16251B", rough=1.0)
m_litter = make_vcol_mat("PE_LeafLitter", "#43301B", rough=1.0)
m_ground = make_mat("PE_Ground", "#0A0D12", rough=0.95)
m_cloth = make_mat("PE_Cloth", "#5A4A3A", rough=0.95)   # 麻布棕 (紫灰在夜光下发玩具感)
m_wood = make_mat("PE_Wood", "#4A3526", rough=0.85)
m_dot = [make_mat(f"PE_Dot{i}", c, emit=c, strength=2.6)
         for i, c in enumerate(("#FFE9C4", "#FFA53B", "#9B5BFF", "#8CFF4A"))]

ROOT_TONE = hex_lin("#0B1D14")[:3]


def tuft_v3(name, x, y, scale=1.0, n=None):
    """草丛 v3: 根盘 + 7±2 弯曲叶"""
    add_sphere(f"{name}_root", 0.1 * scale, (x, y, 0.012), mat=m_ground, seg=8, ring=4,
               scale=(1.0, 1.0, 0.24), sm=False)
    n = n or random.randint(6, 9)
    for b in range(n):
        a = random.uniform(0, 2 * pi)
        blen = random.uniform(0.26, 0.48) * scale
        if random.random() < 0.16:
            blen *= 1.5   # 抽穗长叶
        bw = random.uniform(0.02, 0.03) * scale
        bend = random.uniform(0.55, 1.15)
        root, tip = blade_tone()
        blade(f"{name}_b{b}", (x, y, 0.01), blen, bw, a, bend, m_tuft,
              root, tip, lean=random.uniform(0.12, 0.32), twist=random.uniform(-0.5, 0.5))


def ground_patch(name, x, y, r, mat, tone_lo=0.62, tone_hi=1.0):
    """有机边缘地斑: 波形圆盘 + 顶点色斑驳 (打破纯黑地面)"""
    vs = [(x, y, 0.011)]
    fs = []
    nseg = 22
    wob = [(random.uniform(-1, 1), random.uniform(-1, 1)) for _ in range(3)]
    ring = []
    for k in range(nseg):
        a = 2 * pi * k / nseg
        rr = r * (1 + 0.22 * wob[0][0] * sin(3 * a + wob[0][1] * 6.28)
                  + 0.12 * wob[1][0] * sin(7 * a + wob[1][1] * 6.28))
        ring.append((x + rr * cos(a), y + rr * sin(a), 0.011))
    vs += ring
    for k in range(nseg):
        fs.append((0, 1 + k, 1 + (k + 1) % nseg))
    ob = _new_obj(name, vs, fs, mat, False)
    vcol = []
    for i in range(len(vs)):
        d = hypot(vs[i][0] - x, vs[i][1] - y) / max(r, 1e-4)
        g = tone_hi - (tone_hi - tone_lo) * d * random.uniform(0.6, 1.1)
        g = max(tone_lo, min(tone_hi, g))
        vcol.append((g, g, g))
    set_vcol(ob, vcol)
    return ob


def litter_at(name, x, y, r=0.55):
    """树根落叶圈: 腐叶地斑 + 散叶小片"""
    ground_patch(f"{name}_patch", x, y, r, m_litter, 0.5, 0.95)
    for k in range(5):
        a = random.uniform(0, 2 * pi)
        rr = random.uniform(0.25, 0.9) * r
        px_, py_ = x + rr * cos(a), y + rr * sin(a)
        add_box(f"{name}_leaf{k}", (0.09, 0.06, 0.004), (px_, py_, 0.016),
                rot=(random.uniform(-0.15, 0.15), random.uniform(-0.15, 0.15),
                     random.uniform(0, pi)), mat=m_litter)


def pumpkin_body(name, C, rx, rz, seg, ring, mat, lobes=8, amp=0.09):
    """瓣纹南瓜体: 径向正弦瓣 + 底部压扁 + 顶肩内收, 瓣谷顶点色压暗"""
    vs, vcol, norm = [], [], []
    for j in range(ring + 1):
        phi = pi * j / ring
        sp, cp = sin(phi), cos(phi)
        for i in range(seg):
            th = 2 * pi * i / seg
            lobe = 1 + amp * sin(lobes * th) * (sp ** 1.4)
            px_ = rx * sp * cos(th) * lobe
            py_ = rx * sp * sin(th) * lobe
            pz_ = rz * cp
            if pz_ < 0:
                pz_ *= 0.8            # 底部压扁
            if phi < 0.42:
                pz_ *= 0.94           # 顶肩内收 (蒂坑)
            vs.append((C[0] + px_, C[1] + py_, C[2] + pz_))
            g = 0.58 + 0.42 * ((0.5 + 0.5 * sin(lobes * th)) ** 0.65)
            g *= 0.8 if cp < -0.2 else 1.0
            g *= random.uniform(0.96, 1.04)
            vcol.append((g, g, g))
    fs = []
    for j in range(ring):
        r0, r1 = j * seg, (j + 1) * seg
        for i in range(seg):
            i2 = (i + 1) % seg
            fs.append((r0 + i, r1 + i, r1 + i2, r0 + i2))
    ob = _new_obj(name, vs, fs, mat, True)
    set_vcol(ob, vcol)
    return ob


def bowl(name, C, R, phi_lo, phi_hi, mat, seg=16, ring=5):
    """开口碗面 (腔体/内焰): 绕朝向 +f 的球带, phi 自 +f 轴量起"""
    vs = []
    for j in range(ring + 1):
        phi = phi_lo + (phi_hi - phi_lo) * j / ring
        sp, cp = sin(phi), cos(phi)
        for i in range(seg):
            az = 2 * pi * i / seg
            d = f_axis * cp + (up_axis * cos(az) + rt_axis * sin(az)) * sp
            vs.append((C[0] + d.x * R, C[1] + d.y * R, C[2] + d.z * R))
    fs = []
    for j in range(ring):
        r0, r1 = j * seg, (j + 1) * seg
        for i in range(seg):
            i2 = (i + 1) % seg
            fs.append((r0 + i, r1 + i, r1 + i2, r0 + i2))
    return _new_obj(name, vs, fs, mat, True)


def prism(name, poly2d, origin, fdir, rt, up, near, far, mat):
    """棱柱切割器: poly2d = 面平面内 (right, up) 多边形, 沿 fdir 从 near 到 far"""
    n = len(poly2d)
    # 强制 CCW: 镜像多边形是 CW, 破坏 EXACT 布尔求解器的流形判定 (踩坑: 前脸被整块吃掉)
    area2 = sum(poly2d[i][0] * poly2d[(i + 1) % n][1]
                - poly2d[(i + 1) % n][0] * poly2d[i][1] for i in range(n))
    if area2 < 0:
        poly2d = poly2d[::-1]
    o = Vector(origin)
    vs = []
    for rr, uu in poly2d:
        vs.append(tuple(o + fdir * near + rt * rr + up * uu))
    for rr, uu in poly2d:
        vs.append(tuple(o + fdir * far + rt * rr + up * uu))
    n = len(poly2d)
    fs = []
    for i in range(n):
        j = (i + 1) % n
        fs.append((i, j, n + j, n + i))
    fs.append(tuple(range(n - 1, -1, -1)))
    fs.append(tuple(range(n, 2 * n)))
    return _new_obj(name, vs, fs, mat, False)


FACES = {
    "classic": {
        "eyes": [[(-0.155, 0.045), (-0.055, 0.045), (-0.105, 0.15)],
                 [(0.155, 0.045), (0.055, 0.045), (0.105, 0.15)]],
        "mouth": [(-0.17, -0.02), (-0.125, 0.05), (-0.08, -0.01), (-0.04, 0.05),
                  (0.0, -0.01), (0.04, 0.05), (0.08, -0.01), (0.125, 0.05),
                  (0.17, -0.02), (0.11, -0.115), (-0.11, -0.115)],
    },
    "scowl": {
        "eyes": [[(-0.17, 0.02), (-0.06, 0.09), (-0.16, 0.12)],
                 [(0.17, 0.02), (0.06, 0.09), (0.16, 0.12)]],
        "mouth": [(-0.15, -0.02), (-0.10, -0.075), (-0.05, -0.03), (0.0, -0.075),
                  (0.05, -0.03), (0.10, -0.075), (0.15, -0.02), (0.08, -0.13),
                  (-0.08, -0.13)],
    },
    "cute": {
        "eyes": [[(-0.15, 0.06), (-0.07, 0.06), (-0.055, 0.10), (-0.13, 0.10)],
                 [(0.15, 0.06), (0.07, 0.06), (0.055, 0.10), (0.13, 0.10)]],
        "mouth": [(cos(2 * pi * k / 8) * 0.062, sin(2 * pi * k / 8) * 0.055 - 0.055)
                  for k in range(8)],
    },
}


def pumpkin_v3(name, x, y, s=1.0, ry=0.0, body="round", mat=None, face="classic"):
    """南瓜 v3: 瓣纹体 + 真实雕空脸 (boolean) + 暗腔 + 内焰 + 弯蒂"""
    global f_axis, rt_axis, up_axis
    sz = {"round": 0.86, "tall": 1.06, "flat": 0.68}[body]
    mat = mat or m_pump
    C = Vector((x, y, 0.34 * s * sz * 0.92))
    rx, rz = 0.34 * s, 0.34 * s * sz
    body_ob = pumpkin_body(f"{name}_body", C, rx, rz, 20, 12, mat, lobes=8, amp=0.075)
    tint = random.uniform(0.9, 1.04)   # 逐实例明度差
    attr = body_ob.data.color_attributes[0]
    n_c = len(attr.data) * 4
    buf = [0.0] * n_c
    attr.data.foreach_get("color", buf)
    attr.data.foreach_set("color", [c * tint if i % 4 < 3 else 1.0
                                    for i, c in enumerate(buf)])

    # 面朝向标架
    f_axis = Vector((cos(ry), sin(ry), 0.0))
    rt_axis = Vector((-sin(ry), cos(ry), 0.0))
    up_axis = Vector((0, 0, 1))
    spec = FACES[face]
    cutters = []
    ci = 0
    for poly in spec["eyes"]:
        ci += 1
        prism(f"{name}_cut_e{ci}", [(r_ * s, u_ * s) for r_, u_ in poly],
              C, f_axis, rt_axis, up_axis, -0.6 * s, 0.5 * s, None)
        cutters.append(col.objects[f"{name}_cut_e{ci}"])
    ci += 1
    prism(f"{name}_cut_m", [(r_ * s, u_ * s) for r_, u_ in spec["mouth"]],
          C, f_axis, rt_axis, up_axis, -0.6 * s, 0.5 * s, None)
    cutters.append(col.objects[f"{name}_cut_m"])

    # 逐个 EXACT 雕刻 — 合并多腔切割器会让求解器崩坏(吐空网格/残尾, 踩坑)
    for cob in cutters:
        mod = body_ob.modifiers.new("carve", 'BOOLEAN')
        mod.operation = 'DIFFERENCE'
        mod.solver = 'EXACT'
        mod.object = cob
        dg = bpy.context.evaluated_depsgraph_get()
        me_new = bpy.data.meshes.new_from_object(body_ob.evaluated_get(dg))
        body_ob.modifiers.remove(mod)
        old = body_ob.data
        body_ob.data = me_new
        bpy.data.meshes.remove(old)
        bpy.data.objects.remove(cob, do_unlink=True)

    # 暗腔碗 (开口朝脸) + 内焰碗 (贴腔背, 自发光)
    bowl(f"{name}_cav", C, 0.30 * s * min(sz, 1.0), radians(72), radians(180), m_cavity, 18, 6)
    bowl(f"{name}_flame", C, 0.283 * s * min(sz, 1.0), radians(95), radians(178), m_glow, 14, 4)

    # 弯蒂 (S 曲线锥管, 短钝不刺天)
    top = C + Vector((0, 0, rz * 0.96))
    sway = Vector((cos(ry + pi / 2), sin(ry + pi / 2), 0))
    pts = [top + Vector((0, 0, 0.015 * s)),
           top + sway * 0.03 * s + Vector((0, 0, 0.055 * s)),
           top + sway * 0.07 * s + Vector((0, 0, 0.09 * s)),
           top + sway * 0.11 * s + Vector((0, 0, 0.115 * s))]
    tube_frustum(f"{name}_stem", pts,
                 [0.042 * s, 0.036 * s, 0.028 * s, 0.02 * s], m_stem, sides=7)
    return body_ob


def vine_link(name, p1, p2, s=1.0, leaves=2):
    """藤蔓: 贴地起伏管 + 嫩叶"""
    p1, p2 = Vector(p1), Vector(p2)
    pts = []
    for k in range(6):
        t = k / 5
        p = p1.lerp(p2, t)
        p.z = 0.015 + 0.035 * sin(t * pi)
        perp = Vector((-(p2.y - p1.y), p2.x - p1.x, 0)).normalized()
        p = p + perp * (0.06 * sin(t * 6.28))
        pts.append(p)
    tube_frustum(f"{name}_vine", pts, [0.018 * s] * 6, m_stem, sides=5, cap_end_fan=False)
    for k in range(leaves):
        t = 0.25 + 0.5 * k
        lp = pts[1 + int(min(t, 0.98) * 4)]
        a = random.uniform(0, 2 * pi)
        leaf(f"{name}_lf{k}", lp, a, 0.3 * s)


def leaf(name, base, yaw, size=0.16):
    """弯拱叶片: 复用草叶弯带生成器 (自建拱带会渲成小帐篷, 踩坑)"""
    rc = hex_lin("#1E3618")[:3]
    tc = hex_lin("#4E7A32")[:3]
    return blade(name, base, size, size * 0.3, yaw, random.uniform(0.65, 0.95),
                 m_leaf, rc, tc, lean=0.75, twist=random.uniform(-0.35, 0.35))


def dead_tree_v3(name, x, y, scale=1.0, variant="weep"):
    """枯树 v3: S 弯多段锥干 + 板根 + 递归弯枝(连续变径+尖梢)"""
    h = 3.1 * scale

    def curve_pts(base, dirv, length, segs, wobble=0.24, drift=0.5):
        pts = [Vector(base)]
        d = Vector(dirv).normalized()
        p = pts[0].copy()
        for i in range(segs):
            d = (d + Vector((random.uniform(-drift, drift) * 0.4,
                             random.uniform(-drift, 0) * 0.4,
                             random.uniform(-0.12, 0.10)))).normalized()
            d.z = max(d.z, -0.2)
            p = p + d * (length / segs)
            pts.append(p.copy())
        return pts

    # 板根 x5
    for rf in range(5):
        a = rf * 2 * pi / 5 + random.uniform(-0.3, 0.3)
        outw = Vector((cos(a), sin(a), 0))
        base = Vector((x, y, 0)) + outw * 0.1
        end = Vector((x, y, 0)) + outw * random.uniform(0.7, 1.0) * scale + Vector((0, 0, -0.02))
        mid = Vector((x, y, 0.5 * scale)).lerp(end, 0.55)
        mid.z = 0.16 * scale
        tube_frustum(f"{name}_root{rf}", [base, mid, end],
                     [0.14 * scale, 0.08 * scale, 0.02 * scale], m_trunk, sides=6)

    # 主干: S 弯 7 段
    trunk_pts = curve_pts((x, y, 0), (random.uniform(-0.2, 0.2), random.uniform(-0.2, 0.2), 1.0),
                          h, 7, drift=0.45)
    r0 = 0.26 * scale
    radii = [r0 * (0.82 ** i) for i in range(len(trunk_pts))]
    trunk_ob = tube_frustum(f"{name}_trunk", trunk_pts, radii, m_trunk, sides=8)

    # 枝条递归
    def grow(prefix, base, dirv, length, radius, depth):
        pts = curve_pts(base, dirv, length, 3 if depth >= 2 else 2, drift=0.7)
        radii = [radius * (0.72 ** i) for i in range(len(pts))]
        mat = m_trunk if depth >= 2 else m_twig
        tube_frustum(f"{prefix}", pts, radii, mat, sides=7 if depth >= 2 else 5)
        if depth == 0:
            return
        tip = pts[-1]
        dlast = (pts[-1] - pts[-2]).normalized()
        n_child = 2 if depth <= 1 else random.randint(2, 3)
        for k in range(n_child):
            a = random.uniform(0, 2 * pi)
            tilt = random.uniform(0.45, 0.85)
            nd = (dlast + Vector((cos(a) * tilt, sin(a) * tilt,
                                  random.uniform(-0.15, 0.55)))).normalized()
            if variant == "weep" and depth <= 1:
                nd = (nd + Vector((0, 0, -1.1))).normalized()
            grow(f"{prefix}_{k}", tip, nd, length * random.uniform(0.58, 0.74),
                 radius * 0.52, depth - 1)

    top = trunk_pts[-1]
    for b in range(4):
        a = b * 2 * pi / 4 + random.uniform(-0.5, 0.5)
        d = Vector((cos(a) * 0.7, sin(a) * 0.7, random.uniform(0.8, 1.3))).normalized()
        grow(f"{name}_b{b}", top - (top - Vector((x, y, h * 0.78))) * 0.0, d,
             1.7 * scale, 0.085 * scale, 3)
    # 中干侧枝 x2
    for b in range(2):
        i_ = 3 + b
        a = random.uniform(0, 2 * pi)
        d = Vector((cos(a) * 0.9, sin(a) * 0.9, random.uniform(0.3, 0.7))).normalized()
        grow(f"{name}_m{b}", trunk_pts[i_], d, 1.0 * scale, 0.05 * scale, 2)
    litter_at(f"{name}_lit", x, y, 0.9 * scale)
    tuft_n = random.randint(2, 3)
    for t_ in range(tuft_n):
        a = random.uniform(0, 2 * pi)
        rr = random.uniform(0.5, 1.0) * scale
        tuft_v3(f"{name}_t{t_}", x + rr * cos(a), y + rr * sin(a), 0.8)


def pine_v2(name, x, y, variant="tall", lit=True):
    """缠灯松 v2: 锯齿噪声锥层 (独立针叶材质) + 垂沿裙边"""
    if variant == "tall":
        layers = ((1.9, 1.7), (1.5, 2.6), (1.15, 3.5), (0.8, 4.35), (0.45, 5.1))
    elif variant == "fat":
        layers = ((2.5, 1.5), (1.9, 2.45), (1.25, 3.3), (0.7, 4.0))
    else:
        layers = ((2.0, 1.6), (1.55, 2.5), (1.05, 3.35), (0.6, 4.1))
    lean_a = random.uniform(0, 2 * pi)
    lean = 0.2 if variant == "crooked" else 0.0
    add_cyl(f"{name}_trunk", 0.15, 2.4, (x, y, 1.2), mat=m_trunk, verts=7)
    ph = random.uniform(0, pi)
    for li, (cr, cz) in enumerate(layers):
        ox, oy = lean * cz * cos(lean_a), lean * cz * sin(lean_a)
        seg, ring = 14, 5
        vs, vcol = [], []
        hl = 1.55   # 层高: 锥体要够高, 矮了成「飞碟」(踩坑)
        for j in range(ring + 1):
            t = j / ring
            for i in range(seg):
                a = 2 * pi * i / seg + li * 0.6 + ph
                rr_ = cr * (1 - t * 0.96) * (1 + 0.14 * sin(7 * a + li * 1.7))
                if j == 0:
                    rr_ *= 1.12   # 底缘裙边外翻
                px_ = rr_ * cos(a)
                py_ = rr_ * sin(a)
                pz_ = cz + 0.1 + t * hl + (0.3 * cr * (t - 1))   # 底缘下垂 + 层间叠压
                vs.append((x + ox + px_, y + oy + py_, pz_))
                g = 0.55 + 0.45 * t
                vcol.append((g, g, g))
        fs = []
        for j in range(ring):
            r0, r1 = j * seg, (j + 1) * seg
            for i in range(seg):
                i2 = (i + 1) % seg
                if j == ring - 1:
                    fs.append((r0 + i, r1 + i, r1 + i2))
                else:
                    fs.append((r0 + i, r1 + i, r1 + i2, r0 + i2))
        ob = _new_obj(f"{name}_l{li}", vs, fs, m_pinefol, True)
        set_vcol(ob, vcol)
    if lit:
        for k in range(10):
            th2 = k * 2 * pi / 10
            li = k % len(layers)
            cr, cz = layers[li]
            rr_ = cr * 0.85
            t_d = (1 - 0.85) / 0.96
            pz_ = cz + 0.1 + t_d * 1.55 + 0.3 * cr * (t_d - 1)
            ox, oy = lean * cz * cos(lean_a), lean * cz * sin(lean_a)
            add_sphere(f"{name}_dot{k}", 0.07,
                       (x + ox + rr_ * cos(th2), y + oy + rr_ * sin(th2), pz_),
                       mat=m_dot[k % 4], seg=8, ring=5)
    tuft_v3(f"{name}_t0", x + 0.9, y - 0.4, 0.75)
    litter_at(f"{name}_lit", x, y, 0.7)


def willow_v2(name, x, y, scale=1.0):
    """垂柳 v2: 弯 lean 干 + 锥形垂飘带 (顶点色渐变)"""
    h = 3.3 * scale
    lean_a = random.uniform(0, 2 * pi)
    ld = Vector((cos(lean_a) * 0.4, sin(lean_a) * 0.4, 1)).normalized()
    pts = [Vector((x, y, 0))]
    p = pts[0].copy()
    for i in range(4):
        ld = (ld + Vector((random.uniform(-0.1, 0.1), random.uniform(-0.1, 0.1), 0))).normalized()
        p = p + ld * (h / 4)
        pts.append(p.copy())
    tube_frustum(f"{name}_trunk", pts,
                 [0.2 * scale, 0.165 * scale, 0.13 * scale, 0.1 * scale, 0.07 * scale],
                 m_trunk, sides=8)
    crown = pts[-1]
    for b in range(3):   # 顶部上翘短枝
        a = random.uniform(0, 2 * pi)
        d = Vector((cos(a), sin(a), 0.9)).normalized()
        tube_frustum(f"{name}_up{b}", [crown, crown + d * (1.0 * scale)],
                     [0.05 * scale, 0.015 * scale], m_trunk, sides=5)
    # 飘带挂点沿上干分布 (只挂顶=棕榈观感, 踩坑)
    anchors = [pts[2] + Vector((0, 0, 0.1)), pts[3] + Vector((0, 0, 0.05)), crown]
    for s_ in range(36):
        a = random.uniform(0, 2 * pi)
        anchor = anchors[s_ % len(anchors)]
        rr_ = random.uniform(0.1, 0.5) * scale
        base = anchor + Vector((cos(a) * rr_, sin(a) * rr_, random.uniform(0.0, 0.3)))
        d = Vector((cos(a) * 0.85, sin(a) * 0.85, random.uniform(0.05, 0.25))).normalized()
        segs = 8
        step = random.uniform(0.22, 0.32) * scale
        rows = []
        p = base.copy()
        axis = d.cross(Vector((0, 0, 1))).normalized()
        for i in range(segs + 1):
            t = i / segs
            dd = (d + Vector((0, 0, -2.2 * t ** 1.1))).normalized()
            w = 0.045 * scale * (1 - t) ** 0.8 + 0.004
            rows.append((p - axis * w, p + axis * w, t))
            p = p + dd * step
        vs = []
        vcol = []
        rc = hex_lin("#14201A")[:3]
        tc = hex_lin("#3E5242")[:3]
        for l, r, t in rows:
            vs += [tuple(l), tuple(r)]
            tt = t ** 0.8
            c = [rc[k] + (tc[k] - rc[k]) * tt for k in range(3)]
            vcol += [c, c]
        fs = []
        for i in range(segs):
            a_, b_ = i * 2, i * 2 + 1
            fs.append((a_, b_, b_ + 2))
            fs.append((a_, b_ + 2, a_ + 2))
        ob = _new_obj(f"{name}_w{s_}", vs, fs, m_willow, False)
        set_vcol(ob, vcol)
    litter_at(f"{name}_lit", x, y, 0.8 * scale)


def flower_v2(name, x, y, violet=True, s=1.0):
    """花 v2: 弯茎 + 双叶 + 杯形 6 瓣 + 暖芯 (头要占得住画面, 茎宜短)"""
    h = 0.22 * s
    sway = random.uniform(-0.3, 0.3)
    tube_frustum(f"{name}_st", [(x, y, 0.01), (x + sway * 0.4, y, h * 0.5),
                                (x + sway, y + sway * 0.3, h)],
                 [0.013 * s, 0.01 * s, 0.007 * s], m_stem, sides=5)
    leaf(f"{name}_lf0", (x + sway * 0.2, y, h * 0.42), random.uniform(0, 2 * pi), 0.15 * s)
    head = Vector((x + sway, y + sway * 0.3, h))
    for k in range(6):
        a = k * 2 * pi / 6 + random.uniform(-0.08, 0.08)
        outw = Vector((cos(a), sin(a), 0))
        d0 = (outw * 0.55 + Vector((0, 0, 1)) * 0.8).normalized()
        axis = d0.cross(Vector((0, 0, 1))).normalized()
        rows = []
        p = head.copy()
        step = 0.055 * s
        for i in range(3):
            t = i / 2
            # 瓣尖内拢成杯: 外倾 → 上扬, 不外翻 (外翻=爪子观感, 踩坑)
            dd = (outw * (0.5 - 0.62 * t) + Vector((0, 0, 1)) * (0.7 + 0.5 * t)).normalized()
            w = 0.05 * s * (1 - t * 0.4)
            rows.append((p - axis * w, p + axis * w, t))
            p = p + dd * step
        rc, tc = (hex_lin("#6A3BB0")[:3], hex_lin("#B57BFF")[:3]) if violet \
            else (hex_lin("#C4701F")[:3], hex_lin("#FFB347")[:3])
        vs = []
        vcol = []
        for l, r, t in rows:
            vs += [tuple(l), tuple(r)]
            tt = t ** 0.9
            c = [rc[k] + (tc[k] - rc[k]) * tt for k in range(3)]
            vcol += [c, c]
        fs = []
        for i in range(2):
            a_, b_ = i * 2, i * 2 + 1
            fs.append((a_, b_, b_ + 2))
            fs.append((a_, b_ + 2, a_ + 2))
        ob = _new_obj(f"{name}_p{k}", vs, fs, m_petal, False)
        set_vcol(ob, vcol)
    add_sphere(f"{name}_ct", 0.028 * s, tuple(head + Vector((0, 0, 0.015))), mat=m_core,
               seg=7, ring=4)


def mushroom_v2(name, x, y, s=1.0):
    """发光蘑菇 v2: 波缘伞盖 + 菌褶发光底盘 + 弯柄 + 苔盘"""
    ground_patch(f"{name}_moss", x, y, 0.45 * s, m_moss, 0.6, 1.0)
    tilt = random.uniform(-0.2, 0.2)
    add_cyl(f"{name}_st", 0.035 * s, 0.26 * s, (x + tilt * 0.3, y, 0.13 * s),
            rot=(tilt, 0, 0), mat=m_mushstem, verts=7)
    capC = Vector((x + tilt * 0.55, y, 0.3 * s))
    vs, fs = [], []
    seg, ring = 14, 4
    ph = random.uniform(0, pi)
    for j in range(ring + 1):
        t = j / ring
        phi = pi * 0.5 * (0.25 + 0.75 * t)
        for i in range(seg):
            a = 2 * pi * i / seg + ph
            rr_ = 0.17 * s * sin(phi) * (1 + 0.14 * sin(5 * a))
            vs.append((capC.x + rr_ * cos(a), capC.y + rr_ * sin(a),
                       capC.z + 0.17 * s * cos(phi) * 0.6))
    for j in range(ring):
        r0, r1 = j * seg, (j + 1) * seg
        for i in range(seg):
            i2 = (i + 1) % seg
            fs.append((r0 + i, r1 + i, r1 + i2, r0 + i2))
    _new_obj(f"{name}_cap", vs, fs, m_mushcap, True)
    add_cyl(f"{name}_gill", 0.15 * s, 0.014 * s, tuple(capC - Vector((0, 0, 0.012 * s))),
            mat=m_mushgill, verts=14)
    for k in range(3):
        a = random.uniform(0, 2 * pi)
        add_sphere(f"{name}_spot{k}", 0.016 * s,
                   tuple(capC + Vector((0.1 * s * cos(a), 0.1 * s * sin(a), 0.06 * s))),
                   mat=m_mushspot, seg=6, ring=4)
    tuft_v3(f"{name}_t0", x + 0.35 * s, y + 0.2 * s, 0.5, n=3)


def haystack_v2(name, x, y):
    """干草堆 v2: 瓣纹圆垛 + 顶点色上浅下深 + 外露草叶"""
    ground_patch(f"{name}_g", x, y, 1.15, m_litter, 0.55, 0.9)
    dome = pumpkin_body(f"{name}_dome", (x, y, 0.36), 0.82, 0.42, 18, 8, m_hay,
                        lobes=6, amp=0.1)
    for k in range(20):
        a = random.uniform(0, 2 * pi)
        rr_ = random.uniform(0.55, 0.85)
        px_, py_ = x + rr_ * cos(a), y + rr_ * sin(a)
        tone = random.uniform(0.7, 1.3)
        c_lo = (hex_lin("#6E5426")[:3][0] * tone, hex_lin("#6E5426")[:3][1] * tone,
                hex_lin("#6E5426")[:3][2] * tone)
        c_hi = (hex_lin("#B8924A")[:3][0] * tone, hex_lin("#B8924A")[:3][1] * tone,
                hex_lin("#B8924A")[:3][2] * tone)
        blade(f"{name}_s{k}", (px_, py_, random.uniform(0.15, 0.5)),
              random.uniform(0.25, 0.45), 0.018, a + random.uniform(-0.6, 0.6),
              random.uniform(0.5, 1.0), m_straw, c_lo, c_hi,
              lean=random.uniform(0.4, 0.8))
    # 顶部草束
    for k in range(4):
        a = k * pi / 2 + 0.4
        blade(f"{name}_top{k}", (x + 0.2 * cos(a), y + 0.2 * sin(a), 0.72),
              0.4, 0.02, a, 0.8, m_straw, c_lo, c_hi, lean=0.5)


def scarecrow_v2(name, x, y, ry=0.0):
    """稻草人 v2: 原骨架 + 弯叶草束袖口/头顶草簇"""
    add_cyl(f"{name}_pole", 0.06, 2.0, (x, y, 1.0), mat=m_wood, verts=6)
    add_box(f"{name}_arms", (1.2, 0.07, 0.07), (x, y, 1.5), rot=(0, 0, ry), mat=m_wood)
    add_sphere(f"{name}_head", 0.2, (x, y, 2.05), mat=m_hay, seg=10, ring=7)
    add_cone_hat(name, x, y)
    add_box(f"{name}_body", (0.55, 0.3, 0.75), (x, y, 1.15), rot=(0, 0, ry), mat=m_cloth)
    for as_ in (-1, 1):
        px_ = x + cos(ry) * as_ * 0.6
        py_ = y + sin(ry) * as_ * 0.6
        for k in range(5):
            a = random.uniform(0, 2 * pi)
            tone = random.uniform(0.75, 1.2)
            lo = tuple(c * tone for c in hex_lin("#6E5426")[:3])
            hi = tuple(c * tone for c in hex_lin("#B8924A")[:3])
            blade(f"{name}_cuff{as_}_{k}", (px_, py_, 1.44),
                  random.uniform(0.28, 0.4), 0.016, a, random.uniform(0.7, 1.1),
                  m_straw, lo, hi, lean=0.5)
    for k in range(4):   # 头顶草簇
        a = k * pi / 2 + 0.5
        blade(f"{name}_hair{k}", (x + 0.12 * cos(a), y + 0.12 * sin(a), 2.2),
              0.3, 0.015, a, 0.9, m_straw, lo, hi, lean=0.6)
    litter_at(f"{name}_lit", x, y, 0.7)


def add_cone_hat(name, x, y):
    add_cyl(f"{name}_hatbrim", 0.34, 0.03, (x, y, 2.17), mat=m_cloth, verts=10)
    hz = 0.13
    vs = []
    for i in range(8):
        a = 2 * pi * i / 8
        vs.append((0.3 * cos(a), 0.3 * sin(a), -hz))
    vs.append((0, 0, hz))
    fs = [(i, (i + 1) % 8, 8) for i in range(8)]
    ob = _new_obj(f"{name}_hat", vs, fs, m_cloth, True)
    ob.location = (x, y, 2.3)


# ---------------- 布景: 5 个概念簇 ----------------
tmark("building clusters")

# -- A 草 (原点簇): 4 丛 + 苔斑
ground_patch("A_g0", 0.2, 0.3, 2.2, m_moss)
ground_patch("A_g1", -0.8, -0.6, 1.2, m_litter, 0.5, 0.9)
tuft_v3("A_t0", 0.0, 0.0, 1.15)
tuft_v3("A_t1", 0.75, 0.45, 0.95)
tuft_v3("A_t2", -0.55, 0.35, 1.05)
tuft_v3("A_t3", 0.3, -0.55, 0.8)
tuft_v3("A_t4", 1.15, -0.25, 1.2)

# -- B 南瓜 (x≈9): 大橙经典脸(朝相机 ry=atan2 对着 camB) + 深红 scowl + 淡青 cute + 藤叶
ground_patch("B_g0", 9.0, 0.2, 2.6, m_moss, 0.6, 1.0)
pumpkin_v3("B_p0", 8.6, -0.3, s=1.15, ry=radians(-50), body="round", mat=m_pump, face="classic")
pumpkin_v3("B_p1", 9.9, 0.35, s=0.85, ry=radians(-67), body="flat", mat=m_pump_deep, face="scowl")
pumpkin_v3("B_p2", 9.15, 1.35, s=0.6, ry=radians(-63), body="tall", mat=m_pump_pale, face="cute")
pumpkin_v3("B_p3", 7.7, 1.0, s=0.5, ry=radians(-47), body="round", mat=m_pump, face="classic")
vine_link("B_v0", (8.7, -0.65, 0), (9.7, 0.6, 0), s=1.0, leaves=3)
vine_link("B_v1", (9.0, 0.9, 0), (8.0, 1.2, 0), s=0.8, leaves=2)
tuft_v3("B_t0", 8.0, -0.9, 0.9)
tuft_v3("B_t1", 10.4, 1.0, 1.0)

# -- C 树 (x≈17-25): 枯树 weep + 缠灯松 crooked + 垂柳
dead_tree_v3("C_dead", 17.5, 0.3, scale=1.15, variant="weep")
pine_v2("C_pine", 20.8, 1.4, variant="crooked", lit=True)
willow_v2("C_will", 24.0, -0.8, scale=1.1)
ground_patch("C_g0", 19.5, 0, 4.5, m_moss, 0.55, 0.95)
tuft_v3("C_t0", 16.3, -0.9, 1.1)
tuft_v3("C_t1", 22.6, 0.9, 0.9)
tuft_v3("C_t2", 18.9, -1.4, 1.0)

# -- D 花+蘑菇 (x≈30-36): 花带一列 + 蘑菇圈
ground_patch("D_g0", 32.5, 0, 5.0, m_moss, 0.55, 0.9)
for k in range(6):
    flower_v2(f"D_fv{k}", 30.2 + k * 0.55 + random.uniform(-0.1, 0.1),
              -0.7 + (k % 2) * 0.45, violet=(k % 2 == 0), s=random.uniform(0.9, 1.2))
for k in range(5):
    flower_v2(f"D_fo{k}", 30.5 + k * 0.55, 0.8 + (k % 2) * 0.3, violet=False,
              s=random.uniform(0.85, 1.15))
ring_c = (34.5, -0.2)
ring_r = 1.05
for k in range(6):
    a = k * 2 * pi / 6 + 0.3
    mushroom_v2(f"D_m{k}", ring_c[0] + ring_r * cos(a), ring_c[1] + ring_r * sin(a),
                s=random.uniform(0.8, 1.25))

# -- E 农舍角 (x≈42-46): 干草堆 + 稻草人
ground_patch("E_g0", 44.0, 0, 4.0, m_litter, 0.5, 0.9)
haystack_v2("E_hay", 42.6, 0.4)
scarecrow_v2("E_sc", 45.4, -0.4, ry=radians(28))
tuft_v3("E_t0", 43.8, -1.1, 1.0)
tuft_v3("E_t1", 41.7, -0.5, 0.85)

# ---------------- 夜景灯光 / 世界 / 雾 / 相机 ----------------
tmark("lights & world")


def add_light(kind, name, loc, energy, color, target=None, size=4.0, angle=2.5, radius=0.2):
    ld = bpy.data.lights.new(name, kind)
    ld.energy = energy
    ld.color = hex_lin(color)[:3]
    ob = bpy.data.objects.new(name, ld)
    col.objects.link(ob)
    ob.location = loc
    if kind == 'SUN':
        ld.angle = radians(angle)
    if kind == 'AREA':
        ld.size = size
    if kind == 'POINT':
        ld.shadow_soft_size = radius
    if target:
        look_at(ob, target)
    try:
        ob.visible_camera = False   # 5.3 面光会被相机拍到成白墙 (踩坑)
    except Exception:
        pass
    return ob


def rig(cx, cy, warm=True, sun_energy=2.3, warm_energy=32.0):
    """标准夜机位光: 冷月主光 + 极光双色补 + 暖色点光"""
    add_light('SUN', f"L_sun_{cx}", (cx - 6, cy - 7, 9), sun_energy, "#B4C7FF",
              target=(cx, cy, 1.2), angle=3.5)
    add_light('AREA', f"L_ag_{cx}", (cx - 5, cy + 7, 8.5), 55, "#2FA97C",
              target=(cx, cy, 0.6), size=7)
    add_light('AREA', f"L_av_{cx}", (cx + 6, cy + 5, 7), 34, "#7A4FA8",
              target=(cx, cy, 0.8), size=6)
    if warm:
        add_light('POINT', f"L_wp_{cx}", (cx + 1.6, cy - 2.2, 1.15), warm_energy,
                  "#FFB24A", radius=0.3)
        add_light('POINT', f"L_wp2_{cx}", (cx - 2.4, cy + 1.8, 0.5), 10, "#FFD9A0",
                  radius=0.4)


# 地台 (每簇一块)
for cx in (0.5, 9.3, 20.5, 32.5, 44.0):
    add_cyl(f"GND_{cx}", 9.0, 0.05, (cx, 0, -0.028), mat=m_ground, verts=48, sm=False)

rig(0.5, 0.0, warm_energy=22)
rig(9.3, 0.4, warm_energy=42)
rig(20.5, 0.2, warm=False, sun_energy=2.6)
rig(32.5, 0.0, warm_energy=30)
rig(44.0, 0.0, warm_energy=34)

w = bpy.data.worlds.new("ConceptNight")
sc.world = w
w.use_nodes = True
ntw = w.node_tree
# 5.3 的 use_nodes 可能不自动建节点: 手工补齐 Background/Output/Volume (踩坑: StopIteration)
bg = next((n for n in ntw.nodes if n.type == "BACKGROUND"), None)
wout = next((n for n in ntw.nodes if n.type == "WORLD_OUTPUT"), None)
if wout is None:
    wout = ntw.nodes.new("ShaderNodeOutputWorld")
if bg is None:
    bg = ntw.nodes.new("ShaderNodeBackground")
    ntw.links.new(bg.outputs["Background"], wout.inputs["Surface"])
bg.inputs[0].default_value = hex_lin("#05070F")
bg.inputs[1].default_value = 0.5
# 体积雾: 挂 world (无表面风险; 盒式雾立方会以白面挡住相机 — 已踩坑)
wvol = ntw.nodes.new("ShaderNodeVolumePrincipled")
wvol.inputs["Density"].default_value = 0.0013
wvol.inputs["Color"].default_value = hex_lin("#9FB2D8")
wvol.inputs["Anisotropy"].default_value = 0.3
ntw.links.new(wvol.outputs["Volume"], wout.inputs["Volume"])

def add_cam(name, loc, target, lens=40):
    cd = bpy.data.cameras.new(name)
    cd.lens = lens
    ob = bpy.data.objects.new(name, cd)
    col.objects.link(ob)
    ob.location = loc
    look_at(ob, target)
    return ob


cams = {
    "concept_grass": add_cam("camA", (1.35, -1.75, 0.62), (0.1, 0.15, 0.3), lens=42),
    "concept_pumpkin": add_cam("camB", (11.3, -2.9, 1.35), (8.9, 0.35, 0.42), lens=44),
    "concept_trees": add_cam("camC", (20.2, -9.6, 1.75), (20.4, 0.5, 2.6), lens=30),
    "concept_flora": add_cam("camD", (31.6, -4.4, 1.0), (33.6, 0.1, 0.32), lens=38),
    "concept_farm": add_cam("camE", (43.4, -5.4, 1.45), (44.3, 0.0, 1.1), lens=36),
}

# 渲染设置: Cycles + AgX(Punchy) + 雾光合成 (模拟游戏 bloom)
sc.render.engine = 'CYCLES'
try:
    prefs = bpy.context.preferences.addons.get('cycles')
    if prefs:
        cp = prefs.preferences
        for dtype in ('OPTIX', 'CUDA', 'HIP'):
            try:
                cp.compute_device_type = dtype
                cp.get_devices()
                for d in cp.devices:
                    d.use = True
                sc.cycles.device = 'GPU'
                tmark(f"GPU on: {dtype}")
                break
            except Exception:
                continue
except Exception as e:
    tmark(f"gpu skip: {e}")
sc.cycles.samples = 80
sc.cycles.use_adaptive_sampling = True
sc.cycles.adaptive_threshold = 0.02
sc.cycles.use_denoising = True
sc.render.resolution_x = 1280
sc.render.resolution_y = 800
sc.render.film_transparent = False
try:
    sc.view_settings.view_transform = 'AgX'
    for lk in ('AgX - Punchy', 'Punchy'):
        try:
            sc.view_settings.look = lk
            break
        except Exception:
            continue
    sc.view_settings.exposure = 0.45
except Exception:
    sc.view_settings.view_transform = 'Filmic'

# 合成: FOG_GLOW ≈ 游戏 UnrealBloom (Blender 5 合成器组: RenderLayers→Glare→GroupOutput)
try:
    cnt = getattr(sc, "compositing_node_group", None)
    if cnt is None:
        cnt = bpy.data.node_groups.new("ConceptComp", 'CompositorNodeTree')
        sc.compositing_node_group = cnt
    cnt.nodes.clear()
    rl = cnt.nodes.new('CompositorNodeRLayers')
    rl.location = (-400, 0)
    gl = cnt.nodes.new('CompositorNodeGlare')
    gl.location = (-50, 0)
    try:
        gl.glare_type = 'FOG_GLOW'
        gl.threshold = 1.0   # 游戏 bloom strength 0.3 相当克制, 概念稿只留微光晕
        gl.size = 6
        gl.quality = 'MEDIUM'
    except Exception as e:
        tmark(f"glare props: {e}")
    try:
        cnt.interface.new_socket("Image", in_out='OUTPUT', socket_type='NodeSocketColor')
    except Exception:
        cnt.outputs.new('NodeSocketColor', 'Image')
    gout = cnt.nodes.new('NodeGroupOutput')
    gout.location = (300, 0)
    cnt.links.new(rl.outputs['Image'], gl.inputs['Image'])
    cnt.links.new(gl.outputs['Image'], gout.inputs['Image'])
except Exception as e:
    tmark(f"compositor skip ({e}); 渲染不带 bloom 模拟")
    try:
        sc.compositing_node_group = None
    except Exception:
        pass

tmark("render start")
import os
if os.environ.get("CONCEPT_DEBUG"):
    # 诊断模式: 只渲 cluster A 三视角, 低样本
    dbg = {
        "debugA_high": add_cam("camDbgH", (4.2, -5.2, 3.4), (0.3, 0.2, 0.2), lens=28),
        "debugA_low": add_cam("camDbgL", (-2.6, -2.2, 0.9), (0.5, 0.3, 0.35), lens=30),
        "debugA_back": add_cam("camDbgB", (-1.6, 3.4, 1.1), (0.6, -0.6, 0.3), lens=30),
    }
    sc.cycles.samples = 24
    # 诊断: 找出聚在 cluster A 中心的大物件 (先刷依赖图, matrix_world 才是真值)
    bpy.context.view_layer.update()
    for ob in bpy.context.scene.objects:
        bb = [ob.matrix_world @ Vector(c) for c in ob.bound_box]
        cx_ = sum(v.x for v in bb) / 8
        cy_ = sum(v.y for v in bb) / 8
        cz_ = sum(v.z for v in bb) / 8
        if abs(cx_ - 0.3) < 2.5 and abs(cy_ - 0.2) < 2.5 and cz_ < 3:
            dims = ob.dimensions
            print(f"[diag] {ob.type} {ob.name} at ({cx_:.2f},{cy_:.2f},{cz_:.2f}) "
                  f"dims=({dims.x:.2f},{dims.y:.2f},{dims.z:.2f})")
    for name, cam in dbg.items():
        sc.camera = cam
        sc.render.filepath = str(OUT / f"{name}.png")
        bpy.ops.render.render(write_still=True)
        tmark(f"rendered {name}")
    tmark("ALL DONE")
else:
    for name, cam in cams.items():
        sc.camera = cam
        sc.render.filepath = str(OUT / f"{name}.png")
        bpy.ops.render.render(write_still=True)
        tmark(f"rendered {name}")
    tmark("ALL DONE")
