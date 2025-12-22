"""Anvil fork lifecycle management."""

import subprocess
import time
import socket
import signal
import sys
from typing import Optional
from dataclasses import dataclass

from web3 import Web3

from config import ANVIL_CONFIG, CHAINS


@dataclass
class AnvilInstance:
    process: subprocess.Popen
    rpc_url: str
    chain: str
    fork_block: Optional[int]


class AnvilManager:
    """Manages Anvil fork instances."""

    def __init__(self):
        self.instance: Optional[AnvilInstance] = None
        self.web3: Optional[Web3] = None

    def start(
        self,
        chain: str,
        fork_block: Optional[int] = None,
        rpc_url: Optional[str] = None,
        port: int = ANVIL_CONFIG["port"],
    ) -> Web3:
        """Start an Anvil fork instance.

        Args:
            chain: Chain name (ethereum, bsc)
            fork_block: Optional block number to fork from
            rpc_url: Optional custom RPC URL (overrides chain config)
            port: Port to run Anvil on

        Returns:
            Web3 instance connected to Anvil
        """
        if self.instance:
            self.stop()

        # Get RPC URL
        if rpc_url:
            fork_url = rpc_url
        elif chain in CHAINS:
            fork_url = CHAINS[chain].rpc_url
        else:
            raise ValueError(f"Unknown chain: {chain}. Available: {list(CHAINS.keys())}")

        # Check if port is available
        if not self._is_port_available(port):
            raise RuntimeError(f"Port {port} is already in use")

        # Build anvil command
        cmd = [
            "anvil",
            "--fork-url", fork_url,
            "--port", str(port),
            "--accounts", str(ANVIL_CONFIG["accounts"]),
            "--balance", str(ANVIL_CONFIG["balance"]),
            "--silent",
        ]

        if fork_block:
            cmd.extend(["--fork-block-number", str(fork_block)])

        # Start anvil process
        try:
            # Use CREATE_NEW_PROCESS_GROUP on Windows for proper signal handling
            kwargs = {}
            if sys.platform == "win32":
                kwargs["creationflags"] = subprocess.CREATE_NEW_PROCESS_GROUP

            process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                **kwargs
            )
        except FileNotFoundError:
            raise RuntimeError(
                "Anvil not found. Install Foundry: https://book.getfoundry.sh/getting-started/installation"
            )

        # Wait for Anvil to be ready
        anvil_url = f"http://{ANVIL_CONFIG['host']}:{port}"
        if not self._wait_for_anvil(anvil_url, timeout=30):
            process.terminate()
            raise RuntimeError("Anvil failed to start within timeout")

        # Create Web3 instance
        self.web3 = Web3(Web3.HTTPProvider(anvil_url))

        if not self.web3.is_connected():
            process.terminate()
            raise RuntimeError("Failed to connect to Anvil")

        self.instance = AnvilInstance(
            process=process,
            rpc_url=anvil_url,
            chain=chain,
            fork_block=fork_block,
        )

        return self.web3

    def stop(self):
        """Stop the running Anvil instance."""
        if self.instance:
            try:
                if sys.platform == "win32":
                    self.instance.process.terminate()
                else:
                    self.instance.process.send_signal(signal.SIGTERM)
                self.instance.process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                self.instance.process.kill()
            finally:
                self.instance = None
                self.web3 = None

    def get_web3(self) -> Web3:
        """Get the Web3 instance.

        Returns:
            Web3 instance connected to Anvil
        """
        if not self.web3:
            raise RuntimeError("Anvil not started. Call start() first.")
        return self.web3

    def impersonate(self, address: str):
        """Impersonate an address for testing.

        Args:
            address: Address to impersonate
        """
        w3 = self.get_web3()
        w3.provider.make_request("anvil_impersonateAccount", [address])

    def stop_impersonating(self, address: str):
        """Stop impersonating an address.

        Args:
            address: Address to stop impersonating
        """
        w3 = self.get_web3()
        w3.provider.make_request("anvil_stopImpersonatingAccount", [address])

    def set_balance(self, address: str, balance_wei: int):
        """Set the balance of an address.

        Args:
            address: Address to set balance for
            balance_wei: Balance in wei
        """
        w3 = self.get_web3()
        w3.provider.make_request("anvil_setBalance", [address, hex(balance_wei)])

    def _is_port_available(self, port: int) -> bool:
        """Check if a port is available."""
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            try:
                s.bind((ANVIL_CONFIG["host"], port))
                return True
            except socket.error:
                return False

    def _wait_for_anvil(self, url: str, timeout: int = 30) -> bool:
        """Wait for Anvil to be ready.

        Args:
            url: Anvil RPC URL
            timeout: Timeout in seconds

        Returns:
            True if Anvil is ready, False otherwise
        """
        start = time.time()
        while time.time() - start < timeout:
            try:
                w3 = Web3(Web3.HTTPProvider(url))
                if w3.is_connected():
                    return True
            except Exception:
                pass
            time.sleep(0.5)
        return False

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.stop()
