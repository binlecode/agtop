# asitop

![PyPI - Downloads](https://img.shields.io/pypi/dm/asitop)

Performance monitoring CLI tool for Apple Silicon

![](images/asitop.png)

```shell
pip install asitop
```

## What is `asitop`

A Python-based `nvtop`-inspired command line tool for Apple Silicon Macs.

* Utilization info:
  * CPU (E-cluster and P-cluster), GPU
  * Frequency and utilization
  * ANE utilization (measured by power)
* Memory info:
  * RAM and swap, size and usage
  * (Apple removed memory bandwidth from `powermetrics`)
* Power info:
  * CPU power, GPU power (Apple removed package power from `powermetrics`)
  * Chart for CPU/GPU power
  * Peak power, rolling average display

`asitop` uses the built-in [`powermetrics`](https://www.unix.com/man-page/osx/1/powermetrics/) utility on macOS, which allows access to a variety of hardware performance counters. Note that it requires `sudo` to run due to `powermetrics` needing root access to run. `asitop` is lightweight and has minimal performance impact.

`asitop` is intended for Apple Silicon Macs on modern macOS versions. Runtime metrics are sourced from
`powermetrics`, so available fields can vary by macOS version and chip generation.

## Installation and Usage

Install with Homebrew (recommended on macOS):

```shell
brew install binlecode/asitop/asitop
```

Optional (tap once, then use short name):

```shell
brew tap binlecode/asitop
brew install asitop
```

Install with pip:

```shell
pip install asitop
```

Upgrade / uninstall with Homebrew:

```shell
brew update && brew upgrade asitop
brew uninstall asitop
```

After installation, run in Terminal:

```shell
# to enter password before start
# this mode is recommended!
sudo asitop

# it will prompt password on start
asitop

# advanced options
asitop [-h] [--interval INTERVAL] [--color COLOR] [--avg AVG] [--power-scale {auto,profile}]
optional arguments:
  -h, --help           show this help message and exit
  --interval INTERVAL  Display interval and sampling interval for powermetrics (seconds)
  --color COLOR        Choose display color (0~8)
  --avg AVG            Interval for averaged values (seconds)
  --power-scale {auto,profile}
                       Power chart scaling. "auto" uses rolling peak; "profile" uses chip reference values.
```

## Compatibility

- Chip families: `M1`, `M2`, `M3`, and `M4` are recognized directly.
- Unknown future Apple Silicon names fall back to tier-based defaults (`base`/`Pro`/`Max`/`Ultra`) so charts remain usable.
- `powermetrics` output may differ across macOS releases; some metrics can be unavailable depending on OS/chip.

## How it works

`powermetrics` is used to measure the following:

* CPU/GPU utilization via active residency
* CPU/GPU frequency
* Package/CPU/GPU/ANE energy consumption
* CPU/GPU/Media Total memory bandwidth via the DCS (DRAM Command Scheduler)

[`psutil`](https://github.com/giampaolo/psutil) is used to measure the following:

* memory and swap usage

[`sysctl`](https://developer.apple.com/library/archive/documentation/System/Conceptual/ManPages_iPhoneOS/man3/sysctl.3.html) is used to measure the following:

* CPU name
* CPU core counts

[`system_profiler`](https://ss64.com/osx/system_profiler.html) is used to measure the following:

* GPU core count

Some information is guesstimate and hardcoded as there doesn't seem to be a official source for it on the system:

* CPU/GPU TDP
* CPU/GPU maximum memory bandwidth
* ANE max power
* Media engine max bandwidth

## Why

Because I didn't find something like this online. Also, just curious about stuff.

## Disclaimers

I did this randomly don't blame me if it fried your new MacBook or something.
