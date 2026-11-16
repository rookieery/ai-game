# -*- coding: utf-8 -*-
"""
Ferris Wheel - Neon Night Style (game-ready glTF asset)
Run: blender --background --python ferris_wheel.py
All sizes in meters. Wheel spins around Y axis, cabins stay level.
"""
import bpy
import math
from math import radians, pi, cos, sin
from pathlib import Path
import numpy as np
from mathutils import Vector

# ---------------------------------------------------------------- params ---
P = {
    "wheel_radius": 12.0,      # wheel rim radius
    "rim_half_gap": 1.1,       # rim planes at y = +/- this
    "hub_z": 15.5,             # axle height above ground
    "inner_ring_r": 10.2,      # structural ring spokes attach to
    "platform_r": 9.0,
    "platform_h": 0.7,
    "ground_r": 70.0,
    "cabins": 12,
    "spokes_per_side": 12,
    "spin_period_s": 24.0,     # seconds per full revolution
    "fps": 30,
    "leg_base_x": 4.5,
    "leg_base_y": 2.2,
    "leg_top_x": 0.85,
    "leg_top_y": 1.6,
    "res_still": (1600, 900),
    "res_still_cycles": (1280, 720),
    "glass_alpha": 0.45,       # cabin glass transparency (1.0 = opaque)
}

HEX = {
    "pink":   "#FF2E88",
    "cyan":   "#00E5FF",
    "yellow": "#FFE600",
    "green":  "#7CFF00",
    "purple": "#B26BFF",
    "warm":   "#FFD9A0",
    "metal":  "#262B36",
    "metal_d":"#1E2330",
    "ground": "#0A0D16",
    "platform":"#161B27",
    "night":  "#060913",
}

def hex_lin(h, a=1.0):
    """sRGB hex -> linear RGBA tuple (Blender works in linear)."""
    h = h.lstrip("#")
    out = []
    for i in (0, 2, 4):
        c = int(h[i:i+2], 16) / 255.0
        out.append(c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4)
    return (*out, a)

ASSET_BLOOM = str(Path(bpy.app.binary_path).parent / "5.3" / "datafiles" /
                  "assets" / "nodes" / "compositing_nodes_essentials.blend")
OUT = Path(__file__).resolve().parent
PREV = OUT / "preview"

# ----------------------------------------------------------------- utils ---
def link_col(ob, col):
    for c in ob.users_collection:
        c.objects.unlink(ob)
    col.objects.link(ob)

def sock(node, ident):
    for s in node.inputs:
        if s.identifier == ident:
            return s
    return None

def make_mat(name, color, rough=0.5, metal=0.0, emit=None, strength=0.0,
             coat=0.0, alpha=1.0):
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    p = next(n for n in m.node_tree.nodes if n.type == "BSDF_PRINCIPLED")
    s = sock(p, "Base Color")
    if s: s.default_value = (*hex_lin(color)[:3], alpha)
    if alpha < 1.0:
        s = sock(p, "Alpha")
        if s: s.default_value = alpha
    s = sock(p, "Metallic")
    if s: s.default_value = metal
    s = sock(p, "Roughness")
    if s: s.default_value = rough
    if emit:
        s = sock(p, "Emission Color")
        if s: s.default_value = hex_lin(emit)
        s = sock(p, "Emission Strength")
        if s: s.default_value = strength
    if coat:
        s = sock(p, "Coat Weight")
        if s: s.default_value = coat
    return m

def smooth(ob):
    for poly in ob.data.polygons:
        poly.use_smooth = True

def add_cyl(name, r, depth, loc, rot=(0, 0, 0), mat=None, verts=16, sm=True, scale=(1, 1, 1)):
    bpy.ops.mesh.primitive_cylinder_add(radius=r, depth=depth, vertices=verts,
                                        location=loc, rotation=rot)
    ob = bpy.context.active_object
    ob.name = name
    ob.scale = scale
    if mat: ob.data.materials.append(mat)
    if sm: smooth(ob)
    return ob

