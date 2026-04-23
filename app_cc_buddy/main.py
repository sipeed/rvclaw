import argparse
import asyncio
import logging
import subprocess
import time

from maix import app
app.set_sys_config_kv("comm", "method", "none")
from maix import image
from st7789 import ST7789
from key import Key
from led import Led
from config import (
    setup_logging,
    DISP_W, DISP_H,
    SPI_PORT, SPI_DC, SPI_RST, SPI_BACKLIGHT, SPI_SPEED_HZ, SPI_ROTATION,
    KEY_GPIO, BACK_KEY_GPIO, KEY_ACTIVE_LOW, KEY_DEBOUNCE_MS,
    FONT_PATH, FONT_NAME, FONT_SIZE, FONT_NAME_LARGE, FONT_SIZE_LARGE,
    FONT_NAME_ART, FONT_SIZE_ART,
    SCREEN_OFF_MS, LONG_PRESS_MS, BUDDY_AREA_H,
)
from state import TamaState, PersonaState, DisplayMode, derive
from stats import StatsManager
from transport import TransportManager, StubTransport, NetworkTransport
from protocol import apply_json, make_permission_response
from buddy import renderer, BuddyRenderer
import buddies  # noqa: F401 — registers species
from ui import (
    draw_boot_splash, show_home_icon,
    draw_hud, draw_approval, draw_info, draw_pet, draw_clock,
    draw_menu, draw_settings, INFO_PAGES, PET_PAGES,
    MENU_ITEMS, MENU_N, MENU_SWITCH_IDX, SETTINGS_ITEMS, SETTINGS_N,
    BG, WHITE, DIM,
)


PICOCLAW_INIT = "/etc/init.d/S99picoclaw_app"
CC_BUDDY_INIT = "/opt/app_cc_buddy/S99cc_buddy_app"


def _spawn_switch_to_picoclaw() -> None:
    cmd = f"sleep 1 && {CC_BUDDY_INIT} stop && {PICOCLAW_INIT} start"
    subprocess.Popen(
        ["/bin/sh", "-c", cmd],
        stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        start_new_session=True,
    )


def _show_switching(disp) -> None:
    img = image.Image(DISP_W, DISP_H, image.Format.FMT_RGB888)
    img.draw_rect(0, 0, DISP_W, DISP_H, image.Color.from_rgb(*BG), thickness=-1)

    image.set_default_font(FONT_NAME_LARGE)
    msg = "To PicoClaw..."
    tw, th = image.string_size(msg)
    img.draw_string((DISP_W - tw) // 2, (DISP_H - th) // 2, msg,
                    image.Color.from_rgb(*WHITE))

    image.set_default_font(FONT_NAME)
    sub = "please wait..."
    tw2, _ = image.string_size(sub)
    img.draw_string((DISP_W - tw2) // 2, (DISP_H + th) // 2 + 8, sub,
                    image.Color.from_rgb(*DIM))

    disp.display(img)

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Hardware stubs for deferred peripherals
# ---------------------------------------------------------------------------
def beep(freq: int = 1800, dur: int = 60) -> None:
    pass  # Stub: no buzzer confirmed yet

def check_shake() -> bool:
    return False  # Stub: no IMU confirmed yet

