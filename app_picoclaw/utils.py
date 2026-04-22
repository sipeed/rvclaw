import maix, psutil, subprocess


class DevMem:
    def read(self, addr: int) -> int:
        out = subprocess.check_output(["devmem", hex(addr)]).decode().strip()
        return int(out, 16)

    def write(self, addr: int, val: int) -> None:
        subprocess.run(
            ["devmem", hex(addr), "32", hex(val & 0xFFFFFFFF)], check=True,
        )

    def close(self) -> None:
        pass

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self.close()


def get_device_id() -> str:
    """Get normalized device id for current board."""
    dev_id = maix.sys.device_id()

    if dev_id == "maixcam":
        total = psutil.virtual_memory().total
        if total < 150000000:
            return "maixcam"
        return "licheervnano"

    if dev_id == "maixcam2":
        return "maixcam2"

    return dev_id
