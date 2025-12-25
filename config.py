"""
Configuration settings for EVM Analyzer.

This file contains chain configurations, DEX addresses, and security check parameters.
To add a new chain or DEX, simply extend the relevant dictionaries below.
"""

from dataclasses import dataclass
from typing import Dict, List


@dataclass
class ChainConfig:
    """Configuration for a blockchain network."""
    name: str
    chain_id: int
    rpc_urls: List[str]
    wrapped_native: str
    stablecoins: List[str]
    block_explorer: str

    @property
    def rpc_url(self) -> str:
        return self.rpc_urls[0]


# =============================================================================
# CHAIN CONFIGURATIONS
# =============================================================================
# Add your RPC endpoints here. The first URL in the list is used by default.
# For historical/archive queries, you need an archive-enabled RPC.

CHAINS: Dict[str, ChainConfig] = {
    "ethereum": ChainConfig(
        name="Ethereum Mainnet",
        chain_id=1,
        rpc_urls=[
            "https://eth-mainnet.g.alchemy.com/v2/your_api_key_here",
            "https://eth.llamarpc.com",
            "https://rpc.ankr.com/eth",
            "https://ethereum.publicnode.com",
        ],
        wrapped_native="0xC02aaA39b223FE8D0A0e5C4F27eAD9083C756Cc2",
        stablecoins=[
            "0xA0b86991c6218b36c1d19D4a2e9Eb0cE3606eB48",
            "0xdAC17F958D2ee523a2206206994597C13D831ec7",
            "0x6B175474E89094C44Da98b954EedeAC495271d0F",
        ],
        block_explorer="https://etherscan.io",
    ),
    "bsc": ChainConfig(
        name="BNB Smart Chain",
        chain_id=56,
        rpc_urls=[
            # For BSC archive queries, get a free API key from NodeReal:
            # https://nodereal.io/api-marketplace/bsc-rpc
            "https://bsc-mainnet.nodereal.io/v1/YOUR_API_KEY_HERE",
            "https://bsc-dataseed.bnbchain.org",
            "https://bsc-dataseed1.defibit.io",
            "https://rpc.ankr.com/bsc",
            "https://bsc.publicnode.com",
        ],
        wrapped_native="0xbb4CdB9CBd36B01bD1cBaEBF2De08d9173bc095c",
        stablecoins=[
            "0x8AC76a51cc950d9822D68b83fE1Ad97B32Cd580d",
            "0x55d398326f99059fF775485246999027B3197955",
            "0x1AF3F329e8BE154074D8769D1FFa4eE058B1DBc3",
        ],
        block_explorer="https://bscscan.com",
    ),
}


# =============================================================================
# DEX CONFIGURATIONS
# =============================================================================
# Factory and router addresses for supported DEXes on each chain.

DEX_FACTORIES: Dict[str, Dict[str, Dict[str, str]]] = {
    "ethereum": {
        "uniswap_v2": {
            "factory": "0x5C69bEe701ef814a2B6a3EDD4B1652CB9cc5aA6f",
            "router": "0x7a250d5630B4cF539739dF2C5dAcb4c659F2488D",
        },
        "uniswap_v3": {
            "factory": "0x1F98431c8aD98523631AE4a59f267346ea31F984",
            "quoter": "0xb27308f9F90D607463bb33eA1BeBb41C27CE5AB6",
        },
        "sushiswap": {
            "factory": "0xC0AEe478e3658e2610c5F7A4A2E1777cE9e4f2Ac",
            "router": "0xd9e1cE17f2641f24aE83637ab66a2cca9C378B9F",
        },
        "curve": {
            "registry": "0x90E00ACe148ca3b23Ac1bC8C240C2a7Dd9c2d7f5",
            "factory": "0xB9fC157394Af804a3578134A6585C0dc9cc990d4",
        },
        "balancer": {
            "vault": "0xBA12222222228d8Ba445958a75a0704d566BF2C8",
        },
    },
    "bsc": {
        "pancakeswap_v2": {
            "factory": "0xcA143Ce32Fe78f1f7019d7d551a6402fC5350c73",
            "router": "0x10ED43C718714eb63d5aA57B78B54704E256024E",
        },
        "pancakeswap_v3": {
            "factory": "0x0BFbCF9fa4f9C56B0F40a671Ad40E0805A091865",
            "quoter": "0xB048Bbc1Ee6b733FFfCFb9e9CeF7375518e25997",
        },
        "biswap": {
            "factory": "0x858E3312ed3A876947EA49d572A7C42DE08af7EE",
            "router": "0x3a6d8cA21D1CF76F653A67577FA0D27453350dD8",
        },
        "mdex": {
            "factory": "0x3CD1C46068dAEa5Ebb0d3f55F6915B10648062B8",
            "router": "0x7DAe51BD3E3376B8c7c4900E9107f12Be3AF1bA8",
        },
        "apeswap": {
            "factory": "0x0841BD0B734E4F5853f0dD8d7Ea041c241fb0Da6",
            "router": "0xcF0feBd3f17CEf5b47b0cD257aCf6025c5BFf3b7",
        },
    },
}


# =============================================================================
# SECURITY CHECK PARAMETERS
# =============================================================================

SECURITY_SELECTORS = {
    "owner": "0x8da5cb5b",
    "getOwner": "0x893d20e8",
    "admin": "0xf851a440",
    "paused": "0x5c975abb",
    "isPaused": "0xb187bd26",
    "hasRole": "0x91d14854",
    "getRoleAdmin": "0x248a9ca3",
    "DEFAULT_ADMIN_ROLE": "0xa217fddf",
    "MINTER_ROLE": "0xd5391393",
    "PAUSER_ROLE": "0xe63ab1e9",
    "isBlacklisted": "0xfe575a87",
    "isExcluded": "0xcba0e996",
    "mint": "0x40c10f19",
    "burn": "0x42966c68",
}

PROXY_SLOTS = {
    "implementation": "0x360894a13ba1a3210667c828492db98dca3e2076cc3735a920a3ca505d382bbc",
    "admin": "0xb53127684a568b3173ae13b9f8a6016e243e63b6e8ee1178d6a717850b5d6103",
    "beacon": "0xa3f0ad74e5423aebfd80d3ef4346578335a9a72aeaee59ff6cb3582b35133d50",
}

ZERO_ADDRESS = "0x0000000000000000000000000000000000000000"

ANVIL_CONFIG = {
    "port": 8545,
    "host": "127.0.0.1",
    "accounts": 10,
    "balance": 10000,
}
