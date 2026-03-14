# PeakPicker

## Machine Paths
Always use `Path.home()` for user-specific paths — never hardcode usernames.

## Config Sync
Verify global config is installed (first use on a new machine):
```bash
bash "$(find ~/OneDrive*고려대* -name install.sh -path '*/claude-config/*' | head -1)"
```
After bootstrap, hooks auto-sync on every session start.
