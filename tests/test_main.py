from __future__ import annotations

import asyncio
import importlib
import os
import sys
import tempfile
import types
import unittest
from unittest.mock import AsyncMock, Mock, patch


class _Logger:
    def info(self, *args, **kwargs):
        pass

    def warning(self, *args, **kwargs):
        pass

    def error(self, *args, **kwargs):
        pass


tmp_plugin_dir = tempfile.mkdtemp(prefix="cec-mote-plugin-")
os.makedirs(os.path.join(tmp_plugin_dir, "bin"), exist_ok=True)
with open(os.path.join(tmp_plugin_dir, "bin", "steamos-cec-bt-wake.sh"), "w", encoding="utf-8") as handle:
    handle.write("#!/usr/bin/env bash\n")

sys.modules.setdefault(
    "decky",
    types.SimpleNamespace(logger=_Logger(), DECKY_PLUGIN_DIR=tmp_plugin_dir),
)
mote_main = importlib.import_module("main")


class FakeProcess:
    def __init__(self, *, stdout=b"", stderr=b"", returncode=0):
        self._stdout = stdout
        self._stderr = stderr
        self.returncode = returncode
        self.terminated = False
        self.killed = False
        self.wait_called = False

    async def communicate(self):
        return self._stdout, self._stderr

    def terminate(self):
        self.terminated = True

    def kill(self):
        self.killed = True

    async def wait(self):
        self.wait_called = True
        return self.returncode


class SlowProcess(FakeProcess):
    async def communicate(self):
        await asyncio.sleep(1)
        return await super().communicate()


class PluginTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.plugin = mote_main.Plugin()

    def test_parse_audio_logical_address_tv(self):
        self.assertEqual(self.plugin._parse_audio_logical_address("y 0"), 0)

    def test_parse_audio_logical_address_audio_system(self):
        self.assertEqual(self.plugin._parse_audio_logical_address("y 5"), 5)

    def test_rejects_malformed_audio_logical_address(self):
        with self.assertRaisesRegex(mote_main.CecError, "Malformed AudioLogicalAddress"):
            self.plugin._parse_audio_logical_address("bogus")

    def test_rejects_logical_address_fifteen(self):
        with self.assertRaisesRegex(mote_main.CecError, "Invalid audio logical address"):
            self.plugin._parse_audio_logical_address("y 15")

    def test_parse_setup_result_configured(self):
        result = mote_main.CommandResult(
            args=tuple(),
            returncode=0,
            stdout="\n".join(
                [
                    "Layout",
                    "------",
                    "OK   Persistent data directory exists: /var/lib/steamos-cec-bt-wake",
                    "CEC",
                    "---",
                    "OK   State file loaded: /var/lib/steamos-cec-bt-wake/state.conf",
                    "OK   Stored CEC physical address: 3.0.0.0",
                    "Bluetooth wake",
                    "--------------",
                    "OK   Configured Bluetooth wake target: 13d3:3558",
                    "SteamOS atomic updates",
                    "----------------------",
                    "OK   Atomic-update keep-list exists: /etc/atomic-update.conf.d/steamos-cec-bt-wake.conf",
                    "Verification passed.",
                ]
            ),
            stderr="",
        )

        parsed = self.plugin._parse_setup_result("verify", "bluetooth", result)

        self.assertTrue(parsed["ok"])
        self.assertEqual(parsed["component"], "bluetooth")
        self.assertEqual(parsed["state"], "configured")
        self.assertEqual(parsed["details"]["bluetoothTarget"], "13d3:3558")
        self.assertEqual(
            parsed["details"]["keepListPath"],
            "/etc/atomic-update.conf.d/steamos-cec-bt-wake.conf",
        )

    def test_parse_setup_result_needs_setup(self):
        result = mote_main.CommandResult(
            args=tuple(),
            returncode=1,
            stdout="\n".join(
                [
                    "Layout",
                    "------",
                    "FAIL Persistent data directory missing: /var/lib/steamos-cec-bt-wake",
                    "FAIL CEC helper missing: /var/lib/steamos-cec-bt-wake/cec-control",
                    "FAIL Bluetooth helper missing: /var/lib/steamos-cec-bt-wake/enable-bluetooth-wakeup",
                    "CEC",
                    "---",
                    "WARN State file missing from /var/lib/steamos-cec-bt-wake/state.conf and /etc/steamos-cec-bt-wake.conf",
                    "FAIL cec-sleep.service unit missing: /etc/systemd/system/cec-sleep.service",
                    "SteamOS atomic updates",
                    "----------------------",
                    "FAIL Atomic-update keep-list missing: /etc/atomic-update.conf.d/steamos-cec-bt-wake.conf",
                    "Verification found 8 problem(s).",
                ]
            ),
            stderr="",
        )

        parsed = self.plugin._parse_setup_result("verify", "cec", result)

        self.assertFalse(parsed["ok"])
        self.assertEqual(parsed["component"], "cec")
        self.assertEqual(parsed["state"], "needs_setup")
        self.assertEqual(parsed["summary"], "CEC sleep/wake setup is not installed yet.")

    def test_parse_setup_result_needs_repair(self):
        result = mote_main.CommandResult(
            args=tuple(),
            returncode=1,
            stdout="\n".join(
                [
                    "Layout",
                    "------",
                    "OK   Persistent data directory exists: /var/lib/steamos-cec-bt-wake",
                    "CEC",
                    "---",
                    "OK   State file loaded: /var/lib/steamos-cec-bt-wake/state.conf",
                    "FAIL cec-wake.service not enabled",
                    "WARN Recoverable partial-install damage detected: project files exist but the state file is missing.",
                    "Verification found 1 problem(s).",
                ]
            ),
            stderr="",
        )

        parsed = self.plugin._parse_setup_result("verify", "cec", result)

        self.assertEqual(parsed["component"], "cec")
        self.assertEqual(parsed["state"], "needs_repair")
        self.assertEqual(parsed["summary"], "CEC sleep/wake setup exists but needs repair.")

    def test_get_setup_script_path_uses_bundled_asset(self):
        script_path = self.plugin._get_setup_script_path()
        self.assertTrue(script_path.endswith("bin/steamos-cec-bt-wake.sh"))
        self.assertTrue(os.path.exists(script_path))

    def _use_temp_policy(self) -> str:
        tmpdir = tempfile.TemporaryDirectory(prefix="cec-mote-policy-")
        self.addCleanup(tmpdir.cleanup)
        policy = os.path.join(tmpdir.name, "cec-wake-policy.conf")
        for target, value in (
            ("VAR_LIB_DIR", tmpdir.name),
            ("CEC_WAKE_POLICY_FILE", policy),
        ):
            patcher = patch.object(mote_main, target, value)
            patcher.start()
            self.addCleanup(patcher.stop)
        return policy

    async def test_get_cec_wake_policy_defaults_enabled(self):
        self._use_temp_policy()
        result = await self.plugin.get_cec_wake_policy()
        self.assertEqual(result, {"skipOnNetworkWake": True})

    async def test_set_cec_wake_policy_roundtrip(self):
        policy = self._use_temp_policy()

        disabled = await self.plugin.set_cec_wake_policy(False)
        self.assertTrue(disabled["ok"])
        self.assertFalse(disabled["skipOnNetworkWake"])
        with open(policy, encoding="utf-8") as handle:
            self.assertIn("SKIP_CEC_WAKE_ON_NETWORK=0", handle.read())
        self.assertEqual(
            await self.plugin.get_cec_wake_policy(),
            {"skipOnNetworkWake": False},
        )

        enabled = await self.plugin.set_cec_wake_policy(True)
        self.assertTrue(enabled["skipOnNetworkWake"])
        with open(policy, encoding="utf-8") as handle:
            self.assertIn("SKIP_CEC_WAKE_ON_NETWORK=1", handle.read())
        self.assertEqual(
            await self.plugin.get_cec_wake_policy(),
            {"skipOnNetworkWake": True},
        )

    async def test_get_cec_wake_policy_reads_disabled_value(self):
        policy = self._use_temp_policy()
        with open(policy, "w", encoding="utf-8") as handle:
            handle.write("SKIP_CEC_WAKE_ON_NETWORK=0\n")
        self.assertEqual(
            await self.plugin.get_cec_wake_policy(),
            {"skipOnNetworkWake": False},
        )

    async def test_set_cec_wake_policy_reports_write_failure(self):
        self._use_temp_policy()
        with patch.object(
            mote_main.Plugin,
            "_write_cec_wake_policy",
            Mock(side_effect=OSError("boom")),
        ):
            result = await self.plugin.set_cec_wake_policy(True)
        self.assertFalse(result["ok"])
        self.assertIn("boom", result["error"])

    async def test_volume_up_maps_to_volume_up_method(self):
        await self._assert_action_mapping("volume_up", "VolumeUp")

    async def test_volume_down_maps_to_volume_down_method(self):
        await self._assert_action_mapping("volume_down", "VolumeDown")

    async def test_mute_maps_to_mute_method(self):
        await self._assert_action_mapping("mute", "Mute")

    async def test_call_cec_method_uses_signature_and_dynamic_address(self):
        session = mote_main.SessionContext(
            username="deck",
            busctl_path="/usr/bin/busctl",
            systemctl_path=None,
            runuser_path="/usr/sbin/runuser",
            env_path="/usr/bin/env",
            env={"LC_ALL": "C"},
        )
        self.plugin._run_command = AsyncMock(
            return_value=mote_main.CommandResult(
                args=tuple(),
                returncode=0,
                stdout="",
                stderr="",
            )
        )

        await self.plugin._call_cec_method(
            session,
            "/com/steampowered/CecDaemon1/Devices/Cec1",
            "VolumeDown",
            5,
        )

        args = self.plugin._run_command.await_args.args[0]
        self.assertEqual(
            args,
            (
                "/usr/bin/busctl",
                "--user",
                "call",
                "com.steampowered.CecDaemon1",
                "/com/steampowered/CecDaemon1/Devices/Cec1",
                "com.steampowered.CecDaemon1.CecDevice1",
                "VolumeDown",
                "y",
                "5",
            ),
        )

    async def test_device_discovery_prefers_active_object(self):
        session = mote_main.SessionContext(
            username="deck",
            busctl_path="/usr/bin/busctl",
            systemctl_path=None,
            runuser_path="/usr/sbin/runuser",
            env_path="/usr/bin/env",
            env={"LC_ALL": "C"},
        )

        async def read_property(_session, object_path, property_name, *, error_message):
            if object_path.endswith("Cec0") and property_name == "AudioLogicalAddress":
                return "y 0"
            if object_path.endswith("Cec0") and property_name == "Active":
                return "b false"
            if object_path.endswith("Cec1") and property_name == "AudioLogicalAddress":
                return "y 5"
            if object_path.endswith("Cec1") and property_name == "Active":
                return "b true"
            raise mote_main.CecError(error_message, stderr="Unknown object")

        self.plugin._read_property = AsyncMock(side_effect=read_property)

        device = await self.plugin._discover_device_once(session)

        self.assertEqual(device.object_path, "/com/steampowered/CecDaemon1/Devices/Cec1")
        self.assertTrue(device.active)

    async def test_stale_cached_object_is_invalidated_and_rediscovered(self):
        session = mote_main.SessionContext(
            username="deck",
            busctl_path="/usr/bin/busctl",
            systemctl_path=None,
            runuser_path="/usr/sbin/runuser",
            env_path="/usr/bin/env",
            env={"LC_ALL": "C"},
        )
        self.plugin._cached_object_path = "/com/steampowered/CecDaemon1/Devices/Cec0"
        self.plugin._get_session_context = Mock(return_value=session)
        self.plugin._discover_device = AsyncMock(
            return_value=mote_main.DeviceInfo(
                object_path="/com/steampowered/CecDaemon1/Devices/Cec1",
                active=True,
            )
        )
        self.plugin._read_audio_logical_address = AsyncMock(
            side_effect=[
                mote_main.CecError(
                    "No CEC device object discovered",
                    stderr="Unknown object",
                ),
                5,
            ]
        )
        self.plugin._call_cec_method = AsyncMock(return_value=None)

        result = await self.plugin.volume_up()

        self.assertTrue(result["ok"])
        self.assertEqual(result["objectPath"], "/com/steampowered/CecDaemon1/Devices/Cec1")
        self.assertEqual(
            self.plugin._cached_object_path,
            "/com/steampowered/CecDaemon1/Devices/Cec1",
        )
        self.plugin._discover_device.assert_awaited_once()

    async def test_run_command_returns_controlled_timeout(self):
        process = SlowProcess()

        with patch("main.asyncio.create_subprocess_exec", AsyncMock(return_value=process)):
            with self.assertRaisesRegex(mote_main.CecError, "Command timeout"):
                await self.plugin._run_command(
                    ("/usr/bin/busctl", "--user"),
                    env={"LC_ALL": "C"},
                    error_message="ignored",
                    timeout_seconds=0.01,
                )

        self.assertTrue(process.terminated)
        self.assertTrue(process.wait_called)

    async def test_run_command_never_invokes_shell(self):
        process = FakeProcess(stdout=b"y 0", stderr=b"", returncode=0)

        async def wait_for_side_effect(awaitable, timeout):
            return await awaitable

        with patch("main.asyncio.create_subprocess_exec", AsyncMock(return_value=process)) as exec_mock, patch(
            "main.asyncio.wait_for",
            side_effect=wait_for_side_effect,
        ):
            result = await self.plugin._run_command(
                ("/usr/bin/busctl", "--user", "get-property"),
                env={"LC_ALL": "C"},
                error_message="ignored",
            )

        self.assertEqual(result.stdout, "y 0")
        self.assertNotIn("shell", exec_mock.await_args.kwargs)

    async def _assert_action_mapping(self, action_name: str, expected_method: str):
        session = mote_main.SessionContext(
            username="deck",
            busctl_path="/usr/bin/busctl",
            systemctl_path=None,
            runuser_path="/usr/sbin/runuser",
            env_path="/usr/bin/env",
            env={"LC_ALL": "C"},
        )
        self.plugin._get_session_context = Mock(return_value=session)
        self.plugin._get_object_path = AsyncMock(
            return_value="/com/steampowered/CecDaemon1/Devices/Cec0"
        )
        self.plugin._read_audio_logical_address = AsyncMock(return_value=5)
        self.plugin._call_cec_method = AsyncMock(return_value=None)

        result = await getattr(self.plugin, action_name)()

        self.assertTrue(result["ok"])
        self.plugin._call_cec_method.assert_awaited_once_with(
            session,
            "/com/steampowered/CecDaemon1/Devices/Cec0",
            expected_method,
            5,
        )


if __name__ == "__main__":
    unittest.main()
