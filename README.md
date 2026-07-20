# cec-mote

<img width="2048" height="1152" alt="download" src="https://github.com/user-attachments/assets/4d79921d-6886-436a-afc7-0772105d844d" />

`cec-mote` is a Decky Loader plugin for SteamOS that:

- sends HDMI-CEC volume commands through the built-in `cecd` D-Bus service
- assists with installing, repairing, verifying, and uninstalling services to sleep tv on system sleep, and turn on / change input of tv on system wake, specifically when paired with active DP to HDMI adaptors such as the UGREEN 8k DP to HDMI Adaptor. Additionally it auto discovers bluetooth dongles and enables them as bluetooth wake targets
- can skip powering the TV on when the PC is resumed by a Wake-on-LAN packet (e.g. a Moonlight/Sunshine stream), so a headless streaming wake does not turn on the TV

The plugin does not talk to the CEC adapter directly. It uses `cecd` as the sole controller and sends only the validated high-level D-Bus methods exposed by `com.steampowered.CecDaemon1.CecDevice1`.

## Skip TV wake on Wake-on-LAN (streaming)

By default, once CEC sleep/wake is installed, the TV is powered on every time the PC resumes from sleep. If you wake the PC from your phone with Moonlight/Sunshine over Wake-on-LAN for a headless streaming session, you usually don't want the TV to turn on.

`cec-mote` detects this: it snapshots each network interface's kernel `wakeup_count` just before suspend and compares it after resume. If a NIC counter increased, the resume was a network (WoL) wake and the CEC TV wake is skipped. Local wakes (Bluetooth controller, keyboard, power button) bump a different device's counter, so the TV still turns on as before.

Toggle it any time from the plugin's **CEC Sleep / Wake** section ("Skip TV wake when streaming"). The check is conservative: if it cannot positively detect a network wake, it turns the TV on as usual, so a detection miss never leaves the TV dark on a normal local wake.

### Prerequisites for this to work

1. **Reinstall CEC after installing or updating the plugin.** The on-disk helper (`/var/lib/steamos-cec-bt-wake/cec-control`) is generated at install time, so hit **Reinstall** in the CEC Sleep / Wake section once to write out the new logic. Flipping the toggle afterwards does *not* require a reinstall.
2. **CEC sleep/wake must be installed** (not just the volume remote) — the detection runs inside the `cec-sleep` / `cec-wake` services.
3. **Your NIC must report the wake in sysfs.** This is driver-dependent. Verify that `wakeup_count` actually increases across a WoL resume before trusting it:
   ```bash
   cat /sys/class/net/<iface>/device/power/wakeup_count   # note the value
   # suspend, wake the PC over Moonlight (WoL), then read again — it must have increased
   ```
   If it does not increase on your hardware, network wakes cannot be detected; leave the toggle off.
4. **Applies only to resume-from-sleep.** `cec-wake.service` is bound to `suspend.target`, so a full power-on (cold WoL boot) is unaffected — and does not trigger a CEC wake anyway.
5. **Moonlight must wake the PC via a Wake-on-LAN magic packet** (its standard behavior), so the wake lands on the NIC that prerequisite 3 checks.

You can confirm the decision after a wake in the service log:

```bash
journalctl -u cec-wake.service   # "Network (WoL) wake detected ... skipping CEC TV wake"
```
