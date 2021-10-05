---
name: Bug report
about: Report errors or unexpected behaviors
title: "[BUG] Describe the unexpected behavior in a few words..."
labels: ''
assignees: ''

---

### System specification
- O.S name/version: <os name/version> (e.g: Ubuntu 20.04)
- Python version: <version> (e.g: 3.8)
- Installation method: <method> (pip, pacman, yay)

### Describe the expected behavior
e.g: the application X nice level should have been changed to -1 after launching it with the command: `GUAPOW_CONFIG="proc.nice=-1" guapow X`

###  Describe what is happening 
e.g: the application X nice level remains 0.

### Paste here the logs (as a compressed file, please)
- `guapow-opt` service logs (`journalctl -efu guapow-opt.service`)
- `guapow` command logs (**if applied**. `GUAPOW_LOG=1 guapow command`)
- `guapow-watch`service logs (**if applied**. `journalctl --user -efu guapow-opt.service`)
