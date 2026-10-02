#!/usr/bin/env bash
# One-off (2026-10-02): after the mode probe, kill the probe's deadman and resume the main run (finished adapters are
# skipped) with a fresh deadman. A file, not an ssh one-liner, so the pkill pattern cannot match the ssh command.
set -uo pipefail
source "$(dirname "$0")/config.sh"
cd "$REMOTE_ROOT"
pkill -f "[d]eadman_stop"; sleep 1
(SKIP_SMOKE=1 setsid nohup bash pod/run_rh_main.sh > logs/rh_main_resume.log 2>&1 < /dev/null &)
sleep 3
(GRACE_MIN=30 setsid nohup bash pod/deadman_stop.sh logs/rh_main_resume.log "[r]un_rh_main.sh" > logs/deadman.log 2>&1 < /dev/null &)
sleep 2
ps -eo pid,args | grep -E "[r]un_rh_main|[d]eadman_stop"
head -4 logs/rh_main_resume.log
