# cec-mote

<img width="2048" height="1152" alt="download" src="https://github.com/user-attachments/assets/4d79921d-6886-436a-afc7-0772105d844d" />

`cec-mote` is a Decky Loader plugin for SteamOS that:

- sends HDMI-CEC volume commands through the built-in `cecd` D-Bus service
- assists with installing, repairing, verifying, and uninstalling services to sleep tv on system sleep, and turn on / change input of tv on system wake and on boot, specifically when paired with active DP to HDMI adaptors such as the UGREEN 8k DP to HDMI Adaptor. Additionally it auto discovers bluetooth dongles and enables them as bluetooth wake targets
- can turn the TV back off when the PC is being used only for a Wake-on-LAN stream (e.g. a Moonlight/Sunshine session), so a headless streaming session does not leave the TV on
- can install an opt-in fix for Bluetooth controllers that pose as an Xbox Wireless Controller and briefly stop responding in Steam after connecting (see below)

The plugin does not talk to the CEC adapter directly. It uses `cecd` as the sole controller and sends only the validated high-level D-Bus methods exposed by `com.steampowered.CecDaemon1.CecDevice1`.

## Turn the TV off during streaming (Wake-on-LAN)

Once CEC sleep/wake is installed, the TV turns on every time the PC resumes — a
power-button wake, a controller wake, and a Wake-on-LAN wake all power the TV on,
because at the moment of resume they are indistinguishable.

When the resume was really for a headless Moonlight/Sunshine stream, the TV should
not stay on. A Wake-on-LAN resume does not start the stream immediately — you still
connect from the client a few seconds (or minutes) later — so the plugin cannot
decide at resume time. Instead a `cec-stream-watch` service runs for a short window
after each resume and watches for a stream to actually start: Sunshine writes
`CLIENT CONNECTED` / `CLIENT DISCONNECTED` lines to the journal, and a stream counts
as started when the newest such line since the resume is a `CLIENT CONNECTED`. (Older
Sunshine builds are also recognised by their session-only "Pen passthrough" / "Touch
passthrough" virtual input devices under `/sys/class/input`; newer builds name their
devices "libvirtualhid ..." and keep them after the client leaves, so device names
alone are not a reliable signal.) When a stream starts the watcher sends CEC standby
to turn the TV back off, and repeats it once ten seconds later in case the TV was
still powering on. The watcher never transmits while the wake is still running, so
its standby is never overridden by the wake.
If a stream is already active at the moment the TV would be woken, the wake is
skipped and the TV stays off; if the stream connects later the TV briefly turns on
and then off — you are remote, so you don't see it. Only a stream that (re)connects
*after* the resume counts: journal lines from before the resume are not considered
(and legacy devices from a session that was still up when you slept are recorded at
suspend and ignored on the next resume), so suspending the host
mid-stream and later waking it locally still powers the TV on. Toggle it from the **CEC Sleep /
Wake** section ("Turn TV off when streaming").

## Bluetooth controller fix

Some Bluetooth controllers (e.g. the Flydigi VADER3) identify themselves as an
Xbox Wireless Controller (`045E:02E0`) but never answer HID `GET_REPORT`
requests. Every such request blocks its caller for about 3 seconds. Steam's
controller thread sends them through the controller's hidraw node and by reading
the controller battery (the kernel queries the controller on each read, because
the battery level lives in an input report the controller never sends), so input
freezes for a moment after the controller connects or the PC resumes.

The **Bluetooth Controller Fix** section installs a udev rule
(`/etc/udev/rules.d/72-cec-mote-bt-gamepad-stall.rules`, kept across SteamOS
updates) that, for Bluetooth HID devices `0005:045E:02E0` only:

- removes user access to the controller's hidraw node, so Steam reads it through
  its evdev node instead, and
- makes the controller battery's `status`, `capacity` and `uevent` attributes
  root-only, so those reads fail immediately instead of hanging.

Buttons, sticks and rumble keep working; the controller's battery level is no
longer shown. Reconnect the controller after installing or uninstalling.
CLI: `sudo ./bin/steamos-cec-bt-wake.sh --install --gamepad` (also `--verify`,
`--uninstall`).