def cyl_between(name, p1, p2, r, mat, verts=12, sm=True):
    p1, p2 = Vector(p1), Vector(p2)
    d = p2 - p1
    L = d.length
    bpy.ops.mesh.primitive_cylinder_add(radius=r, depth=1.0, vertices=verts,
                                        location=(p1 + p2) / 2)
    ob = bpy.context.active_object
    ob.name = name
    ob.scale = (1, 1, max(L, 1e-4))
    ob.rotation_euler = d.to_track_quat("Z", "Y").to_euler()
    if mat: ob.data.materials.append(mat)
    if sm: smooth(ob)
    return ob

def add_torus(name, R, tube, loc, rot=(0, 0, 0), mat=None, ms=64, ns=12):
    bpy.ops.mesh.primitive_torus_add(major_radius=R, minor_radius=tube,
                                     major_segments=ms, minor_segments=ns,
                                     location=loc, rotation=rot)
    ob = bpy.context.active_object
    ob.name = name
    if mat: ob.data.materials.append(mat)
    smooth(ob)
    return ob

def add_box(name, size, loc, rot=(0, 0, 0), mat=None):
    bpy.ops.mesh.primitive_cube_add(size=1.0, location=loc, rotation=rot)
    ob = bpy.context.active_object
    ob.name = name
    ob.scale = size
    if mat: ob.data.materials.append(mat)
    return ob

def add_bevel_box(name, size, loc, mat=None, segments=2, width=0.03, rot=(0, 0, 0)):
    ob = add_box(name, size, loc, rot=rot, mat=mat)
    bev = ob.modifiers.new("Bevel", "BEVEL")
    bev.width = width
    bev.segments = segments
    bev.limit_method = "ANGLE"
    try:
        bev.angle_limit = radians(40)
    except Exception:
        pass
    return ob

def add_sphere(name, r, loc, mat=None, seg=16, ring=10, scale=(1, 1, 1)):
    bpy.ops.mesh.primitive_uv_sphere_add(radius=r, segments=seg, ring_count=ring,
                                         location=loc)
    ob = bpy.context.active_object
    ob.name = name
    ob.scale = scale
    if mat: ob.data.materials.append(mat)
    smooth(ob)
    return ob

def add_empty(name, loc):
    bpy.ops.object.empty_add(type="PLAIN_AXES", location=loc)
    ob = bpy.context.active_object
    ob.name = name
    ob.empty_display_size = 0.6
    return ob

def parent_keep(child, parent):
    child.parent = parent
    child.matrix_parent_inverse = parent.matrix_world.inverted()

def look_at(ob, target):
    d = Vector(target) - ob.location
    ob.rotation_euler = d.to_track_quat("-Z", "Y").to_euler()

def obj_fcurves(ob):
    fcs = []
    ad = ob.animation_data
    if not ad or not ad.action:
        return fcs
    act = ad.action
    try:
        for layer in act.layers:
            for strip in layer.strips:
                for cb in strip.channelbags:
                    fcs.extend(cb.fcurves)
    except Exception as e:
        print("WARN fcurve access fallback:", type(e).__name__)
        try:
            fcs.extend(act.fcurves)
        except Exception:
            pass
    return fcs

# ---------------------------------------------------------------- build ----
bpy.ops.wm.read_factory_settings(use_empty=True)
sc = bpy.context.scene
sc.render.fps = P["fps"]
sc.frame_start = 1
spin_frames = int(P["spin_period_s"] * P["fps"])
sc.frame_end = spin_frames

col_static = bpy.data.collections.new("Static")
col_wheel  = bpy.data.collections.new("WheelSpin")
sc.collection.children.link(col_static)
sc.collection.children.link(col_wheel)

pal = [HEX["pink"], HEX["cyan"], HEX["yellow"], HEX["green"], HEX["purple"]]

