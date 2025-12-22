"""Proxy detection module."""

from dataclasses import dataclass
from typing import Optional

from web3 import Web3

from core.contract import ContractHelper
from config import PROXY_SLOTS, ZERO_ADDRESS


@dataclass
class ProxyInfo:
    """Proxy detection information."""
    is_proxy: bool = False
    proxy_type: Optional[str] = None
    implementation: Optional[str] = None
    admin: Optional[str] = None


class ProxyAnalyzer:
    """Analyzes proxy patterns."""

    def __init__(self, web3: Web3):
        self.web3 = web3
        self.helper = ContractHelper(web3)

    def analyze(self, contract_address: str) -> ProxyInfo:
        """Analyze if contract is a proxy.

        Args:
            contract_address: Contract address to analyze

        Returns:
            ProxyInfo object
        """
        contract_address = Web3.to_checksum_address(contract_address)
        info = ProxyInfo()

        # Check EIP-1967 implementation slot
        impl = self._check_eip1967_implementation(contract_address)
        if impl:
            info.is_proxy = True
            info.proxy_type = "EIP-1967"
            info.implementation = impl
            info.admin = self._check_eip1967_admin(contract_address)
            return info

        # Check EIP-1967 beacon slot
        beacon = self._check_eip1967_beacon(contract_address)
        if beacon:
            info.is_proxy = True
            info.proxy_type = "Beacon"
            info.implementation = self._get_beacon_implementation(beacon)
            return info

        # Check for OpenZeppelin TransparentUpgradeableProxy
        impl = self._check_transparent_proxy(contract_address)
        if impl:
            info.is_proxy = True
            info.proxy_type = "Transparent"
            info.implementation = impl
            return info

        # Check for minimal proxy (EIP-1167)
        impl = self._check_minimal_proxy(contract_address)
        if impl:
            info.is_proxy = True
            info.proxy_type = "Minimal (EIP-1167)"
            info.implementation = impl
            return info

        return info

    def _check_eip1967_implementation(self, address: str) -> Optional[str]:
        """Check EIP-1967 implementation slot."""
        slot_value = self.helper.get_storage_at(address, PROXY_SLOTS["implementation"])
        if slot_value and slot_value != b"\x00" * 32:
            impl = "0x" + slot_value[-20:].hex()
            if impl != ZERO_ADDRESS:
                return Web3.to_checksum_address(impl)
        return None

    def _check_eip1967_admin(self, address: str) -> Optional[str]:
        """Check EIP-1967 admin slot."""
        slot_value = self.helper.get_storage_at(address, PROXY_SLOTS["admin"])
        if slot_value and slot_value != b"\x00" * 32:
            admin = "0x" + slot_value[-20:].hex()
            if admin != ZERO_ADDRESS:
                return Web3.to_checksum_address(admin)
        return None

    def _check_eip1967_beacon(self, address: str) -> Optional[str]:
        """Check EIP-1967 beacon slot."""
        slot_value = self.helper.get_storage_at(address, PROXY_SLOTS["beacon"])
        if slot_value and slot_value != b"\x00" * 32:
            beacon = "0x" + slot_value[-20:].hex()
            if beacon != ZERO_ADDRESS:
                return Web3.to_checksum_address(beacon)
        return None

    def _get_beacon_implementation(self, beacon_address: str) -> Optional[str]:
        """Get implementation from beacon contract."""
        result = self.helper.call_safe(beacon_address, "implementation()")
        if result:
            return self.helper.decode_address(result)
        return None

    def _check_transparent_proxy(self, address: str) -> Optional[str]:
        """Check for TransparentUpgradeableProxy pattern."""
        # Try calling implementation() directly (some proxies expose this)
        result = self.helper.call_safe(address, "implementation()")
        if result:
            impl = self.helper.decode_address(result)
            if impl and impl != ZERO_ADDRESS:
                return impl
        return None

    def _check_minimal_proxy(self, address: str) -> Optional[str]:
        """Check for EIP-1167 minimal proxy (clone).

        Bytecode pattern: 363d3d373d3d3d363d73<address>5af43d82803e903d91602b57fd5bf3
        """
        code = self.helper.get_code(address)
        if not code:
            return None

        code_hex = code.hex()

        # EIP-1167 pattern
        if code_hex.startswith("363d3d373d3d3d363d73") and code_hex.endswith(
            "5af43d82803e903d91602b57fd5bf3"
        ):
            # Extract implementation address (20 bytes after prefix)
            impl_hex = code_hex[20:60]  # 20 chars prefix, 40 chars address
            impl = "0x" + impl_hex
            if impl != ZERO_ADDRESS:
                return Web3.to_checksum_address(impl)

        return None
