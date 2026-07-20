# cec-mote

<img width="2048" height="1152" alt="download" src="https://github.com/user-attachments/assets/4d79921d-6886-436a-afc7-0772105d844d" />

`cec-mote` is a Decky Loader plugin for SteamOS that:

- sends HDMI-CEC volume commands through the built-in `cecd` D-Bus service
- assists with installing, repairing, verifying, and uninstalling services to sleep tv on system sleep, and turn on / change input of tv on system wake, specifically when paired with active DP to HDMI adaptors such as the UGREEN 8k DP to HDMI Adaptor. Additionally it auto discovers bluetooth dongles and enables them as bluetooth wake targets
- can skip powering the TV on when the PC is resumed by a Wake-on-LAN packet (e.g. a Moonlight/Sunshine stream), so a headless streaming wake does not turn on the TV

The plugin does not talk to the CEC adapter directly. It uses `cecd` as the sole controller and sends only the validated high-level D-Bus methods exposed by `com.steampowered.CecDaemon1.CecDevice1`.

## Skip TV wake on Wake-on-LAN (streaming)

Once CEC sleep/wake is installed, the TV normally turns on every time the PC resumes. When the PC is woken over Wake-on-LAN for a headless Moonlight/Sunshine stream, `cec-mote` skips the CEC TV wake instead. It decides by checking, right after resume, whether a real game controller is connected (a joystick device that is not Steam Input's virtual one): a controller means someone is at the console → turn the TV on; a streaming wake has none → skip. Toggle it from the **CEC Sleep / Wake** section ("Skip TV wake when streaming").

> **Prerequisite:** you wake locally with a game controller. A wake with no controller connected (e.g. power button only) is treated as a streaming wake and leaves the TV off, and a controller left connected while you stream counts as local — turn controllers off when away, or flip the toggle.
