[![GitHub release](https://img.shields.io/github/release/vinifmor/guapow.svg?label=Release)](https://github.com/vinifmor/guapow/releases/) [![PyPI](https://img.shields.io/pypi/v/guapow?label=PyPI)](https://pypi.org/project/guapow) [![AUR](https://img.shields.io/aur/version/guapow?label=AUR)](https://aur.archlinux.org/packages/guapow) [![AUR-staging](https://img.shields.io/aur/version/guapow-staging?label=AUR-staging)](https://aur.archlinux.org/packages/guapow-staging) [![License](https://img.shields.io/github/license/vinifmor/guapow?label=License)](https://github.com/vinifmor/guapow/blob/master/LICENSE) [![kofi](https://img.shields.io/badge/Ko--Fi-Donate-orange?style=flat&logo=ko-fi)](https://ko-fi.com/vinifmor)

**guapow** is an on-demand and auto performance optimizer for Linux applications. This project's name is an abbreviation for **Guarana powder** (_Guaraná_ is a fruit from the Amazon rainforest with a highly caffeinated seed).

**Key features**

- Changing applications priorities and CPU times
- Changing applications IO priorities
- Changing applications CPU scheduling policies (including realtime)
- Changing CPU energy policy
- Changing applications CPU cores affinities
- Changing CPU cores frequency governors
- Changing GPU power mode (only **Nvidia** and **AMD** devices at the moment)
- Custom scripting
- Optimization profiles
- Auto optimize all your Steam game library without having to edit Launch Options
- And more...

## Index
1.  [Installation](#installation)
    - [Arch-based distros](#inst_arch)
    - [Other distros](#inst_other)
2.  [Quick start](#quick_start)
    - [1. Starting the Optimizer service](#start_opt)
    - [2. Testing guapow](#start_test)
    - [3. Using a profile file](#start_prof)
    - [4. Auto-optimizing applications with the Watcher service](#start_watch)
3. [Optimizations](#opt)
    - [Changing application niceness](#opt_nice)
    - [Changing application I/O niceness](#opt_io)
    - [Changing application CPU scheduling](#opt_sched)
    - [Changing application CPU affinity](#opt_affinity)
    - [Changing CPU cores frequency scaling governor (performance)](#opt_cpu_freq)
    - [Changing CPU cores energy policy level (full performance)](#opt_cpu_epl)
    - [Changing GPU power mode (performance)](#opt_gpu_power)
    - [Disabling window compositor](#opt_compositor)
    - [Stopping applications](#opt_stop_proc)
    - [Executing custom commands and scripts](#opt_scripts)
    - [Hiding mouse pointer](#opt_hide_mouse)
    - [Defining environment variables](#opt_envvars)
4. [Tweaks](#tweaks)
    - [Launchers](#launchers)
    - [Steam games](#steam_games)
6. [Components](#components)
    - [Runner](#runner)
    - [Optimizer service](#optimizer)
        - [Settings](#opt_settings)
    - [Watcher service](#watcher)
        - [Mapping patterns](#watch_patterns)
        - [Built-in patterns (steam)](#watch_builtin)
        - [Ignoring processes](#watch_ignore)
        - [Settings](#watch_settings)
    - [CLI](#cli)
7. [Improving optimizations timing](#improve_opt)
8. [Tutorials](#tutorials)
    - [Auto-optimizing all your Steam games](#tutorial_steam)
9. [Roadmap](#roadmap)
10. [Donations](#donations)

### <a name="installation">Installation</a>

#### <a name="inst_arch">ArchLinux-based distros</a>
- Distribution: [AUR package](https://aur.archlinux.org/packages/guapow)
- Installing with [yay](https://github.com/Jguer/yay): `yay -S guapow`
- Installing manually (requires `pacman` and `git` installed)
```
git clone  https://aur.archlinux.org/guapow.git
cd guapow
makepkg -si
```

#### <a name="inst_other">Other distros</a>
- Distribution: [PyPi package](https://pypi.org/project/guapow)
- Requires **Python 3.8 or higher** (versions bellow have not been tested, but may work) and `pip` installed
- Ubuntu 20.04 based-distros dependencies: `sudo apt-get install python3 python3-pip python3-aiofiles python3-aiohttp python3-pycryptodome`
- Installation: `sudo pip3 install guapow`

### <span name="quick_start">Quick start</span>
#### <span name="start_opt">1. Starting the Optimizer service</span>
- After installing **guapow**, its **optimizer** service must be started and enabled (the current definition requires **systemd** installed). The **optimizer** service is the component responsible to apply most of the available optimizations.

- To start and enable the service, you can use the utility tool `guapow-cli` or do it manually (described below). Both methods require **systemctl** installed.

    - Method 1: Starting and enabling with `guapow-cli`
        ```
            guapow-cli install-optimizer  # may require sudo for non-root users
        ```

    - <a name="opt_manual_install">Method 2: Starting and enabling manually</a>
        - Download the service [definition file](https://github.com/vinifmor/guapow/blob/master/guapow/dist/daemon/systemd/root/guapow-opt.service) and move it to `/usr/lib/systemd/system`
        - To start and enable it: type `systemctl enable --now guapow-opt.service` (may require `sudo` for non-root users)

- To check: 
    - if the service is running, type `ps -Ao pid,comm | grep guapow-opt`
    - the service logs, type: `journalctl -efu guapow-opt.service`


#### 2. <span name="start_test">Testing guapow</a>

- To quickly test **guapow**, you have to use the `guapow` command to start and optimize a target application. The example below starts the **vlc** media player:

    ```
    GUAPOW_CONFIG="cpu.performance proc.nice=-1" guapow vlc
    ```

    - The environment variable `GUAPOW_CONFIG` should be used to define the optimizations that must be applied when the target application starts. In the example above two were defined:
        - `cpu.performance`: changes all CPUs frequency governors to **performance** (for supported Intel cpus, also the energy policy level)
        - `proc.nice=-1`: defines a CPU nice level for the started application. In simple words: a negative nice level will give more CPU priority and time for the application (more on this [here](#opt_nice))

     - The `guapow` command is responsible to start a target application and requests the defined optimizations for it.
 
- How to check if the optimizations were applied ?
    - **Nice level:** type `ps -Ao comm,nice | grep vlc`
    - **CPUs governors:** type `cat /sys/devices/system/cpu/cpu*/cpufreq/scaling_governor`
    - **CPU energy policies (supported Intel CPUs only):**: type `cat /sys/devices/system/cpu/cpu*/power/energy_perf_bias` (values must be `0`)
    - **Optimizer service logs:** type `journalctl -efu guapow-opt.service`
      
- When you close the optimized **vlc**, the **optimizer** service should rollback the CPU governors changes (use the commands above to re-checking)


#### <span name="start_prof">3. Using a profile file</span>
- Instead of defining the environment variable `GUAPOW_CONFIG` with all the wanted optimization settings for every application, you can create a profile file.
- The **guapow-cli** tool can generate a few pre-defined profiles (that can be changed or removed later). To generate the **default** profile file, type the command: `guapow-cli gen-profile default`
- This command should generate a file called **default.profile** in `~/.config/guapow` (or `/etc/guapow` for **root** users)
- You can quickly check the file content by typing the following command: `cat ~/.config/guapow/default.profile` (or `cat /etc/guapow/default.profile`)
- To specify which profile should be used when calling `guapow`, you have to define the environment variable `GUAPOW_PROFILE=profile_name` (without the extension **.profile**). Example below:

`GUAPOW_PROFILE=default guapow vlc`

- By default, if you do not specify neither the `GUAPOW_PROFILE` variable nor `GUAPOW_CONFIG`, the `guapow` command assumes that you are requesting optimizations based on a profile named **default**. In other words: the command `guapow vlc` would be equivalent to `GUAPOW_PROFILE=default guapow vlc`
- If both `GUAPOW_PROFILE` and `GUAPOW_CONFIG` were defined, `GUAPOW_PROFILE` will be ignored.

- Existing profile file priority:
  - for non-root users: `~/.config/guapow/{name}.profile` > `/etc/guapow/{name}.profile`
  - for root users: `/etc/guapow/{name}.profile`

- If a given profile file does not exist:
    - if it is not named **default**, **guapow** will try to load a profile called **default**.
    - if the **default** profile does not exist, no optimization will be applied.


#### <span name="start_watch">4. Auto-optimizing applications with the Watcher service<span>
- If you are not willing to add the `guapow` command for every applicaton you want to optimize, you can the enable the **watcher** service.
- The **watcher** service keeps looking for mapped applications/commands to be optimized, and request optimizations for them when they start.
- Two ways of starting and enabling it:
    - a) Using the **guapow-cli** tool: 
        - type: `guapow-cli install-watcher` (do not run this command with **sudo**, unless you are **root**: this service ideally should be run at the user level)
    - b) <a name="watch_manual_inst">Manual installation:</a>
        - Download the service [definition file](https://github.com/vinifmor/guapow/blob/master/guapow/dist/daemon/systemd/user/guapow-watch.service) and move it to `~/.config/systemd/user`
        - To start and enable it: type `systemctl enable --user --now guapow-opt.service`

- To check:
    - if the service is running: type `ps -Ao pid,comm | grep guapow-watch`
    - the service logs: type: `journalctl --user -efu guapow-watch.service`
    
- To define which applications should be watched, you have to create (or edit) the `watch.map` file (located at `~/.config/guapow` or `/etc/guapow` for **root** users). If the file does not exist, create it before proceeding.
- Edit the file and add the following content: `vlc`
- After that, start the **vlc** application normally and check if the optimizations defined in the **default** profile were applied.
- To map applications to diferrent profiles, you can use the pattern: `command_name=profile_name`. Example:
    
    ```
        vlc=media
        tuxracer=game 
    ```
 
- If the mapping line only contains the application name, the **default** profile is assumed.
- The **watcher** service supports wild-cards and Python regex patterns for processes names or commands (more on that [here](#watch_patterns))


### <a name="opt">Optimizations</a>
- This topic describes every possible change that can be applied to the system and the target process to improve its performance and experience. 
- They can be defined through:
    - the **GUAPOW_CONFIG** environment variable ([example](#start_test)) 
    - a profile file ([example](#start_prof))

#### <a name="opt_nice">Changing application niceness</a>
- The nice level of a given application helps defining its CPU priority and time.
- Property definition: `proc.nice=level` (e.g: `proc.nice=-2`).
- The level is an integer within the range (`-20 to 19`). **Negative** values have **higher prioprity**.
- The application nice level is changed after the target application starts (only once by default)
- Some applications change their nice level when initializing and can conflict with this optimization goal . To avoid such scenarios, it is possible to keep monitoring the target application's nice level through the property `proc.nice.watch` (or `proc.nice.watch=true`).
  - The monitoring interval can be changed on the Optimizer service [settings](#opt_settings) (property `nice.check.interval`).
- It is possible add a delay for the renicing task using the property `proc.nice.delay=seconds`
    - The **seconds** must be an integer (`proc.nice.delay=1`) or float (`proc.nice.delay=0.5`) higher than zero.
- By default, applications generally start with a nice level of **0** (**-20** its intended for very important system tasks).
    
#### <a name="opt_io">Changing application I/O niceness</a>
- Every time your application needs to write or read something from the disk, it competes with other applications.
- The applications I/O needs are split into classes. The supported classes are described below:
    - `best_effort`: default class. Divided in 8 levels (from 0 to 7). Lower levels have higher priority (e.g: 0 > 1).
    - `idle`: for applications that should only perform I/O operations when no other application is doing so.
    - `realtime`: first access to the disk. Divided in 8 levels (like `best_effort`). Not allowed for non-root users.
- This optimization requires the `ionice` command installed.
- Property definition: 
    - `proc.io.class=class_name` (e.g: `proc.io.class=best_effort`)
    - `proc.io.nice=level`: an integer within 0 and 7. **0** is the **default** value for classes supporting priority.  (e.g: `proc.io.nice=1`)
    
- The application I/O niceness is changed after the target application starts.
- The application IO class and priority can be checked though the command: `ionice -p pid`

#### <a name="opt_sched">Changing application CPU scheduling</a>
- Applications CPU scheduling behavior are split into policies.
- The supported policies are described below:
    - `other`: default CPU time-sharing scheduling.
    - `idle`: should be defined for applications with very low priority.
    - `batch`: should be defined for non-interactive CPU-intensive applications.
    - `fifo`: should be defined for very important applications. A FIFO application will lock the CPUs until it finishes to execute the demanded instructions. This policy is divided into priority groups from 1 to 99. Higher values = higher priority.
    - `rr` (round-robin): similar to `fifo`, but the applications have a limited time slice to execute with others of the same policy and priority.
 
    - The policies **fifo** and **rr** are designed for **realtime** applications and have higher priorities than the others. Applications associated with these policies can interrupt other running processes in order to execute. They should be used with care, since they can lock the entire system.

- Properties definitions: 
    - `proc.policy=policy_name` (e.g `proc.policy=rr`)
    - `proc.policy.priority=value`: value must be an integer between **1** and **99** (only supported by **fifo** and **rr**)
 
- The application CPU scheduling is changed after the target application starts.
    
#### <a name="opt_affinity">Changing application CPU affinity</a>
- CPU affinity means the instructions requested by a given application will be executed by determined CPU cores.
- Some applications performance can be improved when tied to less CPU cores, while keeping the other cores free for other tasks (like graphics rendering).
- Property definition: `proc.affinity=cpu` or `proc.affinity=cpu0,cpu1`
- Example 1 (affinity for CPUs 0 and 1):
    ```
    proc.affinity=0
    proc.affinity=1
    ```
- Example 2 (affinity for CPUs 2 and 3):
    `proc.affinity=2,3`
    
- The application CPU affinity is changed after the target application starts.
- The application CPU affinity can be checked though the command: `taskset -pc pid`

#### <a name="opt_cpu_freq">Changing CPU cores frequency scaling governor (performance)</a>
- The scaling governor is responsible for managing the CPU cores clock frequencies.
- The **performance** governor keeps the supported higher clocks whenever possible without caring too much about energy saving. In theory, the CPUs will be able to handle more instructions in less time.
- Property definition: 
    - `cpu.performance` (equivalents: `cpu.performance=true` or `cpu.performance=1`)
- The **optimizer** will keep the **performance** governor until the optimized application finishes. It handles the state if two or more optimized applications require `cpu.performance`. So if application A and B require `cpu.performance` and A finishes after a while, the performance governor will be kept until B finishes.
- The governor is changed after the target application starts.

#### <a name="opt_cpu_epl">Changing CPU cores energy policy level (full performance)</a>
- Only available for supported Intel CPUs (generally laptop ones)
- The CPU energy policy level defines how much of energy should be saved. It ranges from 0 (no savings, full performance) to 15 (full power saving). More info [here](https://wiki.archlinux.org/title/CPU_frequency_scaling#Intel_performance_and_energy_bias_hint).
- Property definition:
  - `cpu.performance` (equivalents: `cpu.performance=true` or `cpu.performance=1`)
- The **optimizer** will keep the performance energy policy level (`0`) until the optimized application finishes. It handles the state if two or more optimized applications require `cpu.performance`. So if application A and B require `cpu.performance` and A finishes after a while, the performance level will be kept until B finishes.
- The energy policy level is changed after the target application starts.

 #### <a name="opt_gpu_power">Changing GPU power mode (performance)</a>
 - The GPU drivers can provide pre-defined power modes for different usages. Some modes focus on energy-saving, while others on performance (higher clocks ands memory transfer rate).
 - Property definition: 
    - `gpu.performance` (equivalents: `gpu.performance=true` or `gpu.performance=1`)
 - For guapow, **performance** would match the **performance power mode** for **Nvida**, and **compute** mode for **AMD** (**Intel devices are currently not supported**).
 - The **performance** mode will not overclock your GPU.
 - Nvidia users require **nvidia-settings** and **nvidia-smi** installed.
 - The **optimizer** service will keep the **performance** state until the optimized application finishes. It handles the state if two or more optimized applications require `gpu.performance`. So if application A and B require `gpu.performance` and A finishes after a while, the performance state will be kept until B finishes.
 - The power mode is changed after the target application starts.
 
 #### <a name="opt_compositor">Disabling window compositor</a>
 - Window compositors are responsible for managing the window/desktop effects, and prevent visual glitches (like screen tearing). They generally come pre-bundled with desktop environments, window managers and distributions.
 - Some applications perform better when the compositor is disabled (e.g: games)
 - Currently supported compositors: 
    - **kwin** (KDE desktop environment)
    - **xfwm4** (XFCE desktop environment)
    - **marco** (Mate desktop environment) 
    - **compton/picom**
    - **compiz**
    - **nvidia** (driver. More on that [here](#opt_comp_nvidia))
 - Property definition: 
    - `compositor.off` (equivalents: `compositor.off=true` or `compositor.off=1`)
 - The **optimizer** service will keep the **compositor** disabled until the optimized application finishes. It handles the state if two or more optimized applications require `compositor.off`. So if application A and B require `compositor.off` and A finishes after a while, the disabled state will be kept until B finishes.
 - The **optimizer** service tries to guess the installed compositor (requires `inxi` installed) on the first request defining `compositor.off`. So the first request will take more time, then the subsequent ones. To prevent that, the installed compositor can be predefined on the **optimizer** service [settings](#opt_settings).
 - <a name="opt_comp_nvidia">**Nvidia** compositor:</a>
    - available when **ForceCompositionPipeline** (or **ForceFullCompositionPipeline**) are defined on the X11 or user settings.
    - the **optimizer** service is not able to detect it by default, so you have to pre-define it through the **optimizer** service [settings](#opt_settings).
- The compositor is disabled after the target application starts.

#### <a name="opt_stop_proc">Stopping applications</a>
- Some applications can impact the performance of others while running at the same time.
- **guapow** allows to stop target applications while the optimized one is running. The applications can be stopped at two possible moments: 
    - **before** the application to be optimized starts
    - right **after** the application to be optimized has started
    
- Property definition: 
    - `stop.{moment}=name_1,name_2,...`

- Example:
```
    stop.before=a
    stop.before=b
    stop.before=c,d  # multiple can be defined on the same line using commas
    stop.after=f,g
```

- In the example above:
    - applications **a**, **b**, **c** and **d** will be stopped before the application to be optimized starts
    - applications **f** and **g** will be stopped right after the application to be optimized starts
  

- The **optimizer** service will not restart the stopped applications when the optimized application finishes, unless the property `stop.{moment}.relaunch` (or `stop.{moment}.relaunch=true`) is defined. Example: 
    ```
    stop.before=a,b 
    stop.before.relaunch  # 'a' and 'b' will be restarted when the optimized application finishes
    ```
    - The **optimizer** service **will not relaunch** stopped applications while there are other optimized applications running that require them stopped.
    
- `stop.before` is only available for applications started through the [runner](#runner).
 
    
#### <a name="opt_scripts">Executing custom commands and scripts</a>
- guapow can execute custom commands and scripts in three possible moments:
    - **before** the application to be optimized starts
    - right **after** the application to be optimized has started
    - when the optimized application finishes (**finish**)
    
- Property definition: `scripts.{moment}=command_or_script_path_1,command_or_script_path_2,...`

- Examples:
```
    scripts.before=vlc,firefox  # vlc and firefox commands
    scripts.before=/home/user/my_script.sh  # my_script.sh path
    scripts.after=/usr/bin/app  # app full binary path
    scripts.finish=poweroff  # poweroff command
```
 
- In the example above:
    - commands `vlc` and `firefox`, and the script **/home/user/my_script.sh** will be executed before the application to be optimized starts
    - command `/usr/bin/app` will be executed right after the application to be optimized starts
    - command `poweroff` will be executed when the optimized application finishes
 
- You can work with the two additional properties below if the commands/scripts should only be executed when the previous finishes:
    - `scripts.{moment}.wait`: will wait a script to finish before starting the next. Example:
    
    ```
        scripts.before=my_script.sh 
        scripts.before=my_script_2.sh 
        scripts.before.wait   # 'my_script_2.sh' will only be executed when 'my_script.sh' finishes.
    ```
    
    - `scripts.{moment}.timeout`: will wait the script to finish for a limited time (in seconds), otherwise the next one in the chain will be executed. Example:
    
    ```
        scripts.after=vlc 
        scripts.after=firefox 
        scripts.after.timeout=5.5  # 'vlc' execution will be waited for `5.5`seconds. If it does not finish, 'firefox' will be started.
    ```
    
- Executing scripts at the **root** level:
    - requires the **optimizer** running at the root level (default installation).
    - root execution is disabled by default as a security mechanism. It can be enabled by adding the property `scripts.allow_root` (or `scripts.allow_root=true`) to the **optimizer** service [settings](#opt_settings).
    - to request scripts execution at the root level, you have also to add the property `scripts.{moment}.root` (or `scripts.{moment}.root=true`) to the configuration or profile file. Example:
     ```
        scripts.after=/path/to/my_script.sh
        scripts.after=/path/to/my_script_2.sh
        scripts.after.root  # with this property defined, both scripts above will be executed as root
     ```
    - `scripts.before` **does not suport root execution** (unless the user calling the `guapow` command is **root**)

#### <a name="opt_hide_mouse">Hiding mouse pointer</a>
- Some applications do not hide the mouse pointer by default, and can spoil the user experience.
- Property definition: 
    - `mouse.hidden` (equivalents: `mouse.hidden=true` or `mouse.hidden=1`)
- Requires **unclutter** installed.
- The mouse pointer will be hidden after the target application starts.
- The **optimizer** service will keep the mouse pointer hidden until the optimized application finishes. It handles the state if two or more optimized applications require `mouse.hidden`. So if application A and B require `mouse.hidden` and A finishes after a while, the pointer will be kept hidden until B finishes.
    
#### <a name="opt_envvars">Defining environment variables</a>
- You can defined specific environment variables to be added or removed when launching the target application.
- Possible property definitions (they can be declared several times):
    - `proc.env=MY_VAR:MY_VAR_VALUE` #  the variable name and value are separated with the symbol `:`
    - `proc.env=VAR_TO_REMOVE`  #  when no separator (`:`) is declared, the variable is removed
- Example:
    ```
    proc.env=COLOR:red (adds the environment variable named 'COLOR' with 'red' as value)
    proc.env=THEME:dark (adds another environment variable)
    proc.env=LD_PRELOAD  # (removes the environment variable named 'LD_PRELOAD')
    ```
- This feature has been added focusing on profile files (to keep all settings in one place). 
- This feature is only available when the application is launched through the [runner](#runner).


### <a name="tweaks">Tweaks</a>
#### <a name="launchers">Launchers</a>
- If the actual application to be optimized is a child of the target process, how can I tell **guapow** to optimize it instead ?
- **guapow** understand this sort of application as a **launcher**. It is possible to provide a mapping telling that when application A starts optimizes B instead.
- Two possible ways:
    
    - a) Providing the mapping through the configuration/profile property `launcher=exe_name:name_or_command`. Several launchers can be defined. Example:
    ```
        launcher=abc:abc-full  # this would map the executable 'abc' to an application named 'abc-full'. So 'abc-full' would be optimized instead of 'abc'
        launcher=def:def-bin   # this would map the executable 'def' to an application named 'def-bin'. So 'def-bin' would be optimized instead of 'def'
    ```
    
    - b) Providing all mapping through the `launchers` file located in `~/.config/guapow` (for non-root users) or `/etc/guapow` (for global or root usage) following the pattern `exe_name=name_or_command`. The advantage of this approach is that you don't have to provide a per-profile/configuration mapping. But at the same time, tons of mappings **may** impact the matching process time. Example:
    ```
    abc=abc-full
    def=def-bin
    fgh=/fgh-java.sh
    ```
    

- **Wild-cards**: the asterisk symbol `*` can be used when you want to match anything inside a word. Example: 

```
    vlc=vlc-*  # the first started application whose name starts with 'vlc-' would be optimized instead of 'vlc'
```

- **Name matching:** by default **guapow** considers an application name (comm) matching if the mapped word **does not start with a forward-slash (/)**. You can force a name matching by starting the word with the prefix **n%**. Examples:

```
    abc=def  # as 'def' does not starts with a forward-slash, guapow will look for an application named 'def'
    fgh=n%/xpto  # as the prefix 'n%' was provided, guapow will look for an application named '/xpto'
```

- **Command matching:** by default **guapow** considers an application command (cmdline) matching if the mapped word **starts with a forward-slash (/)**. You can force a command matching by starting the word with the prefix **c%**. Examples:

```
    abc=/abc-full  # as 'abc-full' starts with a forward-slash, guapow will look for an application launched with the command '/abc-full'
    def=c%xpto  # as the prefix 'c%' was provided, guapow will look for an application launched with the command 'xpto'
```

- If you want to skip the launchers mapping process for a given configuration/profile, use the property `launcher.skip_mapping` (or `launcher.skip_mapping=true`)
- Some examples of games mappings reported to work can be found [here](https://github.com/vinifmor/guapow/blob/master/example/launcher/games/launchers).

#### <a name="steam_games">Steam games</a>
- **guapow** has a tweak to look for the right Steam game executable to be optimized. This tweak is disabled by default. To enable it, you have to add the property `steam` (or `steam=true`) to your configuration or profile file.
- You can auto-optimize all your Steam games by following [this](#tutorial_steam) tutorial.

### [Components](#components)    
#### <a name="runner">Runner</a>
- The **runner** is responsible for launching a target application and request optimizations for it. 
    
- To launch a target application you have to use the command `guapow`. There are 3 possible ways to inform the wanted optimizations:
    - a) `GUAPOW_CONFIG` environment variable: you can provide all the [optimization properties](#opt) with this variable separated by commas.
    ```
    GUAPOW_CONFIG="cpu.performance proc.nice=-1" guapow abc  # starts 'abc' and request some optimizations for it
    ```
    - b) A profile file (`/.config/guapow/{name}.profile` or `/etc/guapow/{name}.profile`) and the environment variable **GUAPOW_PROFILE**. The variable value must consist of the profile file name without the extension.
    
    ```
        GUAPOW_PROFILE=media guapow abc  # starts 'abc' and requests the optimizations defined in the profile file '~/.config/guapow/media.profile`
    ```
    c) If you launch a command without defining the environment variables described above, **guapow** considers that you are requesting optimizations based on a profile file called **default**. In other words: `guapow command` is equivalent to `GUAPOW_PROFILE=default guapow command`
    
- It is possible to define extra optimization properties on-demand for a given profile through the environment variable `GUAPOW_PROFILE_ADD` (follows the same pattern as the environment variable `GUAPOW_CONFIG`).
 ```
    GUAPOW_PROFILE=media GUAPOW_PROFILE_ADD="compositor.off" guapow abc  # requests optimizations declared in the 'media' profile + 'compositor.off'
 ```
    
- To use the **runner** for launching **Steam** games, you can change the game **Launch options** and add something like: `GUAPOW_PROFILE=steam guapow %command%` (or `GUAPOW_CONFIG="properties" guapow %command%`). Make sure to add the [steam](#steam_games) property to your configuration/profile for better optimization handling.

- Logs:
    - Logs can be enabled through the environment variable `GUAPOW_LOG=1` (**1** enables / **0** disables)
    - They can be written to a file through the environment variable `GUAPOW_LOG_FILE=1` (log directory: `~/.local/share/guapow/log`)   

    
#### <a name="optimizer">Optimizer service</a>
- The **optimizer** service is responsible to apply most of the optimizations and tweaks to a target application and/or the system.
- Ideally, it should be run at the **root** level, otherwise some optimizations will not be possible.
- It applies the optimizations changes only once per optimization request. So, if it changes the CPUs governors to performance, and you manually change them later to something else, it will not set the governors to performance again (unless another optimization request arrives).
- [Service definition file](https://github.com/vinifmor/guapow/blob/master/guapow/dist/daemon/systemd/root/guapow-opt.service)
- By default, it runs at port **5087** and demands encrypted requests for security reasons (all done automatically).
  - Its settings are defined on the files: `~/.config/guapow/opt.conf` (user) or `/etc/guapow/opt.conf` (system). Preference: user > system (if running as **root**, system is the only option)
      - <a name="opt_settings">Properties:</a>
      ```
          port = 5087 (TCP port)
          compositor = (pre-defines the installed compositor. Options: kwin, compiz, marco, picom, compton, nvidia)
          scripts.allow_root = false (allow custom scripts/commands to run at the root level)
          check.finished.interval = 3 (finished applications checking interval in seconds. Min accepted value: 0.5)
          launcher.mapping.timeout = 60 (maximum time in seconds to look for a process mapped to a different process. This property also affects the period to look for Steam subprocesses.  float values are allowed)
          launcher.mapping.found_timeout = 10 (maximum time in seconds to still keep looking for a process mapped to a different process after a match. This property also affects the period to look for Steam subprocesses.  float values are allowed)
          gpu.cache = false (if 'true': maps all available GPUs once after the first request (if running as a system service) or during startup (if not running as system service). Otherwise, GPUs will be mapped for every request)
          gpu.id = # comma separated list of integers representing which GPU cards should be optimized (e.g: 0, 1). If not defined, all available GPUs are considered (default)
          gpu.vendor =  # pre-defines your GPU vendor for faster GPUs mapping. Supported: nvidia, amd
          cpu.performance = false  (set cpu governors and energy policy levels to full performance on startup)
          request.allowed_users = (restricts users that can request optimizations, separated by comma. e.g: root,xpto)
          request.encrypted = true (only accepts encrypted requests for security reasons)
          profile.cache = false (cache profile files on demand to skip I/O operations. Changes to profile files require restarting)
          profile.pre_caching = false (loads all existing profile files on disk in memory during the intialization process. Requires 'profile.cache' enabled)
          nice.check.interval = 5  (processes nice levels monitoring interval in seconds)  
          optimize_children.timeout: maximum period in seconds to keep looking for the target process children (default: 30). 0 can be defined if children should be ignored.
          optimize_children.found_timeout: maximum period in seconds to still keep looking for the target process children after a child in found (default: 10). 0 can be defined if the search process should be interrupted immediately after a child is found.
    ```
    
- Its installation can be managed using the **guapow-cli** tool:
    - `guapow-cli install-optimizer`: copies the service definition file to the appropriate directory, starts and enables it.
    - `guapow-cli uninstall-optimizer`: revert changes from the command below.

- For manual installation, check [here](#opt_manual_install).

- Logs:
    - Logs are managed through the environemnt variables:
        - `GUAPOW_OPT_LOG`: enables/disables logs. Options: **1** (enables, default) and **0** (disables).
        - `GUAPOW_OPT_LOG_LEVEL`: controls the type of logging. Options: `info`, `debug`, `error` and `warning` (`debug` is the most detailed type). Default: `info`.
    - if the **optimizer** is running as a service, these variables can be changed on the definition file (`/usr/lib/systemd/system/guapow-opt.service`)
    - Logs can be viewed through the command: `journalctl -efu guapow-opt.service`

#### <a name="watcher">Watcher service</a>
- The **watcher** is an optional service that can automatically requests optimizations. It keeps looking for new started applications matching its mapping settings.
- It should ideally run at the user level, as it should act as the user.
- Its installation can be managed using the **guapow-cli** tool:
    - `guapow-cli install-watcher`: copies the service definition file to the appropriate directory, starts and enables it.
    - `guapow-cli uninstall-watcher`: revert changes from the command below.
- For manual installation, check [here](#watch_manual_inst).
- Application mappings are defined on the file `~/.config/guapow/watch.map` (user) or `/etc/guapow/watch.map` (system). Preference: user > system (if running as **root**, system is the only option).
- <a name="watch_patterns">Mappings patterns: `name_or_command=profile_file_name`</a>
    - if the first word of the pair starts with a forward-slash (/) it will be considered a **command** match, otherwise a **name** match. Example:
        ```
        abc=media   # maps an application named 'abc' to the 'media' profile (~/.config/guapow/media.profile)
        /bin/def=power  # maps an application started with the command '/bin/def' to the 'power' profile  (~/.config/guapow/power.profile)
        ```
    - **Wild-card:** the asterik symbol `*` can be used in the name/command as a replacement for **anything**. Example:
        ```
            a*bc=media  # maps a process named 'a[anything]bc' to the 'media' profile
            /bin/*=power  # map any process started with the command '/bin/{anything}' to the 'power' profile
        ```
    - **Regex:** if you want to provide your own Python regex, you can start the word with the prefix `r:`
        ```
        r:/bin/.+/xpto=media  # all applications started with commands following the pattern '/bin/[anything]/xpto' will be mapped to the 'media' profile
        r:abc.+=power  # all applications named 'abc[anything]' will be mapped to the 'power' profile
        ```
    - <a name="watch_builtin">**Built-in patterns:**<a/>
        - Pre-defined words following the pattern `__word__` that are evaulated as a regex.
            - `__steam__`: defines a regex for any game launched through **Steam** (native and Proton). Example [here](#tutorial_steam).

- <a name="watch_ignore">Ignoring processes:</a> it is possible to define patterns to ignore specific processes through the file `~/.config/guapow/watch.ignore` (user) (or `/etc/guapow/watch.ignore` (system)). Preference: user > system (if running as **root**, system is the only option).
    - this file follows the same mapping rules as `watch.map`, but you don't need to provide the profile names (as it makes no sense). e.g:
        ```
        my_app_name
        my_app_name*  
        /bin/my_proc
        r:/bin/.+/xpto
       ```
    - this feature is useful if you have general mappings that cover a lot of processes in `watch.map` (e.g: `/usr/bin/*`), but want to ignore specific ones
  
- <a name="watch_settings">Settings</a>
    - Defined at the file `~/.config/guapow/watch.conf` (user) or `/etc/guapow/watch.conf` (system). Preference: user > system (if running as **root**, system is the only option).
        ```
           interval = 1 (in seconds to check for new-born applications and request optimizations)
           regex.cache = true (caches pre-compiled regex mapping patterns in memory)
           mapping.cache = false (if 'true', caches the all mapping in memory to skip I/O calls. Changes to watch.map won't have effect until the service is restarted.
           ignored.cache = false (if 'true', caches the all ignored patterns in memory to skip I/O calls. Changes to watch.ignore won't have effect until the service is restarted.
        ```

- Logs:
    - Logs are managed through the environment variables:
        - `GUAPOW_WATCH_LOG`: enables/disables logs. Options: **1** (enables, default), **0** (disables).
        - `GUAPOW_WATCH_LOG_LEVEL`: controls the type of logging that should be printed. Options: `info`, `debug`, `error` and `warning` (`debug` is the most detailed type). Default: `info`.
    - If the **watcher** is running as a service, these variables can be changed on the definition file (`~.config/systemd/user/guapow-watch.service`)
    - Logs can be viewed through the command: `journalctl --user -efu guapow-watch.service`

#### [CLI](#cli)
- guapow provides a CLI tool called **guapow-cli** providing utility commands.
- You can check the available commands by typing: `guapow-cli --help`
- Some of the available commands:
    - `[install-uninstall]-optimizer`: install/uninstalls the **optimizer** service (requires **root**).
    - `[install-uninstall]-watcher`: install/uninstalls the **watcher** service.
    - `gen-profile name`: generates a pre-defined profile. Check the available profiles through the `--help` parameter.
 
    
### <a name="improve_opt">Improving optimizations timing</a>
The optimizations timing can be improved by tweaking some of **guapow** components settings:

- [Optimizer settings file](#opt_settings)
    - If you feel that your system and network environments are secure, you can disable the optimization requests encryption through the property `request.encrypted=false`. This can save time, since the request encryption/decryption process is heavy.
    - If you do not change your profile files frequently, you can enable the properties `profile.cache=true` and `profile.pre_caching=true`. This can save time, since all the defined profiles files are pre-loaded in memory during the service initialization and will not be read for every request.
    - You can pre-define your GPU vendor for faster GPUs mapping through the property `gpu.vendor=vendor_name`.
    - If your GPU drivers are always loaded during the system initialization, you can safely enable the property `gpu.cache=true` to skip the GPUs mapping for every request. This property is not enabled by default, since hybrid-gpu users might load their **dGPU** drivers on demand.
    - Pre-defining your window compositor will also save time for the first request (since the "guess" process will be skipped). You can define it through the `compositor={name}` property.

- [Watcher settings file](#watch_settings)
    - If you do not change your **watcher** mappings frequently, you can enable the property `mapping.cache=true` to skip the reading calls for every checking iteration.

### <a name="tutorials">Tutorials</a>
#### <a name="tutorial_steam">Auto-optimizing all your Steam games</a>
- Requires the **watcher** service installed and enabled (more on that [here](#start_watch))
- Add the following entry to the **watcher** mapping file (`~/.config/guapow/watch.map` or `/etc/guapow/watch.map`):

    ```
    __steam__=steam
    ```
- Now use the **guapow-cli** to generate a Steam profile template by typing:
    ```
    guapow-cli gen-profile steam
    ```
- Start a Steam game and check if the optimizations were applied.

### <a name="roadmap">Roadmap</a>
- More built-in optimizations
- Support more technologies and devices
- Improve memory usage

### <a name="donations">Donations</a>
- You can support this project development through [ko-fi](https://ko-fi.com/vinifmor).
