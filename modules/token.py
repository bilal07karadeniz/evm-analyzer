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
    price_usd: Optional[float] = None
    price_native: Optional[float] = None  # Price in ETH/BNB
    native_symbol: Optional[str] = None   # "ETH" or "BNB"
    price_source: Optional[str] = None


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

    def calculate_price_from_pools(self, pools, token_address: str, chain_config) -> tuple:
        """Calculate token price from liquidity pool reserves.

        Args:
            pools: List of Pool objects
            token_address: Token address to get price for
            chain_config: Chain configuration with stablecoins and wrapped_native

        Returns:
            Tuple of (price_usd, price_native, native_symbol, price_source)
        """
        if not pools:
            return None, None, None, None

        token_address = token_address.lower()
        native_symbol = "ETH" if chain_config.chain_id == 1 else "BNB"
        native_price_usd = 3500 if chain_config.chain_id == 1 else 600

        for pool in pools:
            # Determine which side is our token
            if pool.token0.lower() == token_address:
                our_reserve = pool.reserve0 / (10 ** pool.token0_decimals)
                other_reserve = pool.reserve1 / (10 ** pool.token1_decimals)
                other_token = pool.token1
            else:
                our_reserve = pool.reserve1 / (10 ** pool.token1_decimals)
                other_reserve = pool.reserve0 / (10 ** pool.token0_decimals)
                other_token = pool.token0

            if our_reserve == 0:
                continue

            other_token_lower = other_token.lower()
            stablecoins_lower = [s.lower() for s in chain_config.stablecoins]

            # Calculate price based on paired token
            if other_token_lower in stablecoins_lower:
                price_usd = other_reserve / our_reserve
                price_native = price_usd / native_price_usd
            elif other_token_lower == chain_config.wrapped_native.lower():
                price_native = other_reserve / our_reserve
                price_usd = price_native * native_price_usd
            else:
                continue

            source = f"{pool.dex_name} {pool.token0_symbol}/{pool.token1_symbol}"
            return price_usd, price_native, native_symbol, source

        return None, None, None, None
