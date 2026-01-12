"""Test 2 workers with smart VP Toppa strategy"""
import random
from main import (
    Player, STRATEGIES, assign_random_strategy, deal_fixed_sets,
    reveal_upgrades, declare_tricks, seal_cards, choose_card, trick_winner,
    rank_players_for_upgrade, apply_upgrade, resolve_actions, pay_wages_and_debt,
    ROUNDS, SETS_PER_GAME, TRICKS_PER_ROUND, REVEAL_UPGRADES,
    TAKE_GOLD_INSTEAD, RESCUE_GOLD_FOR_4TH, DECLARATION_BONUS_VP,
    WAGE_CURVE, UPGRADED_WAGE_CURVE, can_take_upgrade, calc_expected_wage
)

def choose_upgrade_smart(player, revealed, round_no, strategy):
    available = [u for u in revealed if can_take_upgrade(player, u)]
    if not available:
        return 'GOLD'

    strat = STRATEGIES[strategy]
    current_workers = player.basic_workers_total + player.basic_workers_new_hires
    expected_wage = calc_expected_wage(player, round_no)

    if strat['prefer_gold']:
        return 'GOLD'

    # Smart VP Toppa: take gold if about to go into heavy debt
    if strategy == 'VP_AGGRESSIVE':
        gold_after_trade = player.gold + (2 + player.trade_level)
        if gold_after_trade < expected_wage - 4:
            return 'GOLD'
        if 'RECRUIT_INSTANT' in available:
            return 'RECRUIT_INSTANT'
        for u in available:
            if u.startswith('UP_') or u.startswith('WITCH_'):
                return u
        return 'GOLD'

    if strategy == 'DEBT_AVOID':
        if player.gold < expected_wage + 3:
            return 'GOLD'

    if current_workers < strat['max_workers']:
        if 'RECRUIT_INSTANT' in available:
            return 'RECRUIT_INSTANT'

    for u in available:
        if u.startswith('UP_HUNT'):
            return u
        if u.startswith('UP_TRADE'):
            return u
    for u in available:
        if u.startswith('WITCH_'):
            return u
    return 'GOLD'

def choose_actions_smart(player, round_no, strategy):
    n = player.basic_workers_total
    actions = []
    strat = STRATEGIES[strategy]
    expected_wage = calc_expected_wage(player, round_no)
    gold_needed = expected_wage - player.gold

    for _ in range(n):
        if strategy == 'CONSERVATIVE':
            actions.append('TRADE')
        elif strategy == 'VP_AGGRESSIVE':
            if gold_needed > 0 and actions.count('TRADE') == 0:
                actions.append('TRADE')
                gold_needed -= (2 + player.trade_level)
            elif player.rng.random() < strat['hunt_ratio']:
                actions.append('HUNT')
            else:
                actions.append('TRADE')
        elif strategy == 'DEBT_AVOID':
            if gold_needed > 0:
                actions.append('TRADE')
                gold_needed -= (2 + player.trade_level)
            elif player.rng.random() < strat['hunt_ratio']:
                actions.append('HUNT')
            else:
                actions.append('TRADE')
        else:
            if player.rng.random() < strat['hunt_ratio']:
                actions.append('HUNT')
            else:
                actions.append('TRADE')
    return actions