# materials -------------------------------------------------------------
m_metal    = make_mat("FW_Metal", "#3A4152", rough=0.45, metal=0.85)
m_metal_d  = make_mat("FW_MetalDark", HEX["metal_d"], rough=0.6, metal=0.7)
m_ground   = make_mat("FW_Ground", HEX["ground"], rough=0.95)
m_platform = make_mat("FW_Platform", HEX["platform"], rough=0.55, metal=0.1)
m_rim_pink  = make_mat("FW_RimPink", HEX["pink"], rough=0.4, emit=HEX["pink"], strength=2.5)
m_rim_cyan  = make_mat("FW_RimCyan", HEX["cyan"], rough=0.4, emit=HEX["cyan"], strength=2.5)
m_dot = [make_mat(f"FW_Dot{i}", c, rough=0.4, emit=c, strength=3.0) for i, c in enumerate(pal)]
m_cabin = [make_mat(f"FW_Cabin{i}", c, rough=0.28, metal=0.05, emit=c, strength=0.45,
                    coat=0.6) for i, c in enumerate(pal)]
m_trim  = [make_mat(f"FW_Trim{i}", c, rough=0.4, emit=c, strength=2.0)
           for i, c in enumerate(pal)]
m_glass = make_mat("FW_Glass", "#142A3E", rough=0.06, metal=0.0, alpha=P["glass_alpha"])
try:
    m_glass.blend_method = "BLEND"
except Exception:
    pass
try:
    m_glass.surface_render_method = "BLENDED"
except Exception:
    pass
m_glow  = make_mat("FW_InteriorGlow", HEX["warm"], rough=0.5, emit=HEX["warm"], strength=2.2)
m_bench = make_mat("FW_Bench", "#1A1E28", rough=0.8)
m_lamp  = make_mat("FW_RoofLamp", HEX["warm"], rough=0.4, emit=HEX["warm"], strength=3.0)
m_edge_cyan = make_mat("FW_EdgeCyan", HEX["cyan"], rough=0.4, emit=HEX["cyan"], strength=3.0)
m_ring_pink   = make_mat("FW_RingPink", HEX["pink"], rough=0.4, emit=HEX["pink"], strength=2.2)
m_ring_purple = make_mat("FW_RingPurple", HEX["purple"], rough=0.4, emit=HEX["purple"], strength=1.8)
m_hub_glow = make_mat("FW_HubGlow", HEX["cyan"], rough=0.4, emit=HEX["cyan"], strength=3.0)

R = P["wheel_radius"]
G = P["rim_half_gap"]
HZ = P["hub_z"]

# ground & platform -----------------------------------------------------
add_cyl("FW_Ground", P["ground_r"], 0.2, (0, 0, -0.1), mat=m_ground, verts=64)
add_cyl("FW_Platform", P["platform_r"], P["platform_h"],
        (0, 0, P["platform_h"] / 2), mat=m_platform, verts=64)
add_torus("FW_EdgeRing", P["platform_r"] - 0.05, 0.07,
          (0, 0, P["platform_h"] + 0.02), mat=m_edge_cyan, ms=96, ns=10)
add_box("FW_Step1", (4.0, 1.2, 0.24), (0, -(P["platform_r"] + 0.6), 0.12), mat=m_platform)
add_box("FW_Step2", (4.0, 1.2, 0.24), (0, -(P["platform_r"] - 0.05), 0.40), mat=m_platform)
add_torus("FW_GroundRing1", 13.0, 0.045, (0, 0, 0.03), mat=m_ring_pink, ms=96, ns=8)
add_torus("FW_GroundRing2", 17.0, 0.045, (0, 0, 0.03), mat=m_ring_purple, ms=96, ns=8)
for i in range(10):
    th = i * pi / 5
    x, y = 9.9 * cos(th), 9.9 * sin(th)
    add_cyl(f"FW_Bollard{i}", 0.1, 0.45, (x, y, 0.225), mat=m_metal_d, verts=10)
    add_sphere(f"FW_BollardTop{i}", 0.09, (x, y, 0.52),
               mat=m_dot[i % len(m_dot)], seg=12, ring=8)

