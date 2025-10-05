# VoidBloom Data Oracle - Autotrader

**Phase 1–2 Pipeline Implementation**

This repository contains the foundational skeleton for the VoidBloom Data Oracle, a sophisticated cryptocurrency analysis system that combines multi-source data ingestion, sentiment synthesis, technical intelligence, and contract security analysis.

## 📁 Repository Structure

```
.
├── ARCHITECTURE.md      # Mermaid architecture diagram and system overview
├── main.py             # Python pipeline skeleton (Phase 1-2)
├── main.ts             # TypeScript pipeline skeleton (Phase 1-2)
├── tsconfig.json       # TypeScript configuration
├── .gitignore          # Git ignore patterns
└── README.md           # This file
```

## 🏗️ Architecture Overview

The system is built on six core layers:

1. **Data Infusion Layer** - Multi-source data ingestion (News, Social, On-chain, Technical)
2. **Sentiment Synthesis Layer** - NVI, Meme Momentum, Archetypal Analysis
3. **Technical Intelligence Layer** - Indicators, Signals, Hype Validation
4. **Contract & Security Layer** - Risk Assessment, Audit Verification
5. **Signal Fusion Matrix** - Composite Scoring Algorithm
6. **Visualization/Dashboard** - Output Layer (Future Phase)

See [ARCHITECTURE.md](ARCHITECTURE.md) for the detailed architecture diagram and component descriptions.

## 🚀 Getting Started

### Python Implementation

The Python skeleton (`main.py`) provides the core pipeline structure:

```bash
# Install dependencies (when ready to implement)
pip install sqlite3 requests chromadb openai

# Run the pipeline
python main.py
```

### TypeScript Implementation

The TypeScript skeleton (`main.ts`) provides an async/await-based pipeline:

```bash
# Install dependencies (when ready to implement)
npm install @supabase/supabase-js axios

# Compile and run
tsc
node main.js
```

## 📊 Key Metrics & Scores

### Sentiment Metrics
- **NVI (Narrative Volatility Index)**: GPT-powered sentiment scoring
- **MMS (Meme Momentum Score)**: Viral content and hype cycle tracking
- **Myth Vectors**: Archetypal narrative patterns

### Technical Metrics
- **APS (Archetype Precision Score)**: Technical indicator precision (0.0-1.0)
- **RSS (Rally Strength Score)**: Momentum and volume analysis (0.0-1.0)
- **RRR (Risk-Reward Ratio)**: Position sizing and risk assessment

### Security Metrics
- **ERR (Exploit Risk Rating)**: Smart contract vulnerability score (0.0-1.0)
- **OCW (On-Chain Wealth)**: Holder distribution analysis (boolean)
- **ACI (Audit Confidence Index)**: Third-party audit verification (0.0-1.0)

## 🔧 Composite Scoring Formula

```
Final Score = (0.4 × APS) + (0.3 × NVI) + (0.2 × ERR⁻¹) + (0.1 × RRR)
```

## 📝 Implementation Status

### Phase 1 - Data Ingestion ✅
- [x] Architecture design
- [x] Python skeleton
- [x] TypeScript skeleton
- [ ] API integrations (placeholder functions)
- [ ] Database setup

### Phase 2 - Sentiment & Analysis ✅
- [x] Sentiment synthesis structure
- [x] Technical analysis framework
- [x] Contract security framework
- [ ] GPT chain implementation
- [ ] Indicator calculations

### Phase 3 - Signal Fusion 🔄
- [x] Fusion algorithm structure
- [ ] Composite scoring implementation
- [ ] Optimization and tuning

### Phase 4 - Visualization (Future)
- [ ] Dashboard development
- [ ] Lore Capsules
- [ ] Real-time monitoring

## 🗄️ Data Sources

### News APIs
- Cointelegraph
- The Block
- Decrypt

### Social Platforms
- Twitter/X
- Reddit
- Telegram
- Discord

### On-Chain Data
- Etherscan
- DefiLlama
- Nansen
- Token Terminal

### Technical Data
- TradingView API
- Custom indicators

## 💾 Storage Solutions

- **SQLite/Supabase**: Structured data persistence
- **Chroma/Pinecone**: Vector database for embeddings and semantic search

## 🛠️ Development

### Prerequisites
- Python 3.8+
- Node.js 16+
- TypeScript 4.5+

### Code Style
- Python: Follow PEP 8
- TypeScript: ESLint configuration included

### Testing
```bash
# Python syntax check
python3 -m py_compile main.py

# TypeScript type check
tsc --noEmit
```

## 📄 License

This project is part of the CrisisCore-Systems Autotrader initiative.

## 🤝 Contributing

This is a foundational skeleton ready for implementation. Key areas for contribution:
1. API integrations for data sources
2. GPT chain implementation for sentiment analysis
3. Technical indicator calculations
4. Smart contract security scanning
5. Database schema and optimization

## 📞 Contact

For questions or contributions, please open an issue or submit a pull request.

---

**Status**: ✅ Phase 1-2 skeleton complete and ready for PR review
