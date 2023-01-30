# Changelog
All notable changes to this project will be documented in this file.


The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/).

## [1.3.2] 2023-01-30
### Improvements
- replaced some subprocess calls executed in behalf of non-root users by async calls (Python's asyncio native approach)

### Fixes
- the optimizer service (as root) not able to execute some commands in behalf of non-root users (started with Python 3.10.9)

## [1.3.1] 2022-10-22
### Improvements
- Optimizing the children of the target process
- New optimizer service properties:
  - `optimize_children.timeout`: maximum period in *seconds* to keep looking for the target process children (default: `30`). `0` can be defined if children should be ignored.
  - `optimize_children.found_timeout`: maximum period in *seconds* to still keep looking for the target process children after a child in found (default: `10`). `0` can be defined if the search process should be interrupted immediately after a child is found.
- Ignoring some Ubisoft launcher sub-processes not required to be optimized (when launched from Steam)

### Fixes
- Only checking for mapped processes when a process optimization is requested


## [1.3.0] 2022-10-15
### Improvements
- Properly detecting all Steam games subprocesses that need to be optimized (no need to map launchers anymore)
- Launcher mapping now optimizes all matches instead of just the last born process
- New optimizer service property `launcher.mapping.found_timeout`: maximum time in *seconds* to still keep looking for a process mapped to a different process after a match. This property also affects the period to look for Steam subprocesses. (default: `10`)
- The optimizer service property `launcher.mapping.timeout` has now a default value of `60` (seconds)

### Fix
- wild card mapping to proper regex pattern

## [1.2.2] 2022-09-22
### Improvements
- Minor code refactoring and log improvements regarding AMD GPU management
- Optimizer:
  - configuration property `check.finished.interval` now accepts floats and the minimum value accepted is `0.5`
  - new configuration property `gpu.id`: allows to define which GPU cards should be optimized (e.g: `gpus.id = 0,1`). If not defined, all available GPUs are considered (default).

### Fixes
- optimizer:
  - when running as a system service, sometimes the GPU mapped directories are not available during the system startup and affects the correct behavior of the property `gpu.cache` when it is enabled (`true`)
     - so now the available GPUs will be cached after a first request when the `optimizer` is running as a system service (otherwise they will be cached normally during the service startup process)

## [1.2.1] 2022-08-22
### Fixes
- Performance mode not being activated for AMD GPUs from the RX 6XX0 series (tested on kernels >= 5.15)

### Improvements
- removed unused code

## [1.2.0] 2022-06-17

### Features
- watcher service:
  - allowing processes to be ignored through the mapping file: **watch.ignore** (must be located in `~/.config/guapow` or `/etc/guapow`)
    - it follows the same patterns as the `watch.map` file, but the profile name is not required (as it makes no sense). e.g:
    ```
    my_app_name
    my_app_name*  
    /bin/my_proc
    r:/bin/.+/xpto
    ```
    - this feature is useful if you have general mappings that cover a lot of processes in `watch.map` (e.g: `/usr/bin/*`), but want to ignore specific ones
    - new config property `ignored.cache` to cache all mapped patterns to memory after the first read and skip next I/O calls (default: `false`) 


## [1.1.1] 2022-06-08

### Fixes
- AMD GPU performance mode not working [#1](https://github.com/vinifmor/guapow/issues/1)
  - (test context -> GPU: Ryzen 7 5700G, Kernel: 5.15.45, O.S: Arch Linux)


## [1.1.0] 2022-06-03

### Features
- If `cpu.performance` is defined, now the energy policy level is also set to full performance. This feature is only available for certain Intel CPUs (generally for laptop models). More on that [here](https://github.com/vinifmor/guapow#opt_cpu_epl)

### Improvements
- Optimizer settings:
  - `launcher.mapping.timeout`: now defaults to `30` seconds instead of `15`

## [1.0.2] 2021-12-26

### Fixes
- test cases relying on inxi installed

## [1.0.1] 2021-10-06

### Fixes
- Random test failures when comparing environment variables


## [1.0.0] 2021-10-06
- First release
