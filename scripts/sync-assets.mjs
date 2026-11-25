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
  ["model/roller_coaster/roller_coaster.glb", "public/assets/models/roller_coaster.glb"],
  ["model/roller_coaster/roller_coaster_train.glb", "public/assets/models/roller_coaster_train.glb"],
  ["model/roller_coaster/centerline.json", "public/assets/models/roller_coaster_centerline.json"],
  ["model/roller_coaster/colliders_coaster.json", "public/assets/models/colliders_coaster.json"],
  ["model/lookout_tower/lookout_tower.glb", "public/assets/models/lookout_tower.glb"],
  ["model/lookout_tower/colliders_tower.json", "public/assets/models/colliders_tower.json"],
  ["model/firework_launcher/salute_launcher.glb", "public/assets/models/salute_launcher.glb"],
  ["model/firework_launcher/colliders_salute_launcher.json", "public/assets/models/colliders_salute_launcher.json"],
];

for (const [src, dst] of MAP) {
  const from = resolve(root, src);
  const to = resolve(root, dst);
  mkdirSync(dirname(to), { recursive: true });
  copyFileSync(from, to);
  console.log(`synced  ${src}  ->  ${dst}`);
}
