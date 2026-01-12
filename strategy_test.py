"""
Strategic CPU Battle Test
4 strategies: Conservative, VP Aggressive, Balanced, Debt Avoidance
"""
import random
from typing import List, Dict, Any
from main import (
    Card, Player, deal_fixed_sets, reveal_upgrades, declare_tricks, seal_cards,
    choose_card, trick_winner, apply_upgrade,
    ROUNDS, SETS_PER_GAME, TRICKS_PER_ROUND, REVEAL_UPGRADES, DECLARATION_BONUS_VP,
    TAKE_GOLD_INSTEAD, RESCUE_GOLD_FOR_4TH, WAGE_CURVE, UPGRADED_WAGE_CURVE,
    INITIAL_WORKERS, DEBT_PENALTY_MULTIPLIER
)

# === Strategy Definitions ===
STRATEGIES = {
    'CONSERVATIVE': {
        'name': 'Kenjitsu',
        'name_jp': '堅実',
        'desc': 'Safe play, avoid workers, take gold',
        'max_workers': 2,
        'prefer_gold': True,
        'hunt_ratio': 0.2,
        'accept_debt': 0,
    },
    'VP_AGGRESSIVE': {
        'name': 'VP Toppa',
        'name_jp': 'VPつっぱ',
        'desc': 'Max workers, always upgrade, hunt for VP',
        'max_workers': 99,
        'prefer_gold': False,
        'hunt_ratio': 0.8,
        'accept_debt': 99,
    },
    'BALANCED': {
        'name': 'Balance',
        'name_jp': 'バランス',
        'desc': 'Moderate workers, accept some debt',
        'max_workers': 4,
        'prefer_gold': False,
        'hunt_ratio': 0.5,
        'accept_debt': 4,
    },
    'DEBT_AVOID': {
        'name': 'DebtAvoid',
        'name_jp': '借金回避',
        'desc': 'Moderate workers but monitor gold carefully',
        'max_workers': 3,
        'prefer_gold': False,
        'hunt_ratio': 0.4,
        'accept_debt': 1,
    },
}

def calc_expected_wage(player, round_no):
    workers = player.basic_workers_total + player.basic_workers_new_hires
    init_count = min(INITIAL_WORKERS, workers)
    hired_count = workers - init_count
    return (init_count * WAGE_CURVE[round_no]) + (hired_count * UPGRADED_WAGE_CURVE[round_no])

def choose_upgrade_strategic(player, revealed, strategy, round_no):
    strat = STRATEGIES[strategy]
    current_workers = player.basic_workers_total + player.basic_workers_new_hires
    expected_wage = calc_expected_wage(player, round_no)

    if strat['prefer_gold']:
        return 'GOLD'

    # VP Aggressive always takes upgrades
    if strategy == 'VP_AGGRESSIVE':
        if 'RECRUIT_INSTANT' in revealed and current_workers < strat['max_workers']:
            return 'RECRUIT_INSTANT'
        for u in revealed:
            if u.startswith('UP_') or u.startswith('WITCH_'):
                return u
        return 'GOLD'

    # Debt Avoid: check if we can afford more workers
    if strategy == 'DEBT_AVOID':
        if player.gold < expected_wage + 3:
            return 'GOLD'

    # Balanced/Debt Avoid: prefer upgrades but limit workers
    if current_workers < strat['max_workers']:
        if 'RECRUIT_INSTANT' in revealed:
            return 'RECRUIT_INSTANT'

    for u in revealed:
        if u.startswith('UP_HUNT'):
            return u
        if u.startswith('UP_TRADE'):
            return u

    return 'GOLD'

def choose_actions_strategic(player, strategy, round_no, rng):
    strat = STRATEGIES[strategy]
    workers = player.basic_workers_total
    actions = []

    expected_wage = calc_expected_wage(player, round_no)
    gold_needed = expected_wage - player.gold

    for _ in range(workers):
        if strategy == 'CONSERVATIVE':
            actions.append('TRADE')
        elif strategy == 'VP_AGGRESSIVE':
            if rng.random() < strat['hunt_ratio']:
                actions.append('HUNT')
            else:
                actions.append('TRADE')
        elif strategy == 'DEBT_AVOID':
            if gold_needed > 0:
                actions.append('TRADE')
                gold_needed -= 2 + player.trade_level
            else:
                if rng.random() < strat['hunt_ratio']:
                    actions.append('HUNT')
                else:
                    actions.append('TRADE')
        else:  # BALANCED
            if rng.random() < strat['hunt_ratio']:
                actions.append('HUNT')
            else:
                actions.append('TRADE')

    return actions

def resolve_actions_simple(player, actions):
    for action in actions:
        if action == 'TRADE':
            player.gold += 2 + player.trade_level
        elif action == 'HUNT':
            player.vp += 1 + player.hunt_level

