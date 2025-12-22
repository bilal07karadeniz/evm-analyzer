"""Curve Finance adapter."""

from typing import List

from web3 import Web3

from config import CHAINS, DEX_FACTORIES
from .base import BaseDEXAdapter, Pool


class CurveAdapter(BaseDEXAdapter):
    """Adapter for Curve Finance stable pools."""

    name = "curve"
    chains = ["ethereum"]

    REGISTRY_ABI = [
        {
            "name": "find_pool_for_coins",
            "outputs": [{"type": "address", "name": ""}],
            "inputs": [
                {"type": "address", "name": "_from"},
                {"type": "address", "name": "_to"},
            ],
            "stateMutability": "view",
            "type": "function",
        },
        {
            "name": "get_balances",
            "outputs": [{"type": "uint256[8]", "name": ""}],
            "inputs": [{"type": "address", "name": "_pool"}],
            "stateMutability": "view",
            "type": "function",
        },
        {
            "name": "get_coins",
            "outputs": [{"type": "address[8]", "name": ""}],
            "inputs": [{"type": "address", "name": "_pool"}],
            "stateMutability": "view",
            "type": "function",
        },
    ]

    def find_pools(self, token_address: str) -> List[Pool]:
        """Find Curve pools containing the token."""
        pools = []
        token_address = Web3.to_checksum_address(token_address)

        if self.chain not in DEX_FACTORIES or "curve" not in DEX_FACTORIES[self.chain]:
            return pools

        chain_config = CHAINS[self.chain]
        quote_tokens = chain_config.stablecoins

        try:
            registry = self.web3.eth.contract(
                address=Web3.to_checksum_address(
                    DEX_FACTORIES[self.chain]["curve"]["registry"]
                ),
                abi=self.REGISTRY_ABI,
            )

            for quote_token in quote_tokens:
                try:
                    pool_address = registry.functions.find_pool_for_coins(
                        token_address,
                        Web3.to_checksum_address(quote_token),
                    ).call()

                    if pool_address == "0x0000000000000000000000000000000000000000":
                        continue

                    pool = self._get_pool_info(pool_address, registry, token_address)
                    if pool:
                        pools.append(pool)

                except Exception:
                    continue

        except Exception:
            pass

        return pools

    def _get_pool_info(self, pool_address: str, registry, token_address: str) -> Pool:
        """Get Curve pool information."""
        try:
            coins = registry.functions.get_coins(
                Web3.to_checksum_address(pool_address)
            ).call()
            balances = registry.functions.get_balances(
                Web3.to_checksum_address(pool_address)
            ).call()

            # Filter out zero addresses
            valid_coins = [
                (coins[i], balances[i])
                for i in range(len(coins))
                if coins[i] != "0x0000000000000000000000000000000000000000"
            ]

            if len(valid_coins) < 2:
                return None

            # Find token and quote
            token_idx = None
            quote_idx = None
            for i, (coin, _) in enumerate(valid_coins):
                if coin.lower() == token_address.lower():
                    token_idx = i
                elif quote_idx is None:
                    quote_idx = i

            if token_idx is None or quote_idx is None:
                return None

            token0, reserve0 = valid_coins[token_idx]
            token1, reserve1 = valid_coins[quote_idx]

            token0_symbol, token0_decimals = self.get_token_info(token0)
            token1_symbol, token1_decimals = self.get_token_info(token1)

            # Calculate USD (assume stablecoins = $1)
            liquidity_usd = self._calculate_liquidity_usd(
                reserve0, reserve1,
                token0, token1,
                token0_decimals, token1_decimals,
            )

            return Pool(
                address=pool_address,
                dex_name="Curve",
                token0=token0,
                token1=token1,
                reserve0=reserve0,
                reserve1=reserve1,
                token0_symbol=token0_symbol,
                token1_symbol=token1_symbol,
                token0_decimals=token0_decimals,
                token1_decimals=token1_decimals,
                liquidity_usd=liquidity_usd,
            )
        except Exception:
            return None

    def _calculate_liquidity_usd(
        self,
        reserve0: int,
        reserve1: int,
        token0: str,
        token1: str,
        decimals0: int,
        decimals1: int,
    ) -> float:
        """Calculate approximate USD liquidity."""
        chain_config = CHAINS[self.chain]
        stablecoins = [s.lower() for s in chain_config.stablecoins]

        # Curve pools are mostly stablecoins
        if token0.lower() in stablecoins:
            return (reserve0 / (10 ** decimals0)) * 2
        elif token1.lower() in stablecoins:
            return (reserve1 / (10 ** decimals1)) * 2

        return 0.0

    def get_reserves(self, pool_address: str) -> tuple:
        """Get reserves for a Curve pool."""
        # Curve pools have varying structures, return basic estimate
        try:
            registry = self.web3.eth.contract(
                address=Web3.to_checksum_address(
                    DEX_FACTORIES[self.chain]["curve"]["registry"]
                ),
                abi=self.REGISTRY_ABI,
            )
            balances = registry.functions.get_balances(
                Web3.to_checksum_address(pool_address)
            ).call()
            return (balances[0], balances[1])
        except Exception:
            return (0, 0)
