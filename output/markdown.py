"""Markdown report generator - optimized for token usage."""

from typing import List, Optional, Dict
from dataclasses import asdict

from modules.token import TokenInfo
from modules.ownership import OwnershipInfo
from modules.proxy import ProxyInfo
from modules.security import SecurityInfo
from dexes.base import Pool
from config import DEX_FACTORIES


class MarkdownReport:
    """Generates compact markdown reports optimized for LLM token usage."""

    def __init__(self):
        self.lines: List[str] = []

    def generate(
        self,
        token: TokenInfo,
        ownership: OwnershipInfo,
        proxy: ProxyInfo,
        security: SecurityInfo,
        pools: List[Pool],
        chain: str,
        dex_verbose: bool = False,
    ) -> str:
        """Generate the full markdown report.

        Only includes detected issues - no "not found" or "not detected" entries.

        Args:
            token: Token information
            ownership: Ownership information
            proxy: Proxy information
            security: Security information
            pools: Top liquidity pools
            chain: Chain name
            dex_verbose: Show factory/router addresses in DEXes section

        Returns:
            Markdown string
        """
        self.lines = []

        self._add_token_info(token)
        self._add_ownership(ownership)
        self._add_proxy(proxy)
        self._add_security(security)
        self._add_liquidity(pools, token.address, token.symbol, token.decimals)
        self._add_queried_dexes(chain, dex_verbose)

        return "\n".join(self.lines)

    def _add_token_info(self, token: TokenInfo):
        """Add token basic info."""
        self.lines.append("## Token Info")

        info_parts = []
        if token.name:
            info_parts.append(f"Name: {token.name}")
        if token.symbol:
            info_parts.append(f"Symbol: {token.symbol}")
        if token.decimals is not None:
            info_parts.append(f"Decimals: {token.decimals}")
        if token.total_supply_formatted:
            info_parts.append(f"Supply: {token.total_supply_formatted}")
        if token.price_usd is not None:
            info_parts.append(f"Price: {self._format_price(token.price_usd)}")
        if token.price_native is not None and token.native_symbol:
            info_parts.append(f"Price ({token.native_symbol}): {self._format_native_price(token.price_native)} {token.native_symbol}")

        for part in info_parts:
            self.lines.append(f"- {part}")

        self.lines.append("")

    def _add_ownership(self, ownership: OwnershipInfo):
        """Add ownership info - only if relevant issues found."""
        items = []

        if ownership.owner:
            owner_type = ""
            if ownership.owner_is_renounced:
                owner_type = " (renounced)"
            elif ownership.owner_is_contract:
                owner_type = " (contract)"
            else:
                owner_type = " (EOA)"
            items.append(f"Owner: `{ownership.owner}`{owner_type}")

        if ownership.paused:
            items.append("**PAUSED**")

        if ownership.has_mint:
            items.append("Has mint()")

        if ownership.has_burn:
            items.append("Has burn()")

        if ownership.has_blacklist:
            items.append("Has blacklist")

        if ownership.roles_detected:
            items.append(f"Roles: {', '.join(ownership.roles_detected)}")

        if items:
            self.lines.append("### Ownership")
            for item in items:
                self.lines.append(f"- {item}")
            self.lines.append("")

    def _add_proxy(self, proxy: ProxyInfo):
        """Add proxy info - only if is proxy."""
        if not proxy.is_proxy:
            return

        self.lines.append("### Proxy")
        self.lines.append(f"- Type: {proxy.proxy_type}")
        if proxy.implementation:
            self.lines.append(f"- Implementation: `{proxy.implementation}`")
        if proxy.admin:
            self.lines.append(f"- Admin: `{proxy.admin}`")
        self.lines.append("")

    def _add_security(self, security: SecurityInfo):
        """Add security flags - only detected issues."""
        items = []

        if security.is_honeypot:
            items.append(f"**HONEYPOT:** {security.honeypot_reason}")

        if security.buy_fee_percent is not None and security.buy_fee_percent > 0:
            items.append(f"Buy fee: {security.buy_fee_percent:.1f}%")

        if security.sell_fee_percent is not None and security.sell_fee_percent > 0:
            items.append(f"Sell fee: {security.sell_fee_percent:.1f}%")

        if security.max_tx_amount:
            items.append(f"Max TX limit exists")

        if security.max_wallet_amount:
            items.append(f"Max wallet limit exists")

        if security.has_trading_cooldown:
            items.append("Trading cooldown enabled")

        if items:
            self.lines.append("### Security Flags")
            for item in items:
                self.lines.append(f"- {item}")
            self.lines.append("")

    def _add_liquidity(self, pools: List[Pool], token_address: str, token_symbol: str, token_decimals: int):
        """Add top liquidity pools sorted by liquidity (high to low)."""
        if not pools:
            self.lines.append("## Liquidity")
            self.lines.append("No pools found")
            self.lines.append("")
            return

        # Sort pools by liquidity USD descending
        sorted_pools = sorted(pools, key=lambda p: p.liquidity_usd, reverse=True)[:5]

        self.lines.append("## Liquidity (Top 5)")
        self.lines.append("")
        self.lines.append("| DEX | Pair | Reserves | Liquidity |")
        self.lines.append("|-----|------|----------|-----------|")

        total_liquidity = 0
        total_token_reserve = 0
        token_address_lower = token_address.lower()

        for pool in sorted_pools:
            pair = f"{pool.token0_symbol}/{pool.token1_symbol}"
            liq = self._format_usd(pool.liquidity_usd)
            fee = f" ({pool.fee_tier/10000:.2f}%)" if pool.fee_tier else ""
            # Format reserves with symbols
            r0 = self._format_amount(pool.reserve0, pool.token0_decimals)
            r1 = self._format_amount(pool.reserve1, pool.token1_decimals)
            reserves = f"{r0} {pool.token0_symbol} / {r1} {pool.token1_symbol}"
            self.lines.append(f"| {pool.dex_name}{fee} | {pair} | {reserves} | {liq} |")
            total_liquidity += pool.liquidity_usd

            # Sum the analyzed token's reserve
            if pool.token0.lower() == token_address_lower:
                total_token_reserve += pool.reserve0
            elif pool.token1.lower() == token_address_lower:
                total_token_reserve += pool.reserve1

        # Format total token amount
        total_token_formatted = self._format_amount(total_token_reserve, token_decimals or 18)
        self.lines.append(f"| **Total** | | **{total_token_formatted} {token_symbol}** | **{self._format_usd(total_liquidity)}** |")
        self.lines.append("")

    def _format_amount(self, value: int, decimals: int) -> str:
        """Format token amount with decimals."""
        amount = value / (10 ** decimals)
        if amount >= 1_000_000_000:
            return f"{amount / 1_000_000_000:.2f}B"
        elif amount >= 1_000_000:
            return f"{amount / 1_000_000:.2f}M"
        elif amount >= 1_000:
            return f"{amount / 1_000:.2f}K"
        elif amount >= 1:
            return f"{amount:.2f}"
        else:
            return f"{amount:.6f}"

    def _format_usd(self, value: float) -> str:
        """Format USD value."""
        if value >= 1_000_000_000:
            return f"${value / 1_000_000_000:.2f}B"
        elif value >= 1_000_000:
            return f"${value / 1_000_000:.2f}M"
        elif value >= 1_000:
            return f"${value / 1_000:.2f}K"
        elif value > 0:
            return f"${value:.2f}"
        else:
            return "$0"

    def _format_price(self, value: float) -> str:
        """Format token price (handles very small values)."""
        if value >= 1:
            return f"${value:.2f}"
        elif value >= 0.01:
            return f"${value:.4f}"
        elif value >= 0.0001:
            return f"${value:.6f}"
        elif value > 0:
            return f"${value:.10f}"
        else:
            return "$0"

    def _format_native_price(self, value: float) -> str:
        """Format price in native currency (ETH/BNB)."""
        if value >= 1:
            return f"{value:.4f}"
        elif value >= 0.0001:
            return f"{value:.8f}"
        elif value > 0:
            return f"{value:.12f}"
        else:
            return "0"

    def _add_queried_dexes(self, chain: str, verbose: bool = False):
        """Add section showing which DEXes were queried."""
        dex_config = DEX_FACTORIES.get(chain, {})
        if not dex_config:
            return

        self.lines.append("### Queried DEXes")

        # Map internal names to display names
        dex_names = {
            "uniswap_v2": "Uniswap V2",
            "uniswap_v3": "Uniswap V3",
            "sushiswap": "SushiSwap",
            "curve": "Curve",
            "balancer": "Balancer",
            "pancakeswap_v2": "PancakeSwap V2",
            "pancakeswap_v3": "PancakeSwap V3",
            "biswap": "BiSwap",
            "mdex": "MDEX",
            "apeswap": "ApeSwap",
        }

        for idx, (dex_key, addresses) in enumerate(dex_config.items(), 1):
            dex_name = dex_names.get(dex_key, dex_key)

            if verbose:
                self.lines.append(f"{idx}. **{dex_name}**")
                for addr_type, addr in addresses.items():
                    # Capitalize address type (factory -> Factory)
                    addr_label = addr_type.capitalize()
                    self.lines.append(f"   - {addr_label}: `{addr}`")
            else:
                self.lines.append(f"{idx}. {dex_name}")

        self.lines.append("")
