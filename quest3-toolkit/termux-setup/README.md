# Quest 3 Termux Setup Scripts

Automated environment setup for Termux running on Meta Quest 3.

## Prerequisites

- Meta Quest 3 with Termux installed (via F-Droid or GitHub releases; **not** the deprecated Play Store version)
- Internet connection for package downloads

## Usage

### Full setup (recommended)

```bash
cd ~/termux-setup   # or wherever you placed these scripts
chmod +x *.sh
bash setup-all.sh
```

This runs all steps in order: base packages, storage, Node.js, and Python.

### Individual scripts

Run only what you need:

| Script | Purpose |
|---|---|
| `setup-base.sh` | Update repos, install git/python/node/build tools |
| `setup-storage.sh` | Grant storage permission, create `~/projects` and `~/downloads` symlinks |
| `setup-nodejs.sh` | Configure npm globals, install Claude Code |
| `setup-python.sh` | Set up pip, create default venv with common packages |

All scripts are **idempotent** -- safe to run multiple times.

### After setup

```bash
source ~/.bashrc                        # reload PATH
cd ~/projects                           # shared storage
source ~/venvs/default/bin/activate     # Python venv
claude                                  # Claude Code (if installed)
```

## Notes

- Scripts use the Termux-specific shebang (`#!/data/data/com.termux/files/usr/bin/bash`) but also work if sourced from a standard `bash` session.
- Claude Code on Quest 3 ARM64 is experimental and may not install cleanly on all configurations.
- Storage symlinks point into `~/storage/shared/` so files are accessible from the Quest file manager and other apps.
