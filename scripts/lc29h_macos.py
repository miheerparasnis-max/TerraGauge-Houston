#!/usr/bin/env python3
"""Minimal macOS serial utility for the Waveshare/Quectel LC29H(BS).

This tool deliberately uses only the Python standard library.  It is intended
for a directly connected LC29H(BS) whose Waveshare UART-selection jumper is in
position A (USB <-> LC29H).  It does *not* claim that a short Survey-in is a
surveyed coordinate or evidence of land motion.

Examples (the port is auto-detected; pass --port to override):
  python3 scripts/lc29h_macos.py listen
  python3 scripts/lc29h_macos.py probe --port /dev/cu.usbserial-110
  python3 scripts/lc29h_macos.py audit --port /dev/cu.usbserial-110
  python3 scripts/lc29h_macos.py configure-test --port /dev/cu.usbserial-110
  python3 scripts/lc29h_macos.py capture --port /dev/cu.usbserial-110 \
      --seconds 240 --output ~/Desktop/terragauge_rtcm_test.bin
"""

from __future__ import annotations

import argparse
import fcntl
import os
from pathlib import Path
import select
import sys
import termios
import time


def _detect_port() -> str:
    """First CP210x-style USB serial device; the number after usbserial- changes with the USB socket."""
    import glob
    found = sorted(glob.glob("/dev/cu.usbserial-*")) + sorted(glob.glob("/dev/cu.SLAB_USBtoUART*"))
    return found[0] if found else "/dev/cu.usbserial-110"


DEFAULT_PORT = _detect_port()
DEFAULT_BAUD = 115200


def nmea_sentence(body: str) -> bytes:
    """Build a Quectel proprietary NMEA-style command with its XOR checksum."""
    checksum = 0
    for character in body:
        checksum ^= ord(character)
    return f"${body}*{checksum:02X}\r\n".encode("ascii")


IOSSIOSPEED = 0x80045402  # <IOKit/serial/ioss.h>: any speed, e.g. 460800 or 921600


def baud_constant(baud: int) -> int | None:
    """termios constant for standard speeds; None means 'set it with IOSSIOSPEED'."""
    return getattr(termios, f"B{baud}", None)


def open_port(port: str, baud: int) -> int:
    """Open a raw 8-N-1 serial port and assert modem-control outputs if present."""
    fd = os.open(port, os.O_RDWR | os.O_NOCTTY | os.O_NONBLOCK)
    speed = baud_constant(baud) or termios.B230400
    settings = termios.tcgetattr(fd)
    settings[0] = 0
    settings[1] = 0
    settings[2] = termios.CS8 | termios.CREAD | termios.CLOCAL
    settings[3] = 0
    settings[4] = speed
    settings[5] = speed
    settings[6][termios.VMIN] = 0
    settings[6][termios.VTIME] = 0
    termios.tcsetattr(fd, termios.TCSANOW, settings)
    if baud_constant(baud) is None:
        import struct
        fcntl.ioctl(fd, IOSSIOSPEED, struct.pack("L", baud))
    termios.tcflush(fd, termios.TCIOFLUSH)

    # CP2102N boards normally do not require DTR/RTS, but asserting them is
    # harmless and matches what desktop GNSS tools do when opening a port.
    for control in ("TIOCSDTR", "TIOCSRTS"):
        request = getattr(termios, control, None)
        if request is not None:
            try:
                fcntl.ioctl(fd, request)
            except OSError:
                pass
    return fd


def read_for(fd: int, seconds: float) -> bytes:
    """Collect every received byte during a bounded interval."""
    received = bytearray()
    deadline = time.monotonic() + seconds
    while time.monotonic() < deadline:
        ready, _, _ = select.select([fd], [], [], min(0.25, deadline - time.monotonic()))
        if ready:
            try:
                received.extend(os.read(fd, 4096))
            except BlockingIOError:
                pass
    return bytes(received)


def print_bytes(label: str, data: bytes) -> None:
    print(f"{label}: {len(data)} byte(s)")
    if not data:
        return
    text = data.decode("ascii", "replace").replace("\r", "\\r").replace("\n", "\\n\n")
    print(f"ASCII preview: {text[:500]}")
    print(f"hex preview: {data[:64].hex(' ')}")


def probe(args: argparse.Namespace) -> int:
    fd = open_port(args.port, args.baud)
    try:
        command = nmea_sentence("PQTMVERNO")
        print(f"Sending {command.decode().strip()} at {args.baud} bps")
        os.write(fd, command)
        print_bytes("Receiver response", read_for(fd, args.wait))
    finally:
        os.close(fd)
    return 0


