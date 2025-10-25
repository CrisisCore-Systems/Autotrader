# AutoTrader System Diagrams

This document contains visual representations of the AutoTrader system architecture.

## System Overview

```mermaid
graph TB
    subgraph "USER INTERFACES"
        CLI[CLI Tools]
        API[FastAPI Server]
        UI[Dashboard UI]
        JN[Jupyter Notebooks]
    end
    
    subgraph "TRADING STRATEGIES"
        HGS[Hidden-Gem Scanner<br/>Crypto Intelligence]
        BH[BounceHunter<br/>Gap Trading]
    end
    
    subgraph "INTELLIGENCE LAYER"
        FS[Feature Store<br/>127 Features]
        AG[8 AI Agents]
        SE[Scoring Engine<br/>GemScore]
        RG[Risk Gates<br/>5 Filters]
    end
    
    subgraph "DATA SOURCES (FREE)"
        CG[CoinGecko]
        DS[Dexscreener]
        BC[Blockscout]
        ER[Ethereum RPC]
        GA[Groq AI]
    end
    
    subgraph "DATA SOURCES (PAID)"
        ES[Etherscan]
        DL[DefiLlama]
        AL[Alpaca]
    end
    
    subgraph "BROKER LAYER"
        PB[Paper Broker]
        AB[Alpaca Broker]
        QB[Questrade]
        IB[Interactive Brokers]
    end
    
    subgraph "INFRASTRUCTURE"
        LOG[Logging<br/>structlog]
        MET[Metrics<br/>Prometheus]
        TRC[Tracing<br/>OpenTelemetry]
        SEC[Security<br/>Scanning]
    end
    
    CLI --> HGS
    CLI --> BH
    API --> HGS
    API --> BH
    UI --> API
    JN --> HGS
    
    HGS --> FS
    HGS --> SE
    BH --> FS
    BH --> AG
    BH --> RG
    
    FS --> CG
    FS --> DS
    FS --> BC
    FS --> ER
    FS --> GA
    FS -.-> ES
    FS -.-> DL
    
    AG --> SE
    SE --> RG
    
    BH --> PB
    BH --> AB
    BH --> QB
    BH --> IB
    
    HGS --> LOG
    BH --> LOG
    HGS --> MET
    BH --> MET
    HGS --> TRC
    BH --> TRC
    
    LOG --> SEC
    MET --> SEC
```

## Hidden-Gem Scanner Flow

```mermaid
flowchart TD
    Start([Token Address]) --> Ingest[Data Ingestion]
    
    Ingest --> Price[Price & Volume<br/>CoinGecko, Dexscreener]
    Ingest --> Chain[On-Chain Metrics<br/>Ethereum RPC, Blockscout]
    Ingest --> Social[Social Sentiment<br/>Twitter, Reddit]
    Ingest --> Contract[Contract Safety<br/>Slither, Static Analysis]
    
    Price --> Features[Feature Extraction<br/>127 Features]
    Chain --> Features
    Social --> Features
    Contract --> Features
    
    Features --> Valid{Feature<br/>Validation}
    Valid -->|Fail| Log1[Log Warning]
    Valid -->|Pass| Score[GemScore Calculation<br/>Weighted Ensemble]
    
    Score --> Safety{Safety<br/>Gate}
    Safety -->|Blocked| Reject[Reject: High Risk]
    Safety -->|Pass| Confidence[Confidence Score]
    
    Confidence --> Output[Ranked Output]
    Output --> Dashboard[Dashboard Display]
    Output --> Alert[Alert if Score > Threshold]
    Output --> Artifact[Collapse Artifact<br/>Report Generation]
    
    Log1 --> Monitor[Monitoring System]
    Reject --> Monitor
    Alert --> Monitor
    
    style Start fill:#e1f5ff
    style Output fill:#d4edda
    style Reject fill:#f8d7da
    style Safety fill:#fff3cd
```

## BounceHunter Trading Flow

