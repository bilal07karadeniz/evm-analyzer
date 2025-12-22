"""DEX adapter registry with auto-discovery."""

import importlib
import pkgutil
from pathlib import Path
from typing import Dict, List, Type

from web3 import Web3

from .base import BaseDEXAdapter, Pool


class DEXRegistry:
    """Registry for DEX adapters with auto-discovery."""

    def __init__(self):
        self._adapters: Dict[str, Type[BaseDEXAdapter]] = {}
        self._discover_adapters()

    def _discover_adapters(self):
        """Auto-discover all DEX adapters in the dexes package."""
        package_dir = Path(__file__).parent

        for module_info in pkgutil.iter_modules([str(package_dir)]):
            if module_info.name in ("base", "registry", "__init__"):
                continue

            try:
                module = importlib.import_module(f".{module_info.name}", package="dexes")

                # Find all BaseDEXAdapter subclasses in the module
                for attr_name in dir(module):
                    attr = getattr(module, attr_name)
                    if (
                        isinstance(attr, type)
                        and issubclass(attr, BaseDEXAdapter)
                        and attr is not BaseDEXAdapter
                        and hasattr(attr, "name")
                    ):
                        self._adapters[attr.name] = attr

            except Exception:
                pass  # Skip adapters that fail to load

    def get_adapters_for_chain(
        self, web3: Web3, chain: str
    ) -> List[BaseDEXAdapter]:
        """Get all adapters that support the given chain.

        Args:
            web3: Web3 instance
            chain: Chain name

        Returns:
            List of instantiated adapters
        """
        adapters = []
        for adapter_class in self._adapters.values():
            if chain in adapter_class.chains:
                try:
                    adapters.append(adapter_class(web3, chain))
                except Exception:
                    pass  # Skip adapters that fail to instantiate
        return adapters

    def find_all_pools(
        self, web3: Web3, chain: str, token_address: str
    ) -> List[Pool]:
        """Find pools across all DEXes for a token.

        Args:
            web3: Web3 instance
            chain: Chain name
            token_address: Token address

        Returns:
            List of all pools, sorted by liquidity
        """
        all_pools = []
        adapters = self.get_adapters_for_chain(web3, chain)

        for adapter in adapters:
            try:
                pools = adapter.find_pools(token_address)
                all_pools.extend(pools)
            except Exception:
                pass  # Skip DEXes that fail

        # Sort by liquidity (highest first)
        all_pools.sort(key=lambda p: p.liquidity_usd, reverse=True)
        return all_pools

    def get_top_pools(
        self,
        web3: Web3,
        chain: str,
        token_address: str,
        limit: int = 5,
        include_base_pair: bool = True,
    ) -> List[Pool]:
        """Get top pools by liquidity.

        Args:
            web3: Web3 instance
            chain: Chain name
            token_address: Token address
            limit: Max number of pools to return
            include_base_pair: Ensure base currency pair is included

        Returns:
            List of top pools
        """
        from config import CHAINS

        all_pools = self.find_all_pools(web3, chain, token_address)

        if not all_pools:
            return []

        # Get wrapped native token for this chain
        wrapped_native = CHAINS[chain].wrapped_native.lower()

        # Find base pair (with WETH/WBNB)
        base_pair = None
        other_pools = []

        for pool in all_pools:
            if (
                pool.token0.lower() == wrapped_native
                or pool.token1.lower() == wrapped_native
            ):
                if base_pair is None:
                    base_pair = pool
                else:
                    other_pools.append(pool)
            else:
                other_pools.append(pool)

        # Build result
        result = []

        if include_base_pair and base_pair:
            result.append(base_pair)
            limit -= 1

        # Add top pools by liquidity
        result.extend(other_pools[:limit])

        return result

    @property
    def registered_adapters(self) -> List[str]:
        """Get list of registered adapter names."""
        return list(self._adapters.keys())


# Global registry instance
registry = DEXRegistry()
