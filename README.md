# agtop

Apple GPU Top for Apple Silicon.

![](images/agtop.png)

## Project Status

`agtop` is an independent hard fork with its own release cycle and maintenance policy.

Origin attribution: this project started from `tlkh/asitop` and is now maintained as `binlecode/agtop`.

## Features

- CPU and GPU utilization/frequency display.
- ANE utilization estimation from power usage.
- RAM and swap usage display.
- CPU/GPU power charts with profile-aware scaling.
- Apple Silicon profile defaults for current and future M-series tiers.

## Requirements

- Apple Silicon Mac.
- macOS with `powermetrics` available.
- `sudo` access (required by `powermetrics`).

## Install

Install from this tap:

```shell
brew tap --custom-remote binlecode/agtop https://github.com/binlecode/agtop.git
brew install agtop
```

If formula names are ambiguous:

```shell
brew install binlecode/agtop/agtop
```

## Upgrade / Uninstall

```shell
brew update
brew upgrade agtop
brew uninstall agtop
```

## Usage

```shell
agtop --help
sudo agtop
sudo agtop --interval 1 --avg 30 --power-scale profile
```

## Compatibility Notes

- Chip families `M1` through `M4` are recognized directly.
- Unknown future Apple Silicon names fall back to tier defaults (`base`, `Pro`, `Max`, `Ultra`).
- Available `powermetrics` fields vary by macOS and chip generation.

Use `agtop` for install and runtime commands in this repository.
