# Changelog
All notable changes to this project will be documented in this file.


The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/).

## [1.1.0] 2022-06-03

### Features
- If `cpu.performance` is defined, now the energy policy level is also set to full performance. This feature is only available for certain Intel CPUs (generally for laptop models). More on that [here](https://github.com/vinifmor/guapow/tree/cpu_epb#changing-cpu-cores-energy-policy-level-full-performance)

### Improvements
- Optimizer settings:
  - `launcher.mapping.timeout`: now defaults to `30` seconds instead of `15`.

## [1.0.2] 2021-12-26

### Fixes
- test cases relying on inxi installed

## [1.0.1] 2021-10-06

### Fixes
- Random test failures when comparing environment variables


## [1.0.0] 2021-10-06
- First release
