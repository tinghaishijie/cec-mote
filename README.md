# cec-mote

<img width="2048" height="1152" alt="download" src="https://github.com/user-attachments/assets/4d79921d-6886-436a-afc7-0772105d844d" />

`cec-mote` is a Decky Loader plugin for SteamOS that:

- sends HDMI-CEC volume commands through the built-in `cecd` D-Bus service
- assists with installing, repairing, verifying, and uninstalling services to sleep tv on system sleep, and turn on / change input of tv on system wake, specifically when paired with active DP to HDMI adaptors such as the UGREEN 8k DP to HDMI Adaptor. Additionally it auto discovers bluetooth dongles and enables them as bluetooth wake targets
- can turn the TV back off when the PC is being used only for a Wake-on-LAN stream (e.g. a Moonlight/Sunshine session), so a headless streaming session does not leave the TV on

The plugin does not talk to the CEC adapter directly. It uses `cecd` as the sole controller and sends only the validated high-level D-Bus methods exposed by `com.steampowered.CecDaemon1.CecDevice1`.

## Turn the TV off during streaming (Wake-on-LAN)

Once CEC sleep/wake is installed, the TV turns on every time the PC resumes — a
power-button wake, a controller wake, and a Wake-on-LAN wake all power the TV on,
because at the moment of resume they are indistinguishable.

When the resume was really for a headless Moonlight/Sunshine stream, the TV should
not stay on. A Wake-on-LAN resume does not start the stream immediately — you still
connect from the client a few seconds (or minutes) later — so the plugin cannot
decide at resume time. Instead a `cec-stream-watch` service runs for a short window
after each resume and watches for a stream to actually start (Sunshine creates
session-only virtual input devices such as "Pen passthrough" / "Touch passthrough"
under `/sys/class/input` that exist only while a client is streaming); when one
appears it sends CEC standby to turn the TV back off. During a streaming wake the TV
briefly turns on and then off — you are remote, so you don't see it. Toggle it from
the **CEC Sleep / Wake** section ("Turn TV off when streaming").
