# Hyperparameter Tuning Guide

## Overview

This guide explains how to optimize PPO hyperparameters for the intraday trading agent using two methods:
1. **Bayesian Optimization** (Optuna) - Smart, efficient, recommended
2. **Grid Search** - Exhaustive, simple, guaranteed to find best in space

---

## Method 1: Bayesian Optimization (Optuna)

### Why Bayesian Optimization?
- **Efficient**: Finds good hyperparameters in fewer trials (~20-50 vs 100+)
- **Smart pruning**: Stops unpromising trials early
- **Parallel execution**: Can run multiple trials simultaneously
- **Resume capability**: Can pause and resume optimization

### Installation

```bash
pip install optuna optuna-dashboard
```

### Basic Usage

```bash
# Run 50 trials with 50K timesteps each (~6-10 hours)
python scripts/tune_hyperparameters.py --trials 50 --timesteps 50000

# Quick test (10 trials, 20K timesteps)
python scripts/tune_hyperparameters.py --trials 10 --timesteps 20000

# With timeout (24 hours max)
python scripts/tune_hyperparameters.py --trials 100 --timesteps 50000 --timeout 86400
```

### Persistent Studies (Recommended)

Use SQLite database to save progress:

```bash
# Create study
python scripts/tune_hyperparameters.py \
  --trials 50 \
  --timesteps 50000 \
  --study-name "ppo_spy_tuning_v1" \
  --storage "sqlite:///optuna_studies.db"

# Resume later (will continue from where it left off)
python scripts/tune_hyperparameters.py \
  --trials 50 \
  --timesteps 50000 \
  --study-name "ppo_spy_tuning_v1" \
  --storage "sqlite:///optuna_studies.db"
```

### Visualize Results

```bash
# Launch dashboard
optuna-dashboard sqlite:///optuna_studies.db

# Open browser: http://localhost:8080
```

### Hyperparameters Being Tuned

| Parameter | Range | Type | Description |
|-----------|-------|------|-------------|
| `learning_rate` | 1e-5 to 1e-3 | Log | Step size for gradient descent |
| `ent_coef` | 0.001 to 0.1 | Log | Entropy coefficient (exploration) |
| `batch_size` | 256, 512, 1024, 2048 | Categorical | Mini-batch size |
| `n_steps` | 1024, 2048, 4096 | Categorical | Steps per rollout |
| `clip_range` | 0.1 to 0.3 | Float | PPO clipping parameter |
| `gamma` | 0.95 to 0.995 | Float | Discount factor |
| `gae_lambda` | 0.90 to 0.99 | Float | GAE lambda (advantage estimation) |
| `n_epochs` | 5 to 20 | Int | Optimization epochs per rollout |
| `max_grad_norm` | 0.3 to 1.0 | Float | Gradient clipping threshold |
| `net_arch` | small/medium/large | Categorical | Network size |

---

## Method 2: Grid Search

### Why Grid Search?
- **Comprehensive**: Tests all combinations
- **Simpler**: No external dependencies
- **Reproducible**: Deterministic results
- **Easier to understand**: Clear what's being tested

### Basic Usage

```bash
# Run grid search (default: 72 combinations)
python scripts/grid_search_hyperparameters.py --timesteps 30000

# Quick test with fewer timesteps
python scripts/grid_search_hyperparameters.py --timesteps 20000
```

### Default Grid Space

```python
GRID_SEARCH_SPACE = {
    'learning_rate': [1e-4, 3e-4, 5e-4],        # 3 values
    'ent_coef': [0.01, 0.05, 0.1],              # 3 values
    'batch_size': [512, 1024],                   # 2 values
    'n_steps': [2048, 4096],                     # 2 values
    'clip_range': [0.15, 0.20, 0.25],           # 3 values
    'gamma': [0.99, 0.995],                      # 2 values
    'net_arch': [[256,256], [256,256,128]],     # 2 values
}
# Total: 3 × 3 × 2 × 2 × 3 × 2 × 2 = 432 combinations
```

### Customize Grid Space

Edit `scripts/grid_search_hyperparameters.py`:

```python
# Reduced grid for faster testing
GRID_SEARCH_SPACE = {
    'learning_rate': [3e-4],                    # Fixed
    'ent_coef': [0.05],                         # Fixed
    'batch_size': [512, 1024],                   # 2 values
    'n_steps': [2048],                           # Fixed
    'clip_range': [0.15, 0.20, 0.25],           # 3 values
    'gamma': [0.99],                             # Fixed
    'net_arch': [[256,256], [256,256,128]],     # 2 values
}
# Total: 1 × 1 × 2 × 1 × 3 × 1 × 2 = 12 combinations
```

---

## Interpreting Results

### Best Hyperparameters Output

After tuning completes, you'll see:

```
🥇 BEST RESULT:
  Win rate: 42.3%
  Sharpe: 1.85
  Avg PnL: $127.45

  Hyperparameters:
    learning_rate: 0.0003
    ent_coef: 0.05
    batch_size: 512
    n_steps: 2048
    clip_range: 0.20
    gamma: 0.99
    gae_lambda: 0.95
    n_epochs: 10
    max_grad_norm: 0.5
    net_arch: [256, 256, 128]
```

### Applying Results

Update `scripts/train_intraday_ppo.py` with the best hyperparameters:

```python
def train_ppo(
    # ...
    learning_rate: float = 3e-4,      # ← Updated
    n_steps: int = 2048,               # ← Updated
    batch_size: int = 512,             # ← Updated
    # ...
):
    # ...
    model = PPO(
        'MlpPolicy',
        env,
        learning_rate=learning_rate,
        n_steps=n_steps,
        batch_size=batch_size,
        clip_range=0.20,               # ← Updated
        gamma=0.99,                    # ← Updated
        ent_coef=0.05,                 # ← Updated
        policy_kwargs=dict(
            net_arch=[256, 256, 128],  # ← Updated
            # ...
        ),
        # ...
    )
```

