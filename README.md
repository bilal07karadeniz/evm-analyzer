# EVM Analyzer

A command-line tool for gathering smart contract security data from EVM-compatible blockchains. Analyzes token contracts to extract ownership information, liquidity pools, and security flags using an Anvil fork.

## Features

- **Token Analysis**: Name, symbol, decimals, total supply
- **Ownership Detection**: Owner address, renounced status, access control roles
- **Security Flags**: Transfer fees, max TX limits, blacklist detection, pause status
- **Liquidity Discovery**: Top 5 pools across multiple DEXes with USD values
- **Proxy Detection**: EIP-1967, Beacon, and Transparent proxy patterns
- **Historical Analysis**: Query contract state at any past block
- **Multi-chain Support**: Ethereum and BSC (easily extensible)

## Supported DEXes

**Ethereum:**
- Uniswap V2 & V3
- SushiSwap
- Curve
- Balancer

**BSC:**
- PancakeSwap V2 & V3
- BiSwap
- MDEX
- ApeSwap

## Requirements

- Python 3.8+
- [Foundry](https://book.getfoundry.sh/getting-started/installation) (for Anvil)

## Installation

```bash
# Clone the repository
git clone <repository-url>
cd evm_analyzer

# Install dependencies
pip install requirements

# Install Foundry (if not installed)
curl -L https://foundry.paradigm.xyz | bash
foundryup
```

## Configuration

Edit `config.py` to add your RPC endpoints:

```python
# Ethereum - Get free key from Alchemy
"https://eth-mainnet.g.alchemy.com/v2/YOUR_ALCHEMY_KEY"

# BSC - Get free key from NodeReal (required for historical queries)
"https://bsc-mainnet.nodereal.io/v1/YOUR_NODEREAL_KEY"
```

**RPC Providers:**
- Ethereum: [Alchemy](https://www.alchemy.com/) (free tier includes archive)
- BSC: [NodeReal](https://nodereal.io/api-marketplace/bsc-rpc) (free tier, 100M requests/month)

## Usage

### Basic Commands

```bash
# Analyze token on Ethereum (default chain)
python gatherer.py 0x6982508145454Ce325dDbE47a25d4ec3d2311933

# Analyze token on BSC
python gatherer.py 0x0E09FaBB73Bd3Ade0a17ECC321fD13a19e81cE82 bsc

# Save report to file
python gatherer.py 0x6982508145454Ce325dDbE47a25d4ec3d2311933 -o report.md

# Query historical state at specific block
python gatherer.py 0x6982508145454Ce325dDbE47a25d4ec3d2311933 -b 18000000

# Historical report + Save File
python gatherer.py 0xc748673057861a797275CD8A068AbB95A902e8de bsc -b 22580541 -o babydogehist.md

# Use custom RPC
python gatherer.py 0x... -r "https://your-rpc-url.com"
```

### Chain Shortcuts

```bash
python gatherer.py 0x... eth      # Ethereum
python gatherer.py 0x... bsc      # BSC
python gatherer.py 0x... bnb      # BSC (alias)
```

### CLI Options

| Option | Description |
|--------|-------------|
| `address` | Token contract address (required) |
| `chain` | Chain: ethereum/eth, bsc/bnb (default: ethereum) |
| `-b, --block` | Fork from specific block number |
| `-o, --output` | Save report to file |
| `-r, --rpc` | Custom RPC URL |
| `-p, --port` | Anvil port (default: 8545) |
| `--anvil-url` | Connect to existing Anvil instance |

## Starting Anvil Manually

If you prefer to manage Anvil yourself:

```bash
# Ethereum
anvil --fork-url https://eth-mainnet.g.alchemy.com/v2/YOUR_KEY --port 8545

# BSC
anvil --fork-url https://bsc-dataseed.bnbchain.org --port 8546 --chain-id 56
```

The tool auto-detects running Anvil instances by matching chain ID.

## Example Output

```markdown
# PEPE Analysis
**Address:** `0x6982508145454Ce325dDbE47a25d4ec3d2311933`
**Chain:** ethereum

## Token Info
- Name: Pepe
- Symbol: PEPE
- Decimals: 18
- Supply: 420.69T

## Ownership
- Owner: `0x0000000000000000000000000000000000000000` (renounced)
- Has burn()

## Liquidity (Top 5)

| DEX | Pair | Liquidity |
|-----|------|-----------|
| Uniswap V3 (0.30%) | PEPE/WETH | $82.04M |
| Uniswap V2 | PEPE/WETH | $9.47M |
| Uniswap V3 (1.00%) | PEPE/WETH | $344.78K |
```

## Test Addresses

**Ethereum:**
```bash
# PEPE - Meme token, renounced
python gatherer.py 0x6982508145454Ce325dDbE47a25d4ec3d2311933

# USDC - Stablecoin, proxy contract
python gatherer.py 0xA0b86991c6218b36c1d19D4a2e9Eb0cE3606eB48

# UNI - Governance token
python gatherer.py 0x1f9840a85d5aF5bf1D1762F925BDADdC4201F984

# SHIB - Large supply meme token
python gatherer.py 0x95aD61b0a150d79219dCF64E1E6Cc01f0B64C4cE
```

**BSC:**
```bash
# CAKE - PancakeSwap token
python gatherer.py 0x0E09FaBB73Bd3Ade0a17ECC321fD13a19e81cE82 bsc

# BabyDoge - Meme token
python gatherer.py 0xc748673057861a797275CD8A068AbB95A902e8de bsc

# BUSD - Stablecoin
python gatherer.py 0xe9e7CEA3DedcA5984780Bafc599bD69ADd087D56 bsc
```

## Project Structure

```
evm_analyzer/
├── gatherer.py          # Main CLI entry point
├── config.py            # Chain and DEX configurations
├── core/
│   ├── anvil.py         # Anvil fork management
│   └── contract.py      # Web3 contract helpers
├── modules/
│   ├── token.py         # Token analysis
│   ├── ownership.py     # Ownership detection
│   ├── proxy.py         # Proxy detection
│   └── security.py      # Security checks
├── dexes/
│   ├── base.py          # DEX adapter interface
│   ├── registry.py      # DEX auto-discovery
│   ├── uniswap_v2.py    # V2 forks adapter
│   ├── uniswap_v3.py    # V3 adapter
│   ├── curve.py         # Curve adapter
│   └── balancer.py      # Balancer adapter
└── output/
    └── markdown.py      # Report generator
```

## Adding New Chains

1. Add chain config to `config.py`:
```python
"arbitrum": ChainConfig(
    name="Arbitrum One",
    chain_id=42161,
    rpc_urls=["https://arb1.arbitrum.io/rpc"],
    wrapped_native="0x82aF49447D8a07e3bd95BD0d56f35241523fBab1",
    stablecoins=[...],
    block_explorer="https://arbiscan.io",
),
```

2. Add DEX factories for the chain in `DEX_FACTORIES`.

## Adding New DEXes

Create a new adapter in `dexes/` following the base interface:

```python
from dexes.base import DEXAdapter, Pool

class MyDEXAdapter(DEXAdapter):
    name = "MyDEX"
    supported_chains = ["ethereum"]

    def get_pools(self, web3, chain, token_address):
        # Return list of Pool objects
        ...
```

The adapter is auto-discovered and registered.

## License

MIT
