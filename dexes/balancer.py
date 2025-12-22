"""Balancer adapter."""

from typing import List

from web3 import Web3

from config import CHAINS, DEX_FACTORIES
from .base import BaseDEXAdapter, Pool


class BalancerAdapter(BaseDEXAdapter):
    """Adapter for Balancer weighted pools."""

    name = "balancer"
    chains = ["ethereum"]

    VAULT_ABI = [
        {
            "inputs": [{"name": "poolId", "type": "bytes32"}],
            "name": "getPoolTokens",
            "outputs": [
                {"name": "tokens", "type": "address[]"},
                {"name": "balances", "type": "uint256[]"},
                {"name": "lastChangeBlock", "type": "uint256"},
            ],
            "stateMutability": "view",
            "type": "function",
        },
    ]

    # Common Balancer pool IDs that might contain the token
    # In practice, you'd query subgraph or events to find pools
    def find_pools(self, token_address: str) -> List[Pool]:
        """Find Balancer pools containing the token.

        Note: Balancer pool discovery typically requires subgraph queries.
        This is a simplified implementation.
        """
        pools = []
        token_address = Web3.to_checksum_address(token_address)

        if self.chain not in DEX_FACTORIES or "balancer" not in DEX_FACTORIES[self.chain]:
            return pools

        # Balancer V2 uses a single Vault contract
        # Pool discovery typically requires subgraph queries
        # For now, return empty - full implementation would use Balancer subgraph
        return pools

    def get_pool_info_by_id(self, pool_id: str) -> Pool:
        """Get pool information by Balancer pool ID.

        Args:
            pool_id: 32-byte pool ID

        Returns:
            Pool object or None
        """
        try:
            vault = self.web3.eth.contract(
                address=Web3.to_checksum_address(
                    DEX_FACTORIES[self.chain]["balancer"]["vault"]
                ),
                abi=self.VAULT_ABI,
            )

            tokens, balances, _ = vault.functions.getPoolTokens(
                bytes.fromhex(pool_id[2:] if pool_id.startswith("0x") else pool_id)
            ).call()

            if len(tokens) < 2:
                return None

            token0 = tokens[0]
            token1 = tokens[1]
            reserve0 = balances[0]
            reserve1 = balances[1]

            token0_symbol, token0_decimals = self.get_token_info(token0)
            token1_symbol, token1_decimals = self.get_token_info(token1)

            liquidity_usd = self._calculate_liquidity_usd(
                reserve0, reserve1,
                token0, token1,
                token0_decimals, token1_decimals,
            )

            # Pool address is first 20 bytes of pool ID
            pool_address = "0x" + pool_id[2:42] if pool_id.startswith("0x") else "0x" + pool_id[:40]

            return Pool(
                address=pool_address,
                dex_name="Balancer",
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

        if token0.lower() in stablecoins:
            return (reserve0 / (10 ** decimals0)) * 2
        elif token1.lower() in stablecoins:
            return (reserve1 / (10 ** decimals1)) * 2

        wrapped_native = chain_config.wrapped_native.lower()
        native_price_usd = 2000

        if token0.lower() == wrapped_native:
            return (reserve0 / (10 ** decimals0)) * native_price_usd * 2
        elif token1.lower() == wrapped_native:
            return (reserve1 / (10 ** decimals1)) * native_price_usd * 2

        return 0.0

    def get_reserves(self, pool_address: str) -> tuple:
        """Get reserves for a Balancer pool.

        Note: Requires pool ID, not just address.
        """
        return (0, 0)