# support structure (static) ---------------------------------------------
lbx, lby, ltx, lty = P["leg_base_x"], P["leg_base_y"], P["leg_top_x"], P["leg_top_y"]
legs = {}
for sx in (1, -1):
    for sy in (1, -1):
        base = (sx * lbx, sy * lby, P["platform_h"])
        top = (sx * ltx, sy * lty, HZ)
        legs[(sx, sy)] = (base, top)
        ob = cyl_between(f"FW_Leg_{sx}_{sy}", base, top, 0.28, m_metal_d)
        link_col(ob, col_static)
        ob = add_cyl(f"FW_Foot_{sx}_{sy}", 0.5, 0.15, (sx * lbx, sy * lby, 0.075),
                     mat=m_metal_d, verts=12)
        link_col(ob, col_static)

def leg_point(sx, sy, t):
    base, top = legs[(sx, sy)]
    return tuple(Vector(base) + (Vector(top) - Vector(base)) * t)

# X ties between left/right leg pairs (front and back)
for sy in (1, -1):
    for t, rr in ((0.32, 0.14), (0.62, 0.14)):
        p1 = leg_point(-1, sy, t)
        p2 = leg_point(1, sy, t)
        ob = cyl_between(f"FW_TieX_{sy}_{int(t*100)}", p1, p2, rr, m_metal_d)
        link_col(ob, col_static)

# Y ties + X braces on each side pair
for sx in (1, -1):
    for t in (0.25, 0.5, 0.75):
        p1 = leg_point(sx, 1, t)
        p2 = leg_point(sx, -1, t)
        ob = cyl_between(f"FW_TieY_{sx}_{int(t*100)}", p1, p2, 0.11, m_metal_d)
        link_col(ob, col_static)
    for (t1, t2) in ((0.18, 0.55), (0.55, 0.85)):
        p1 = leg_point(sx, 1, t1)
        p2 = leg_point(sx, -1, t2)
        ob = cyl_between(f"FW_Brace_{sx}_{int(t1*100)}", p1, p2, 0.06, m_metal_d)
        link_col(ob, col_static)

# axle housings (static bearings)
for sy in (1, -1):
    add_cyl(f"FW_Housing_{sy}", 0.55, 0.8, (0, sy * 1.85, HZ),
            rot=(radians(90), 0, 0), mat=m_metal, verts=20)
    link_col(bpy.context.active_object, col_static)

# wheel (rotating) ---------------------------------------------------------
wheel = add_empty("FW_Wheel", (0, 0, HZ))
link_col(wheel, col_wheel)

def wheel_child(ob):
    parent_keep(ob, wheel)
    link_col(ob, col_wheel)

# rotating axle shaft
ob = add_cyl("FW_Axle", 0.3, 4.0, (0, 0, HZ), rot=(radians(90), 0, 0), mat=m_metal, verts=16)
wheel_child(ob)

# rims (glowing) + structural inner rings
ob = add_torus("FW_RimPlus", R, 0.18, (0, G, HZ), rot=(radians(90), 0, 0),
               mat=m_rim_pink, ms=72, ns=14)
wheel_child(ob)
ob = add_torus("FW_RimMinus", R, 0.18, (0, -G, HZ), rot=(radians(90), 0, 0),
               mat=m_rim_cyan, ms=72, ns=14)
wheel_child(ob)
for sy in (1, -1):
    ob = add_torus(f"FW_InnerRing_{sy}", P["inner_ring_r"], 0.14, (0, sy * G, HZ),
                   rot=(radians(90), 0, 0), mat=m_metal, ms=48, ns=10)
    wheel_child(ob)