def run_game(seed, initial_workers, smart_vp=False):
    rng = random.Random(seed)
    bot_rng = random.Random(seed + 100)

    players = [
        Player('P1', is_bot=True, rng=random.Random(seed+1), strategy=assign_random_strategy(bot_rng)),
        Player('P2', is_bot=True, rng=random.Random(seed+2), strategy=assign_random_strategy(bot_rng)),
        Player('P3', is_bot=True, rng=random.Random(seed+3), strategy=assign_random_strategy(bot_rng)),
        Player('P4', is_bot=True, rng=random.Random(seed+4), strategy=assign_random_strategy(bot_rng)),
    ]

    for p in players:
        p.basic_workers_total = initial_workers

    deal_fixed_sets(players, seed=seed, logger=None, max_rank=6, num_decks=4)
    total_debt = {p.name: 0 for p in players}

    for round_no in range(ROUNDS):
        revealed = reveal_upgrades(rng, REVEAL_UPGRADES)
        set_index = round_no % SETS_PER_GAME
        leader_index = round_no % len(players)

        for p in players:
            p.tricks_won_this_round = 0

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

        ranked = sorted(players, key=lambda x: (x.tricks_won_this_round, -players.index(x)), reverse=True)

        for p in ranked:
            if smart_vp:
                choice = choose_upgrade_smart(p, revealed, round_no, p.strategy)
            else:
                from main import choose_upgrade_or_gold
                choice = choose_upgrade_or_gold(p, revealed, round_no)
            if choice == 'GOLD':
                p.gold += TAKE_GOLD_INSTEAD
            elif choice in revealed:
                revealed.remove(choice)
                apply_upgrade(p, choice)
        ranked[-1].gold += RESCUE_GOLD_FOR_4TH

        for p in players:
            if smart_vp:
                actions = choose_actions_smart(p, round_no, p.strategy)
            else:
                from main import choose_actions_for_player
                actions = choose_actions_for_player(p, round_no)
            resolve_actions(p, actions)

        for p in players:
            before_vp = p.vp
            pay_wages_and_debt(p, round_no)
            if before_vp > p.vp:
                total_debt[p.name] += before_vp - p.vp

        for p in players:
            if p.basic_workers_new_hires > 0:
                p.basic_workers_total += p.basic_workers_new_hires
                p.basic_workers_new_hires = 0

    return [{
        'name': p.name,
        'strategy': p.strategy,
        'vp': p.vp,
        'debt_penalty': total_debt[p.name],
    } for p in sorted(players, key=lambda x: (x.vp, x.gold), reverse=True)]

def run_game_with_trade(seed, initial_workers, base_trade, smart_vp=True):
    """Run game with custom base TRADE value"""
    rng = random.Random(seed)
    bot_rng = random.Random(seed + 100)

    players = [
        Player('P1', is_bot=True, rng=random.Random(seed+1), strategy=assign_random_strategy(bot_rng)),
        Player('P2', is_bot=True, rng=random.Random(seed+2), strategy=assign_random_strategy(bot_rng)),
        Player('P3', is_bot=True, rng=random.Random(seed+3), strategy=assign_random_strategy(bot_rng)),
        Player('P4', is_bot=True, rng=random.Random(seed+4), strategy=assign_random_strategy(bot_rng)),
    ]

    for p in players:
        p.basic_workers_total = initial_workers

    deal_fixed_sets(players, seed=seed, logger=None, max_rank=6, num_decks=4)
    total_debt = {p.name: 0 for p in players}

    for round_no in range(ROUNDS):
        revealed = reveal_upgrades(rng, REVEAL_UPGRADES)
        set_index = round_no % SETS_PER_GAME
        leader_index = round_no % len(players)

        for p in players:
            p.tricks_won_this_round = 0

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

        ranked = sorted(players, key=lambda x: (x.tricks_won_this_round, -players.index(x)), reverse=True)

        for p in ranked:
            choice = choose_upgrade_smart(p, revealed, round_no, p.strategy)
            if choice == 'GOLD':
                p.gold += TAKE_GOLD_INSTEAD
            elif choice in revealed:
                revealed.remove(choice)
                apply_upgrade(p, choice)
        ranked[-1].gold += RESCUE_GOLD_FOR_4TH

        # Custom TRADE value
        for p in players:
            actions = choose_actions_smart(p, round_no, p.strategy)
            for a in actions:
                if a == 'TRADE':
                    p.gold += base_trade + p.trade_level  # base_trade instead of 2
                elif a == 'HUNT':
                    p.vp += 1 + p.hunt_level
                elif a == 'RECRUIT':
                    p.basic_workers_new_hires += 1

        for p in players:
            before_vp = p.vp
            pay_wages_and_debt(p, round_no)
            if before_vp > p.vp:
                total_debt[p.name] += before_vp - p.vp

        for p in players:
            if p.basic_workers_new_hires > 0:
                p.basic_workers_total += p.basic_workers_new_hires
                p.basic_workers_new_hires = 0

    return [{
        'name': p.name,
        'strategy': p.strategy,
        'vp': p.vp,
        'debt_penalty': total_debt[p.name],
    } for p in sorted(players, key=lambda x: (x.vp, x.gold), reverse=True)]


