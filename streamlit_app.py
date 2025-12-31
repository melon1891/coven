#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Streamlit GUI for Witch ASC card game.
Run with: uv run streamlit run streamlit_app.py
"""

import streamlit as st
import random
from main import (
    GameEngine, Card, ROUNDS, TRICKS_PER_ROUND, CARDS_PER_SET,
    ACTIONS, TAKE_GOLD_INSTEAD, upgrade_name, legal_cards
)

st.set_page_config(page_title="Witch ASC", layout="wide")


def init_game():
    """Initialize a new game."""
    seed = random.randint(1, 10000)
    st.session_state.game = GameEngine(seed=seed)
    st.session_state.awaiting_input = False
    # Run until first human input is needed
    run_until_input()


def run_until_input():
    """Run game steps until human input is needed or game ends."""
    game = st.session_state.game
    while True:
        if game.get_pending_input() is not None:
            st.session_state.awaiting_input = True
            break
        if not game.step():
            # Game ended
            st.session_state.awaiting_input = False
            break


def parse_card(s: str) -> Card:
    """Parse card string like 'S13' to Card object."""
    suit_map = {"S": "Spade", "H": "Heart", "D": "Diamond", "C": "Club"}
    suit = suit_map[s[0]]
    rank = int(s[1:])
    return Card(suit, rank)


# Initialize session state
if "game" not in st.session_state:
    init_game()

game = st.session_state.game
state = game.get_state()
pending = game.get_pending_input()

# Header
col1, col2 = st.columns([4, 1])
with col1:
    if state["game_over"]:
        st.title("Witch ASC - Game Over")
    else:
        st.title(f"Witch ASC - Round {state['round_no'] + 1}/{ROUNDS}")
with col2:
    if st.button("New Game"):
        init_game()
        st.rerun()

# Player status
st.subheader("Players")
cols = st.columns(4)
for i, p in enumerate(state["players"]):
    with cols[i]:
        name = p["name"]
        if not p["is_bot"]:
            name += " (You)"
        st.markdown(f"**{name}**")
        st.text(f"Gold: {p['gold']}  VP: {p['vp']}")
        st.text(f"Workers: {p['workers']}")
        st.text(f"Trade Lv{p['trade_level']} Hunt Lv{p['hunt_level']}")

st.divider()

# Current phase display and input
if pending is not None:
    req_type = pending.type
    player = pending.player
    context = pending.context

    if req_type == "declaration":
        st.subheader(f"Declaration Phase - {player.name}")
        hand = context["hand"]
        st.write("Your hand:")
        hand_cols = st.columns(len(hand))
        for i, card in enumerate(hand):
            with hand_cols[i]:
                suit_emoji = {"Spade": "♠", "Heart": "♥", "Diamond": "♦", "Club": "♣"}
                st.markdown(f"**{suit_emoji[card.suit]}{card.rank}**")

        declared = st.slider(
            "How many tricks will you win?",
            min_value=0,
            max_value=TRICKS_PER_ROUND,
            value=2
        )
        if st.button("Declare", type="primary"):
            game.provide_input(declared)
            run_until_input()
            st.rerun()

    elif req_type == "seal":
        st.subheader(f"Seal Phase - {player.name}")
        hand = context["hand"]
        need_seal = context["need_seal"]
        st.write(f"Select {need_seal} cards to seal (they won't be playable this round):")

        hand_strs = [str(c) for c in hand]
        selected = st.multiselect(
            "Cards to seal:",
            options=hand_strs,
            max_selections=need_seal
        )

        if st.button("Seal Cards", type="primary", disabled=len(selected) != need_seal):
            sealed_cards = [parse_card(s) for s in selected]
            game.provide_input(sealed_cards)
            run_until_input()
            st.rerun()

    elif req_type == "choose_card":
        st.subheader(f"Trick Phase - {player.name}'s Turn")

        # Show plays so far
        plays = context["plays_so_far"]
        if plays:
            st.write("Played so far:")
            play_cols = st.columns(len(plays))
            for i, (pname, card_str) in enumerate(plays):
                with play_cols[i]:
                    st.markdown(f"**{pname}**: {card_str}")

        lead = context["lead_card"]
        if lead:
            st.write(f"Lead suit: **{lead.suit}** (must follow if possible)")
        else:
            st.write("You are leading this trick.")

        hand = context["hand"]
        legal = context["legal"]
        legal_strs = [str(c) for c in legal]

        st.write("Your hand:")
        card_cols = st.columns(len(hand))
        for i, card in enumerate(hand):
            with card_cols[i]:
                card_str = str(card)
                is_legal = card in legal
                if is_legal:
                    if st.button(card_str, key=f"card_{i}", type="primary"):
                        game.provide_input(card)
                        run_until_input()
                        st.rerun()
                else:
                    st.button(card_str, key=f"card_{i}", disabled=True)

    elif req_type == "upgrade":
        st.subheader(f"Upgrade Selection - {player.name}")
        available = context["available"]

        st.write("Choose your reward:")
        options = [f"{upgrade_name(u)} [{u}]" for u in available]
        options.append(f"Take {TAKE_GOLD_INSTEAD} Gold instead")

        choice = st.radio("Select:", options, index=0)

        if st.button("Confirm", type="primary"):
            if choice.startswith("Take"):
                game.provide_input("GOLD")
            else:
                # Extract upgrade key from choice
                idx = options.index(choice)
                game.provide_input(available[idx])
            run_until_input()
            st.rerun()

    elif req_type == "worker_actions":
        st.subheader(f"Worker Placement - {player.name}")
        num_workers = context["num_workers"]

        st.write(f"Assign actions for your {num_workers} workers:")
        actions = []
        for i in range(num_workers):
            action = st.selectbox(
                f"Worker {i+1}:",
                options=ACTIONS,
                key=f"worker_{i}"
            )
            actions.append(action)

        if st.button("Confirm Actions", type="primary"):
            game.provide_input(actions)
            run_until_input()
            st.rerun()

else:
    # No pending input - show current phase info
    if state["game_over"]:
        st.subheader("Final Results")
        # Get sorted players
        sorted_players = sorted(
            state["players"],
            key=lambda p: (p["vp"], p["gold"]),
            reverse=True
        )
        for i, p in enumerate(sorted_players, start=1):
            medal = {1: "🥇", 2: "🥈", 3: "🥉"}.get(i, "")
            st.write(f"{medal} **{i}. {p['name']}** - VP: {p['vp']}, Gold: {p['gold']}")
    else:
        st.info(f"Phase: {state['phase']}")

# Game log
st.divider()
with st.expander("Game Log", expanded=False):
    for msg in reversed(state["log"]):
        st.text(msg)