def pay_wages(player, round_no):
    workers_paid = player.basic_workers_total + player.basic_workers_new_hires
    init_count = min(INITIAL_WORKERS, workers_paid)
    hired_count = workers_paid - init_count
    wage = (init_count * WAGE_CURVE[round_no]) + (hired_count * UPGRADED_WAGE_CURVE[round_no])

    short = max(0, wage - player.gold)
    if player.gold >= wage:
        player.gold -= wage
    else:
        player.gold = 0
        player.vp -= short * DEBT_PENALTY_MULTIPLIER
    return short

def run_strategic_game(seed, strategies):
    rng = random.Random(seed)

    players = []
    for i, strat in enumerate(strategies):
        p = Player(f'P{i+1}', is_bot=True, rng=random.Random(seed + i + 1))
        p.strategy = strat
        players.append(p)

    deal_fixed_sets(players, seed=seed, logger=None, max_rank=6, num_decks=4)

    player_debt = {p.name: 0 for p in players}

    for round_no in range(ROUNDS):
        revealed = reveal_upgrades(rng, REVEAL_UPGRADES)
        set_index = round_no % SETS_PER_GAME
        leader_index = round_no % len(players)

        for p in players:
            p.tricks_won_this_round = 0

        # Trick-taking phase
        full_hands = {p.name: p.sets[set_index][:] for p in players}
        for p in players:
            p.declared_tricks = declare_tricks(p, full_hands[p.name][:], set_index)

        playable_hands = {}
        for p in players:
            hand = full_hands[p.name]
            seal_cards(p, hand, set_index)
            playable_hands[p.name] = hand[:]

        leader = leader_index
        for trick_idx in range(TRICKS_PER_ROUND):
            plays = []
            lead_card = None
            for offset in range(len(players)):
                idx = (leader + offset) % len(players)
                pl = players[idx]
                hand = playable_hands[pl.name]
                chosen = choose_card(pl, lead_card, hand)
                hand.remove(chosen)
                plays.append((pl, chosen))
                if lead_card is None:
                    lead_card = chosen
            winner = trick_winner(lead_card.suit, plays)
            winner.tricks_won_this_round += 1
            leader = next(i for i, pp in enumerate(players) if pp.name == winner.name)

        for p in players:
            if p.tricks_won_this_round == p.declared_tricks:
                p.vp += DECLARATION_BONUS_VP

        # Upgrade selection (strategic)
        ranked = sorted(players, key=lambda p: (p.tricks_won_this_round, -players.index(p)), reverse=True)
        for p in ranked:
            choice = choose_upgrade_strategic(p, revealed, p.strategy, round_no)
            if choice == 'GOLD':
                p.gold += TAKE_GOLD_INSTEAD
            elif choice in revealed:
                revealed.remove(choice)
                apply_upgrade(p, choice)
        ranked[-1].gold += RESCUE_GOLD_FOR_4TH

        # Worker placement (strategic)
        for p in players:
            actions = choose_actions_strategic(p, p.strategy, round_no, rng)
            resolve_actions_simple(p, actions)

        # Wages
        for p in players:
            short = pay_wages(p, round_no)
            player_debt[p.name] += short

        for p in players:
            if p.basic_workers_new_hires > 0:
                p.basic_workers_total += p.basic_workers_new_hires
                p.basic_workers_new_hires = 0

    sorted_p = sorted(players, key=lambda x: (x.vp, x.gold), reverse=True)
    return [{
        'name': p.name,
        'strategy': p.strategy,
        'rank': i + 1,
        'vp': p.vp,
        'gold': p.gold,
        'workers': p.basic_workers_total,
        'debt': player_debt[p.name],
    } for i, p in enumerate(sorted_p)]


def run_matchup_test(strategies_list, num_games, label):
    """Run games with specified strategy combinations"""
    strat_stats = {s: {'wins': 0, 'top2': 0, 'total_vp': 0, 'total_debt': 0, 'count': 0} for s in STRATEGIES}

    for game_id in range(num_games):
        strategies = strategies_list[:]
        random.Random(game_id).shuffle(strategies)
        results = run_strategic_game(game_id * 100, strategies)

        for r in results:
            s = r['strategy']
            strat_stats[s]['count'] += 1
            strat_stats[s]['total_vp'] += r['vp']
            strat_stats[s]['total_debt'] += r['debt']
            if r['rank'] == 1:
                strat_stats[s]['wins'] += 1
            if r['rank'] <= 2:
                strat_stats[s]['top2'] += 1

    print(f"\n{label}")
    print("=" * 80)
    print(f"{'Strategy':<15} | {'Wins':>5} | {'Top2':>5} | {'Win%':>6} | {'Top2%':>6} | {'AvgVP':>7} | {'AvgDebt':>7}")
    print("-" * 80)

    results_list = []
    for s in ['CONSERVATIVE', 'VP_AGGRESSIVE', 'BALANCED', 'DEBT_AVOID']:
        stats = strat_stats[s]
        if stats['count'] > 0:
            win_pct = stats['wins'] / stats['count'] * 100
            top2_pct = stats['top2'] / stats['count'] * 100
            avg_vp = stats['total_vp'] / stats['count']
            avg_debt = stats['total_debt'] / stats['count']
            print(f"{STRATEGIES[s]['name']:<15} | {stats['wins']:>5} | {stats['top2']:>5} | {win_pct:>5.1f}% | {top2_pct:>5.1f}% | {avg_vp:>+7.1f} | {avg_debt:>7.1f}")
            results_list.append({
                'strategy': s,
                'name': STRATEGIES[s]['name'],
                'wins': stats['wins'],
                'top2': stats['top2'],
                'count': stats['count'],
                'win_pct': win_pct,
                'top2_pct': top2_pct,
                'avg_vp': avg_vp,
                'avg_debt': avg_debt,
            })

    return results_list


