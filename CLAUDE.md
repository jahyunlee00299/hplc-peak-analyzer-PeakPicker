# PeakPicker

## Machine Paths
Always use `Path.home()` for user-specific paths — never hardcode usernames.

## Config Sync
Global config syncs from the claude-config master at session start; hooks come with it.

Manual re-sync:
```bash
bash ~/.claude/scripts/sync_config.sh
```

> Do **not** run `find` over OneDrive to locate the config — recursive traversal forces
> every cloud-only file to download. The old bootstrap line here pointed at an
> `install.sh` that does not exist, so it scanned OneDrive and then executed nothing.
> First use on a new machine: run `shared/apply.sh` from the claude-config master.
