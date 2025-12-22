"""Base DEX adapter interface."""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import List, Optional

from web3 import Web3


@dataclass
class Pool:
    """Represents a liquidity pool."""
    address: str
    dex_name: str
    token0: str
    token1: str
    reserve0: int
    reserve1: int
    token0_symbol: str
    token1_symbol: str
    token0_decimals: int
    token1_decimals: int
    liquidity_usd: float
    fee_tier: Optional[int] = None  # For V3 pools


class BaseDEXAdapter(ABC):
    """Abstract base class for DEX adapters.

    To add a new DEX:
    1. Create a new file in dexes/ folder
    2. Inherit from BaseDEXAdapter
    3. Implement the required methods
    4. The registry will auto-discover it
    """

    # Override in subclass
    name: str = "base"
    chains: List[str] = []

    def __init__(self, web3: Web3, chain: str):
        """Initialize the adapter.

        Args:
            web3: Web3 instance
            chain: Chain name (ethereum, bsc)
        """
        self.web3 = web3
        self.chain = chain

    @abstractmethod
    def find_pools(self, token_address: str) -> List[Pool]:
        """Find all pools containing the token.

        Args:
            token_address: Token contract address

        Returns:
            List of Pool objects
        """
        pass

    @abstractmethod
    def get_reserves(self, pool_address: str) -> tuple:
        """Get reserves for a pool.

        Args:
            pool_address: Pool contract address

        Returns:
            Tuple of (reserve0, reserve1)
        """
        pass

    def supports_chain(self, chain: str) -> bool:
        """Check if this adapter supports the given chain.

        Args:
            chain: Chain name

        Returns:
            True if supported
        """
        return chain in self.chains

    def get_token_info(self, token_address: str) -> tuple:
        """Get token symbol and decimals.

        Args:
            token_address: Token address

        Returns:
            Tuple of (symbol, decimals)
        """
        try:
            # Minimal ERC20 ABI for symbol and decimals
            abi = [
                {"constant": True, "inputs": [], "name": "symbol", "outputs": [{"type": "string"}], "type": "function"},
                {"constant": True, "inputs": [], "name": "decimals", "outputs": [{"type": "uint8"}], "type": "function"},
            ]
            contract = self.web3.eth.contract(
                address=Web3.to_checksum_address(token_address),
                abi=abi
            )
            symbol = contract.functions.symbol().call()
            decimals = contract.functions.decimals().call()
            return symbol, decimals
        except Exception:
            return "???", 18
