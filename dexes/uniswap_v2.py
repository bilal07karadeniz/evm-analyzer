"""Uniswap V2 adapter (also works for forks: Sushiswap, PancakeSwap V2, BiSwap, MDEX, ApeSwap)."""

from typing import List, Dict

from web3 import Web3

from config import CHAINS, DEX_FACTORIES
from .base import BaseDEXAdapter, Pool


class UniswapV2Adapter(BaseDEXAdapter):
    """Adapter for Uniswap V2 and forks."""

    name = "uniswap_v2"
    chains = ["ethereum", "bsc"]

    # DEX configs per chain
    DEX_CONFIGS: Dict[str, List[Dict]] = {
        "ethereum": [
            {"name": "Uniswap V2", "factory": DEX_FACTORIES["ethereum"]["uniswap_v2"]["factory"]},
            {"name": "SushiSwap", "factory": DEX_FACTORIES["ethereum"]["sushiswap"]["factory"]},
        ],
        "bsc": [
            {"name": "PancakeSwap V2", "factory": DEX_FACTORIES["bsc"]["pancakeswap_v2"]["factory"]},
            {"name": "BiSwap", "factory": DEX_FACTORIES["bsc"]["biswap"]["factory"]},
            {"name": "MDEX", "factory": DEX_FACTORIES["bsc"]["mdex"]["factory"]},
            {"name": "ApeSwap", "factory": DEX_FACTORIES["bsc"]["apeswap"]["factory"]},
        ],
    }

    FACTORY_ABI = [
        {
            "constant": True,
            "inputs": [
                {"name": "tokenA", "type": "address"},
                {"name": "tokenB", "type": "address"},
            ],
            "name": "getPair",
            "outputs": [{"name": "pair", "type": "address"}],
            "type": "function",
        },
    ]

    PAIR_ABI = [
        {"constant": True, "inputs": [], "name": "token0", "outputs": [{"type": "address"}], "type": "function"},
        {"constant": True, "inputs": [], "name": "token1", "outputs": [{"type": "address"}], "type": "function"},
        {
            "constant": True,
            "inputs": [],
            "name": "getReserves",
            "outputs": [
                {"name": "reserve0", "type": "uint112"},
                {"name": "reserve1", "type": "uint112"},
                {"name": "blockTimestampLast", "type": "uint32"},
            ],
            "type": "function",
        },
    ]

    def find_pools(self, token_address: str) -> List[Pool]:
        """Find V2 pools containing the token."""
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
                try:
                    pair_address = factory.functions.getPair(
                        token_address,
                        Web3.to_checksum_address(quote_token),
                    ).call()

                    if pair_address == "0x0000000000000000000000000000000000000000":
                        continue

                    pool = self._get_pool_info(pair_address, dex["name"])
                    if pool:
                        pools.append(pool)

                except Exception:
                    continue

        return pools

    def _get_pool_info(self, pair_address: str, dex_name: str) -> Pool:
        """Get detailed pool information."""
        try:
            pair = self.web3.eth.contract(
                address=Web3.to_checksum_address(pair_address),
                abi=self.PAIR_ABI,
            )

            token0 = pair.functions.token0().call()
            token1 = pair.functions.token1().call()
            reserves = pair.functions.getReserves().call()

            token0_symbol, token0_decimals = self.get_token_info(token0)
            token1_symbol, token1_decimals = self.get_token_info(token1)

            # Calculate USD value (simplified - assumes stablecoin is $1)
            liquidity_usd = self._calculate_liquidity_usd(
                reserves[0], reserves[1],
                token0, token1,
                token0_decimals, token1_decimals,
            )

            return Pool(
                address=pair_address,
                dex_name=dex_name,
                token0=token0,
                token1=token1,
                reserve0=reserves[0],
                reserve1=reserves[1],
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
        """Calculate approximate USD liquidity value."""
        chain_config = CHAINS[self.chain]
        stablecoins = [s.lower() for s in chain_config.stablecoins]

        # If one side is a stablecoin, use it as price reference
        if token0.lower() in stablecoins:
            return (reserve0 / (10 ** decimals0)) * 2
        elif token1.lower() in stablecoins:
            return (reserve1 / (10 ** decimals1)) * 2

        # If one side is wrapped native, estimate based on native price
        # This is a rough estimate - for accurate pricing, use an oracle
        wrapped_native = chain_config.wrapped_native.lower()
        native_price_usd = 2000 if self.chain == "ethereum" else 300  # Rough ETH/BNB price

        if token0.lower() == wrapped_native:
            return (reserve0 / (10 ** decimals0)) * native_price_usd * 2
        elif token1.lower() == wrapped_native:
            return (reserve1 / (10 ** decimals1)) * native_price_usd * 2

        # Unknown tokens - return 0
        return 0.0

    def get_reserves(self, pool_address: str) -> tuple:
        """Get reserves for a V2 pool."""
        pair = self.web3.eth.contract(
            address=Web3.to_checksum_address(pool_address),
            abi=self.PAIR_ABI,
        )
        reserves = pair.functions.getReserves().call()
        return (reserves[0], reserves[1])