# spokes
spokes_mid = {}
for sy in (1, -1):
    for k in range(P["spokes_per_side"]):
        th = k * 2 * pi / P["spokes_per_side"] + (pi / 12 if sy < 0 else 0)
        ix = P["inner_ring_r"] * cos(th)
        iz = HZ + P["inner_ring_r"] * sin(th)
        ob = cyl_between(f"FW_Spoke_{sy}_{k}", (0, sy * G, HZ), (ix, sy * G, iz),
                         0.11, m_metal)
        wheel_child(ob)
        spokes_mid[(sy, k)] = (0.5 * ix, sy * G, 0.5 * (HZ + iz))

# zigzag cross bracing between spoke planes
n_sp = P["spokes_per_side"]
for k in range(n_sp):
    p1 = spokes_mid[(1, k)]
    k2 = (k + 1) % n_sp
    p2 = spokes_mid[(-1, k2)]
    ob = cyl_between(f"FW_BraceSpoke_{k}", p1, p2, 0.05, m_metal)
    wheel_child(ob)

# rim struts (offset from cabin angles)
for k in range(24):
    th = (k + 0.5) * 2 * pi / 24
    x, z = R * cos(th), HZ + R * sin(th)
    ob = cyl_between(f"FW_Strut_{k}", (x, G, z), (x, -G, z), 0.07, m_metal)
    wheel_child(ob)

# hub discs + glow rings
for sy in (1, -1):
    ob = add_cyl(f"FW_HubDisc_{sy}", 1.25, 0.18, (0, sy * G, HZ),
                 rot=(radians(90), 0, 0), mat=m_metal, verts=24)
    wheel_child(ob)
    ob = add_torus(f"FW_HubGlow_{sy}", 1.15, 0.10, (0, sy * (G + 0.22), HZ),
                   rot=(radians(90), 0, 0), mat=m_hub_glow, ms=48, ns=10)
    wheel_child(ob)

# light dots along rims
n_dots = 36
for sy in (1, -1):
    for k in range(n_dots):
        th = k * 2 * pi / n_dots
        x, z = R * cos(th), HZ + R * sin(th)
        ob = add_sphere(f"FW_Dot_{sy}_{k}", 0.12, (x, sy * (G + 0.15), z),
                        mat=m_dot[k % len(m_dot)], seg=12, ring=8)
        wheel_child(ob)

