# Product

<!-- impeccable:product-schema 1 -->

## Platform

web

## Stack

Vite + Three.js（用户确认）；3D 资产走 Blender 5.3（E:\blender）程序化生成管线导出 glb，源码在 model/，经 `npm run assets:sync` 同步到 public/assets/models/。

## Users

中文玩家，桌面浏览器 + 键鼠（WASD + 指针锁定鼠标视角）。休闲体验者：想在夜间万圣节乐园里漫步、乘坐摩天轮高空观光。手机端明确不做。

## Product Purpose

「幽夜游乐场」——万圣节惊魂夜主题的第一人称 3D 网页游乐场。玩家从幽暗入口进入园区，穿过灯串与南瓜灯阵列，登上摩天轮在高空俯瞰整座被极光笼罩的乐园。成功 = 玩家愿意在园里停留漫游、乘坐、打卡，并说得出"氛围像参考图一样好"。

## Positioning

全程序化：所有 3D 资产由 Blender 脚本参数化生成（无下载模型），所有音效由 WebAudio 程序合成（无音频文件）。零外部素材依赖、可参数化重生成，是同类 threejs 乐园作品难以直接复制的机制。

## Operating Context

本地 `npm run dev`（端口 8765）运行；无头 Chrome 截图脚本（scripts/screenshot.mjs）做画面验证；Blender 后台渲染做资产预览验证。

## Capabilities and Constraints

- 第一人称走动（WASD/Shift 疾走/指针锁定环视）
- 摩天轮乘坐：站台按 E 上客，舱内**随时按 E 可下**（用户确认），第一人称环视
- 旋转木马骑乘：平台上按 E 骑上就近灵兽/座车，固定座位随盘环游 + 自由环视，**随时按 E 下乘回平台**（用户确认 2026-11-17；多设施乘坐约束解除）
- 轻量打卡收集：园区散布打卡点，靠近按 E 收集，HUD 显示进度 0/N（用户确认）
- 程序化音频：环境音 + 程序合成 BGM，HUD 静音开关（用户确认）
- 性能预算：1080p ~60fps，draw call < 300
- 明确不做：手机适配、任务/商店系统（后续版本）

## Brand Commitments

- 名称「幽夜游乐场」Hollow Night Carnival（暂定，可改）
- 主题「万圣节惊魂夜」：暗夜 + 极光 + 南瓜灯 + 雾气 + 暖光灯串（用户确认绑定，参考图即标准）
- 色板方向：南瓜橙 #FFA53B / 暗夜紫 #9B5BFF / 磷光绿 #8CFF4A / 暗红 #C43B3B / 暖白 #FFE9C4

## Evidence on Hand

- 用户提供 3 张参考截图（某 threejs 万圣节游乐场的实拍：极光夜空、乘坐 HUD、舱内第一人称视角）——氛围与交互的标准，位于本会话上下文
- model/ferris_wheel/：v1 摩天轮资产 + 4 张 Blender 预览图 + 旋转视频
- 项目内无文案库、无 logo、无字体资产——后续不得虚构"已有品牌素材"

## Product Principles

1. 氛围优先：夜间光照层次（天空极光/地面雾/设施自发光）是产品本体，画面标准对齐参考图
2. 沉浸少 UI：HUD 平时退后甚至隐藏，只在关键节点（交互提示/打卡/乘坐）出现
3. 程序化一切：资产与声音皆可参数化重生成，保持零外部素材
4. 可扩展设施架构：摩天轮是第一个设施，交互/乘坐/HUD 模式为后续设施立模板
