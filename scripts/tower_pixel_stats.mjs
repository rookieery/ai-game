// 取证图像素统计（开发用）: 纯白过曝占比 (r,g,b>=250) 与 画面中央 60% 近黑占比 (Rec.709 亮度<12)
// 用法: node scripts/_tower_pixel_stats.mjs <目录> F01,F02,...      (需本机 ffmpeg/ffprobe)
import { spawnSync } from "node:child_process";

const DIR = process.argv[2] ?? "shots/tower/v3/E";
const IDS = (process.argv[3] ?? Array.from({ length: 42 }, (_, i) => `F${String(i + 1).padStart(2, "0")}`).join(",")).split(",");
const rows = [];
for (const id of IDS) {
  const file = `${DIR}/${id}.png`;
  const ff = spawnSync("ffmpeg", ["-v", "error", "-i", file, "-f", "rawvideo", "-pix_fmt", "rgb24", "-"], { maxBuffer: 64 * 1024 * 1024 });
  if (ff.status !== 0) { rows.push({ id, error: String(ff.stderr).slice(0, 80) }); continue; }
  const pr = spawnSync("ffprobe", ["-v", "error", "-select_streams", "v:0", "-show_entries", "stream=width,height", "-of", "csv=p=0", file], { encoding: "utf8" });
  const [W, H] = pr.stdout.trim().split(",").map(Number);
  const b = ff.stdout, n = W * H;
  let white = 0, cBlack = 0, cN = 0;
  const x0 = Math.floor(W * 0.2), x1 = Math.ceil(W * 0.8), y0 = Math.floor(H * 0.2), y1 = Math.ceil(H * 0.8);
  for (let y = 0; y < H; y++) for (let x = 0; x < W; x++) {
    const o = (y * W + x) * 3, r = b[o], g = b[o + 1], bl = b[o + 2];
    const w = r >= 250 && g >= 250 && bl >= 250;
    if (w) white++;
    if (x >= x0 && x < x1 && y >= y0 && y < y1) { cN++; if (0.2126 * r + 0.7152 * g + 0.0722 * bl < 12) cBlack++; }
  }
  rows.push({ id, whitePct: +(100 * white / n).toFixed(3), blackPct: +(100 * cBlack / cN).toFixed(2) });
}
for (const r of rows) console.log(r.error ? `${r.id} ERROR ${r.error}` : `${r.id}  纯白 ${String(r.whitePct).padStart(6)}%   中央近黑 ${String(r.blackPct).padStart(6)}%`);
const ok = rows.filter((r) => !r.error);
console.log(`-- ${ok.length} 张: 纯白 最高 ${Math.max(...ok.map((r) => r.whitePct))}%  平均 ${(ok.reduce((a, r) => a + r.whitePct, 0) / ok.length).toFixed(3)}% ; 中央近黑 最高 ${Math.max(...ok.map((r) => r.blackPct))}%  平均 ${(ok.reduce((a, r) => a + r.blackPct, 0) / ok.length).toFixed(1)}%`);
