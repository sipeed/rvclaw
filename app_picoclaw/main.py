import asyncio
import logging
import re

import numpy as np
from maix import audio, app, image
from st7789 import ST7789
from key import Key
from led import Led
from picoclaw import PicoclawAgent
from asr import asr_session, get_asr_backend, ASRNotConfiguredError
from config import (
    setup_logging,
    SPI_PORT, SPI_DC, SPI_RST, SPI_BACKLIGHT, SPI_SPEED_HZ, SPI_ROTATION,
    KEY_GPIO, BACK_KEY_GPIO, KEY_ACTIVE_LOW, KEY_DEBOUNCE_MS,
    FONT_PATH, FONT_NAME, FONT_SIZE, FONT_NAME_LARGE, FONT_SIZE_LARGE,
    SAMPLE_RATE, AUDIO_CHANNELS, RECORDER_VOLUME, AGENT_TIMEOUT, TEST_MODE, IPERF_SERVER,
)

logger = logging.getLogger(__name__)
from ui import (
    start_anim, stop_anim,
    show_no_speech, show_error, show_info_screen,
    animate_speak_now, animate_transcribing, animate_thinking,
    show_result, show_home_icon,
)


# -----------------------------------------------------------------------
# Main application
# -----------------------------------------------------------------------
async def main():
    setup_logging()
    image.load_font(FONT_NAME, FONT_PATH, size=FONT_SIZE)
    image.load_font(FONT_NAME_LARGE, FONT_PATH, size=FONT_SIZE_LARGE)
    image.set_default_font(FONT_NAME)

    disp = ST7789(port=SPI_PORT, dc=SPI_DC, rst=SPI_RST, backlight=SPI_BACKLIGHT,
                  spi_speed_hz=SPI_SPEED_HZ, rotation=SPI_ROTATION)

    show_home_icon(disp)
    disp.set_backlight(1)

    led = Led()
    key = Key(gpio_num=KEY_GPIO, active_low=KEY_ACTIVE_LOW, debounce_ms=KEY_DEBOUNCE_MS)
    back_key = Key(gpio_num=BACK_KEY_GPIO, active_low=KEY_ACTIVE_LOW, debounce_ms=KEY_DEBOUNCE_MS)
    recorder = audio.Recorder(sample_rate=SAMPLE_RATE, channel=AUDIO_CHANNELS, block=False)
    recorder.volume(RECORDER_VOLUME)
    recorder.reset(True)

    player = None
    if TEST_MODE:
        player = audio.Player(sample_rate=SAMPLE_RATE, channel=AUDIO_CHANNELS, block=True)
        player.volume(RECORDER_VOLUME)

    agent = PicoclawAgent(timeout=AGENT_TIMEOUT)
    _asr_fn = asr_session

    async def record_audio_until_release() -> np.ndarray | None:
        """Record while key is pressed, stop on release, return float32 PCM or None."""
        led.set_on()
        start_anim(animate_speak_now(disp))
        recorder.reset(True)

        pcm_chunks = []
        while key.is_pressed() and not app.need_exit():
            remain = recorder.get_remaining_frames()
            if remain > 0:
                raw = recorder.record(50)
                if raw and len(raw) >= 2:
                    samples = (
                        np.frombuffer(raw, dtype=np.int16)
                        .astype(np.float32) / 32768.0
                    )
                    pcm_chunks.append(samples)
            await asyncio.sleep(0.005)

        for _ in range(20):  # Read up to 20×5ms = 100ms after key release
            await asyncio.sleep(0.005)
            remain = recorder.get_remaining_frames()
            if remain <= 0:
                break
            raw = recorder.record(50)
            if raw and len(raw) >= 2:
                samples = (
                    np.frombuffer(raw, dtype=np.int16)
                    .astype(np.float32) / 32768.0
                )
                pcm_chunks.append(samples)

        if not pcm_chunks:
            return None
        return np.concatenate(pcm_chunks)

    async def transcribe_audio(pcm_all: np.ndarray) -> str | None:
        nonlocal _asr_fn
        if _asr_fn is None:
            try:
                _asr_fn = get_asr_backend(use_cache=False)
            except (ASRNotConfiguredError, Exception):
                pass
        if _asr_fn is None:
            stop_anim()
            led.set_off()
            logger.warning("ASR not configured, cannot transcribe")
            await show_error(disp, "ASR not configured")
            return None

        logger.debug("Uploading for transcription...")
        led.start_blink()
        start_anim(animate_transcribing(disp))
        try:
            result = await _asr_fn(pcm_all)
            logger.info("Transcription: %s", result) if result else logger.info("No speech recognized")
            return result or ""
        except asyncio.CancelledError:
            raise
        except Exception as e:
            logger.error("Transcription failed: %s", e)
            return ""
        finally:
            led.stop_blink()

    async def play_recorded_audio(pcm_all: np.ndarray) -> bool:
        """Play recorded float32 PCM in test mode. Return True if played."""
        if pcm_all.size == 0 or player is None:
            return False

        stop_anim()
        led.start_blink()
        start_anim(animate_transcribing(disp))
        try:
            pcm_i16 = np.clip(pcm_all, -1.0, 1.0)
            pcm_i16 = (pcm_i16 * 32767.0).astype(np.int16)
            raw = pcm_i16.tobytes()
            if not raw:
                return False

            logger.debug("Test mode: playing back recorded audio (%d bytes)", len(raw))
            player.reset(True)
            player.play(raw)
            player.reset(False)
            return True
        except Exception as e:
            logger.error("Playback failed in test mode: %s", e)
            return False
        finally:
            stop_anim()
            led.stop_blink()

    async def ask_agent_with_interrupt(text: str) -> tuple[str | None, list[str], bool]:
        logger.debug("Asking PicoClaw...")
        tool_names = []

        async def _on_tool(tc):
            tool_names.append(tc.name)

        led.start_blink()
        start_anim(animate_thinking(disp, tool_names))
        answer = None
        interrupted = False

        ask_task = None
        interrupt_task = None
        try:
            ask_task = asyncio.create_task(agent.ask(text, on_tool_call=_on_tool))

            async def wait_key_interrupt():
                while not key.is_pressed() and not app.need_exit():
                    await asyncio.sleep(0.05)

            interrupt_task = asyncio.create_task(wait_key_interrupt())

            done, pending = await asyncio.wait(
                [ask_task, interrupt_task],
                return_when=asyncio.FIRST_COMPLETED
            )

            for task in pending:
                task.cancel()

            if interrupt_task in done:
                ask_task.cancel()
                stop_anim()
                logger.info("PicoClaw interrupted, ready for next input")
                try:
                    await ask_task
                except asyncio.CancelledError:
                    pass
                interrupted = True
            else:
                response = await ask_task
                answer = response.text if response else None
                logger.info("PicoClaw response: %s", answer) if answer else logger.warning("PicoClaw returned no content")
        except Exception as e:
            logger.error("PicoClaw error: %s", e)
        finally:
            if ask_task and not ask_task.done():
                ask_task.cancel()
            if interrupt_task and not interrupt_task.done():
                interrupt_task.cancel()

        stop_anim()
        led.stop_blink()
        return answer, tool_names, interrupted

    async def _active_cycle():
        """Run one complete voice interaction cycle."""
        try:
            pcm_all = await record_audio_until_release()
            if pcm_all is None:
                return

            if TEST_MODE:
                played = await play_recorded_audio(pcm_all)
                if not played:
                    led.set_off()
                    await show_error(disp, "Playback failed")
                return

            result = await transcribe_audio(pcm_all)
            stop_anim()
            if result is None:
                return
            if not result:
                led.set_off()
                await show_no_speech(disp)
                return

            answer, tool_names, interrupted = await ask_agent_with_interrupt(result)
            if interrupted:
                return

            if answer:
                led.set_on()
                await show_result(disp, result, answer, tool_names=tool_names)
            else:
                led.set_off()
                await show_error(disp, "No response")

            while not key.is_pressed() and not app.need_exit():
                await asyncio.sleep(0.05)

        finally:
            stop_anim()
            led.set_off()

    async def _watch_back():
        while not back_key.is_pressed() and not app.need_exit():
            await asyncio.sleep(0.05)

    async def _run_wifi_speed_test() -> str:
        if not IPERF_SERVER:
            return "not configured"

        try:
            proc = await asyncio.create_subprocess_exec(
                "iperf3", "-c", IPERF_SERVER,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
        except Exception as e:
            logger.warning("iperf start failed: %s", e)
            return "iperf unable"

        try:
            stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=20)
        except asyncio.TimeoutError:
            proc.kill()
            await proc.communicate()
            return "timeout"
        except Exception as e:
            logger.warning("iperf failed: %s", e)
            return "failed"

        output = (stdout or b"").decode("utf-8", errors="ignore") + "\n" + (stderr or b"").decode("utf-8", errors="ignore")
        for line in reversed(output.splitlines()):
            m = re.search(r"([0-9]+(?:\.[0-9]+)?)\s+([KMG])bits/sec", line)
            if m:
                return f"{m.group(1)} {m.group(2)}bits/s"

        return "parse failed"

    try:
        while not app.need_exit():
            if back_key.is_pressed():
                speed_text = None
                speed_task = None
                speed_updated = False

                if TEST_MODE:
                    speed_text = "testing"
                    show_info_screen(disp, wifi_speed=speed_text)
                    speed_task = asyncio.create_task(_run_wifi_speed_test())
                else:
                    show_info_screen(disp)

                while back_key.is_pressed() and not app.need_exit():
                    await asyncio.sleep(0.02)

                while not back_key.is_pressed() and not app.need_exit():
                    if speed_task and speed_task.done() and not speed_updated:
                        try:
                            speed_text = speed_task.result()
                        except Exception as e:
                            logger.warning("iperf task failed: %s", e)
                            speed_text = "failed"
                        show_info_screen(disp, wifi_speed=speed_text)
                        speed_updated = True
                    await asyncio.sleep(0.05)

                if speed_task and not speed_task.done():
                    speed_task.cancel()
                    try:
                        await speed_task
                    except asyncio.CancelledError:
                        pass

                show_home_icon(disp)
                while back_key.is_pressed() and not app.need_exit():
                    await asyncio.sleep(0.02)
                continue

            if not key.is_pressed():
                await asyncio.sleep(0.05)
                continue

            cycle_task = asyncio.create_task(_active_cycle())
            back_task = asyncio.create_task(_watch_back())

            done, pending = await asyncio.wait(
                [cycle_task, back_task],
                return_when=asyncio.FIRST_COMPLETED
            )
            for t in pending:
                t.cancel()
                try:
                    await t
                except (asyncio.CancelledError, Exception):
                    pass

            if back_task in done and cycle_task not in done:
                show_home_icon(disp)
                logger.debug("Back key: return to home screen")
                while back_key.is_pressed() and not app.need_exit():
                    await asyncio.sleep(0.02)

    except KeyboardInterrupt:
        logger.info("Exit")
    finally:
        stop_anim()
        led.close()
        disp.turn_off()
        key.close()
        back_key.close()
        await agent.close()


if __name__ == "__main__":
    asyncio.run(main())