def audit(args: argparse.Namespace) -> int:
    """Send only documented read-only LC29H(BS) queries at selected baud rates.

    The audit deliberately does not write receiver configuration or NVM.  A
    healthy LC29H(BS) returns a response to each query.  An echoed command on
    its own is not a receiver response.
    """
    queries = ("PQTMVERNO", "PQTMCFGSVIN,R", "PAIR433", "PAIR435", "PAIR437")
    any_response = False
    echoes_everywhere = True
    for baud in args.bauds:
        print(f"\n=== {args.port} at {baud} bps ===")
        try:
            fd = open_port(args.port, baud)
        except (OSError, ValueError) as error:
            print(f"Could not open: {error}")
            continue
        try:
            for body in queries:
                command = nmea_sentence(body)
                os.write(fd, command)
                reply = read_for(fd, args.wait)
                # The module is expected to return a sentence that contains
                # extra fields after the command name, not merely the command
                # byte-for-byte. Preserve every received byte for diagnosis.
                echoed = reply == command
                print_bytes(f"{body}{' (echo only)' if echoed else ''}", reply)
                any_response = any_response or bool(reply and not echoed)
                echoes_everywhere = echoes_everywhere and echoed
        finally:
            os.close(fd)
    if not any_response:
        print("\nNo documented LC29H(BS) query produced a receiver response.")
        if echoes_everywhere:
            print("Every command came back byte-for-byte at every speed: the USB chip's TX is looped to its own RX and the\n"
                  "module is not on the line. Check the yellow UART jumpers: both on position A (USB <-> LC29H), seated\n"
                  "vertically as on the silkscreen. Then run 'listen': a working LC29H streams NMEA with no command sent.")
        return 2
    print("\nAt least one documented receiver query returned data beyond command echo.")
    return 0


def listen(args: argparse.Namespace) -> int:
    """Send nothing; report what the receiver emits on its own at each speed."""
    heard = False
    for baud in args.bauds:
        fd = open_port(args.port, baud)
        try:
            data = read_for(fd, args.seconds)
        finally:
            os.close(fd)
        nmea = data.count(b"$G")
        print(f"{baud} bps: {len(data)} byte(s), {nmea} NMEA sentence start(s)")
        if data:
            print_bytes("  preview", data[:200])
        heard = heard or bool(data)
    if not heard:
        print("Silence at every speed. A powered LC29H on position A streams NMEA unprompted, so check power (PWR LED),\n"
              "the jumpers (position A), and that the module is seated; then run 'audit' to test for a TX/RX loopback.")
        return 2
    return 0


def configure_test(args: argparse.Namespace) -> int:
    """Start a short, clearly non-survey-grade Survey-in and enable RTCM output.

    The parameters are deliberately *not* saved to flash.  This makes the
    command set a reversible bench test.  For final sessions, use an approved
    static setup and the project's documented multi-session protocol.
    """
    if args.seconds < 60:
        raise ValueError("Survey-in must be at least 60 seconds for this bench test")
    fd = open_port(args.port, args.baud)
    try:
        commands = [
            f"PQTMCFGSVIN,W,1,{args.seconds},{args.accuracy},0,0,0",
            "PAIR432,1",  # RTCM3 MSM7 raw observations.
            "PAIR434,1",  # RTCM 1005 reference-station ARP message.
        ]
        for body in commands:
            command = nmea_sentence(body)
            print(f"Sending {command.decode().strip()}")
            os.write(fd, command)
            print_bytes("Immediate response", read_for(fd, args.command_wait))
        print(
            "Configuration commands sent. Keep the antenna fixed under open sky; "
            "then use 'capture' for at least the configured Survey-in duration plus 60 seconds."
        )
    finally:
        os.close(fd)
    return 0


def port_in_use(port: str) -> bool:
    """True if another process already has the serial port open (two readers split the bytes)."""
    import subprocess
    try:
        return bool(subprocess.run(["lsof", "-t", port], capture_output=True, text=True, timeout=10).stdout.strip())
    except (OSError, subprocess.SubprocessError):
        return False


def capture(args: argparse.Namespace) -> int:
    output = Path(args.output).expanduser().resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    if port_in_use(args.port):
        raise OSError(f"{args.port} is already open in another process; two captures would split the data. Stop the other one first.")
    if output.exists() and output.stat().st_size:
        raise OSError(f"{output} already has data; choose a new file name rather than overwrite a session.")
    fd = open_port(args.port, args.baud)
    total = 0
    started = time.monotonic()
    try:
        with output.open("wb", buffering=0) as handle:  # unbuffered: the file grows as data arrives
            while time.monotonic() - started < args.seconds:
                remaining = args.seconds - (time.monotonic() - started)
                ready, _, _ = select.select([fd], [], [], min(0.5, max(0, remaining)))
                if ready:
                    try:
                        chunk = os.read(fd, 4096)
                    except BlockingIOError:
                        continue
                    handle.write(chunk)
                    total += len(chunk)
        print(f"Saved {total} byte(s) to {output}")
        if total == 0:
            print("No bytes were captured. Do not claim a hardware result; run 'probe' and retain this empty log as diagnostic evidence.")
            return 2
        return 0
    finally:
        os.close(fd)


