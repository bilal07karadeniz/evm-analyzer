#!/usr/bin/env python3
"""
EVM Analyzer - Smart Contract Security Data Gatherer

Collects token information, ownership details, liquidity data, and security
flags from EVM-compatible smart contracts using an Anvil fork.

See README.md for full documentation.
"""

import argparse
import sys
import os
from pathlib import Path

if sys.platform == "win32":
    os.system("")
    os.environ["PYTHONIOENCODING"] = "utf-8"
    if hasattr(sys.stdout, 'reconfigure'):
        sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    if hasattr(sys.stderr, 'reconfigure'):
        sys.stderr.reconfigure(encoding='utf-8', errors='replace')

sys.path.insert(0, str(Path(__file__).parent))

from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn

console = Console(force_terminal=True)

from config import CHAINS
from core.anvil import AnvilManager
from core.contract import ContractHelper
from modules.token import TokenAnalyzer
from modules.ownership import OwnershipAnalyzer
from modules.proxy import ProxyAnalyzer
from modules.security import SecurityAnalyzer
from dexes.registry import registry
from output.markdown import MarkdownReport


def find_running_anvil(chain: str) -> tuple:
    """Auto-detect a running Anvil instance.

    Scans common ports and checks if the chain matches.

    Returns:
        Tuple of (url, chain_id) if found, (None, None) otherwise
    """
    from web3 import Web3

    # Common Anvil ports to check
    ports_to_check = [8545, 8546, 8547, 8548, 8549] + list(range(43690, 43700))

    expected_chain_id = CHAINS[chain].chain_id

    for port in ports_to_check:
        url = f"http://127.0.0.1:{port}"
        try:
            web3 = Web3(Web3.HTTPProvider(url, request_kwargs={'timeout': 1}))
            if web3.is_connected():
                chain_id = web3.eth.chain_id
                if chain_id == expected_chain_id:
                    return url, chain_id
        except Exception:
            continue

    return None, None


