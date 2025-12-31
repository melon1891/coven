#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Streamlit GUI for 魔女協会 card game.
Run with: uv run streamlit run streamlit_app.py
"""

import streamlit as st
import random
from main import (
    GameEngine, Card, ROUNDS, TRICKS_PER_ROUND, CARDS_PER_SET,
    ACTIONS, TAKE_GOLD_INSTEAD, upgrade_name, upgrade_description, legal_cards,
    WAGE_CURVE, UPGRADED_WAGE_CURVE
)

st.set_page_config(page_title="coven", layout="wide")

# Sidebar - Rules Menu
with st.sidebar:
    st.header("📖 メニュー")

    with st.expander("🎴 ゲーム概要", expanded=False):
        st.markdown("""
        **魔女協会** は、トリックテイキングとワーカープレイスメントを組み合わせた
        魔女ギルドをテーマにしたカードゲームです。

        - **プレイヤー**: 4人（あなた + Bot 3人）
        - **ラウンド数**: 4ラウンド
        - **勝利条件**: 最終的に最も多くのVP（勝利点）を獲得
        """)

    with st.expander("🃏 トリックテイキング", expanded=False):
        st.markdown("""
        **各ラウンドの流れ:**

        1. **宣言フェーズ**: 6枚の手札を見て、獲得トリック数を宣言（0〜4）
        2. **シールフェーズ**: 2枚を封印（使用不可に）
        3. **トリックフェーズ**: 残り4枚で4回のトリックを行う

        **トリックのルール:**
        - リードスートをフォロー必須（持っていれば）
        - リードスートの最高ランクが勝利
        - 宣言通りのトリック数を獲得すると **+1 VP** ボーナス

        **🌟 切り札カード:**
        - 1〜4の数字がついた特殊カード（4枚）
        - リードスートをフォローできない時のみ使用可能
        - 切り札でリードすることはできない
        - 切り札 > 通常カード、切り札同士は数字が大きい方が勝ち
        """)

    with st.expander("🏆 アップグレード選択", expanded=False):
        st.markdown("""
        トリック終了後、獲得トリック数の多い順にアップグレードを選択。

        **アップグレード種類:**
        - **交易拠点 改善**: TRADE収益 +1金（最大Lv2）
        - **魔物討伐 改善**: HUNT収益 +1VP（最大Lv2）
        - **集団育成計画**: 雇用時に2人雇える
        - **育成負担軽減の護符**: 雇用ターンの給料軽減
        - **永続魔女**: タイブレーク時に有利

        アップグレードを取らず **2金** を得ることも可能。
        4位のプレイヤーには救済として **+2金**。
        """)

    with st.expander("👷 ワーカープレイスメント", expanded=False):
        st.markdown("""
        各ワーカーに1つのアクションを割り当て:

        | アクション | 効果 |
        |-----------|------|
        | **TRADE** | 金貨を獲得（2 + Trade Level） |
        | **HUNT** | VPを獲得（1 + Hunt Level） |
        | **RECRUIT** | 見習いを雇用（次ラウンドから稼働） |

        **給料支払い:**
        - ラウンド終了時、全ワーカーに給料を支払う
        - 初期ワーカー給料: R1=1, R2=1, R3=2, R4=2
        - 雇用ワーカー給料: R1=1, R2=2, R3=3, R4=4
        - 金が不足すると段階的ペナルティ（1-3金:-1VP, 4-6金:-2VP, 7+:-3VP上限）
        """)

    with st.expander("🎯 攻略のヒント", expanded=False):
        st.markdown("""
        - 宣言ボーナス（+1VP）を狙おう。確実に取れる数を宣言
        - 序盤はTRADEで資金を確保
        - ワーカー雇用は給料コストとのバランスを考慮
        - アップグレードの優先度を考えてトリックを狙おう
        - 負債ペナルティは段階的（上限-3VP）なので多少のリスクは取れる
        """)

    with st.expander("🧙 魔女カード一覧", expanded=False):
        st.markdown("""
        **《黒路の魔女》** - 交易・供給
        > TRADEを行うたび、追加で+1金
        > *かつて閉ざされた交易路を、魔法で「通れるもの」に変えた魔女。*

        ---
        **《血誓の討伐官》** - 魔物討伐・VP加速
        > HUNTを行うたび、追加で+1VP
        > *討伐の成功は、必ず誓約と引き換えに訪れる。*

        ---
        **《群導の魔女》** - 見習い・雇用支援
        > 見習いを雇用したラウンド、給料合計-1
        > *見習いたちは彼女の合図ひとつで動く。*

        ---
        **《大儀式の執行者》** - 爆発力・借金前提
        > 各ラウンド1回、選んだ基本アクションをもう一度実行
        > *協会が「許可した」時にのみ執り行われる儀式。*

        ---
        **《巡察の魔女》** - 柔軟性・事故回避
        > 各ラウンド1回、自分のアクションを別の基本アクションに変更可能
        > *村を「視察」していると彼女は言う。*

        ---
        **《結界織りの魔女》** - 防衛・条件付きVP
        > 各ラウンド最初にHUNTを行った場合、追加で+1VP
        > *結界は村を守る。同時に、外へ出ることも難しくする。*
        """)

    st.divider()
    st.caption("魔女協会 v0.1")


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
    """Parse card string like 'S13' or 'T01' to Card object."""
    suit_map = {"S": "Spade", "H": "Heart", "D": "Diamond", "C": "Club", "T": "Trump"}
    suit = suit_map[s[0]]
    rank = int(s[1:])
    return Card(suit, rank)


def card_display(card: Card) -> str:
    """Return formatted display string for a card with emoji."""
    if card.is_trump():
        return f"🌟{card.rank}"
    suit_emoji = {"Spade": "♠", "Heart": "♥", "Diamond": "♦", "Club": "♣"}
    return f"{suit_emoji[card.suit]}{card.rank}"


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
        st.title("魔女協会 - Game Over")
    else:
        st.title(f"魔女協会 - Round {state['round_no'] + 1}/{ROUNDS}")
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
        # 給料単価表示
        round_no = state["round_no"]
        if round_no < len(WAGE_CURVE):
            st.text(f"Wage: {WAGE_CURVE[round_no]}G / {UPGRADED_WAGE_CURVE[round_no]}G")
        st.text(f"Trade Lv{p['trade_level']} Hunt Lv{p['hunt_level']}")
        # Show recruit upgrade
        if p.get("recruit_upgrade"):
            upgrade_short = {"RECRUIT_DOUBLE": "雇用×2", "RECRUIT_WAGE_DISCOUNT": "給料軽減"}.get(p["recruit_upgrade"], "")
            st.text(f"📦 {upgrade_short}")
        # Show witches
        if p.get("witches"):
            witch_names = {"WITCH_BLACKROAD": "黒路", "WITCH_BLOODHUNT": "血誓", "WITCH_HERD": "群導",
                          "WITCH_RITUAL": "大儀式", "WITCH_BARRIER": "結界"}
            witch_display = ", ".join(witch_names.get(w, w) for w in p["witches"])
            st.text(f"🧙 {witch_display}")
        # Show declaration info during trick phase
        if p.get("declared_tricks", 0) > 0 or p.get("tricks_won", 0) > 0:
            st.text(f"宣言: {p['declared_tricks']} / 獲得: {p['tricks_won']}")

# Revealed Upgrades display
if state["revealed_upgrades"] and not state["game_over"]:
    st.subheader("今ラウンドのアップグレード")
    upgrade_cols = st.columns(len(state["revealed_upgrades"]))
    for i, u in enumerate(state["revealed_upgrades"]):
        with upgrade_cols[i]:
            st.markdown(
                f'<span title="{upgrade_description(u)}" style="cursor:help; '
                f'border-bottom:1px dotted #666;">📜 {upgrade_name(u)}</span>',
                unsafe_allow_html=True
            )

# Sealed Cards display
if state.get("sealed_by_player"):
    st.subheader("封印されたカード")
    sealed_cols = st.columns(len(state["sealed_by_player"]))
    for i, (pname, sealed_cards) in enumerate(state["sealed_by_player"].items()):
        with sealed_cols[i]:
            st.markdown(f"**{pname}**")
            st.text(", ".join(sealed_cards) if sealed_cards else "-")

# Trick History display
if state["trick_history"]:
    st.subheader(f"トリック結果 ({len(state['trick_history'])}/{TRICKS_PER_ROUND})")
    for trick in state["trick_history"]:
        plays_str = " | ".join(f"{pname}:{card}" for pname, card in trick["plays"])
        winner_mark = "🏆"
        st.markdown(f"**Trick {trick['trick_no']}**: {plays_str} → {winner_mark} **{trick['winner']}**")

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
                st.markdown(f"**{card_display(card)}**")

        declared = st.selectbox(
            "何トリック取る？",
            options=list(range(1, TRICKS_PER_ROUND + 1)),
            index=1
        )
        if st.button("宣言", type="primary"):
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
            if lead.is_trump():
                st.write(f"Lead: **🌟切り札{lead.rank}**")
            else:
                st.write(f"Lead suit: **{lead.suit}** (must follow if possible)")
        else:
            st.write("You are leading this trick. (Cannot lead with trump)")

        hand = context["hand"]
        legal = context["legal"]
        legal_strs = [str(c) for c in legal]

        st.write("Your hand:")
        card_cols = st.columns(len(hand))
        for i, card in enumerate(hand):
            with card_cols[i]:
                display_str = card_display(card)
                is_legal = card in legal
                if is_legal:
                    if st.button(display_str, key=f"card_{i}", type="primary"):
                        game.provide_input(card)
                        run_until_input()
                        st.rerun()
                else:
                    st.button(display_str, key=f"card_{i}", disabled=True)

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
        can_use_ritual = context.get("can_use_ritual", False)

        st.write(f"Assign actions for your {num_workers} workers:")
        actions = []
        for i in range(num_workers):
            action = st.selectbox(
                f"Worker {i+1}:",
                options=ACTIONS,
                key=f"worker_{i}"
            )
            actions.append(action)

        # WITCH_RITUAL: 追加アクション
        ritual_action = None
        if can_use_ritual:
            st.divider()
            st.markdown("🔮 **《大儀式の執行者》** - 追加アクション実行可能")
            use_ritual = st.checkbox("追加アクションを実行する", key="use_ritual")
            if use_ritual:
                ritual_action = st.selectbox(
                    "追加で実行するアクション:",
                    options=ACTIONS,
                    key="ritual_action"
                )

        if st.button("Confirm Actions", type="primary"):
            response = {
                "actions": actions,
                "ritual_action": ritual_action,
            }
            game.provide_input(response)
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
