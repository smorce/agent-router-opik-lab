#!/usr/bin/env python3
"""IPv4-only TCP proxy for WSL -> Windows localhost access.

aigw's admin server listens on a dual-stack socket. On WSL2 NAT mode,
Windows IPv4 localhost forwarding often fails for that socket while
IPv6 ::1 still works. This proxy binds IPv4 0.0.0.0 so Windows browsers
can use http://127.0.0.1:<listen_port>.
"""

from __future__ import annotations

import argparse
import asyncio
import signal
import socket
import sys


async def _pipe(reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
    try:
        while True:
            data = await reader.read(65536)
            if not data:
                break
            writer.write(data)
            await writer.drain()
    except (ConnectionResetError, BrokenPipeError, asyncio.CancelledError):
        pass
    finally:
        try:
            writer.close()
            await writer.wait_closed()
        except Exception:
            pass


async def _handle(
    client_reader: asyncio.StreamReader,
    client_writer: asyncio.StreamWriter,
    upstream_host: str,
    upstream_port: int,
) -> None:
    try:
        upstream_reader, upstream_writer = await asyncio.open_connection(
            upstream_host,
            upstream_port,
            family=socket.AF_INET,
        )
    except OSError:
        client_writer.close()
        await client_writer.wait_closed()
        return

    await asyncio.gather(
        _pipe(client_reader, upstream_writer),
        _pipe(upstream_reader, client_writer),
    )


async def _serve(
    listen_host: str,
    listen_port: int,
    upstream_host: str,
    upstream_port: int,
) -> None:
    server = await asyncio.start_server(
        lambda r, w: _handle(r, w, upstream_host, upstream_port),
        host=listen_host,
        port=listen_port,
        family=socket.AF_INET,
        reuse_address=True,
    )
    async with server:
        await server.serve_forever()


def main() -> None:
    parser = argparse.ArgumentParser(description="IPv4 TCP proxy for Agent Router admin")
    parser.add_argument("--listen-host", default="0.0.0.0")
    parser.add_argument("--listen-port", type=int, default=1064)
    parser.add_argument("--upstream-host", default="127.0.0.1")
    parser.add_argument("--upstream-port", type=int, default=1065)
    args = parser.parse_args()

    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

    def _stop(*_args: object) -> None:
        for task in asyncio.all_tasks(loop):
            task.cancel()

    for sig in (signal.SIGINT, signal.SIGTERM):
        loop.add_signal_handler(sig, _stop)

    try:
        loop.run_until_complete(
            _serve(args.listen_host, args.listen_port, args.upstream_host, args.upstream_port)
        )
    except asyncio.CancelledError:
        pass
    finally:
        loop.close()


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        sys.exit(0)
