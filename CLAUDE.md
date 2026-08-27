# PeakPicker

## HPLC Quantitation
HPLC quantitation / peak area / calibration curve work → read `docs/QUANTITATION_RULES.md`
FIRST (area convention, calibration YAML schema, column ID, peak assignment, allowed tuning axes).

## Machine Paths
Always use `Path.home()` for user-specific paths — never hardcode usernames.

## Config Sync
Verify global config is installed (first use on a new machine):
```bash
bash "$(find ~/OneDrive*고려대* -name install.sh -path '*/claude-config/*' | head -1)"
```
After bootstrap, hooks auto-sync on every session start.

## Git Workflow
- **Never push directly to main** — work branches → integration branch → main
- Merge path: `{project}/feature/{subtopic}-{YYMMDD}` → `{project}/{topic}` → `main`
- Integration branches: `{project}/{topic}` (no date)
- Work branches: `{project}/feature/{subtopic}-{YYMMDD}` or `{project}/fix/{subtopic}-{YYMMDD}`
