import subprocess


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