def run_game_with_start_gold(seed, initial_workers, start_gold):
    """Run game with custom starting gold"""
    rng = random.Random(seed)
    bot_rng = random.Random(seed + 100)

    players = [
        Player('P1', is_bot=True, rng=random.Random(seed+1), strategy=assign_random_strategy(bot_rng)),
        Player('P2', is_bot=True, rng=random.Random(seed+2), strategy=assign_random_strategy(bot_rng)),
        Player('P3', is_bot=True, rng=random.Random(seed+3), strategy=assign_random_strategy(bot_rng)),
        Player('P4', is_bot=True, rng=random.Random(seed+4), strategy=assign_random_strategy(bot_rng)),
    ]

    for p in players:
        p.basic_workers_total = initial_workers
        p.gold = start_gold  # Custom starting gold

    deal_fixed_sets(players, seed=seed, logger=None, max_rank=6, num_decks=4)
    total_debt = {p.name: 0 for p in players}

    for round_no in range(ROUNDS):
        revealed = reveal_upgrades(rng, REVEAL_UPGRADES)
        set_index = round_no % SETS_PER_GAME
        leader_index = round_no % len(players)

        for p in players:
            p.tricks_won_this_round = 0

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

        ranked = sorted(players, key=lambda x: (x.tricks_won_this_round, -players.index(x)), reverse=True)

        for p in ranked:
            choice = choose_upgrade_smart(p, revealed, round_no, p.strategy)
            if choice == 'GOLD':
                p.gold += TAKE_GOLD_INSTEAD
            elif choice in revealed:
                revealed.remove(choice)
                apply_upgrade(p, choice)
        ranked[-1].gold += RESCUE_GOLD_FOR_4TH

        for p in players:
            actions = choose_actions_smart(p, round_no, p.strategy)
            resolve_actions(p, actions)

        for p in players:
            before_vp = p.vp
            pay_wages_and_debt(p, round_no)
            if before_vp > p.vp:
                total_debt[p.name] += before_vp - p.vp

        for p in players:
            if p.basic_workers_new_hires > 0:
                p.basic_workers_total += p.basic_workers_new_hires
                p.basic_workers_new_hires = 0

    return [{
        'name': p.name,
        'strategy': p.strategy,
        'vp': p.vp,
        'debt_penalty': total_debt[p.name],
    } for p in sorted(players, key=lambda x: (x.vp, x.gold), reverse=True)]


