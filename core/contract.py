"""Web3 contract interaction helpers."""

import json
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

from web3 import Web3
from web3.contract import Contract
from eth_abi import decode

from config import ZERO_ADDRESS, PROXY_SLOTS


class ContractHelper:
    """Helper class for contract interactions."""

    def __init__(self, web3: Web3):
        self.web3 = web3
        self.abis: Dict[str, List] = {}
        self._load_abis()

    def _load_abis(self):
        """Load all ABI files from the abis directory."""
        abis_dir = Path(__file__).parent.parent / "abis"
        for abi_file in abis_dir.glob("*.json"):
            name = abi_file.stem
            with open(abi_file) as f:
                self.abis[name] = json.load(f)

    def get_contract(self, address: str, abi_name: str) -> Contract:
        """Get a contract instance.

        Args:
            address: Contract address
            abi_name: Name of the ABI file (without .json)

        Returns:
            Web3 Contract instance
        """
        if abi_name not in self.abis:
            raise ValueError(f"ABI not found: {abi_name}")

        return self.web3.eth.contract(
            address=Web3.to_checksum_address(address),
            abi=self.abis[abi_name],
        )

    def call_safe(
        self,
        address: str,
        function_sig: str,
        args: Optional[List] = None,
        abi_name: Optional[str] = None,
    ) -> Optional[Any]:
        """Safely call a contract function, returning None on failure.

        Args:
            address: Contract address
            function_sig: Function signature (e.g., "owner()" or "balanceOf(address)")
            args: Optional function arguments
            abi_name: Optional ABI name for typed calls

        Returns:
            Function result or None if call fails
        """
        try:
            if abi_name and abi_name in self.abis:
                contract = self.get_contract(address, abi_name)
                func_name = function_sig.split("(")[0]
                func = getattr(contract.functions, func_name)
                if args:
                    return func(*args).call()
                return func().call()
            else:
                # Raw call using function selector
                return self._raw_call(address, function_sig, args)
        except Exception:
            return None

    def _raw_call(
        self,
        address: str,
        function_sig: str,
        args: Optional[List] = None,
    ) -> Optional[Any]:
        """Make a raw eth_call.

        Args:
            address: Contract address
            function_sig: Function signature
            args: Optional arguments

        Returns:
            Decoded result or None
        """
        # Build calldata
        selector = Web3.keccak(text=function_sig)[:4]
        data = selector

        if args:
            from eth_abi import encode
            # Extract types from signature
            types = function_sig.split("(")[1].rstrip(")").split(",")
            types = [t.strip() for t in types if t.strip()]
            if types:
                data += encode(types, args)

        try:
            result = self.web3.eth.call({
                "to": Web3.to_checksum_address(address),
                "data": data.hex() if isinstance(data, bytes) else data,
            })

            if result and result != b"" and result != "0x":
                return result
            return None
        except Exception:
            return None

    def get_code(self, address: str) -> bytes:
        """Get contract bytecode.

        Args:
            address: Contract address

        Returns:
            Contract bytecode
        """
        return self.web3.eth.get_code(Web3.to_checksum_address(address))

    def get_storage_at(self, address: str, slot: Union[str, int]) -> bytes:
        """Read storage at a specific slot.

        Args:
            address: Contract address
            slot: Storage slot (hex string or int)

        Returns:
            Storage value
        """
        if isinstance(slot, str):
            slot = int(slot, 16)
        return self.web3.eth.get_storage_at(
            Web3.to_checksum_address(address),
            slot,
        )

    def is_contract(self, address: str) -> bool:
        """Check if an address is a contract.

        Args:
            address: Address to check

        Returns:
            True if contract, False if EOA
        """
        code = self.get_code(address)
        return len(code) > 0

    def get_proxy_implementation(self, address: str) -> Optional[str]:
        """Get the implementation address if contract is a proxy.

        Args:
            address: Proxy contract address

        Returns:
            Implementation address or None if not a proxy
        """
        # Try EIP-1967 implementation slot
        impl_slot = self.get_storage_at(address, PROXY_SLOTS["implementation"])
        if impl_slot and impl_slot != b"\x00" * 32:
            impl_address = "0x" + impl_slot[-20:].hex()
            if impl_address != ZERO_ADDRESS:
                return Web3.to_checksum_address(impl_address)

        # Try calling implementation() function
        impl = self.call_safe(address, "implementation()")
        if impl and isinstance(impl, bytes) and len(impl) >= 20:
            impl_address = "0x" + impl[-20:].hex()
            if impl_address != ZERO_ADDRESS:
                return Web3.to_checksum_address(impl_address)

        return None

    def decode_address(self, data: bytes) -> Optional[str]:
        """Decode an address from bytes.

        Args:
            data: Bytes containing address

        Returns:
            Checksummed address or None
        """
        if not data or len(data) < 20:
            return None
        try:
            # Address is right-padded in 32 bytes
            address = "0x" + data[-20:].hex()
            if address == ZERO_ADDRESS:
                return ZERO_ADDRESS
            return Web3.to_checksum_address(address)
        except Exception:
            return None

    def decode_uint256(self, data: bytes) -> Optional[int]:
        """Decode a uint256 from bytes.

        Args:
            data: Bytes containing uint256

        Returns:
            Integer value or None
        """
        if not data or len(data) < 32:
            return None
        try:
            return int.from_bytes(data[:32], "big")
        except Exception:
            return None

    def decode_string(self, data: bytes) -> Optional[str]:
        """Decode a string from bytes.

        Args:
            data: Bytes containing encoded string

        Returns:
            Decoded string or None
        """
        if not data or len(data) < 64:
            return None
        try:
            decoded = decode(["string"], data)
            return decoded[0]
        except Exception:
            return None

    def decode_bool(self, data: bytes) -> Optional[bool]:
        """Decode a bool from bytes.

        Args:
            data: Bytes containing bool

        Returns:
            Boolean value or None
        """
        if not data:
            return None
        try:
            return int.from_bytes(data[-32:], "big") != 0
        except Exception:
            return None