# cabins -------------------------------------------------------------------
cabin_roots = []
for i in range(P["cabins"]):
    th = i * 2 * pi / P["cabins"]
    px, pz = R * cos(th), HZ + R * sin(th)
    pivot = add_empty(f"FW_Pivot_{i}", (px, 0, pz))
    parent_keep(pivot, wheel)
    link_col(pivot, col_wheel)

    root = add_empty(f"FW_CabinRoot_{i}", (px, 0, pz))
    parent_keep(root, pivot)
    link_col(root, col_wheel)
    cabin_roots.append((root, th))

    def cabin_part(ob):
        parent_keep(ob, root)
        link_col(ob, col_wheel)

    ci = i % len(m_cabin)
    paint = m_cabin[ci]
    trim = m_trim[ci]

    # crossbar connecting the two rims
    ob = cyl_between(f"FW_Crossbar_{i}", (px, -(G + 0.15), pz), (px, G + 0.15, pz),
                     0.055, m_metal)
    cabin_part(ob)
    # pivot joint + A-frame hanger arms
    ob = add_cyl(f"FW_Joint_{i}", 0.07, 0.16, (px, 0, pz - 0.12), mat=m_metal, verts=10)
    cabin_part(ob)
    ob = cyl_between(f"FW_ArmL_{i}", (px, 0, pz - 0.20), (px - 0.42, 0, pz - 0.70),
                     0.045, m_metal)
    cabin_part(ob)
    ob = cyl_between(f"FW_ArmR_{i}", (px, 0, pz - 0.20), (px + 0.42, 0, pz - 0.70),
                     0.045, m_metal)
    cabin_part(ob)
    # roof cap (thin) + neon eave trim + roof lamp
    ob = add_bevel_box(f"FW_Roof_{i}", (1.48, 0.96, 0.10), (px, 0, pz - 0.75),
                       mat=paint, segments=3, width=0.03)
    cabin_part(ob)
    ob = add_box(f"FW_RoofTrim_{i}", (1.52, 1.0, 0.04), (px, 0, pz - 0.82), mat=trim)
    cabin_part(ob)
    ob = add_sphere(f"FW_RoofLamp_{i}", 0.07, (px, 0, pz - 0.63), mat=m_lamp,
                    seg=12, ring=8)
    cabin_part(ob)
    # wraparound glass band (dominant, the actual wall between roof and body)
    ob = add_bevel_box(f"FW_Glass_{i}", (1.42, 0.90, 0.62), (px, 0, pz - 1.10),
                       mat=m_glass, segments=3, width=0.03)
    cabin_part(ob)
    # window frame: corner posts + mid mullions + transom bar
    for sx in (1, -1):
        for sy in (1, -1):
            ob = add_box(f"FW_Post_{i}_{sx}_{sy}", (0.07, 0.07, 0.64),
                         (px + sx * 0.72, sy * 0.47, pz - 1.10), mat=m_metal)
            cabin_part(ob)
    ob = add_box(f"FW_MullX_{i}", (0.05, 0.96, 0.64), (px, 0, pz - 1.10), mat=m_metal)
    cabin_part(ob)
    ob = add_box(f"FW_MullY_{i}", (1.48, 0.05, 0.64), (px, 0, pz - 1.10), mat=m_metal)
    cabin_part(ob)
    ob = add_box(f"FW_Transom_{i}", (1.46, 0.96, 0.045), (px, 0, pz - 0.97), mat=m_metal)
    cabin_part(ob)
    # interior: glowing ceiling + back wall + floor + bench silhouette
    ob = add_box(f"FW_GlowCeil_{i}", (1.30, 0.66, 0.04), (px, 0, pz - 0.84), mat=m_glow)
    cabin_part(ob)
    ob = add_box(f"FW_GlowWall_{i}", (1.30, 0.04, 0.52), (px, 0.37, pz - 1.10), mat=m_glow)
    cabin_part(ob)
    ob = add_box(f"FW_GlowFloor_{i}", (1.30, 0.62, 0.04), (px, 0, pz - 1.38), mat=m_glow)
    cabin_part(ob)
    ob = add_box(f"FW_BenchSeat_{i}", (0.70, 0.24, 0.08), (px, 0.16, pz - 1.24), mat=m_bench)
    cabin_part(ob)
    ob = add_box(f"FW_BenchBack_{i}", (0.70, 0.06, 0.26), (px, 0.30, pz - 1.10), mat=m_bench)
    cabin_part(ob)
    # lower body (clearcoat paint) + neon belt line + skirt + corner bumpers
    ob = add_bevel_box(f"FW_Body_{i}", (1.42, 0.92, 0.40), (px, 0, pz - 1.61),
                       mat=paint, segments=3, width=0.05)
    cabin_part(ob)
    ob = add_box(f"FW_TrimBelt_{i}", (1.46, 0.96, 0.06), (px, 0, pz - 1.47), mat=trim)
    cabin_part(ob)
    ob = add_box(f"FW_Skirt_{i}", (1.50, 0.98, 0.12), (px, 0, pz - 1.87), mat=m_metal_d)
    cabin_part(ob)
    for sx in (1, -1):
        for sy in (1, -1):
            ob = add_sphere(f"FW_Bumper_{i}_{sx}_{sy}", 0.06,
                            (px + sx * 0.70, sy * 0.44, pz - 1.87),
                            mat=m_metal, seg=10, ring=6)
            cabin_part(ob)

# lights, world, camera ------------------------------------------------------
bpy.ops.object.light_add(type="SUN", location=(25, -30, 55))
sun = bpy.context.active_object
sun.data.energy = 2.4
sun.data.color = hex_lin("#B4C7FF")[:3]
sun.data.angle = radians(6)
look_at(sun, (0, 0, 10))
link_col(sun, col_static)