def is_face_down() -> bool:
    return False  # Stub: no IMU confirmed yet


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------
def parse_args():
    p = argparse.ArgumentParser(description="CC Buddy — Claude Code companion device")
    p.add_argument("--no-ble", action="store_true", help="skip BLE transport")
    p.add_argument("--no-net", action="store_true", help="skip network (TCP) transport")
    p.add_argument("--net-host", default="0.0.0.0", help="network transport bind address (default: 0.0.0.0)")
    p.add_argument("--net-port", type=int, default=19000, help="network transport TCP port (default: 19000)")
    p.add_argument("--demo", action="store_true", help="force demo mode (ignore BLE/net)")
    p.add_argument("--log-level", default=None, help="override LOG_LEVEL env var")
    return p.parse_args()


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
async def main():
    args = parse_args()
    if args.log_level:
        import config as _cfg
        _cfg.LOG_LEVEL = args.log_level.upper()
    setup_logging()
    image.load_font(FONT_NAME, FONT_PATH, size=FONT_SIZE)
    image.load_font(FONT_NAME_LARGE, FONT_PATH, size=FONT_SIZE_LARGE)
    image.set_default_font(FONT_NAME)

    renderer.init_font()

    disp = ST7789(port=SPI_PORT, dc=SPI_DC, rst=SPI_RST, backlight=SPI_BACKLIGHT,
                  spi_speed_hz=SPI_SPEED_HZ, rotation=SPI_ROTATION)

    led = Led()
    key = Key(gpio_num=KEY_GPIO, active_low=KEY_ACTIVE_LOW, debounce_ms=KEY_DEBOUNCE_MS)
    back_key = Key(gpio_num=BACK_KEY_GPIO, active_low=KEY_ACTIVE_LOW, debounce_ms=KEY_DEBOUNCE_MS)

    sm = StatsManager()
    sm.load()

    if sm.stats.species_idx < renderer.species_count:
        renderer.set_species_idx(sm.stats.species_idx)

    mgr = TransportManager()

    if args.demo:
        mgr.add(StubTransport())
        logger.info("Demo mode (--demo)")
    else:
        if not args.no_ble:
            try:
                from ble_transport import BleTransport
                ble = BleTransport()
                await ble.start()
                mgr.add(ble)
                logger.info("BLE transport ready: %s", ble._local_name)
            except Exception as e:
                logger.warning("BLE init failed: %s", e)

        if not args.no_net:
            try:
                net = NetworkTransport(host=args.net_host, port=args.net_port)
                await net.start()
                mgr.add(net)
            except Exception as e:
                logger.warning("Network transport failed: %s", e)

    tama = TamaState()

    # State
    base_state = PersonaState.SLEEP
    active_state = PersonaState.SLEEP
    one_shot_until: float = 0
    display_mode = DisplayMode.NORMAL
    info_page = 0
    pet_page = 0
    msg_scroll = 0
    last_line_gen = 0
    last_prompt_id = ""
    prompt_arrived_ms: float = 0
    response_sent = False
    last_interact: float = time.time()
    screen_off = False

    menu_open = False
    menu_sel = 0
    settings_open = False
    settings_sel = 0

    key_a_pressed_at: float = 0
    key_a_was_pressed = False
    key_a_long_fired = False
    swallow_a = False
    swallow_b = False
    key_b_was_pressed = False

    # Boot splash
    img = image.Image(DISP_W, DISP_H, image.Format.FMT_RGB888)
    body_color = renderer._species_table[renderer.species_idx].body_color if renderer.species_count > 0 else (192, 85, 48)
    draw_boot_splash(img, sm.stats.owner_name, sm.stats.pet_name, body_color)
    disp.display(img)
    disp.set_backlight(1)
    await asyncio.sleep(1.8)

    def wake():
        nonlocal last_interact, screen_off
        last_interact = time.time()
        if screen_off:
            disp.set_backlight(1)
            screen_off = False

    def trigger_one_shot(state: PersonaState, dur_ms: int):
        nonlocal active_state, one_shot_until
        active_state = state
        one_shot_until = time.time() + dur_ms / 1000.0

    framebuf = image.Image(DISP_W, DISP_H, image.Format.FMT_RGB888)
    prev_tama_updated = 0.0
    prev_active_state = PersonaState.SLEEP
    last_render_sec = 0

    try:
        while not app.need_exit():
            now = time.time()
            img = framebuf
            dirty = False

            # --- Poll transport ---
            response = await mgr.poll(tama)
            if response:
                await mgr.write_line(response)
            if tama.last_updated != prev_tama_updated:
                prev_tama_updated = tama.last_updated
                dirty = True

            if sm.stats.tokens != tama.tokens and tama.tokens > 0:
                sm.on_bridge_tokens(tama.tokens)

            if sm.poll_level_up():
                trigger_one_shot(PersonaState.CELEBRATE, 3000)
                dirty = True

            # --- Derive state ---
            if not mgr.is_connected():
                tama.connected = False
            elif tama.last_updated > 0 and now - tama.last_updated > 30:
                tama.connected = False
                tama.msg = "No Claude connected"

            base_state = derive(tama)
            if now >= one_shot_until:
                active_state = base_state
            if active_state != prev_active_state:
                prev_active_state = active_state
                dirty = True

            # --- Prompt detection ---
            if tama.prompt_id != last_prompt_id:
                last_prompt_id = tama.prompt_id
                response_sent = False
                dirty = True
                if tama.prompt_id:
                    prompt_arrived_ms = now
                    wake()
                    beep(1200, 80)
                    display_mode = DisplayMode.NORMAL
                    menu_open = False
                    settings_open = False
                    renderer.invalidate()

            in_prompt = bool(tama.prompt_id) and not response_sent

            # --- LED ---
            if active_state == PersonaState.ATTENTION and sm.settings.led:
                if int(now * 2.5) % 2 == 0:
                    led.set_on()
                else:
                    led.set_off()
            else:
                led.set_off()

            # --- Transcript scroll reset ---
            if tama.line_gen != last_line_gen:
                msg_scroll = 0
                last_line_gen = tama.line_gen
                dirty = True
                wake()

            # --- Button handling ---
            key_a_now = key.is_pressed()
            key_b_now = back_key.is_pressed()

            if key_a_now or key_b_now:
                if screen_off:
                    if key_a_now:
                        swallow_a = True
                    if key_b_now:
                        swallow_b = True
                dirty = True
                wake()

            # Key A long-press detection
            if key_a_now and not key_a_was_pressed:
                key_a_pressed_at = now
                key_a_long_fired = False
            key_a_was_pressed_prev = key_a_was_pressed
            key_a_was_pressed = key_a_now

            if key_a_now and not key_a_long_fired and not swallow_a:
                if (now - key_a_pressed_at) * 1000 >= LONG_PRESS_MS:
                    key_a_long_fired = True
                    beep(800, 60)
                    if settings_open:
                        settings_open = False
                        renderer.invalidate()
                    else:
                        menu_open = not menu_open
                        menu_sel = 0
                        if not menu_open:
                            renderer.invalidate()

            # Key A release
            if not key_a_now and key_a_was_pressed_prev:
                dirty = True
                if not key_a_long_fired and not swallow_a:
                    if in_prompt:
                        cmd = make_permission_response(tama.prompt_id, "once")
                        await mgr.write_line(cmd)
                        response_sent = True
                        took_s = int(now - prompt_arrived_ms)
                        sm.on_approval(took_s)
                        beep(2400, 60)
                        if took_s < 5:
                            trigger_one_shot(PersonaState.HEART, 2000)
                    elif settings_open:
                        beep(1800, 30)
                        settings_sel = (settings_sel + 1) % SETTINGS_N
                    elif menu_open:
                        beep(1800, 30)
                        menu_sel = (menu_sel + 1) % MENU_N
                    else:
                        beep(1800, 30)
                        display_mode = DisplayMode((display_mode + 1) % DisplayMode.COUNT)
                        renderer.invalidate()
                swallow_a = False

            # Key B edge detection (non-blocking, like A)
            key_b_edge = key_b_now and not key_b_was_pressed
            key_b_was_pressed = key_b_now

            if key_b_edge and not swallow_b:
                dirty = True
                if in_prompt:
                    cmd = make_permission_response(tama.prompt_id, "deny")
                    await mgr.write_line(cmd)
                    response_sent = True
                    sm.on_denial()
                    beep(600, 60)
                elif settings_open:
                    _apply_setting(settings_sel, sm, renderer)
                    beep(2400, 30)
                elif menu_open:
                    _apply_menu(menu_sel, sm)
                    if menu_sel == MENU_N - 1:
                        menu_open = False
                        renderer.invalidate()
                    elif menu_sel == 0:
                        settings_open = True
                        menu_open = False
                        settings_sel = 0
                    elif menu_sel == 1:
                        menu_open = False
                        display_mode = DisplayMode.INFO
                        info_page = 1
                        renderer.invalidate()
                    elif menu_sel == 2:
                        menu_open = False
                        display_mode = DisplayMode.INFO
                        info_page = 5
                        renderer.invalidate()
                    elif menu_sel == 3:
                        pass
                    elif menu_sel == MENU_SWITCH_IDX:
                        beep(800, 120)
                        _show_switching(disp)
                        _spawn_switch_to_picoclaw()
                        try:
                            await asyncio.sleep(30)
                        except asyncio.CancelledError:
                            pass
                        return
                    beep(2400, 30)
                elif display_mode == DisplayMode.INFO:
                    beep(2400, 30)
                    info_page = (info_page + 1) % INFO_PAGES
                elif display_mode == DisplayMode.PET:
                    beep(2400, 30)
                    pet_page = (pet_page + 1) % PET_PAGES
                else:
                    beep(2400, 30)
                    msg_scroll = 0 if msg_scroll >= 30 else msg_scroll + 1

            if not key_b_now:
                swallow_b = False

            # --- Clock mode ---
            clocking = (display_mode == DisplayMode.NORMAL
                        and not menu_open and not settings_open
                        and not in_prompt
                        and tama.sessions_running == 0
                        and tama.sessions_waiting == 0
                        and not tama.connected)

            if clocking:
                h = time.localtime().tm_hour
                dow = time.localtime().tm_wday
                if 1 <= h < 7:
                    active_state = PersonaState.SLEEP
                else:
                    active_state = PersonaState.IDLE if now >= one_shot_until else active_state

            # --- Dirty: time-based displays ---
            if renderer.is_tick_due():
                dirty = True
            if clocking or in_prompt:
                cur_sec = int(now)
                if cur_sec != last_render_sec:
                    last_render_sec = cur_sec
                    dirty = True

            # --- Render (only when dirty) ---
            if not screen_off and dirty:
                renderer.tick(img, active_state)

                if settings_open:
                    draw_settings(img, settings_sel, sm, renderer, body_color)
                elif menu_open:
                    demo_on = isinstance(mgr.active, StubTransport)
                    draw_menu(img, menu_sel, demo_on, body_color)
                elif display_mode == DisplayMode.INFO:
                    draw_info(img, info_page, tama, sm, active_state, body_color)
                elif display_mode == DisplayMode.PET:
                    draw_pet(img, pet_page, sm, body_color)
                elif clocking:
                    draw_clock(img, body_color)
                elif sm.settings.hud:
                    if in_prompt:
                        draw_approval(img, tama, prompt_arrived_ms, response_sent,
                                      body_color)
                    else:
                        draw_hud(img, tama, msg_scroll, body_color)

                disp.display(img)

            # --- Screen auto-off ---
            if sm.settings.sleep and not screen_off and not in_prompt:
                if now - last_interact > SCREEN_OFF_MS / 1000:
                    disp.set_backlight(0)
                    screen_off = True

            await asyncio.sleep(0.1 if screen_off else 0.05)

    except KeyboardInterrupt:
        logger.info("Exit")
    finally:
        led.close()
        disp.turn_off()
        key.close()
        back_key.close()
        await mgr.close()


def _apply_setting(idx: int, sm: StatsManager, buddy: BuddyRenderer) -> None:
    s = sm.settings
    if idx == 0:
        s.brightness = (s.brightness + 1) % 5
    elif idx == 1:
        s.sound = not s.sound
    elif idx == 2:
        s.led = not s.led
    elif idx == 3:
        s.hud = not s.hud
    elif idx == 4:
        buddy.next_species()
        sm.set_species_idx(buddy.species_idx)
    elif idx == 5:
        s.sleep = not s.sleep
    elif idx == 6:
        sm.factory_reset()
        return
    elif idx == 7:
        return
    sm.save_settings()


def _apply_menu(idx: int, sm: StatsManager) -> None:
    pass


if __name__ == "__main__":
    asyncio.run(main())
