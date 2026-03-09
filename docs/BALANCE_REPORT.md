# Strategy Balance Report (給与未払い1金 = -2VP)

## Test Configuration
- **Penalty**: 給与未払い1金につき -2VP
- **Games per test**: 30-50 games
- **Strategies**: 4 types

---

## Strategy Definitions

| Strategy | Description | Max Workers | Hunt Ratio | Debt Tolerance |
|----------|-------------|-------------|------------|----------------|
| **Kenjitsu (Conservative)** | Safe play, gold priority | 2 | 20% | 0G |
| **VP Toppa (Aggressive)** | Max workers, VP hunting | Unlimited | 80% | Unlimited |
| **Balance** | Moderate approach | 4 | 50% | 4G |
| **DebtAvoid** | Careful gold management | 3 | 40% | 1G |

---

## Test 1: Mixed Matchup (1 of each strategy)
*50 games, all 4 strategies competing*

| Rank | Strategy | Win% | Top2% | Avg VP | Avg Debt |
|------|----------|------|-------|--------|----------|
| 1 | **DebtAvoid** | 44.0% | 78.0% | +4.6 | 0.0G |
| 2 | Balance | 32.0% | 60.0% | +2.0 | 2.8G |
| 3 | VP Toppa | 24.0% | 46.0% | -2.6 | 5.3G |
| 4 | Kenjitsu | 0.0% | 16.0% | +0.8 | 0.0G |

### Analysis
- **DebtAvoid dominates**: Best win rate AND highest VP
- **Balance is viable**: Good win rate with moderate debt
- **VP Toppa is high-risk**: Negative VP average, but can win
- **Kenjitsu is too passive**: Zero wins, needs VP sources

---

## Test 2: Mirror Matchups (4 of same strategy)
*30 games each, 4 identical strategies*

| Strategy | Avg VP | Avg Debt | VP Spread |
|----------|--------|----------|-----------|
| Kenjitsu | +0.7 | 0.0G | 1.5 |
| VP Toppa | -0.9 | 5.1G | **20.3** |
| Balance | +2.5 | 1.8G | 9.5 |
| DebtAvoid | +4.1 | 0.0G | 4.1 |

### Analysis
- **VP Toppa has extreme variance**: 20.3 VP spread = game decided by luck/card draw
- **Kenjitsu is stable but low**: Minimal spread but low VP ceiling
- **DebtAvoid scales well**: High VP even in mirror

---

## Test 3: 2v2 Matchups

### Conservative vs VP Aggressive
| Strategy | Win% | Top2% | Avg VP |
|----------|------|-------|--------|
| VP Toppa | 38.3% | 46.7% | -6.5 |
| Kenjitsu | 11.7% | 53.3% | +0.5 |

> VP Aggressive wins more often but goes negative; Conservative places 2nd consistently

### Balanced vs DebtAvoid
| Strategy | Win% | Top2% | Avg VP |
|----------|------|-------|--------|
| Balance | 28.3% | 46.7% | +3.3 |
| DebtAvoid | 21.7% | 53.3% | +4.2 |

> Close matchup - both viable, DebtAvoid more consistent

### Conservative vs Balanced
| Strategy | Win% | Top2% | Avg VP |
|----------|------|-------|--------|
| Balance | 46.7% | 73.3% | +1.1 |
| Kenjitsu | 3.3% | 26.7% | +0.5 |

> Balanced crushes Conservative

### VP Aggressive vs DebtAvoid
| Strategy | Win% | Top2% | Avg VP |
|----------|------|-------|--------|
| DebtAvoid | 28.3% | 55.0% | +4.5 |
| VP Toppa | 21.7% | 45.0% | -0.9 |

> DebtAvoid wins the "smart vs reckless" matchup

---

## Test 4: Triple Matchups (3 same + 1 different)

| Scenario | Minority Win% | Majority Win%/player |
|----------|---------------|---------------------|
| 3x Conservative + 1x VP Aggressive | VP: 20% | Cons: 26.7% |
| 3x Conservative + 1x Balanced | **Bal: 46.7%** | Cons: 17.8% |
| 3x VP Aggressive + 1x DebtAvoid | **Debt: 30%** | VP: 23.3% |
| 3x Balanced + 1x DebtAvoid | Debt: 20% | Bal: 26.7% |

### Analysis
- Balanced exploits conservative lobbies
- DebtAvoid holds its own even against 3x VP Aggressive
- When everyone is aggressive, DebtAvoid thrives

---

## Sample Game Results

| Game | 1st | 2nd | 3rd | 4th |
|------|-----|-----|-----|-----|
| 1 | Balance +5 | DebtAvoid +4 | Kenjitsu +0 | VP Toppa -9 |
| 2 | DebtAvoid +2 | Kenjitsu +0 | Balance -8 | VP Toppa -9 |
| 3 | **VP Toppa +8** | Balance +3 | DebtAvoid +0 | Kenjitsu +0 |
| 4 | DebtAvoid +5 | Balance +4 | Kenjitsu +2 | VP Toppa -4 |
| 5 | DebtAvoid +6 | Kenjitsu +1 | Balance -3 | VP Toppa -25 |

> Game 3: VP Toppa can dominate when debt is avoided
> Game 5: VP Toppa crashes hard (-25 VP) with 21G debt

---

## Conclusions

### Balance Assessment

| Aspect | Rating | Notes |
|--------|--------|-------|
| Strategy Diversity | B+ | 3/4 strategies viable, Conservative needs buff |
| Risk/Reward | A | Aggressive play has upside but real downside |
| Debt Penalty (-2VP/1G) | A- | Punishing but not game-ending |
| Variance | B | VP Aggressive too swingy |

### Strategic Viability
1. **DebtAvoid** - Optimal strategy, may need nerf
2. **Balance** - Solid mid-tier choice
3. **VP Toppa** - High risk/reward, viable for gamblers
4. **Kenjitsu** - Too weak, needs VP generation

### Recommendations

1. **Conservative needs help**: Add VP bonus for zero-debt or buff TRADE returns
2. **DebtAvoid may be too strong**: Consider reducing max workers to 2
3. **-2VP/1Gペナルティは適切**: Creates meaningful decisions without being brutal
4. **Strategic debt (1-3G) is viable**: Players can intentionally take small debt

### Debt as Strategy (-2VP/1G)
| Debt Range | Viability | Risk Level |
|------------|-----------|------------|
| 0G | Safe | None |
| 1-3G | **Strategic** | Low |
| 4-6G | Gambling | Medium |
| 7G+ | Losing | High |

---

## Final Verdict

**給与未払い1金 = -2VP のペナルティは良いゲームプレイの緊張感を生む。**

Workers are valuable but risky. Aggressive expansion can win but often backfires.
The "worker placement dilemma" (need workers for VP, but workers cost money) works well.

Conservative play is currently too weak - this may be a bot logic issue rather than
a balance problem. In human play, Conservative might perform better with skilled
trick-taking.
