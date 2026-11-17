# -*- coding: utf-8 -*-
"""从 park_env.blend 区域级移除旋转木马占位剪影 + 横穿机台的灯串, 重导出 park_env.glb。
不重跑 park_env.py (random.uniform 无种子, 重跑会漂移干草/枯树)。
park_env 网格已按材质合并 (PE_PE_<mat>), 所以按空间区域删面:
  圆柱: 圆心 (45,18), 半径 7.0 — 罩住旧剪影 (r<=5.3) 与灯串 (41,14)->(49,22) (端点距心 5.66)。
  判据: 面的所有顶点都在圆柱内 (2D 距离) 才删 — 地面大盘无内部顶点不受影响。
Run: blender --background --python scripts/strip_carousel_placeholder.py
"""
import bpy
import bmesh
from math import sqrt
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CX, CY, CR = 45.0, 18.0, 7.0

bpy.ops.wm.open_mainfile(filepath=str(ROOT / "model/park_env/park_env.blend"))

# ---- 查询: 哪些对象在圆柱附近有顶点 ----
near = {}
for ob in bpy.context.scene.objects:
    if ob.type != "MESH":
        continue
    cnt = 0
    for v in ob.data.vertices:
        c = ob.matrix_world @ v.co
        if (c.x - CX) ** 2 + (c.y - CY) ** 2 < (CR + 0.5) ** 2:
            cnt += 1
    if cnt:
        near[ob.name] = cnt
print("NEAR_OBJECTS", sorted(near.items(), key=lambda kv: -kv[1]))

# ---- 区域删面: 面的全部顶点在圆柱内才删 ----
removed = 0
for ob in bpy.context.scene.objects:
    if ob.type != "MESH":
        continue
    bm = bmesh.new()
    bm.from_mesh(ob.data)
    mw = ob.matrix_world
    doomed = []
    for f in bm.faces:
        if all(((mw @ v.co).x - CX) ** 2 + ((mw @ v.co).y - CY) ** 2 < CR * CR
               for v in f.verts):
            doomed.append(f)
    if doomed:
        removed += len(doomed)
        bmesh.ops.delete(bm, geom=doomed, context="FACES")
        bm.to_mesh(ob.data)
        ob.data.update()
    bm.free()
print("FACES_REMOVED", removed)

# 删空对象
for ob in [o for o in bpy.context.scene.objects if o.type == "MESH" and not len(o.data.vertices)]:
    print("EMPTY_REMOVED", ob.name)
    bpy.data.objects.remove(ob, do_unlink=True)

bpy.ops.wm.save_as_mainfile(filepath=str(ROOT / "model/park_env/park_env.blend"))
print("BLEND_SAVED")

try:
    bpy.ops.export_scene.gltf(filepath=str(ROOT / "model/park_env/park_env.glb"),
                              export_format="GLB", export_apply=True)
except (TypeError, RuntimeError):
    bpy.ops.export_scene.gltf(filepath=str(ROOT / "model/park_env/park_env.glb"),
                              export_format="GLB")
print("GLB_EXPORTED")
tris = 0
for ob in bpy.context.scene.objects:
    if ob.type == "MESH":
        me = ob.data
        me.calc_loop_triangles()
        tris += len(me.loop_triangles)
print(f"SUMMARY tris={tris}")
print("DONE")
