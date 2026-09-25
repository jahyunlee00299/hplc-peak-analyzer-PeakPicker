# Plugins — keeping experiment-specific code out of the library

PeakPicker's library code is generic. Anything that only makes sense for one
lab's experiments — how its sample folders are named, its quantification
presets, which method YAML a data folder should use — is supplied by
**plugins** and **method YAML files** that live outside this repository.

## Where plugins are loaded from

`peakpicker.plugins.load_plugins()` imports every `*.py` file (not starting
with `_`) from:

1. each directory in the `PEAKPICKER_PLUGIN_PATH` environment variable
   (`os.pathsep`-separated), or, if it is unset,
2. `<repo>/plugins/` when that directory exists (it is gitignored).

Loading is lazy and idempotent: the registries below call it before a lookup.
A plugin that fails to import raises a `UserWarning` naming the file; it never
aborts the run and is never silently ignored.

## What a plugin can register

| Registry | Call | Used by |
|---|---|---|
| Sample-name parser | `peakpicker.sample_parser.register_parser(name, detect, factory, priority=0)` | `get_parser(data_dir)` — highest-priority parser whose `detect(d_folders)` is true, else `GenericSampleParser` |
| Experiment factors | `SampleMeta.register_factor_defaults(**defaults)` | unset factors read as their declared default; `meta.all_factors()` in exports |
| Quantification preset | `peakpicker.config.quantification_config.register_preset(name, fn)` | `get_preset(name)(...)` |

Per-sample experiment factors (doses, ratios, feed flags, …) are stored in
`SampleMeta.factors`; `meta.some_factor` reads and writes route through it.

## Method selection rules live in the method YAML

`MethodSelector.suggest(data_dir, methods_dir)` reads an optional `match:`
block from every YAML in `methods_dir` — see
[`methods/example_hpx87h.yaml`](../methods/example_hpx87h.yaml):

```yaml
match:
  signal: RID1A.ch          # detector file that must be present
  keywords: [EXAMPLE_COMPOUND]   # optional; matched against the folder path
  priority: 5
  fallback_for_signal: false     # true = default method for this signal
```

## Private overlay layout

Lab-specific files sit in the same working tree but are tracked by a separate
private repository, so the public `.gitignore` excludes `analyses/`,
`methods/*.yaml` (except the example), `methods/standards/`, `tests/lab/`
(collected by pytest when present), `archive/` and `plugins/`.
