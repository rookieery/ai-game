// 将 Blender 管线产出的资产同步到 Vite 静态目录
// 资产源 = model/（source of truth），应用只读拷贝
import { copyFileSync, mkdirSync } from "node:fs";
import { dirname, resolve } from "node:path";

const root = resolve(import.meta.dirname, "..");

const MAP = [
  ["model/ferris_wheel/ferris_wheel.glb", "public/assets/models/ferris_wheel.glb"],
  ["model/carousel/carousel.glb", "public/assets/models/carousel.glb"],
  ["model/park_env/park_env.glb", "public/assets/models/park_env.glb"],
  ["model/park_env/colliders.json", "public/assets/models/colliders.json"],
];

for (const [src, dst] of MAP) {
  const from = resolve(root, src);
  const to = resolve(root, dst);
  mkdirSync(dirname(to), { recursive: true });
  copyFileSync(from, to);
  console.log(`synced  ${src}  ->  ${dst}`);
}
