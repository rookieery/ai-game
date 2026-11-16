# 摩天轮 3D 模型（霓虹夜景风）

程序化生成的游戏引擎资产：轮体旋转动画 + 吊舱始终保持垂直（真实摩天轮特性）。

## 吊舱结构（经典观光轿舱）

每舱 22 部件：销轴接头 + 人字吊臂 / 舱顶盖 + 霓虹檐线 + 顶灯 / 真半透明环绕玻璃带
（角柱 + 竖梃 + 横楣分格）/ 舱内暖光天花 + 后壁 + 地板 + 座椅剪影 / 清漆漆面舱体 +
霓虹腰线 + 底盘裙边 + 缓冲块。玻璃走 glTF alphaMode: BLEND，引擎端直接支持。

## 文件说明

| 文件 | 用途 |
|------|------|
| `ferris_wheel.py` | 参数化生成脚本（Blender Python） |
| `ferris_wheel.blend` | Blender 源文件，可双击打开手动编辑 |
| `ferris_wheel.glb` | glTF 2.0 导出（含旋转动画），游戏引擎用这个 |
| `preview/01_front.png` | 正面全景预览 |
| `preview/02_three_quarter.png` | 3/4 视角（主展示图） |
| `preview/03_side.png` | 侧面结构图 |
| `preview/04_cabin_detail.png` | 吊舱特写 |
| `preview/spin_preview.mp4` | 旋转动画预览视频 |
| `build_log.txt` | 最近一次生成的运行日志 |

## 如何调整参数重新生成

所有参数集中在 `ferris_wheel.py` 顶部的 `P` 字典和 `HEX` 颜色表里：

```python
P = {
    "wheel_radius": 12.0,   # 轮半径（米）
    "cabins": 12,           # 吊舱数量
    "spin_period_s": 24.0,  # 旋转一圈秒数
    ...
}
HEX = { "pink": "#FF2E88", "cyan": "#00E5FF", ... }  # 霓虹色板
```

改完后让 AI 重新运行，或自己执行（命令行）：

```
E:\blender\blender.exe --background --python ferris_wheel.py
```

生成内容：建模 → 保存 .blend → 导出 .glb → 渲染预览图和视频，全程无需打开界面。

## 在游戏引擎中使用

- **Three.js / Babylon / Godot**：直接加载 `ferris_wheel.glb`，动画名为各节点的旋转轨道（如 `FW_Wheel` 的 Y 轴旋转），循环播放即可
- 发光效果使用 glTF emissive 通道，引擎端开启 Bloom 后处理即可还原夜景辉光
- 面数约几万三角面，适合实时渲染
