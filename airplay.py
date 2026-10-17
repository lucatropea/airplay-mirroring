from __future__ import annotations

from mirror.uxplay import ensure_uxplay, launch_uxplay


def main() -> None:
    exe = ensure_uxplay()
    raise SystemExit(launch_uxplay(exe))


if __name__ == "__main__":
    main()