bpy.ops.object.light_add(type="AREA", location=(0, -10, 16))
fill = bpy.context.active_object
fill.data.energy = 150
fill.data.size = 10
fill.data.color = hex_lin("#FF9A5C")[:3]
look_at(fill, (0, 0, 5))
link_col(fill, col_static)

w = bpy.data.worlds.new("Night")
sc.world = w
w.use_nodes = True
bg = next(n for n in w.node_tree.nodes if n.type == "BACKGROUND")
bg.inputs[0].default_value = hex_lin(HEX["night"])
bg.inputs[1].default_value = 0.35

def add_cam(name, loc, target, lens=50):
    bpy.ops.object.camera_add(location=loc)
    cam = bpy.context.active_object
    cam.name = name
    cam.data.lens = lens
    look_at(cam, target)
    link_col(cam, col_static)
    return cam

cam_front = add_cam("FW_CamFront", (0, -47, 17.0), (0, 0.5, 15.5), lens=35)
cam_three = add_cam("FW_CamThree", (33, -38, 20), (0, 0, 15.0), lens=38)
cam_side  = add_cam("FW_CamSide", (52, -4, 17), (0, 0, 15.5), lens=35)
# detail shot targets the cabin nearest to front-right-bottom
det_th = radians(-28)
def _ang_diff(a, b):
    return abs(((a - b + pi) % (2 * pi)) - pi)
best = min(range(P["cabins"]), key=lambda i: _ang_diff(cabin_roots[i][1], det_th))
cz = HZ + R * sin(cabin_roots[best][1])
cx = R * cos(cabin_roots[best][1])
cam_det = add_cam("FW_CamDetail", (cx + 7.0, -14.0, cz + 3.5), (cx, 0, cz - 1.2), lens=50)

sc.view_settings.view_transform = "Standard"
sc.view_settings.exposure = 0.15

# bloom (compositor effect, 5.3 API) ----------------------------------------
try:
    sc.use_nodes = True
    eff = sc.compositor_effects.new(name="Bloom")
    with bpy.data.libraries.load(ASSET_BLOOM, link=False) as (src, dst):
        dst.node_groups = [n for n in src.node_groups if "Bloom" == n]
    bloom = bpy.data.node_groups.get("Bloom")
    eff.node_group = bloom
    print("BLOOM_OK")
except Exception as e:
    print("BLOOM_FAIL", type(e).__name__, str(e)[:120])

# animation -------------------------------------------------------------------
wheel.rotation_euler.y = 0.0
wheel.keyframe_insert("rotation_euler", frame=1)
wheel.rotation_euler.y = 2 * pi
wheel.keyframe_insert("rotation_euler", frame=1 + spin_frames)

for root, _ in cabin_roots:
    root.rotation_euler.y = 0.0
    root.keyframe_insert("rotation_euler", frame=1)
    root.rotation_euler.y = -2 * pi
    root.keyframe_insert("rotation_euler", frame=1 + spin_frames)

def finalize_curves(ob):
    for fc in obj_fcurves(ob):
        for kp in fc.keyframe_points:
            kp.interpolation = "LINEAR"
        try:
            mod = fc.modifiers.new("CYCLES")
        except Exception:
            pass

finalize_curves(wheel)
for root, _ in cabin_roots:
    finalize_curves(root)

# save source + export glb -----------------------------------------------------
bpy.ops.wm.save_as_mainfile(filepath=str(OUT / "ferris_wheel.blend"))
print("BLEND_SAVED")

try:
    bpy.ops.export_scene.gltf(filepath=str(OUT / "ferris_wheel.glb"),
                              export_format="GLB", export_animations=True,
                              export_apply=True)
