# AGENTS.md — PeakPicker

Rules for AI coding agents working in this repository (Claude Code, Codex, Gemini CLI, Hermes and others).

## Public repository

This repo is public and ships to PyPI as `hplc-peakpicker`. Never commit personal names, machine names,
absolute home paths, lab data or credentials. Machine-specific settings go in git-ignored local files
(for example `.fiducial.local.toml` overrides `.fiducial.toml`).

## HPLC quantitation

Before any quantitation, peak-area or calibration-curve work, read the local `docs/QUANTITATION_RULES.md`
when your checkout carries that overlay (area convention, calibration YAML schema, column ID, peak
assignment, allowed tuning axes), then `docs/QUANTITATION_PITFALLS.md` and `docs/REQUANT_RUNBOOK.md`.
Calibration slopes and intercepts are read from `methods/*.yaml`; never type them into `scripts/` or plugins
(the `.fiducial.toml` `literals` rule checks this).

## Layout and tests

See `PROJECT_STRUCTURE.md` for the module map. Run tests with `python -m pytest` from the repo root.

## Git

Default branch `main`; work on a branch and merge into `main`, never commit to `main` directly.
