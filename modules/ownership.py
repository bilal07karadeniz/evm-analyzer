"""Ownership and access control analysis module."""

from dataclasses import dataclass, field
from typing import Optional, List

from web3 import Web3

from core.contract import ContractHelper
from config import ZERO_ADDRESS


@dataclass
class OwnershipInfo:
    """Ownership and access control information."""
    owner: Optional[str] = None
    owner_is_contract: Optional[bool] = None
    owner_is_renounced: bool = False
    paused: Optional[bool] = None
    has_mint: bool = False
    has_burn: bool = False
    has_blacklist: bool = False
    roles_detected: List[str] = field(default_factory=list)


class OwnershipAnalyzer:
    """Analyzes ownership and access control."""

    # Known role hashes
    ROLE_HASHES = {
        "0x0000000000000000000000000000000000000000000000000000000000000000": "DEFAULT_ADMIN",
        "0x9f2df0fed2c77648de5860a4cc508cd0818c85b8b8a1ab4ceeef8d981c8956a6": "MINTER",
        "0x65d7a28e3265b37a6474929f336521b332c1681b933f6cb9f3376673440d862a": "PAUSER",
        "0x3c11d16cbaffd01df69ce1c404f6340ee057498f5f00246190ea54220576a848": "UPGRADER",
    }

    def __init__(self, web3: Web3):
        self.web3 = web3
        self.helper = ContractHelper(web3)

    def analyze(self, contract_address: str) -> OwnershipInfo:
        """Analyze ownership and access control.

        Args:
            contract_address: Contract address to analyze

        Returns:
            OwnershipInfo object
        """
        contract_address = Web3.to_checksum_address(contract_address)
        info = OwnershipInfo()

        # Check owner
        owner = self._get_owner(contract_address)
        if owner:
            info.owner = owner
            info.owner_is_renounced = owner == ZERO_ADDRESS
            if not info.owner_is_renounced:
                info.owner_is_contract = self.helper.is_contract(owner)

        # Check paused status
        info.paused = self._check_paused(contract_address)

        # Check for mint/burn functions
        info.has_mint = self._has_function(contract_address, "mint(address,uint256)")
        info.has_burn = self._has_function(contract_address, "burn(uint256)")

        # Check for blacklist
        info.has_blacklist = self._has_blacklist(contract_address)

        # Check for AccessControl roles
        info.roles_detected = self._detect_roles(contract_address)

        return info

    def _get_owner(self, address: str) -> Optional[str]:
        """Get owner address trying multiple methods."""
        # Try owner()
        result = self.helper.call_safe(address, "owner()")
        if result:
            decoded = self.helper.decode_address(result)
            if decoded:
                return decoded

        # Try getOwner()
        result = self.helper.call_safe(address, "getOwner()")
        if result:
            decoded = self.helper.decode_address(result)
            if decoded:
                return decoded

        # Try admin()
        result = self.helper.call_safe(address, "admin()")
        if result:
            decoded = self.helper.decode_address(result)
            if decoded:
                return decoded

        return None

    def _check_paused(self, address: str) -> Optional[bool]:
        """Check if contract is paused."""
        result = self.helper.call_safe(address, "paused()")
        if result:
            return self.helper.decode_bool(result)

        result = self.helper.call_safe(address, "isPaused()")
        if result:
            return self.helper.decode_bool(result)

        return None

    def _has_function(self, address: str, signature: str) -> bool:
        """Check if contract has a specific function by checking bytecode for selector."""
        code = self.helper.get_code(address)
        if not code:
            return False

        selector = Web3.keccak(text=signature)[:4].hex()
        return selector in code.hex()

    def _has_blacklist(self, address: str) -> bool:
        """Check if contract has blacklist functionality."""
        # Check for common blacklist function signatures
        signatures = [
            "isBlacklisted(address)",
            "isBlackListed(address)",
            "blacklist(address)",
            "isExcluded(address)",
            "_isExcludedFromFee(address)",
        ]

        for sig in signatures:
            if self._has_function(address, sig):
                return True

        return False

    def _detect_roles(self, address: str) -> List[str]:
        """Detect AccessControl roles."""
        roles = []

        # Check if contract supports AccessControl
        if not self._has_function(address, "hasRole(bytes32,address)"):
            return roles

        # Check for common roles
        for role_hash, role_name in self.ROLE_HASHES.items():
            result = self.helper.call_safe(
                address,
                "getRoleAdmin(bytes32)",
                [bytes.fromhex(role_hash[2:])],
            )
            if result:
                roles.append(role_name)

        return roles