except (TypeError, RuntimeError) as e:
    print("GLTF_KWARG_FALLBACK", type(e).__name__)
    bpy.ops.export_scene.gltf(filepath=str(OUT / "ferris_wheel.glb"),
                              export_format="GLB")
print("GLB_EXPORTED")

# renders ----------------------------------------------------------------------
def brightness(path):
    try:
        img = bpy.data.images.load(str(path))
        w_, h_ = img.size
        px = np.empty(w_ * h_ * 4, dtype=np.float32)
        img.pixels.foreach_get(px)
        a = px.reshape(h_, w_, 4)
        mean = float(a[..., :3].mean())
        bpy.data.images.remove(img)
        return mean
    except Exception as e:
        print("CHECK_ERR", type(e).__name__, str(e)[:80])
        return -1.0

def set_engine_cycles(res, samples):
    sc.render.engine = "CYCLES"
    sc.cycles.samples = samples
    sc.cycles.use_denoising = True
    try:
        sc.cycles.denoiser = "OPENIMAGEDENOISE"
    except Exception:
        pass
    sc.cycles.device = "CPU"
    sc.render.resolution_x, sc.render.resolution_y = res

def render_still(name, cam):
    sc.camera = cam
    path = PREV / name
    sc.render.image_settings.media_type = "IMAGE"
    sc.render.image_settings.file_format = "PNG"
    sc.render.filepath = str(path)
    sc.render.resolution_x, sc.render.resolution_y = P["res_still"]
    sc.render.resolution_percentage = 100
    try:
        bpy.ops.render.render(write_still=True)
    except Exception as e:
        print("RENDER_FAIL", name, type(e).__name__, str(e)[:120])
        return False
    mean = brightness(path)
    print("CHECK", name, f"mean={mean:.4f}")
    return mean > 0.008

PREV.mkdir(exist_ok=True)
sc.render.engine = "BLENDER_EEVEE"
try:
    sc.eevee.taa_render_samples = 64
except Exception:
    pass

stills = [("01_front.png", cam_front), ("02_three_quarter.png", cam_three),
          ("03_side.png", cam_side), ("04_cabin_detail.png", cam_det)]
ok = True
for name, cam in stills:
    if not render_still(name, cam):
        ok = False

if not ok:
    print("FALLBACK_CYCLES")
    set_engine_cycles(P["res_still_cycles"], 64)
    for name, cam in stills:
        if not render_still(name, cam):
            print("STILL_FAILED_FINAL", name)

# video (5.3 API: media_type selects movie output)
sc.camera = cam_three
sc.render.image_settings.media_type = "VIDEO"
sc.render.image_settings.file_format = "FFMPEG"
sc.render.filepath = str(PREV / "spin_preview.mp4")
sc.render.ffmpeg.format = "MPEG4"
sc.render.ffmpeg.codec = "H264"
try:
    sc.render.ffmpeg.constant_rate_factor = "HIGH"
    sc.render.ffmpeg.ffmpeg_preset = "GOOD"
    sc.render.ffmpeg.audio_codec = "NONE"
except Exception:
    pass
if sc.render.engine == "BLENDER_EEVEE":
    sc.render.resolution_x, sc.render.resolution_y = (1280, 720)
    sc.frame_end = 181
else:
    sc.render.resolution_x, sc.render.resolution_y = (960, 540)
    sc.cycles.samples = 32
    sc.frame_end = 121
sc.render.filepath = str(PREV / "spin_preview.mp4")
try:
    bpy.ops.render.render(animation=True)
    print("VIDEO_OK")
except Exception as e:
    print("VIDEO_FAIL", type(e).__name__, str(e)[:160])

# report ------------------------------------------------------------------------
tris = 0
for ob in bpy.context.scene.objects:
    if ob.type == "MESH":
        me = ob.data
        me.calc_loop_triangles()
        tris += len(me.loop_triangles)
print(f"SUMMARY tris={tris} fps={P['fps']} frames={sc.frame_start}-{sc.frame_end}")
print("DONE")
