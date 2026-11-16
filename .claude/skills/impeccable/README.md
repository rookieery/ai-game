# impeccable (vendored skill)

This folder is a trimmed install of the [impeccable](https://github.com/pbakaus/impeccable) skill,
copied from `agent/impeccable/.claude/skills/impeccable/` on 2026-11-16 (v4.9.2, commit `d41d9860b`).
The rest of that repo clone was removed; this folder is the only part ai-game uses.

- Scope: project-wide skill for ai-game (`/impeccable <command>`, 24 design commands).
- Runtime: `scripts/impeccable` launcher downloads the pinned engine binary into `~/.impeccable/bin/`
  on first run (no Node/Rust needed afterwards). Update = re-copy a newer `.claude/skills` folder
  from a fresh clone, then clear `~/.impeccable/bin` if the VERSION changed.

## License

Apache 2.0 (upstream `pbakaus/impeccable`).

## Third-Party Notices

`reference/ios.md` and `reference/android.md` are distilled from ehmo's
[platform-design-skills](https://github.com/ehmo/platform-design-skills) (MIT), rewritten in
Impeccable's voice.
