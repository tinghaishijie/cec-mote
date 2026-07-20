# cec-mote

<img width="2048" height="1152" alt="download" src="https://github.com/user-attachments/assets/4d79921d-6886-436a-afc7-0772105d844d" />

`cec-mote` is a Decky Loader plugin for SteamOS that:

- sends HDMI-CEC volume commands through the built-in `cecd` D-Bus service
- assists with installing, repairing, verifying, and uninstalling services to sleep tv on system sleep, and turn on / change input of tv on system wake, specifically when paired with active DP to HDMI adaptors such as the UGREEN 8k DP to HDMI Adaptor. Additionally it auto discovers bluetooth dongles and enables them as bluetooth wake targets
- can skip powering the TV on when the PC is resumed by a Wake-on-LAN packet (e.g. a Moonlight/Sunshine stream), so a headless streaming wake does not turn on the TV

The plugin does not talk to the CEC adapter directly. It uses `cecd` as the sole controller and sends only the validated high-level D-Bus methods exposed by `com.steampowered.CecDaemon1.CecDevice1`.

## Skip TV wake on Wake-on-LAN (streaming)

Once CEC sleep/wake is installed, the TV normally turns on every time the PC resumes. When the PC is woken over Wake-on-LAN (e.g. a Moonlight/Sunshine stream), `cec-mote` skips the CEC TV wake instead — it compares each network interface's kernel `wakeup_count` across the suspend, and if a NIC counter increased the resume was a network wake. Local wakes (Bluetooth, keyboard) still turn the TV on. Toggle it from the **CEC Sleep / Wake** section ("Skip TV wake when streaming").

> **Prerequisite:** your NIC must report the wake in sysfs — i.e. `wakeup_count` must actually increase on a WoL resume. This is driver-dependent; if it does not on your hardware, turn the toggle off.
