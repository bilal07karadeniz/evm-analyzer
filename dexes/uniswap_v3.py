"""Uniswap V3 adapter (also works for forks: PancakeSwap V3)."""

from typing import List, Dict

from web3 import Web3

from config import CHAINS, DEX_FACTORIES
from .base import BaseDEXAdapter, Pool


class UniswapV3Adapter(BaseDEXAdapter):
    """Adapter for Uniswap V3 and forks."""

    name = "uniswap_v3"
    chains = ["ethereum", "bsc"]

    # Fee tiers to check (in hundredths of a bip)
    # Uniswap V3: 100, 500, 3000, 10000
    # PancakeSwap V3: 100, 500, 2500, 10000
    FEE_TIERS = [100, 500, 2500, 3000, 10000]  # 0.01%, 0.05%, 0.25%, 0.3%, 1%

    # DEX configs per chain
    DEX_CONFIGS: Dict[str, List[Dict]] = {
        "ethereum": [
            {"name": "Uniswap V3", "factory": DEX_FACTORIES["ethereum"]["uniswap_v3"]["factory"]},
        ],
        "bsc": [
            {"name": "PancakeSwap V3", "factory": DEX_FACTORIES["bsc"]["pancakeswap_v3"]["factory"]},
        ],
    }

    FACTORY_ABI = [
        {
            "inputs": [
                {"name": "tokenA", "type": "address"},
                {"name": "tokenB", "type": "address"},
                {"name": "fee", "type": "uint24"},
            ],
            "name": "getPool",
            "outputs": [{"name": "pool", "type": "address"}],
            "stateMutability": "view",
            "type": "function",
        },
    ]

    POOL_ABI = [
        {"inputs": [], "name": "token0", "outputs": [{"type": "address"}], "stateMutability": "view", "type": "function"},
        {"inputs": [], "name": "token1", "outputs": [{"type": "address"}], "stateMutability": "view", "type": "function"},
        {"inputs": [], "name": "fee", "outputs": [{"type": "uint24"}], "stateMutability": "view", "type": "function"},
        {"inputs": [], "name": "liquidity", "outputs": [{"type": "uint128"}], "stateMutability": "view", "type": "function"},
        {
            "inputs": [],
            "name": "slot0",
            "outputs": [
                {"name": "sqrtPriceX96", "type": "uint160"},
                {"name": "tick", "type": "int24"},
                {"name": "observationIndex", "type": "uint16"},
                {"name": "observationCardinality", "type": "uint16"},
                {"name": "observationCardinalityNext", "type": "uint16"},
                {"name": "feeProtocol", "type": "uint8"},
                {"name": "unlocked", "type": "bool"},
            ],
            "stateMutability": "view",
            "type": "function",
        },
    ]

    def find_pools(self, token_address: str) -> List[Pool]:
        """Find V3 pools containing the token."""
        pools = []
        token_address = Web3.to_checksum_address(token_address)

        chain_config = CHAINS[self.chain]
        quote_tokens = [chain_config.wrapped_native] + chain_config.stablecoins

        dex_configs = self.DEX_CONFIGS.get(self.chain, [])

        for dex in dex_configs:
            factory = self.web3.eth.contract(
                address=Web3.to_checksum_address(dex["factory"]),
                abi=self.FACTORY_ABI,
            )

            for quote_token in quote_tokens:
                for fee in self.FEE_TIERS:
                    try:
                        pool_address = factory.functions.getPool(
                            token_address,
                            Web3.to_checksum_address(quote_token),
                            fee,
                        ).call()

                        if pool_address == "0x0000000000000000000000000000000000000000":
                            continue

                        pool = self._get_pool_info(pool_address, dex["name"])
                        if pool:
                            pools.append(pool)

                    except Exception:
                        continue

        return pools

    def _get_pool_info(self, pool_address: str, dex_name: str) -> Pool:
        """Get detailed pool information."""
        try:
            pool_contract = self.web3.eth.contract(
                address=Web3.to_checksum_address(pool_address),
                abi=self.POOL_ABI,
            )

            token0 = pool_contract.functions.token0().call()
            token1 = pool_contract.functions.token1().call()
            fee = pool_contract.functions.fee().call()
            liquidity = pool_contract.functions.liquidity().call()
            slot0 = pool_contract.functions.slot0().call()

            token0_symbol, token0_decimals = self.get_token_info(token0)
            token1_symbol, token1_decimals = self.get_token_info(token1)

            # Calculate reserves from liquidity and price
            sqrt_price = slot0[0]
            reserve0, reserve1 = self._calculate_reserves(
                liquidity, sqrt_price, token0_decimals, token1_decimals
            )

            # Calculate USD value
            liquidity_usd = self._calculate_liquidity_usd(
                reserve0, reserve1,
                token0, token1,
                token0_decimals, token1_decimals,
            )

            return Pool(
                address=pool_address,
                dex_name=dex_name,
                token0=token0,
                token1=token1,
                reserve0=reserve0,
                reserve1=reserve1,
                token0_symbol=token0_symbol,
                token1_symbol=token1_symbol,
                token0_decimals=token0_decimals,
                token1_decimals=token1_decimals,
                liquidity_usd=liquidity_usd,
                fee_tier=fee,
            )
        except Exception:
            return None

    def _calculate_reserves(
        self,
        liquidity: int,
        sqrt_price_x96: int,
        decimals0: int,
        decimals1: int,
    ) -> tuple:
        """Estimate reserves from V3 liquidity and price.

        This is a simplified calculation - actual reserves depend on tick range.
        """
        if sqrt_price_x96 == 0 or liquidity == 0:
            return (0, 0)

        # sqrtPriceX96 = sqrt(price) * 2^96
        # price = (sqrtPriceX96 / 2^96)^2
        Q96 = 2 ** 96

        # Approximate reserves (simplified)
        try:
            reserve0 = (liquidity * Q96) // sqrt_price_x96
            reserve1 = (liquidity * sqrt_price_x96) // Q96
            return (reserve0, reserve1)
        except Exception:
            return (0, 0)

    def _calculate_liquidity_usd(
        self,
        reserve0: int,
        reserve1: int,
        token0: str,
        token1: str,
        decimals0: int,
        decimals1: int,
    ) -> float:
        """Calculate approximate USD liquidity value."""
        chain_config = CHAINS[self.chain]
        stablecoins = [s.lower() for s in chain_config.stablecoins]

        if token0.lower() in stablecoins:
            return (reserve0 / (10 ** decimals0)) * 2
        elif token1.lower() in stablecoins:
            return (reserve1 / (10 ** decimals1)) * 2

        wrapped_native = chain_config.wrapped_native.lower()
        native_price_usd = 2000 if self.chain == "ethereum" else 300

        if token0.lower() == wrapped_native:
            return (reserve0 / (10 ** decimals0)) * native_price_usd * 2
        elif token1.lower() == wrapped_native:
            return (reserve1 / (10 ** decimals1)) * native_price_usd * 2

        return 0.0

    def get_reserves(self, pool_address: str) -> tuple:
        """Get reserves for a V3 pool (estimated from liquidity)."""
        pool_contract = self.web3.eth.contract(
            address=Web3.to_checksum_address(pool_address),
            abi=self.POOL_ABI,
        )

        liquidity = pool_contract.functions.liquidity().call()
        slot0 = pool_contract.functions.slot0().call()
        token0 = pool_contract.functions.token0().call()
        token1 = pool_contract.functions.token1().call()

        _, decimals0 = self.get_token_info(token0)
        _, decimals1 = self.get_token_info(token1)

        return self._calculate_reserves(liquidity, slot0[0], decimals0, decimals1)