def run_game_with_gold_vp(seed, initial_workers, start_gold, gold_per_vp):
    """Run game with gold-to-VP conversion at end"""
    rng = random.Random(seed)
    bot_rng = random.Random(seed + 100)

    players = [
        Player('P1', is_bot=True, rng=random.Random(seed+1), strategy=assign_random_strategy(bot_rng)),
        Player('P2', is_bot=True, rng=random.Random(seed+2), strategy=assign_random_strategy(bot_rng)),
        Player('P3', is_bot=True, rng=random.Random(seed+3), strategy=assign_random_strategy(bot_rng)),
        Player('P4', is_bot=True, rng=random.Random(seed+4), strategy=assign_random_strategy(bot_rng)),
    ]

    for p in players:
        p.basic_workers_total = initial_workers
        p.gold = start_gold

    deal_fixed_sets(players, seed=seed, logger=None, max_rank=6, num_decks=4)
    total_debt = {p.name: 0 for p in players}

    for round_no in range(ROUNDS):
        revealed = reveal_upgrades(rng, REVEAL_UPGRADES)
        set_index = round_no % SETS_PER_GAME
        leader_index = round_no % len(players)

        for p in players:
            p.tricks_won_this_round = 0

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

        ranked = sorted(players, key=lambda x: (x.tricks_won_this_round, -players.index(x)), reverse=True)

        for p in ranked:
            choice = choose_upgrade_smart(p, revealed, round_no, p.strategy)
            if choice == 'GOLD':
                p.gold += TAKE_GOLD_INSTEAD
            elif choice in revealed:
                revealed.remove(choice)
                apply_upgrade(p, choice)
        ranked[-1].gold += RESCUE_GOLD_FOR_4TH

        for p in players:
            actions = choose_actions_smart(p, round_no, p.strategy)
            resolve_actions(p, actions)

        for p in players:
            before_vp = p.vp
            pay_wages_and_debt(p, round_no)
            if before_vp > p.vp:
                total_debt[p.name] += before_vp - p.vp

        for p in players:
            if p.basic_workers_new_hires > 0:
                p.basic_workers_total += p.basic_workers_new_hires
                p.basic_workers_new_hires = 0

    # End game: convert gold to VP
    if gold_per_vp > 0:
        for p in players:
            bonus_vp = p.gold // gold_per_vp
            p.vp += bonus_vp

    return [{
        'name': p.name,
        'strategy': p.strategy,
        'vp': p.vp,
        'gold': p.gold,
        'debt_penalty': total_debt[p.name],
    } for p in sorted(players, key=lambda x: (x.vp, x.gold), reverse=True)]


if __name__ == "__main__":
    NUM_GAMES = 100
    print("=" * 65)
    print("GOLD-TO-VP CONVERSION TEST (2 Workers, 7G Start)")
    print("=" * 65)

    for gold_per_vp in [0, 3, 2]:
        label = "No conversion" if gold_per_vp == 0 else f"{gold_per_vp}G = 1VP"
        print(f"\n{'='*65}")
        print(f"=== {label} ===")
        print(f"{'='*65}")

        strat_stats = {s: {'vp': 0, 'debt': 0, 'wins': 0, 'top2': 0, 'count': 0, 'gold': 0} for s in STRATEGIES}

        for game_id in range(NUM_GAMES):
            results = run_game_with_gold_vp(game_id * 100, 2, 7, gold_per_vp)
            for i, r in enumerate(results):
                strat_stats[r['strategy']]['vp'] += r['vp']
                strat_stats[r['strategy']]['debt'] += r['debt_penalty']
                strat_stats[r['strategy']]['gold'] += r['gold']
                strat_stats[r['strategy']]['count'] += 1
                if i == 0:
                    strat_stats[r['strategy']]['wins'] += 1
                if i <= 1:
                    strat_stats[r['strategy']]['top2'] += 1

        print(f"{'Strategy':<12} | {'Win%':>5} | {'Top2%':>5} | {'AvgVP':>6} | {'AvgGold':>7}")
        print("-" * 52)
        for s in ['CONSERVATIVE', 'VP_AGGRESSIVE', 'BALANCED', 'DEBT_AVOID']:
            stats = strat_stats[s]
            if stats['count'] > 0:
                win_pct = stats['wins'] / stats['count'] * 100
                top2_pct = stats['top2'] / stats['count'] * 100
                avg_vp = stats['vp'] / stats['count']
                avg_gold = stats['gold'] / stats['count']
                name = STRATEGIES[s]['name_en'][:12]
                print(f"{name:<12} | {win_pct:>4.0f}% | {top2_pct:>4.0f}% | {avg_vp:>+5.1f} | {avg_gold:>7.1f}")