---

## Comparison: Optuna vs Grid Search

| Aspect | Optuna (Bayesian) | Grid Search |
|--------|-------------------|-------------|
| **Efficiency** | ⭐⭐⭐⭐⭐ (20-50 trials) | ⭐⭐ (100+ trials) |
| **Quality** | ⭐⭐⭐⭐ (near-optimal) | ⭐⭐⭐⭐⭐ (optimal in grid) |
| **Speed** | Fast (prunes bad trials) | Slow (tests all) |
| **Parallelization** | ✅ Easy | ⚠️ Manual |
| **Resume** | ✅ Built-in | ❌ None |
| **Setup** | Moderate | Simple |
| **Dependencies** | Optuna | None |

### Recommendation

- **For most users**: Use Optuna with 50 trials
- **For exhaustive search**: Use Grid Search with reduced space
- **For quick testing**: Optuna with 10 trials

---

## Advanced: Parallel Optimization

Run multiple Optuna trials in parallel:

### Setup

```bash
# Terminal 1: Start shared study
python scripts/tune_hyperparameters.py \
  --trials 100 \
  --study-name "parallel_tuning" \
  --storage "sqlite:///optuna_studies.db"

# Terminal 2: Join same study
python scripts/tune_hyperparameters.py \
  --trials 100 \
  --study-name "parallel_tuning" \
  --storage "sqlite:///optuna_studies.db"

# Terminal 3: Join same study
python scripts/tune_hyperparameters.py \
  --trials 100 \
  --study-name "parallel_tuning" \
  --storage "sqlite:///optuna_studies.db"
```

All terminals will share the same study and run different trials in parallel!

---

## Troubleshooting

### Issue: "Out of Memory"

**Solution**: Reduce batch size or network size

```bash
# Edit tune_hyperparameters.py
# Reduce batch_size range: [256, 512] instead of [256, 512, 1024, 2048]
# Reduce n_steps range: [1024, 2048] instead of [1024, 2048, 4096]
```

### Issue: "All trials failing"

**Symptoms**: Every trial returns 0% win rate

**Diagnosis**:
1. Check IBKR connection
2. Check data pipeline (need 30+ days of data)
3. Check logs for errors

**Solution**:
```bash
# Test with single trial first
python scripts/tune_hyperparameters.py --trials 1 --timesteps 10000
```

### Issue: "Takes too long"

**Solution**: Reduce search space or use fewer timesteps

```bash
# Faster tuning (less accurate)
python scripts/tune_hyperparameters.py --trials 20 --timesteps 30000

# Or use grid search with reduced space (see "Customize Grid Space" above)
```

### Issue: "Database locked"

**Symptoms**: "database is locked" error with SQLite

**Solution**: Use PostgreSQL or MySQL instead:

```bash
# Install PostgreSQL connector
pip install psycopg2-binary

# Use PostgreSQL
python scripts/tune_hyperparameters.py \
  --storage "postgresql://user:pass@localhost/optuna"
```

---

## Best Practices

### 1. Start Small
```bash
# Test with 10 trials first
python scripts/tune_hyperparameters.py --trials 10 --timesteps 20000
```

### 2. Use Sufficient Training Steps
- **Minimum**: 30K timesteps/trial
- **Recommended**: 50K timesteps/trial
- **Thorough**: 100K timesteps/trial

### 3. Monitor Progress
```bash
# Watch logs in real-time
tail -f logs/hyperparameter_tuning/*.json
```

### 4. Save Studies
Always use `--storage` to persist results:
```bash
python scripts/tune_hyperparameters.py \
  --trials 50 \
  --storage "sqlite:///optuna_studies.db"
```

### 5. Validate Results
After finding best hyperparameters, train a full model:
```bash
python scripts/train_intraday_ppo.py \
  --lr 3e-4 \
  --n-steps 2048 \
  --batch-size 512 \
  --timesteps 500000
```

---

## Expected Results

Based on previous tuning runs:

### Typical Hyperparameters (Win Rate > 40%)

```python
learning_rate = 3e-4        # Standard PPO learning rate
ent_coef = 0.05             # Moderate exploration
batch_size = 512            # Balance between speed and accuracy
n_steps = 2048              # Frequent policy updates
clip_range = 0.20           # Standard PPO clipping
gamma = 0.99                # Short-term focus (intraday)
net_arch = [256, 256, 128]  # Medium-large network
```

### Performance Metrics

- **Good**: Win rate > 35%, Sharpe > 1.5
- **Excellent**: Win rate > 40%, Sharpe > 2.0
- **Outstanding**: Win rate > 45%, Sharpe > 2.5

### Training Time

- **Optuna (50 trials)**: 6-10 hours on CPU, 3-5 hours on GPU
- **Grid Search (72 combinations)**: 10-15 hours on CPU, 5-8 hours on GPU

---

## Next Steps

After hyperparameter tuning:

1. **✅ Apply best hyperparameters** to `train_intraday_ppo.py`
2. **✅ Train full model** with 500K-1M timesteps
3. **✅ Backtest** on out-of-sample data
4. **✅ Paper trade** to validate live performance
5. **✅ Monitor and iterate** based on real results

---

## References

- [Optuna Documentation](https://optuna.readthedocs.io/)
- [PPO Paper](https://arxiv.org/abs/1707.06347)
- [Hyperparameter Importance](https://arxiv.org/abs/1709.06560)
- [RL Hyperparameter Tuning Best Practices](https://spinningup.openai.com/)
