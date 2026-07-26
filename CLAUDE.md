# PeakPicker

Shared conventions — machine paths, config sync, branch/merge, commit trailer — live in the
global `~/.claude/CLAUDE.md` under **Per-Repo Conventions**. They are deliberately not
repeated here; duplicating them is what let a dead bootstrap line rot in four repos at once.

## This repo only
- `.claude/params_spec.yaml` — read by the global params-strict hook on edit/commit.
  Add or change a learnable parameter there first, or the write is rejected.
- `.claude/worktrees/` — refactor work is carried out in a separate worktree.
