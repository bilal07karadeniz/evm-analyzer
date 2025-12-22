"""ERC20 token analysis module."""

from dataclasses import dataclass
from typing import Optional

from web3 import Web3

from core.contract import ContractHelper


@dataclass
class TokenInfo:
    """Token basic information."""
    address: str
    name: Optional[str]
    symbol: Optional[str]
    decimals: Optional[int]
    total_supply: Optional[int]
    total_supply_formatted: Optional[str]


class TokenAnalyzer:
    """Analyzes ERC20 token properties."""

    def __init__(self, web3: Web3):
        self.web3 = web3
        self.helper = ContractHelper(web3)

    def analyze(self, token_address: str, implementation: str = None) -> TokenInfo:
        """Analyze token basic properties.

        Args:
            token_address: Token contract address
            implementation: Optional implementation address for proxy contracts

        Returns:
            TokenInfo object
        """
        token_address = Web3.to_checksum_address(token_address)

        # Get name - try proxy first, then implementation
        name = self._get_name(token_address)
        if not name and implementation:
            name = self._get_name(implementation)

        # Get symbol - try proxy first, then implementation
        symbol = self._get_symbol(token_address)
        if not symbol and implementation:
            symbol = self._get_symbol(implementation)

        # Get decimals
        decimals = self._get_decimals(token_address)

        # Get total supply
        total_supply = self._get_total_supply(token_address)

        # Format total supply
        total_supply_formatted = None
        if total_supply is not None and decimals is not None:
            total_supply_formatted = self._format_supply(total_supply, decimals)

        return TokenInfo(
            address=token_address,
            name=name,
            symbol=symbol,
            decimals=decimals,
            total_supply=total_supply,
            total_supply_formatted=total_supply_formatted,
        )

    def _get_name(self, address: str) -> Optional[str]:
        """Get token name."""
        result = self.helper.call_safe(address, "name()", abi_name="erc20")
        if result:
            return result
        return None

    def _get_symbol(self, address: str) -> Optional[str]:
        """Get token symbol."""
        result = self.helper.call_safe(address, "symbol()", abi_name="erc20")
        if result:
            return result
        return None

    def _get_decimals(self, address: str) -> Optional[int]:
        """Get token decimals."""
        result = self.helper.call_safe(address, "decimals()", abi_name="erc20")
        if result is not None:
            return int(result)
        return 18  # Default to 18

    def _get_total_supply(self, address: str) -> Optional[int]:
        """Get total supply."""
        result = self.helper.call_safe(address, "totalSupply()", abi_name="erc20")
        if result is not None:
            return int(result)
        return None

    def _format_supply(self, supply: int, decimals: int) -> str:
        """Format supply with proper decimal places."""
        value = supply / (10 ** decimals)
        if value >= 1_000_000_000_000:
            return f"{value / 1_000_000_000_000:.2f}T"
        elif value >= 1_000_000_000:
            return f"{value / 1_000_000_000:.2f}B"
        elif value >= 1_000_000:
            return f"{value / 1_000_000:.2f}M"
        elif value >= 1_000:
            return f"{value / 1_000:.2f}K"
        else:
            return f"{value:.2f}"

    def get_balance(self, token_address: str, holder_address: str) -> Optional[int]:
        """Get token balance for an address.

        Args:
            token_address: Token contract address
            holder_address: Holder address to check

        Returns:
            Balance in wei or None
        """
        try:
            contract = self.helper.get_contract(token_address, "erc20")
            balance = contract.functions.balanceOf(
                Web3.to_checksum_address(holder_address)
            ).call()
            return balance
        except Exception:
            return None