def main():
    print("=" * 80)
    print("STRATEGY BALANCE TEST REPORT")
    print(f"Penalty Multiplier: {DEBT_PENALTY_MULTIPLIER}x")
    print("=" * 80)

    # Test 1: Mixed matchup (one of each)
    mixed_results = run_matchup_test(
        ['CONSERVATIVE', 'VP_AGGRESSIVE', 'BALANCED', 'DEBT_AVOID'],
        50,
        "TEST 1: Mixed Matchup (1 of each strategy) - 50 games"
    )

    # Test 2: Same strategy matchups
    print("\n" + "=" * 80)
    print("TEST 2: Same Strategy Matchups (4 of same) - 30 games each")
    print("=" * 80)

    same_strat_results = {}
    for strat in ['CONSERVATIVE', 'VP_AGGRESSIVE', 'BALANCED', 'DEBT_AVOID']:
        strat_stats = {'total_vp': 0, 'total_debt': 0, 'games': 0, 'vp_spread': []}

        for game_id in range(30):
            results = run_strategic_game(game_id * 100 + hash(strat) % 1000, [strat] * 4)
            vps = [r['vp'] for r in results]
            debts = [r['debt'] for r in results]
            strat_stats['total_vp'] += sum(vps)
            strat_stats['total_debt'] += sum(debts)
            strat_stats['games'] += 4
            strat_stats['vp_spread'].append(max(vps) - min(vps))

        avg_vp = strat_stats['total_vp'] / strat_stats['games']
        avg_debt = strat_stats['total_debt'] / strat_stats['games']
        avg_spread = sum(strat_stats['vp_spread']) / len(strat_stats['vp_spread'])

        same_strat_results[strat] = {
            'avg_vp': avg_vp,
            'avg_debt': avg_debt,
            'avg_spread': avg_spread,
        }

        print(f"{STRATEGIES[strat]['name']:<15}: AvgVP={avg_vp:+.1f}, AvgDebt={avg_debt:.1f}, VP Spread={avg_spread:.1f}")

    # Test 3: Pair matchups
    print("\n" + "=" * 80)
    print("TEST 3: Pair Matchups (2v2) - 30 games each")
    print("=" * 80)

    pairs = [
        (['CONSERVATIVE', 'CONSERVATIVE', 'VP_AGGRESSIVE', 'VP_AGGRESSIVE'], 'Conservative vs VP Aggressive'),
        (['BALANCED', 'BALANCED', 'DEBT_AVOID', 'DEBT_AVOID'], 'Balanced vs Debt Avoid'),
        (['CONSERVATIVE', 'CONSERVATIVE', 'BALANCED', 'BALANCED'], 'Conservative vs Balanced'),
        (['VP_AGGRESSIVE', 'VP_AGGRESSIVE', 'DEBT_AVOID', 'DEBT_AVOID'], 'VP Aggressive vs Debt Avoid'),
    ]

    pair_results = []
    for strats, label in pairs:
        results = run_matchup_test(strats, 30, f"  {label}")
        pair_results.append((label, results))

    # Summary
    print("\n" + "=" * 80)
    print("SUMMARY")
    print("=" * 80)

    print("\nMixed Matchup Rankings (by Win%):")
    for i, r in enumerate(sorted(mixed_results, key=lambda x: x['win_pct'], reverse=True), 1):
        print(f"  {i}. {r['name']}: {r['win_pct']:.1f}% wins, {r['top2_pct']:.1f}% top2, VP={r['avg_vp']:+.1f}")

    print("\nStrategy Characteristics:")
    for strat in ['CONSERVATIVE', 'VP_AGGRESSIVE', 'BALANCED', 'DEBT_AVOID']:
        mixed = next((r for r in mixed_results if r['strategy'] == strat), None)
        same = same_strat_results.get(strat, {})
        if mixed:
            print(f"  {STRATEGIES[strat]['name']:<15}: Win={mixed['win_pct']:>5.1f}%, Debt={mixed['avg_debt']:.1f}G, Mirror-Spread={same.get('avg_spread', 0):.1f}")


if __name__ == "__main__":
    main()
