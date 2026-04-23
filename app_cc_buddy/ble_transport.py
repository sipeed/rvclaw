"""
BLE Transport — NUS GATT Server via BlueZ D-Bus API.

Advertises as "Claude-XXXX" with Nordic UART Service so Claude Desktop's
Hardware Buddy bridge discovers and connects to us.  Uses dbus-fast
(already installed on the Picoclaw) to talk to BlueZ.

Protocol: same newline-delimited JSON as the ESP32 reference firmware.
Claude Desktop writes heartbeats to RX; we send permission responses via TX notify.
"""

import asyncio
import logging
import subprocess

from dbus_fast import BusType, Variant
from dbus_fast.aio import MessageBus
from dbus_fast.service import ServiceInterface, method, dbus_property

from transport import Transport
from protocol import LineBuf, apply_json
from state import TamaState

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# NUS UUIDs (must match REFERENCE.md / ble_bridge.cpp exactly)
# ---------------------------------------------------------------------------
NUS_SVC_UUID = "6e400001-b5a3-f393-e0a9-e50e24dcca9e"
NUS_RX_UUID  = "6e400002-b5a3-f393-e0a9-e50e24dcca9e"
NUS_TX_UUID  = "6e400003-b5a3-f393-e0a9-e50e24dcca9e"
CCCD_UUID    = "00002902-0000-1000-8000-00805f9b34fb"

# D-Bus object paths
APP_ROOT = "/org/ccbuddy"
SVC_PATH = APP_ROOT + "/service0"
RX_PATH  = SVC_PATH + "/char0"
TX_PATH  = SVC_PATH + "/char1"
ADV_PATH = APP_ROOT + "/advertisement0"

ADAPTER_PATH = "/org/bluez/hci0"
BLUEZ_BUS    = "org.bluez"


# ---------------------------------------------------------------------------
# D-Bus interfaces for BlueZ GATT Server
# ---------------------------------------------------------------------------

class Advertisement(ServiceInterface):
    def __init__(self, local_name: str):
        super().__init__("org.bluez.LEAdvertisement1")
        self._local_name = local_name

    @dbus_property()
    def Type(self) -> "s":
        return "peripheral"

    @dbus_property()
    def ServiceUUIDs(self) -> "as":
        return [NUS_SVC_UUID]

    @dbus_property()
    def LocalName(self) -> "s":
        return self._local_name

    @dbus_property()
    def Includes(self) -> "as":
        return ["tx-power"]

    @method()
    def Release(self):
        logger.info("Advertisement released")


class GattService(ServiceInterface):
    def __init__(self):
        super().__init__("org.bluez.GattService1")

    @dbus_property()
    def UUID(self) -> "s":
        return NUS_SVC_UUID

    @dbus_property()
    def Primary(self) -> "b":
        return True


class RxCharacteristic(ServiceInterface):
    def __init__(self, on_write):
        super().__init__("org.bluez.GattCharacteristic1")
        self._on_write = on_write

    @dbus_property()
    def UUID(self) -> "s":
        return NUS_RX_UUID

    @dbus_property()
    def Service(self) -> "o":
        return SVC_PATH

    @dbus_property()
    def Flags(self) -> "as":
        return ["write", "write-without-response"]

    @method()
    def WriteValue(self, value: "ay", options: "a{sv}"):
        data = bytes(value)
        self._on_write(data)


class TxCharacteristic(ServiceInterface):
    def __init__(self):
        super().__init__("org.bluez.GattCharacteristic1")
        self._notifying = False

    @dbus_property()
    def UUID(self) -> "s":
        return NUS_TX_UUID

    @dbus_property()
    def Service(self) -> "o":
        return SVC_PATH

    @dbus_property()
    def Flags(self) -> "as":
        return ["notify"]

    @method()
    def StartNotify(self):
        self._notifying = True
        logger.info("TX notifications started")

    @method()
    def StopNotify(self):
        self._notifying = False
        logger.info("TX notifications stopped")

    @property
    def notifying(self) -> bool:
        return self._notifying


class GattApplication(ServiceInterface):
    """Implements org.freedesktop.DBus.ObjectManager for the GATT application."""

    def __init__(self, managed_objects: dict):
        super().__init__("org.freedesktop.DBus.ObjectManager")
        self._objects = managed_objects

    @method()
    def GetManagedObjects(self) -> "a{oa{sa{sv}}}":
        return self._objects


# ---------------------------------------------------------------------------
# BLE Transport
# ---------------------------------------------------------------------------