def bench_run(args: argparse.Namespace) -> int:
    """Keep one USB session open while configuring and capturing RTCM output.

    This rules out a host-side USB re-open resetting a temporary receiver
    configuration. The receiver configuration is deliberately not saved.
    """
    output = Path(args.output).expanduser().resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    fd = open_port(args.port, args.baud)
    try:
        commands = (
            f"PQTMCFGSVIN,W,1,{args.survey_seconds},0,0,0,0",
            "PAIR432,1",  # MSM7 raw observations
            "PAIR434,1",  # RTCM 1005 station reference point
            "PAIR436,1",  # satellite ephemeris
        )
        for body in commands:
            command = nmea_sentence(body)
            print(f"Sending {command.decode().strip()}")
            os.write(fd, command)
            print_bytes("Immediate response", read_for(fd, args.command_wait))

        print(f"Capturing for {args.capture_seconds} seconds without closing the USB port.")
        total = 0
        started = time.monotonic()
        with output.open("wb") as handle:
            while time.monotonic() - started < args.capture_seconds:
                remaining = args.capture_seconds - (time.monotonic() - started)
                ready, _, _ = select.select([fd], [], [], min(0.5, max(0, remaining)))
                if ready:
                    try:
                        chunk = os.read(fd, 4096)
                    except BlockingIOError:
                        continue
                    handle.write(chunk)
                    total += len(chunk)
        print(f"Saved {total} byte(s) to {output}")
        return 0 if total else 2
    finally:
        os.close(fd)


def parser() -> argparse.ArgumentParser:
    result = argparse.ArgumentParser(description=__doc__)
    result.add_argument("--port", default=DEFAULT_PORT, help=f"macOS serial device (default: {DEFAULT_PORT})")
    result.add_argument("--baud", type=int, default=DEFAULT_BAUD, help=f"serial baud rate (default: {DEFAULT_BAUD})")
    subparsers = result.add_subparsers(dest="action", required=True)

    probe_parser = subparsers.add_parser("probe", help="ask the receiver for its firmware version")
    probe_parser.add_argument("--wait", type=float, default=5, help="seconds to wait for a response")
    probe_parser.set_defaults(handler=probe)

    audit_parser = subparsers.add_parser("audit", help="run read-only official receiver queries across baud rates")
    audit_parser.add_argument(
        "--bauds",
        type=int,
        nargs="+",
        default=[9600, 19200, 38400, 57600, 115200, 230400],
        help="serial speeds to test",
    )
    audit_parser.add_argument("--wait", type=float, default=1.5, help="seconds to await each query response")
    audit_parser.set_defaults(handler=audit)

    listen_parser = subparsers.add_parser("listen", help="send nothing; check whether the receiver streams on its own")
    listen_parser.add_argument("--bauds", type=int, nargs="+", default=[115200, 460800, 921600, 9600], help="serial speeds to try")
    listen_parser.add_argument("--seconds", type=float, default=3, help="seconds to listen at each speed")
    listen_parser.set_defaults(handler=listen)

    configure_parser = subparsers.add_parser("configure-test", help="start a reversible bench Survey-in and enable RTCM")
    configure_parser.add_argument("--seconds", type=int, default=120, help="bench Survey-in duration in seconds (minimum 60)")
    configure_parser.add_argument("--accuracy", type=float, default=15.0, help="bench 3D accuracy limit in metres")
    configure_parser.add_argument("--command-wait", type=float, default=2, help="seconds to await each command response")
    configure_parser.set_defaults(handler=configure_test)

    capture_parser = subparsers.add_parser("capture", help="write a raw serial/RTCM log")
    capture_parser.add_argument("--seconds", type=int, default=240, help="capture duration in seconds")
    capture_parser.add_argument("--output", required=True, help="destination .bin file")
    capture_parser.set_defaults(handler=capture)

    bench_parser = subparsers.add_parser(
        "bench-run", help="configure and capture in one unsaved USB session"
    )
    bench_parser.add_argument("--survey-seconds", type=int, default=60, help="temporary Survey-in duration")
    bench_parser.add_argument("--capture-seconds", type=int, default=120, help="same-session capture duration")
    bench_parser.add_argument("--command-wait", type=float, default=1.0, help="seconds to await command responses")
    bench_parser.add_argument("--output", required=True, help="destination .bin file")
    bench_parser.set_defaults(handler=bench_run)
    return result


def main() -> int:
    try:
        args = parser().parse_args()
        return args.handler(args)
    except (OSError, ValueError) as error:
        print(f"LC29H error: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
