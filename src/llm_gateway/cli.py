from __future__ import annotations

import argparse
import asyncio

from .client import LLMGatewayClient


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Call an LLM through Agent Router")
    parser.add_argument("prompt", help="Prompt to send to the LLM")
    parser.add_argument("--model", default=None, help="Model name or Auto")
    return parser


async def run(prompt: str, model: str | None) -> None:
    async with LLMGatewayClient.from_env() as client:
        print(await client.complete(prompt, model=model))


def main() -> None:
    args = build_parser().parse_args()
    asyncio.run(run(args.prompt, args.model))


if __name__ == "__main__":
    main()
