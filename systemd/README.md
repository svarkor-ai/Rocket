# Rocket Stock Scanner - Systemd Services

## Setup

Copy the service and timer files to the systemd user directory:

```bash
cp daily-scan.service ~/.config/systemd/user/
cp daily-scan.timer ~/.config/systemd/user/
cp portfolio-check.service ~/.config/systemd/user/
cp portfolio-check.timer ~/.config/systemd/user/
```

## Enable

```bash
systemctl --user enable daily-scan.timer
systemctl --user enable portfolio-check.timer
systemctl --user start daily-scan.timer
systemctl --user start portfolio-check.timer
```

## Schedule

- **daily-scan**: Runs at 22:00 every night
- **portfolio-check**: Runs every 5 minutes

## Logs

```bash
journalctl --user -u daily-scan.service
journalctl --user -u portfolio-check.service
systemctl --user list-timers daily-scan.timer portfolio-check.timer
```

## Manual Run

```bash
systemctl --user start daily-scan.service
systemctl --user start portfolio-check.service
```