```mermaid
flowchart TD
    Start([Market Open]) --> Regime[Market Regime Check<br/>SPY/VIX Analysis]
    
    Regime --> RegimeOK{Favorable<br/>Regime?}
    RegimeOK -->|No| Stop1([Stop: Market Unfavorable])
    RegimeOK -->|Yes| Scan[Gap Scanner<br/>Detect Overnight Gaps]
    
    Scan --> Agents[8 AI Agents Analyze]
    
    Agents --> Sentinel[Sentinel: Regime Confirm]
    Agents --> Screener[Screener: Technical Filter]
    Agents --> Forecaster[Forecaster: Probability Model]
    Agents --> Risk[RiskOfficer: 5 Risk Filters]
    Agents --> News[NewsSentry: News Check]
    
    Sentinel --> Consensus{Agent<br/>Consensus}
    Screener --> Consensus
    Forecaster --> Consensus
    Risk --> Consensus
    News --> Consensus
    
    Consensus -->|Reject| Log2[Log Signal Rejection]
    Consensus -->|Approve| Filters[Advanced Filters]
    
    Filters --> Liquidity[Liquidity Delta Check]
    Filters --> Slippage[Slippage Estimation]
    Filters --> Runway[Cash Runway Validation]
    Filters --> Sector[Sector Diversification]
    Filters --> Volume[Volume Fade Detection]
    
    Liquidity --> FiltersOK{All Filters<br/>Pass?}
    Slippage --> FiltersOK
    Runway --> FiltersOK
    Sector --> FiltersOK
    Volume --> FiltersOK
    
    FiltersOK -->|Fail| Log2
    FiltersOK -->|Pass| Quality{Quality<br/>Score > 5.5?}
    
    Quality -->|No| Log2
    Quality -->|Yes| Execute[Trader: Execute Order]
    
    Execute --> Bracket[Bracket Order<br/>Entry + Stop + Target]
    Bracket --> Monitor[Historian: Track Position]
    
    Monitor --> Outcome{Trade<br/>Outcome}
    Outcome -->|Win| Journal1[Journal: Record Win]
    Outcome -->|Loss| Journal1[Journal: Record Loss]
    
    Journal1 --> Audit[Auditor: Post-Trade Analysis]
    Audit --> Memory[(Agent Memory<br/>SQLite DB)]
    
    Log2 --> Memory
    
    style Start fill:#e1f5ff
    style Execute fill:#d4edda
    style Stop1 fill:#f8d7da
    style Quality fill:#fff3cd
    style Memory fill:#cfe2ff
```

## Feature Store Architecture

```mermaid
graph TB
    subgraph "Data Ingestion"
        Source1[Market Data APIs]
        Source2[On-Chain APIs]
        Source3[Social APIs]
        Source4[News APIs]
    end
    
    subgraph "Feature Store Core"
        Ingest[Ingestion Layer<br/>Normalization]
        Valid[Validation Layer<br/>Data Contracts]
        Store[Storage Layer<br/>SQLite/PostgreSQL]
        Cache[Cache Layer<br/>Redis/Memory]
    end
    
    subgraph "Feature Categories"
        Market[Market Features<br/>15 features]
        Liquidity[Liquidity Features<br/>12 features]
        Flow[Order Flow Features<br/>18 features]
        Deriv[Derivatives Features<br/>10 features]
        Sentiment[Sentiment Features<br/>14 features]
        Chain[On-Chain Features<br/>16 features]
        Tech[Technical Features<br/>22 features]
        Quality[Quality Features<br/>8 features]
        Score[Scoring Features<br/>12 features]
    end
    
    subgraph "Consumers"
        Scanner[Hidden-Gem Scanner]
        BH[BounceHunter]
        Backtest[Backtesting Engine]
        API[API Server]
    end
    
    Source1 --> Ingest
    Source2 --> Ingest
    Source3 --> Ingest
    Source4 --> Ingest
    
    Ingest --> Valid
    Valid --> Store
    Valid --> Cache
    
    Store --> Market
    Store --> Liquidity
    Store --> Flow
    Store --> Deriv
    Store --> Sentiment
    Store --> Chain
    Store --> Tech
    Store --> Quality
    Store --> Score
    
    Cache --> Market
    Cache --> Liquidity
    Cache --> Flow
    
    Market --> Scanner
    Liquidity --> Scanner
    Flow --> Scanner
    Sentiment --> Scanner
    Chain --> Scanner
    
    Market --> BH
    Tech --> BH
    Quality --> BH
    
    Market --> Backtest
    Liquidity --> Backtest
    Tech --> Backtest
    
    Scanner --> API
    BH --> API
    Backtest --> API
    
    style Store fill:#cfe2ff
    style Cache fill:#fff3cd
    style Scanner fill:#d4edda
    style BH fill:#d4edda
```

## Observability Stack

