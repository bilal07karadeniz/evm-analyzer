"""Markdown report generator - optimized for token usage."""

from typing import List, Optional
from dataclasses import asdict

from modules.token import TokenInfo
from modules.ownership import OwnershipInfo
from modules.proxy import ProxyInfo
from modules.security import SecurityInfo
from dexes.base import Pool


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

        Returns:
            Markdown string
        """
        self.lines = []

        self._add_header(token, chain)
        self._add_token_info(token)
        self._add_ownership(ownership)
        self._add_proxy(proxy)
        self._add_security(security)
        self._add_liquidity(pools)

        return "\n".join(self.lines)

    def _add_header(self, token: TokenInfo, chain: str):
        """Add report header."""
        symbol = token.symbol or "Unknown"
        self.lines.append(f"# {symbol} Analysis")
        self.lines.append(f"**Address:** `{token.address}`")
        self.lines.append(f"**Chain:** {chain}")
        self.lines.append("")

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
            self.lines.append("## Ownership")
            for item in items:
                self.lines.append(f"- {item}")
            self.lines.append("")

    def _add_proxy(self, proxy: ProxyInfo):
        """Add proxy info - only if is proxy."""
        if not proxy.is_proxy:
            return

        self.lines.append("## Proxy")
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
            self.lines.append("## Security Flags")
            for item in items:
                self.lines.append(f"- {item}")
            self.lines.append("")

    def _add_liquidity(self, pools: List[Pool]):
        """Add top liquidity pools."""
        if not pools:
            self.lines.append("## Liquidity")
            self.lines.append("No pools found")
            self.lines.append("")
            return

        self.lines.append("## Liquidity (Top 5)")
        self.lines.append("")
        self.lines.append("| DEX | Pair | Liquidity |")
        self.lines.append("|-----|------|-----------|")

        for pool in pools[:5]:
            pair = f"{pool.token0_symbol}/{pool.token1_symbol}"
            liq = self._format_usd(pool.liquidity_usd)
            fee = f" ({pool.fee_tier/10000:.2f}%)" if pool.fee_tier else ""
            self.lines.append(f"| {pool.dex_name}{fee} | {pair} | {liq} |")

        self.lines.append("")

    def _format_usd(self, value: float) -> str:
        """Format USD value."""
        if value >= 1_000_000:
            return f"${value / 1_000_000:.2f}M"
        elif value >= 1_000:
            return f"${value / 1_000:.2f}K"
        elif value > 0:
            return f"${value:.2f}"
        else:
            return "$0"