class BleTransport(Transport):
    def __init__(self, adapter: str = "hci0"):
        self._adapter = adapter
        self._adapter_path = f"/org/bluez/{adapter}"
        self._bus: MessageBus | None = None
        self._connected = False
        self._line_buf = LineBuf()
        self._rx_queue: asyncio.Queue[str] = asyncio.Queue()
        self._tx_char: TxCharacteristic | None = None
        self._local_name = "Claude"

    async def start(self) -> None:
        self._power_on()
        mac = self._read_mac()
        if mac:
            suffix = mac.replace(":", "")[-4:].upper()
            self._local_name = f"Claude-{suffix}"

        logger.info("BLE starting as '%s'", self._local_name)

        self._bus = await MessageBus(bus_type=BusType.SYSTEM).connect()

        self._tx_char = TxCharacteristic()
        rx_char = RxCharacteristic(on_write=self._on_rx_write)
        svc = GattService()
        adv = Advertisement(self._local_name)

        managed = self._build_managed_objects(svc, rx_char, self._tx_char)
        app = GattApplication(managed)

        self._bus.export(APP_ROOT, app)
        self._bus.export(SVC_PATH, svc)
        self._bus.export(RX_PATH, rx_char)
        self._bus.export(TX_PATH, self._tx_char)
        self._bus.export(ADV_PATH, adv)

        await self._set_alias()

        introspection = await self._bus.introspect(BLUEZ_BUS, self._adapter_path)
        proxy = self._bus.get_proxy_object(BLUEZ_BUS, self._adapter_path, introspection)

        gatt_mgr = proxy.get_interface("org.bluez.GattManager1")
        await gatt_mgr.call_register_application(APP_ROOT, {})
        logger.info("GATT application registered")

        adv_mgr = proxy.get_interface("org.bluez.LEAdvertisingManager1")
        await adv_mgr.call_register_advertisement(ADV_PATH, {})
        logger.info("Advertisement registered, discoverable as '%s'", self._local_name)

        self._connected = True

    def _power_on(self) -> None:
        try:
            subprocess.run(["hciconfig", self._adapter, "up"], check=True,
                           capture_output=True, timeout=5)
            logger.info("BLE adapter %s powered on", self._adapter)
        except Exception as e:
            logger.error("Failed to power on %s: %s", self._adapter, e)
            raise

    def _read_mac(self) -> str | None:
        try:
            with open(f"/sys/class/bluetooth/{self._adapter}/address") as f:
                return f.read().strip()
        except Exception:
            return None

    async def _set_alias(self) -> None:
        try:
            introspection = await self._bus.introspect(BLUEZ_BUS, self._adapter_path)
            proxy = self._bus.get_proxy_object(BLUEZ_BUS, self._adapter_path, introspection)
            props = proxy.get_interface("org.freedesktop.DBus.Properties")
            await props.call_set("org.bluez.Adapter1", "Alias",
                                 Variant("s", self._local_name))
        except Exception as e:
            logger.warning("Could not set adapter alias: %s", e)

    def _build_managed_objects(self, svc, rx_char, tx_char) -> dict:
        return {
            SVC_PATH: {
                "org.bluez.GattService1": {
                    "UUID": Variant("s", NUS_SVC_UUID),
                    "Primary": Variant("b", True),
                },
            },
            RX_PATH: {
                "org.bluez.GattCharacteristic1": {
                    "UUID": Variant("s", NUS_RX_UUID),
                    "Service": Variant("o", SVC_PATH),
                    "Flags": Variant("as", ["write", "write-without-response"]),
                },
            },
            TX_PATH: {
                "org.bluez.GattCharacteristic1": {
                    "UUID": Variant("s", NUS_TX_UUID),
                    "Service": Variant("o", SVC_PATH),
                    "Flags": Variant("as", ["notify"]),
                },
            },
        }

    def _on_rx_write(self, data: bytes) -> None:
        text = data.decode("utf-8", errors="replace")
        lines = self._line_buf.feed(text)
        for line in lines:
            self._rx_queue.put_nowait(line)

    # --- Transport interface ---

    async def read_line(self) -> str | None:
        try:
            return self._rx_queue.get_nowait()
        except asyncio.QueueEmpty:
            return None

    async def write_line(self, data: str) -> None:
        if self._tx_char is None or not self._tx_char.notifying:
            logger.debug("TX: not notifying, dropping: %s", data[:60])
            return
        payload = (data + "\n").encode("utf-8")
        chunk_size = 180
        for i in range(0, len(payload), chunk_size):
            chunk = payload[i:i + chunk_size]
            try:
                self._tx_char.emit_properties_changed(changed={"Value": chunk})
            except Exception as e:
                logger.warning("TX notify failed: %s", e)
                break
            if i + chunk_size < len(payload):
                await asyncio.sleep(0.004)

    def is_connected(self) -> bool:
        return self._connected

    async def close(self) -> None:
        if self._bus:
            try:
                introspection = await self._bus.introspect(BLUEZ_BUS, self._adapter_path)
                proxy = self._bus.get_proxy_object(BLUEZ_BUS, self._adapter_path,
                                                    introspection)
                adv_mgr = proxy.get_interface("org.bluez.LEAdvertisingManager1")
                await adv_mgr.call_unregister_advertisement(ADV_PATH)
                gatt_mgr = proxy.get_interface("org.bluez.GattManager1")
                await gatt_mgr.call_unregister_application(APP_ROOT)
            except Exception:
                pass
            self._bus.disconnect()
            self._bus = None
        self._connected = False
        logger.info("BLE transport closed")