```mermaid
graph LR
    subgraph "Application Layer"
        App1[Hidden-Gem Scanner]
        App2[BounceHunter]
        App3[API Server]
        App4[Data Clients]
    end
    
    subgraph "Observability Layer"
        Log[Structured Logging<br/>structlog + JSON]
        Metric[Metrics Collection<br/>Prometheus Client]
        Trace[Distributed Tracing<br/>OpenTelemetry]
        Prov[Provenance Tracking<br/>Data Lineage]
    end
    
    subgraph "Collection & Storage"
        LogStore[(Log Storage<br/>ELK/Loki)]
        MetricStore[(Metrics DB<br/>Prometheus)]
        TraceStore[(Trace Backend<br/>Jaeger/Zipkin)]
        ProvStore[(Lineage DB<br/>SQLite)]
    end
    
    subgraph "Visualization"
        LogUI[Log Explorer<br/>Kibana/Grafana]
        Dashboard[Metrics Dashboard<br/>Grafana]
        TraceUI[Trace Viewer<br/>Jaeger UI]
        Lineage[Lineage Diagrams<br/>Mermaid]
    end
    
    subgraph "Alerting"
        Alert[Alert Manager<br/>Prometheus]
        Notify[Notifications<br/>Telegram/Slack]
    end
    
    App1 --> Log
    App1 --> Metric
    App1 --> Trace
    App1 --> Prov
    
    App2 --> Log
    App2 --> Metric
    App2 --> Trace
    App2 --> Prov
    
    App3 --> Log
    App3 --> Metric
    App3 --> Trace
    
    App4 --> Log
    App4 --> Metric
    App4 --> Trace
    
    Log --> LogStore
    Metric --> MetricStore
    Trace --> TraceStore
    Prov --> ProvStore
    
    LogStore --> LogUI
    MetricStore --> Dashboard
    TraceStore --> TraceUI
    ProvStore --> Lineage
    
    MetricStore --> Alert
    Alert --> Notify
    
    style Log fill:#fff3cd
    style Metric fill:#fff3cd
    style Trace fill:#fff3cd
    style Dashboard fill:#d4edda
```

## Security Architecture

```mermaid
flowchart TD
    subgraph "Development"
        Code[Source Code] --> PreCommit[Pre-Commit Hooks<br/>Secret Detection]
        PreCommit --> Commit[Git Commit]
    end
    
    subgraph "CI Pipeline"
        Commit --> GH[GitHub Push]
        GH --> Lint[Linting<br/>black, isort, flake8]
        Lint --> Type[Type Checking<br/>mypy]
        Type --> Test[Unit Tests<br/>pytest]
        Test --> Coverage[Coverage Check<br/>80% minimum]
    end
    
    subgraph "Security Scanning"
        Coverage --> Semgrep[Semgrep<br/>100+ Rules]
        Semgrep --> Bandit[Bandit<br/>Python Security]
        Bandit --> PipAudit[pip-audit<br/>Dependency Vulns]
        PipAudit --> TruffleHog[TruffleHog<br/>Secret Detection]
        TruffleHog --> Trivy[Trivy<br/>Container Scan]
    end
    
    subgraph "Results"
        Trivy --> SARIF[SARIF Report]
        SARIF --> GHSecurity[GitHub Security Tab]
        SARIF --> Pass{All Checks<br/>Pass?}
    end
    
    Pass -->|No| Block[Block Merge]
    Pass -->|Yes| Merge[Allow Merge]
    
    Block --> Notify1[Notify Team]
    Merge --> Deploy[Deploy to Production]
    
    subgraph "Production Monitoring"
        Deploy --> Runtime[Runtime Security]
        Runtime --> Secrets[Secret Management<br/>Env Variables]
        Runtime --> Container[Container Hardening<br/>Non-root, Read-only]
        Runtime --> Network[Network Security<br/>Rate Limiting]
    end
    
    Secrets --> Monitor[Security Monitoring]
    Container --> Monitor
    Network --> Monitor
    
    Monitor --> Incident{Security<br/>Incident?}
    Incident -->|Yes| Response[Incident Response]
    Incident -->|No| Continue[Continue Monitoring]
    
    Response --> Rotate[Rotate Secrets]
    Response --> Patch[Apply Patches]
    Response --> Audit[Security Audit]
    
    style Block fill:#f8d7da
    style Merge fill:#d4edda
    style Pass fill:#fff3cd
    style Monitor fill:#cfe2ff
```

## Data Flow: Token Analysis

