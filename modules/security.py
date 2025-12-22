"""Security analysis module - fee simulation, honeypot detection."""

from dataclasses import dataclass
from typing import Optional, Tuple

from web3 import Web3

from core.contract import ContractHelper
from config import CHAINS


@dataclass
class SecurityInfo:
    """Security analysis information."""
    buy_fee_percent: Optional[float] = None
    sell_fee_percent: Optional[float] = None
    is_honeypot: bool = False
    honeypot_reason: Optional[str] = None
    max_tx_amount: Optional[int] = None
    max_wallet_amount: Optional[int] = None
    has_trading_cooldown: bool = False


class SecurityAnalyzer:
    """Security analysis including fee simulation."""

    # Transfer simulation amount (0.01 ETH worth)
    SIMULATION_AMOUNT = 10 ** 16

    def __init__(self, web3: Web3, chain: str):
        self.web3 = web3
        self.chain = chain
        self.helper = ContractHelper(web3)

    def analyze(self, token_address: str) -> SecurityInfo:
        """Analyze token security properties.

        Args:
            token_address: Token address

        Returns:
            SecurityInfo object
        """
        token_address = Web3.to_checksum_address(token_address)
        info = SecurityInfo()

        # Check for max transaction/wallet limits
        info.max_tx_amount = self._get_max_tx(token_address)
        info.max_wallet_amount = self._get_max_wallet(token_address)

        # Check for trading cooldown
        info.has_trading_cooldown = self._has_cooldown(token_address)

        # Simulate transfers to detect fees
        buy_fee, sell_fee = self._simulate_fees(token_address)
        info.buy_fee_percent = buy_fee
        info.sell_fee_percent = sell_fee

        # Check for honeypot
        if sell_fee is not None and sell_fee > 50:
            info.is_honeypot = True
            info.honeypot_reason = f"Sell fee too high ({sell_fee}%)"
        elif self._check_sell_blocked(token_address):
            info.is_honeypot = True
            info.honeypot_reason = "Sell transfers blocked"

        return info

    def _get_max_tx(self, address: str) -> Optional[int]:
        """Get max transaction amount."""
        # Try common function names
        for func in ["maxTxAmount()", "_maxTxAmount()", "maxTransactionAmount()"]:
            result = self.helper.call_safe(address, func)
            if result:
                value = self.helper.decode_uint256(result)
                if value and value > 0:
                    return value
        return None

    def _get_max_wallet(self, address: str) -> Optional[int]:
        """Get max wallet amount."""
        for func in ["maxWalletAmount()", "_maxWalletAmount()", "maxWallet()"]:
            result = self.helper.call_safe(address, func)
            if result:
                value = self.helper.decode_uint256(result)
                if value and value > 0:
                    return value
        return None

    def _has_cooldown(self, address: str) -> bool:
        """Check if token has trading cooldown."""
        code = self.helper.get_code(address)
        if not code:
            return False

        code_hex = code.hex().lower()

        # Common cooldown-related signatures
        cooldown_indicators = [
            Web3.keccak(text="cooldownEnabled()")[:4].hex(),
            Web3.keccak(text="tradingCooldown()")[:4].hex(),
            "cooldown",
        ]

        for indicator in cooldown_indicators:
            if indicator in code_hex:
                return True

        return False

    def _simulate_fees(self, token_address: str) -> Tuple[Optional[float], Optional[float]]:
        """Simulate buy/sell to detect fees.

        Returns:
            Tuple of (buy_fee_percent, sell_fee_percent)
        """
        # First, try to read fees directly from contract (more reliable)
        buy_fee, sell_fee = self._read_fees_from_contract(token_address)
        if buy_fee is not None or sell_fee is not None:
            return (buy_fee, sell_fee)

        # Fallback to simulation
        try:
            holder = self._find_holder(token_address)
            if not holder:
                return (None, None)

            contract = self.helper.get_contract(token_address, "erc20")
            balance = contract.functions.balanceOf(holder).call()

            if balance == 0:
                return (None, None)

            test_amount = min(balance // 10, self.SIMULATION_AMOUNT)
            if test_amount == 0:
                return (None, None)

            self.web3.provider.make_request("anvil_impersonateAccount", [holder])
            self.web3.provider.make_request(
                "anvil_setBalance",
                [holder, hex(10 ** 18)],
            )

            # Use a random address instead of dead address (which is often excluded)
            receiver = "0x1234567890123456789012345678901234567890"

            balance_before = contract.functions.balanceOf(receiver).call()

            try:
                tx_hash = contract.functions.transfer(receiver, test_amount).transact({
                    "from": holder,
                    "gas": 500000,
                })
                self.web3.eth.wait_for_transaction_receipt(tx_hash)
            except Exception as e:
                self.web3.provider.make_request("anvil_stopImpersonatingAccount", [holder])
                error_msg = str(e).lower()
                if "revert" in error_msg and ("blacklist" in error_msg or "blocked" in error_msg):
                    return (None, 100.0)
                return (None, None)

            balance_after = contract.functions.balanceOf(receiver).call()
            received = balance_after - balance_before

            self.web3.provider.make_request("anvil_stopImpersonatingAccount", [holder])

            if test_amount > 0 and received > 0:
                fee_percent = ((test_amount - received) / test_amount) * 100
                if fee_percent > 0.1:  # Only report if fee > 0.1%
                    return (fee_percent, fee_percent)

            return (None, None)

        except Exception:
            return (None, None)

    def _read_fees_from_contract(self, token_address: str) -> Tuple[Optional[float], Optional[float]]:
        """Try to read fees directly from contract functions."""
        buy_fee = None
        sell_fee = None

        # Common fee function names for buy fees
        buy_fee_funcs = [
            "buyTotalFees()",
            "_buyTotalFees()",
            "buyFee()",
            "_buyFee()",
            "buyTaxFee()",
            "totalBuyFee()",
            "_totalBuyFee()",
            "buyMarketingFee()",
            "buyLiquidityFee()",
            "_taxFee()",
            "taxFee()",
            # SafeMoon/BabyDoge style
            "_buyTax()",
            "buyTax()",
            "_buyFees()",
            "getBuyTax()",
        ]

        # Common fee function names for sell fees
        sell_fee_funcs = [
            "sellTotalFees()",
            "_sellTotalFees()",
            "sellFee()",
            "_sellFee()",
            "sellTaxFee()",
            "totalSellFee()",
            "_totalSellFee()",
            "sellMarketingFee()",
            "sellLiquidityFee()",
            # SafeMoon/BabyDoge style
            "_sellTax()",
            "sellTax()",
            "_sellFees()",
            "getSellTax()",
        ]

        # Try to get buy fee
        for func in buy_fee_funcs:
            result = self.helper.call_safe(token_address, func)
            if result:
                value = self.helper.decode_uint256(result)
                if value is not None and 0 < value <= 100:
                    buy_fee = float(value)
                    break

        # Try to get sell fee
        for func in sell_fee_funcs:
            result = self.helper.call_safe(token_address, func)
            if result:
                value = self.helper.decode_uint256(result)
                if value is not None and 0 < value <= 100:
                    sell_fee = float(value)
                    break

        # If not found, try generic fee functions
        if buy_fee is None and sell_fee is None:
            generic_funcs = [
                "totalFee()",
                "totalFees()",
                "_totalFees()",
                "_totalFee()",
                "fee()",
                "_fee()",
                # Reflection token style
                "_taxFee()",
                "_liquidityFee()",
                "reflectionFee()",
            ]
            for func in generic_funcs:
                result = self.helper.call_safe(token_address, func)
                if result:
                    value = self.helper.decode_uint256(result)
                    if value is not None and 0 < value <= 100:
                        buy_fee = float(value)
                        sell_fee = float(value)
                        break

        # Try to sum up individual fees (SafeMoon style: liquidity + reflection + marketing)
        if buy_fee is None and sell_fee is None:
            total = 0
            fee_components = [
                "_liquidityFee()",
                "_reflectionFee()",
                "_marketingFee()",
                "_burnFee()",
                "liquidityFee()",
                "reflectionFee()",
                "marketingFee()",
            ]
            for func in fee_components:
                result = self.helper.call_safe(token_address, func)
                if result:
                    value = self.helper.decode_uint256(result)
                    if value is not None and value <= 50:
                        total += value
            if total > 0 and total <= 100:
                buy_fee = float(total)
                sell_fee = float(total)

        # Some tokens store fees in basis points (divide by 100) or per-mille (divide by 10)
        if buy_fee is not None and buy_fee > 50:
            buy_fee = buy_fee / 100 if buy_fee > 100 else buy_fee / 10
        if sell_fee is not None and sell_fee > 50:
            sell_fee = sell_fee / 100 if sell_fee > 100 else sell_fee / 10

        return (buy_fee, sell_fee)

    def _find_holder(self, token_address: str) -> Optional[str]:
        """Find a token holder to use for simulation.

        Prefers regular wallets over LPs since LPs are often excluded from fees.
        """
        from config import DEX_FACTORIES

        chain_config = CHAINS[self.chain]
        contract = self.helper.get_contract(token_address, "erc20")

        # First, try to find a regular holder by checking top Transfer events
        # This helps find wallets that aren't excluded from fees
        try:
            # Get a few recent blocks and find transfer recipients
            latest_block = self.web3.eth.block_number
            transfer_topic = Web3.keccak(text="Transfer(address,address,uint256)")

            logs = self.web3.eth.get_logs({
                "address": Web3.to_checksum_address(token_address),
                "topics": [transfer_topic.hex()],
                "fromBlock": max(0, latest_block - 1000),
                "toBlock": latest_block,
            })

            # Check recipients for balance
            checked = set()
            for log in logs[-50:]:  # Check last 50 transfers
                if len(log["topics"]) >= 3:
                    recipient = "0x" + log["topics"][2].hex()[-40:]
                    recipient = Web3.to_checksum_address(recipient)

                    if recipient in checked:
                        continue
                    checked.add(recipient)

                    # Skip zero address and common excluded addresses
                    if recipient == "0x0000000000000000000000000000000000000000":
                        continue
                    if recipient.lower() == "0x000000000000000000000000000000000000dead":
                        continue

                    try:
                        balance = contract.functions.balanceOf(recipient).call()
                        if balance > 10 ** 15:  # Has meaningful balance
                            return recipient
                    except Exception:
                        continue
        except Exception:
            pass

        # Fallback: try to find a liquidity pool
        if self.chain in DEX_FACTORIES:
            for dex_name, dex_config in DEX_FACTORIES[self.chain].items():
                if "factory" not in dex_config:
                    continue

                try:
                    factory_abi = [
                        {"constant": True, "inputs": [{"name": "tokenA", "type": "address"}, {"name": "tokenB", "type": "address"}], "name": "getPair", "outputs": [{"name": "pair", "type": "address"}], "type": "function"},
                    ]
                    factory = self.web3.eth.contract(
                        address=Web3.to_checksum_address(dex_config["factory"]),
                        abi=factory_abi,
                    )
                    pair = factory.functions.getPair(
                        Web3.to_checksum_address(token_address),
                        Web3.to_checksum_address(chain_config.wrapped_native),
                    ).call()

                    if pair and pair != "0x0000000000000000000000000000000000000000":
                        balance = contract.functions.balanceOf(pair).call()
                        if balance > 0:
                            return pair
                except Exception:
                    continue

        return None

    def _check_sell_blocked(self, token_address: str) -> bool:
        """Check if sells are blocked."""
        code = self.helper.get_code(token_address)
        if not code:
            return False

        code_hex = code.hex().lower()

        # Check for common anti-sell patterns
        # This is a heuristic - actual behavior requires simulation
        block_indicators = [
            "onlybuy",
            "nosell",
            "selllock",
        ]

        for indicator in block_indicators:
            if indicator in code_hex:
                return True

        return False