def main():
    parser = argparse.ArgumentParser(
        description="Gather smart contract data for security analysis",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python gatherer.py 0x...                          # Ethereum (default)
  python gatherer.py 0x... bsc                      # BSC
  python gatherer.py 0x... eth -b 18000000          # Historical block
  python gatherer.py 0x... bsc -o report.md         # Save to file
        """,
    )

    parser.add_argument(
        "address",
        help="Token contract address to analyze",
    )

    parser.add_argument(
        "chain",
        nargs="?",
        choices=["ethereum", "eth", "bsc", "bnb"],
        default="ethereum",
        help="Chain: ethereum/eth, bsc/bnb (default: ethereum)",
    )

    parser.add_argument(
        "-b", "--block",
        type=int,
        help="Fork from specific block number",
    )

    parser.add_argument(
        "-o", "--output",
        help="Output file path (default: stdout)",
    )

    parser.add_argument(
        "-r", "--rpc",
        help="Custom RPC URL (overrides chain default)",
    )

    parser.add_argument(
        "-p", "--port",
        type=int,
        default=8545,
        help="Anvil port (default: 8545)",
    )

    parser.add_argument(
        "--anvil-url",
        help="Connect to existing Anvil instance",
    )

    args = parser.parse_args()

    try:
        run_analysis(args)
    except KeyboardInterrupt:
        console.print("\n[yellow]Interrupted[/yellow]")
        sys.exit(1)
    except Exception as e:
        console.print(f"[red]Error: {e}[/red]")
        sys.exit(1)


def try_rpc_with_fallback(web3, rpc_urls: list, block: int = None) -> str:
    """Try each RPC until one works. Returns the working RPC URL."""
    last_error = None
    for rpc_url in rpc_urls:
        try:
            reset_params = {"jsonRpcUrl": rpc_url}
            if block:
                reset_params["blockNumber"] = block
            web3.provider.make_request("anvil_reset", [{"forking": reset_params}])
            # Verify it worked
            web3.eth.block_number
            return rpc_url
        except Exception as e:
            last_error = e
            continue
    raise RuntimeError(f"All RPCs failed. Last error: {last_error}")


def run_analysis(args):
    """Run the full analysis pipeline."""
    from web3 import Web3

    # Normalize chain aliases
    chain_map = {"eth": "ethereum", "bnb": "bsc"}
    args.chain = chain_map.get(args.chain, args.chain)

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=console,
    ) as progress:

        anvil = None
        anvil_url = args.anvil_url

        # Try to find running Anvil if URL not provided
        if not anvil_url:
            task = progress.add_task("Looking for Anvil...", total=None)
            anvil_url, chain_id = find_running_anvil(args.chain)
            if anvil_url:
                progress.update(task, description=f"Found Anvil at {anvil_url}")

        # Connect to existing Anvil or start new one
        if anvil_url:
            task = progress.add_task("Connecting to Anvil...", total=None)
            web3 = Web3(Web3.HTTPProvider(anvil_url))
            if not web3.is_connected():
                raise RuntimeError(f"Cannot connect to Anvil at {anvil_url}")

            # Reset Anvil to specified block or latest (with RPC fallback)
            if args.rpc:
                rpc_urls = [args.rpc]
            else:
                rpc_urls = CHAINS[args.chain].rpc_urls

            if args.block:
                progress.update(task, description=f"Resetting to block {args.block}...")
                try_rpc_with_fallback(web3, rpc_urls, args.block)
                progress.update(task, description=f"Connected (block {args.block})")
            else:
                progress.update(task, description="Resetting to latest block...")
                try_rpc_with_fallback(web3, rpc_urls)
                block_num = web3.eth.block_number
                progress.update(task, description=f"Connected (block {block_num})")
        else:
            task = progress.add_task("Starting Anvil fork...", total=None)
            anvil = AnvilManager()
            web3 = anvil.start(
                chain=args.chain,
                fork_block=args.block,
                rpc_url=args.rpc,
                port=args.port,
            )
            progress.update(task, description="Anvil running")

        try:
            # Validate address
            if not web3.is_address(args.address):
                raise ValueError(f"Invalid address: {args.address}")

            # Check if contract exists
            code = web3.eth.get_code(args.address)
            if len(code) == 0:
                raise ValueError(f"No contract at address: {args.address}")

            # Analyze proxy first (needed for token analysis)
            progress.update(task, description="Checking proxy status...")
            proxy_analyzer = ProxyAnalyzer(web3)
            proxy_info = proxy_analyzer.analyze(args.address)

            # Analyze token (pass implementation if proxy)
            progress.update(task, description="Analyzing token...")
            token_analyzer = TokenAnalyzer(web3)
            token_info = token_analyzer.analyze(args.address, proxy_info.implementation)

            # Analyze ownership
            progress.update(task, description="Analyzing ownership...")
            ownership_analyzer = OwnershipAnalyzer(web3)
            ownership_info = ownership_analyzer.analyze(args.address)

            # Analyze security
            progress.update(task, description="Running security checks...")
            security_analyzer = SecurityAnalyzer(web3, args.chain)
            security_info = security_analyzer.analyze(args.address)

            # Find liquidity pools
            progress.update(task, description="Discovering liquidity pools...")
            pools = registry.get_top_pools(
                web3=web3,
                chain=args.chain,
                token_address=args.address,
                limit=5,
                include_base_pair=True,
            )

            progress.update(task, description="Generating report...")

        finally:
            if anvil:
                anvil.stop()

    # Generate markdown report
    report = MarkdownReport()
    markdown = report.generate(
        token=token_info,
        ownership=ownership_info,
        proxy=proxy_info,
        security=security_info,
        pools=pools,
        chain=args.chain,
    )

    # Output
    if args.output:
        output_path = Path(args.output)
        output_path.write_text(markdown)
        console.print(f"[green]Report saved to {output_path}[/green]")
    else:
        console.print()
        console.print(markdown)


if __name__ == "__main__":
    main()