```mermaid
sequenceDiagram
    participant User
    participant Scanner as Hidden-Gem Scanner
    participant FS as Feature Store
    participant CG as CoinGecko (FREE)
    participant DS as Dexscreener (FREE)
    participant RPC as Ethereum RPC (FREE)
    participant Score as Scoring Engine
    participant Safety as Safety Gate
    participant Output as Output Layer
    
    User->>Scanner: Analyze Token (0x123...)
    Scanner->>FS: Request Features
    
    par Parallel Data Fetch
        FS->>CG: Get Price & Market Data
        CG-->>FS: Price, Volume, MCap
        
        FS->>DS: Get Liquidity Data
        DS-->>FS: Pool Liquidity, DEX Volume
        
        FS->>RPC: Get On-Chain Data
        RPC-->>FS: Holders, Transactions
    end
    
    FS->>FS: Validate Features
    FS->>FS: Calculate Derived Features
    FS-->>Scanner: Feature Vector (127 features)
    
    Scanner->>Score: Calculate GemScore
    Score->>Score: Weight Features
    Score->>Score: Normalize (0-100)
    Score-->>Scanner: GemScore + Confidence
    
    Scanner->>Safety: Check Safety Gates
    
    alt High Risk Detected
        Safety-->>Scanner: BLOCKED (Honeypot/Rug)
        Scanner-->>User: Reject: High Risk
    else Safety Pass
        Safety-->>Scanner: PASS
        Scanner->>Output: Generate Output
        Output->>Output: Create Dashboard Entry
        Output->>Output: Generate Collapse Artifact
        Output-->>User: Results + Report
    end
    
    Scanner->>Scanner: Log to Provenance DB
    Scanner->>Scanner: Update Metrics
```

## Deployment Architecture

```mermaid
graph TB
    subgraph "Development"
        Dev[Developer Workstation]
        Git[Git Repository]
    end
    
    subgraph "CI/CD (GitHub Actions)"
        Build[Build & Test]
        Scan[Security Scan]
        Package[Docker Build]
        Push[Push to Registry]
    end
    
    subgraph "Container Registry"
        Registry[Docker Hub /<br/>GitHub Container Registry]
    end
    
    subgraph "Production (Cloud/Self-Hosted)"
        direction TB
        
        subgraph "Application Tier"
            API1[API Server 1]
            API2[API Server 2]
            Worker1[Scanner Worker 1]
            Worker2[Scanner Worker 2]
        end
        
        subgraph "Data Tier"
            DB[(PostgreSQL<br/>+ TimescaleDB)]
            Cache[(Redis Cache)]
            Vector[(Vector DB<br/>Pinecone/Milvus)]
        end
        
        subgraph "Observability Tier"
            Prom[Prometheus]
            Grafana[Grafana]
            Jaeger[Jaeger]
        end
        
        subgraph "Security Tier"
            WAF[WAF / Rate Limiter]
            Secrets[Secret Manager]
        end
        
        LB[Load Balancer]
        
        LB --> API1
        LB --> API2
        
        API1 --> DB
        API2 --> DB
        Worker1 --> DB
        Worker2 --> DB
        
        API1 --> Cache
        API2 --> Cache
        Worker1 --> Cache
        Worker2 --> Cache
        
        Worker1 --> Vector
        Worker2 --> Vector
        
        API1 --> Prom
        API2 --> Prom
        Worker1 --> Prom
        Worker2 --> Prom
        
        Prom --> Grafana
        API1 --> Jaeger
        API2 --> Jaeger
        
        WAF --> LB
        
        API1 --> Secrets
        API2 --> Secrets
        Worker1 --> Secrets
        Worker2 --> Secrets
    end
    
    subgraph "External"
        Users[Users / Clients]
        DataSources[Data Sources<br/>APIs]
        Brokers[Brokers<br/>Alpaca, Questrade]
    end
    
    Dev --> Git
    Git --> Build
    Build --> Scan
    Scan --> Package
    Package --> Push
    Push --> Registry
    Registry --> API1
    Registry --> API2
    Registry --> Worker1
    Registry --> Worker2
    
    Users --> WAF
    Worker1 --> DataSources
    Worker2 --> DataSources
    Worker1 --> Brokers
    Worker2 --> Brokers
    
    style Dev fill:#e1f5ff
    style Registry fill:#fff3cd
    style WAF fill:#f8d7da
    style DB fill:#cfe2ff
    style Cache fill:#cfe2ff
```

---

**Note**: These diagrams can be rendered using Mermaid-compatible tools like:
- GitHub Markdown (automatic rendering)
- Mermaid Live Editor (https://mermaid.live)
- VS Code with Mermaid extension
- MkDocs with Mermaid plugin
- Obsidian with Mermaid support

**Generated**: October 25, 2025
