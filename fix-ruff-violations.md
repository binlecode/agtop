# Ruff Fix Tracker

This file tracks the 20 lint violations reported before manual fixes.

## Rule Summary

- `F403`: 2
- `F405`: 14
- `E741`: 3
- `E722`: 1

## Detailed Checklist

1. [x] `F403` `agtop/agtop.py:7` wildcard import from `.utils`
2. [x] `F405` `agtop/agtop.py:115` `get_soc_info`
3. [x] `F405` `agtop/agtop.py:254` `run_powermetrics_process`
4. [x] `F405` `agtop/agtop.py:261` `parse_powermetrics`
5. [x] `F405` `agtop/agtop.py:264` `parse_powermetrics`
6. [x] `F405` `agtop/agtop.py:307` `clear_console`
7. [x] `F405` `agtop/agtop.py:317` `run_powermetrics_process`
8. [x] `F405` `agtop/agtop.py:321` `parse_powermetrics`
9. [x] `F405` `agtop/agtop.py:436` `get_ram_metrics_dict`
10. [x] `E741` `agtop/parsers.py:84` ambiguous loop variable `l`
11. [x] `F403` `agtop/utils.py:6` wildcard import from `.parsers`
12. [x] `F405` `agtop/utils.py:18` `parse_thermal_pressure`
13. [x] `F405` `agtop/utils.py:19` `parse_cpu_metrics`
14. [x] `F405` `agtop/utils.py:20` `parse_gpu_metrics`
15. [x] `F405` `agtop/utils.py:36` `parse_thermal_pressure`
16. [x] `F405` `agtop/utils.py:37` `parse_cpu_metrics`
17. [x] `F405` `agtop/utils.py:38` `parse_gpu_metrics`
18. [x] `E741` `agtop/utils.py:128` ambiguous loop variable `l`
19. [x] `E741` `agtop/utils.py:148` ambiguous loop variable `l`
20. [x] `E722` `agtop/utils.py:172` bare `except`

## Change Notes

- Replaced wildcard imports with explicit imports in `agtop/agtop.py` and `agtop/utils.py`.
- Renamed ambiguous loop variable `l` to descriptive names.
- Replaced bare `except` with `except Exception`.
- Run `ruff` and tests to verify completion.
