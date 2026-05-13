# Hyperparameter Tuning Summary (Thought 2.5)

## Changes Made

### 1. **Curriculum Learning Adjustments (Thought 2.4)**

**BEFORE:**
- Stage 1: 52% win rate target (too aggressive)
- Stage 2: 58% win rate target (unrealistic)
- 3 stages total

**AFTER:**
- Stage 0 (Bootstrap): 0% win rate - auto-advance
- Stage 1 (Confidence): **15% win rate** ✅ (achievable early learning)
- Stage 2 (Intermediate): **30% win rate** ✅ (NEW - gradual progression)
- Stage 3 (Production): **45% win rate** ✅ (realistic long-term target)
- 4 stages total for smoother progression

**Rationale:**
- 15% win rate is achievable within first 10K steps (vs random 50%)
- Gradual progression prevents getting stuck in early stages
- 45% final target is realistic for intraday trading (vs 58% which was too optimistic)

---

### 2. **PPO Hyperparameter Tuning (Thought 2.5)**

#### Learning Rate
- **BEFORE:** 1e-4 (initial) → 5e-5 (final)
- **AFTER:** 3e-4 (initial) → 1e-4 (final)
- **Rationale:** Faster learning in early stages, prevents premature convergence

#### Entropy Coefficient
- **BEFORE:** 0.01 (initial) → 0.0005 (final)
- **AFTER:** 0.05 (initial) → 0.01 (final)
- **Rationale:** 
  - Stronger exploration in early training (0.05 vs 0.01)
  - Maintains exploration longer (0.01 final vs 0.0005)
  - Prevents premature convergence to suboptimal policies

#### Rollout Configuration
- **BEFORE:** n_steps=4096, batch_size=8192 (MISMATCH!)
- **AFTER:** n_steps=2048, batch_size=512
- **Rationale:**
  - More frequent policy updates (every 2048 steps vs 4096)
  - Better gradient estimates with smaller mini-batches (512)
  - Proper batch_size < n_steps relationship

#### Clipping
- **BEFORE:** clip_range=0.10 (too tight)
- **AFTER:** clip_range=0.2 (standard PPO)
- **Rationale:** Allows larger policy updates when beneficial

#### Discount Factor
- **BEFORE:** gamma=0.995 (too long-term)
- **AFTER:** gamma=0.99 (standard)
- **Rationale:** Better for intraday trading (shorter horizons)

#### Target KL
- **BEFORE:** target_kl=0.08 (causes early stopping)
- **AFTER:** target_kl=None (disabled)
- **Rationale:** Prevents premature stopping when learning is progressing

#### Early Stopping Patience
- **BEFORE:** patience=4 checks (too impatient)
- **AFTER:** patience=6 checks (more tolerant)
- **Rationale:** Allows agent time to recover from performance dips

---

## Expected Outcomes

### Curriculum Learning
✅ Agent should now progress through stages:
- Bootstrap → Confidence (15%) at ~10K steps
- Confidence → Intermediate (30%) at ~50K steps
- Intermediate → Production (45%) at ~100K steps

### Hyperparameter Tuning
✅ Improved learning dynamics:
- **Faster initial learning** (3e-4 LR vs 1e-4)
- **Better exploration** (0.05 → 0.01 entropy vs 0.01 → 0.0005)
- **More stable gradients** (batch_size=512 vs 8192)
- **Frequent updates** (n_steps=2048 vs 4096)
- **No premature stopping** (target_kl=None, patience=6)

---

## Training Command

```bash
cd C:\Users\kay\Documents\Projects\AutoTrader\Autotrader
..\.venv-2\Scripts\python.exe scripts\train_intraday_ppo.py --symbol SPY --duration "30 D" --timesteps 100000
```

**Expected Timeline:**
- **0-10K steps**: Bootstrap exploration, achieve 15%+ win rate
- **10K-50K steps**: Confidence building, reach 30%+ win rate
- **50K-100K steps**: Intermediate refinement, target 45%+ win rate
- **100K+ steps**: Production tuning, optimize Sharpe ratio

---

## Monitoring

Track these metrics in TensorBoard:
1. **Win rate progression** (target: 15% → 30% → 45%)
2. **Action distribution** (should see ~33% LONG, ~33% SHORT, ~33% FLAT initially)
3. **Curriculum stage transitions** (should advance every 40-50K steps)
4. **Entropy coefficient decay** (0.05 → 0.01 over training)
5. **Learning rate decay** (3e-4 → 1e-4 over training)

---

## Rationale for Each Change

### Why Lower Curriculum Targets?
**Problem:** Agent was stuck at bootstrap stage forever (0% → 52% is too big a jump)
**Solution:** Gradual targets (0% → 15% → 30% → 45%) allow steady progression
**Evidence:** Most RL papers use gradual curriculum (e.g., OpenAI Five used 10+ stages)

### Why Higher Learning Rate?
**Problem:** 1e-4 LR is too conservative for early exploration
**Solution:** 3e-4 is standard PPO learning rate (OpenAI Baselines default)
**Evidence:** Original PPO paper used 3e-4 for Atari and MuJoCo

### Why Higher Entropy?
**Problem:** 0.01 initial entropy led to premature convergence (agent learned "never trade")
**Solution:** 0.05 initial entropy encourages diverse action exploration
**Evidence:** High entropy early = better exploration (entropy annealing is standard)

### Why Smaller Batches?
**Problem:** batch_size=8192 with n_steps=4096 is impossible (batch > buffer!)
**Solution:** batch_size=512 < n_steps=2048 allows proper mini-batch sampling
**Evidence:** PPO requires batch_size < n_steps for mini-batch SGD

### Why Disable target_kl?
**Problem:** target_kl=0.08 caused early stopping even when learning was progressing
**Solution:** Disable target_kl to let learning continue until natural convergence
**Evidence:** Many practitioners disable target_kl for better training stability

---

## References

1. **PPO Paper:** [Proximal Policy Optimization Algorithms (Schulman et al., 2017)](https://arxiv.org/abs/1707.06347)
2. **Curriculum Learning:** [Curriculum Learning (Bengio et al., 2009)](https://qmro.qmul.ac.uk/xmlui/handle/123456789/15972)
3. **Entropy Annealing:** [Soft Actor-Critic (Haarnoja et al., 2018)](https://arxiv.org/abs/1801.01290)
4. **OpenAI Baselines:** [PPO2 Hyperparameters](https://github.com/openai/baselines)

---

## Next Steps

1. **Run Training:** Execute command above for 100K steps
2. **Monitor Progress:** Watch TensorBoard for stage transitions
3. **Validate Results:** Check if agent achieves 15% → 30% → 45% win rate progression
4. **Iterate:** If still stuck, consider:
   - Further reducing Stage 1 target to 10%
   - Increasing entropy coefficient to 0.1
   - Adding auxiliary losses (behavioral cloning from expert demonstrations)

---

**Status:** ✅ Ready for training
**Expected Improvement:** Agent should now progress beyond bootstrap stage and learn profitable strategies
