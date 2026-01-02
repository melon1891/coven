#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Streamlit GUI for 魔女協会 card game.
Run with: uv run streamlit run streamlit_app.py
"""

import streamlit as st
import random
from main import (
    GameEngine, GameConfig, Card, ROUNDS, TRICKS_PER_ROUND, CARDS_PER_SET,
    ACTIONS, TAKE_GOLD_INSTEAD, upgrade_name, upgrade_description, legal_cards,
    WAGE_CURVE, UPGRADED_WAGE_CURVE, STRATEGIES,
    START_GOLD, INITIAL_WORKERS, DECLARATION_BONUS_VP,
    DEBT_PENALTY_MULTIPLIER, DEBT_PENALTY_CAP, GOLD_TO_VP_RATE, RESCUE_GOLD_FOR_4TH
)

st.set_page_config(page_title="coven", layout="wide")


# ======= Authentication =======
def check_password():
    """Returns True if the user has entered the correct password."""

    def password_entered():
        """Checks whether a password entered by the user is correct."""
        if st.session_state["password"] == st.secrets["auth"]["password"]:
            st.session_state["password_correct"] = True
            del st.session_state["password"]  # Don't store password
        else:
            st.session_state["password_correct"] = False

    # First run or password not yet checked
    if "password_correct" not in st.session_state:
        st.text_input("Password", type="password", key="password")
        if st.button("Login", type="primary"):
            password_entered()
            st.rerun()
        st.caption("Enter the password to access the game.")
        return False

    # Password incorrect
    if not st.session_state["password_correct"]:
        st.text_input("Password", type="password", key="password")
        if st.button("Login", type="primary"):
            password_entered()
            st.rerun()
        st.error("Password incorrect. Please try again.")
        return False

    # Password correct
    return True


# Check authentication before showing the app
if not check_password():
    st.stop()

# Sidebar - Rules Menu
with st.sidebar:
    st.header("📖 メニュー")

    with st.expander("🌙 世界観", expanded=False):
        st.markdown("""
## 灰燼の時代（The Age of Ashes）

*かつて、空は青く、大地は豊かだった。*
*しかしあの日、世界は終わりを告げた。*

**災厄**が訪れた。
名もなき闇が大地を覆い、作物は枯れ、獣は狂い、人々は希望を失った。

---

### 残された者たち

あなたは小さな村を預かる**村長**。
かろうじて生き延びた民を守り、明日へと繋ぐ責務を負う。

村には一人の**見習い魔女**がいる。
未熟ながらも、その小さな炎は災厄の闇を払う唯一の光。
だが、それだけでは足りない。
いつも、何かが足りない。

---

### 魔女協会（The Witch Association）

世界の裏側で、**魔女協会**は息づいている。
古の知恵を継ぐ者たち。災厄に抗う力を持つ者たち。

彼女たちは各村に手を差し伸べる。
薬草を、呪文を、時には一人前の魔女を。

*「我らは助けよう」*と彼女たちは囁く。
*「だが、すべての村を救うことはできない」*

---

### 支援会議

季節ごとに、村長たちは**魔女協会の支援会議**へと招かれる。

限られた支援を、どの村が受けるのか。
会議室では言葉と思惑が交錯し、腹の探り合いが繰り広げられる。

より多くの信任を勝ち取った村長から、支援を選ぶ権利が与えられる。
そして、己の立場を正しく見極めた者には、さらなる信頼の証が。

---

### 村の備え

会議から戻れば、村長としての本当の仕事が待っている。

**交易**で物資を集め、**狩猟**で食料を確保し、**人手**を増やす。
限られた人員を、どこに割り振るか。
その決断が、村の命運を左右する。

---

### 大災厄の予兆

魔女たちは告げる。

*「季節が一巡したとき、**大災厄**が訪れるであろう」*

今の災厄はまだ序章に過ぎない。
真の闇が来る前に備えなければ。
**例え誰を蹴落としたとしても。**

――
*残された時間はあまり多くない*
        """)

    with st.expander("🎴 ゲーム概要", expanded=False):
        st.markdown("""
        **魔女協会** は、トリックテイキングとワーカープレイスメントを組み合わせた
        戦略カードゲームです。

        - **プレイヤー**: 4人（あなた + Bot 3人）
        - **ラウンド数**: 4ラウンド
        - **勝利条件**: 最終的に最も多くの **VP（勝利点）** を獲得

        **カード構成:**
        - 通常カード: 4スート（♠♥♦♣）× ランク1〜6 × 4セット
        - 切り札カード: 🌟1〜4（各2枚、計8枚）
        """)

    with st.expander("🃏 トリックテイキング", expanded=False):
        st.markdown("""
        **各ラウンドの流れ:**

        1. **宣言フェーズ**: 6枚の手札を見て、獲得トリック数を宣言（1〜4）
        2. **シールフェーズ**: 2枚を封印（そのラウンドは使用不可）
        3. **トリックフェーズ**: 残り4枚で4回のトリックを行う

        **トリックのルール:**
        - リードスートをフォロー必須（持っていれば）
        - リードスートの最高ランクが勝利
        - **同ランク時**: 親（リード）に近いプレイヤーが勝利
        - 宣言通りのトリック数を獲得すると **+1 VP** ボーナス

        **🌟 切り札カード（計8枚: 1〜4が各2枚）:**
        - リードスートをフォローできない時のみ使用可能
        - 切り札でリードすることはできない
        - 切り札 > 通常カード
        - 切り札同士は数字が大きい方が勝ち
        - **同ランクの切り札**: 親に近い方が勝利
        """)

    with st.expander("🏆 アップグレード選択", expanded=False):
        st.markdown("""
        トリック終了後、**獲得トリック数の多い順**にアップグレードを選択。

        **アップグレード種類:**
        | 名前 | 効果 |
        |------|------|
        | 交易拠点 改善 | TRADE収益 +1金（最大Lv2） |
        | 魔物討伐 改善 | HUNT収益 +1VP（最大Lv2） |
        | 見習い魔女派遣 | 即座にワーカー+2（即行動・給料発生） |
        | 育成負担軽減の護符 | 雇用ターンの給料軽減 |
        | 魔女カード | 特殊能力を獲得 |

        - アップグレードを取らず **2金** を得ることも可能
        - **4位のプレイヤー**: 救済として **+2金** を獲得
        """)

    with st.expander("👷 ワーカープレイスメント", expanded=False):
        st.markdown("""
        各ワーカーに1つのアクションを割り当て:

        | アクション | 効果 |
        |-----------|------|
        | **TRADE** | 金貨を獲得（2 + Trade Level） |
        | **HUNT** | VPを獲得（1 + Hunt Level） |
        | **RECRUIT** | 見習いを雇用（次ラウンドから稼働） |

        **給料支払い（ラウンド終了時）:**
        | ラウンド | 初期ワーカー | 雇用ワーカー |
        |---------|-------------|-------------|
        | R1 | 1金 | 1金 |
        | R2 | 1金 | 2金 |
        | R3 | 2金 | 3金 |
        | R4 | 2金 | 4金 |

        **負債ペナルティ（金不足時）:**
        - 1〜3金不足: -1 VP
        - 4〜6金不足: -2 VP
        - 7金以上不足: -3 VP（上限）
        """)

    with st.expander("🎯 攻略のヒント", expanded=False):
        st.markdown("""
        **序盤（R1-R2）:**
        - TRADEで資金を確保
        - 宣言ボーナス（+1VP）を確実に狙う

        **中盤（R2-R3）:**
        - アップグレードの優先度を考えてトリック数を調整
        - ワーカー雇用は給料コストとのバランスを考慮

        **終盤（R4）:**
        - 負債ペナルティは上限-3VPなので、リスクを取れる場面も
        - 最終ラウンドは雇用より直接VP獲得が有利

        **切り札の使い方:**
        - 切り札は「保険」として温存
        - 宣言を達成するための最後の手段に
        """)

    with st.expander("🧙 魔女カード一覧", expanded=False):
        st.markdown("""
        **《黒路の魔女》** - 交易強化
        > TRADEを行うたび、追加で+1金
        > *かつて閉ざされた交易路を、魔法で「通れるもの」に変えた魔女。*

        ---
        **《血誓の討伐官》** - 討伐強化
        > HUNTを行うたび、追加で+1VP
        > *討伐の成功は、必ず誓約と引き換えに訪れる。*

        ---
        **《群導の魔女》** - 雇用支援
        > 見習いを雇用したラウンド、給料合計-1
        > *見習いたちは彼女の合図ひとつで動く。*

        ---
        **《大儀式の執行者》** - アクション倍化
        > 各ラウンド1回、選んだ基本アクションをもう一度実行
        > *協会が「許可した」時にのみ執り行われる儀式。*

        ---
        **《結界織りの魔女》** - 条件付きVP
        > 各ラウンド最初にHUNTを行った場合、追加で+1VP
        > *結界は村を守る。同時に、外へ出ることも難しくする。*
        """)

    st.divider()
    st.header("⚙️ ゲーム設定")

    # 設定をsession_stateで管理
    if "game_config" not in st.session_state:
        st.session_state.game_config = {
            "start_gold": START_GOLD,
            "initial_workers": INITIAL_WORKERS,
            "declaration_bonus_vp": DECLARATION_BONUS_VP,
            "debt_penalty_multiplier": DEBT_PENALTY_MULTIPLIER,
            "debt_penalty_cap": DEBT_PENALTY_CAP,
            "gold_to_vp_rate": GOLD_TO_VP_RATE,
            "take_gold_instead": TAKE_GOLD_INSTEAD,
            "rescue_gold_for_4th": RESCUE_GOLD_FOR_4TH,
        }

    with st.expander("💰 初期リソース", expanded=False):
        st.session_state.game_config["start_gold"] = st.number_input(
            "初期金貨",
            min_value=0, max_value=20, value=st.session_state.game_config["start_gold"],
            help="ゲーム開始時の金貨数"
        )
        st.session_state.game_config["initial_workers"] = st.number_input(
            "初期ワーカー数",
            min_value=1, max_value=5, value=st.session_state.game_config["initial_workers"],
            help="ゲーム開始時のワーカー数"
        )

    with st.expander("🎯 トリックテイキング", expanded=False):
        st.session_state.game_config["declaration_bonus_vp"] = st.number_input(
            "宣言成功ボーナス(VP)",
            min_value=0, max_value=5, value=st.session_state.game_config["declaration_bonus_vp"],
            help="トリック数の宣言が的中した際のVPボーナス"
        )

    with st.expander("📜 アップグレード選択", expanded=False):
        st.session_state.game_config["take_gold_instead"] = st.number_input(
            "アップグレード辞退時の金貨",
            min_value=0, max_value=10, value=st.session_state.game_config["take_gold_instead"],
            help="アップグレードを取らない場合に得られる金貨"
        )
        st.session_state.game_config["rescue_gold_for_4th"] = st.number_input(
            "4位救済の金貨",
            min_value=0, max_value=10, value=st.session_state.game_config["rescue_gold_for_4th"],
            help="トリック最下位(4位)のプレイヤーが得る追加金貨"
        )

    with st.expander("💸 負債ペナルティ", expanded=False):
        st.session_state.game_config["debt_penalty_multiplier"] = st.number_input(
            "負債ペナルティ倍率",
            min_value=1, max_value=5, value=st.session_state.game_config["debt_penalty_multiplier"],
            help="給与未払い1金につき失うVP"
        )
        use_debt_cap = st.checkbox(
            "ペナルティ上限を設定",
            value=st.session_state.game_config["debt_penalty_cap"] is not None
        )
        if use_debt_cap:
            current_cap = st.session_state.game_config["debt_penalty_cap"] or 10
            st.session_state.game_config["debt_penalty_cap"] = st.number_input(
                "ペナルティ上限(VP)",
                min_value=1, max_value=20, value=current_cap,
                help="負債ペナルティの最大値"
            )
        else:
            st.session_state.game_config["debt_penalty_cap"] = None

    with st.expander("🏁 ゲーム終了時", expanded=False):
        st.session_state.game_config["gold_to_vp_rate"] = st.number_input(
            "金貨→VP変換レート",
            min_value=1, max_value=10, value=st.session_state.game_config["gold_to_vp_rate"],
            help="ゲーム終了時、この金貨数で1VPに変換"
        )

    # 現在の設定を表示
    with st.expander("📋 現在の設定値", expanded=False):
        config = st.session_state.game_config
        st.markdown(f"""
        - **初期金貨**: {config['start_gold']}G
        - **初期ワーカー**: {config['initial_workers']}人
        - **宣言ボーナス**: +{config['declaration_bonus_vp']}VP
        - **アップグレード辞退**: {config['take_gold_instead']}G
        - **4位救済**: +{config['rescue_gold_for_4th']}G
        - **負債ペナルティ**: -{config['debt_penalty_multiplier']}VP/金{' (上限' + str(config['debt_penalty_cap']) + 'VP)' if config['debt_penalty_cap'] else ''}
        - **金貨→VP**: {config['gold_to_vp_rate']}G = 1VP
        """)

    st.caption("※設定変更は次のNew Game開始時に反映されます")
    st.divider()
    st.caption("魔女協会 v0.1")


def init_game():
    """Initialize a new game with current settings."""
    seed = random.randint(1, 10000)

    # 設定をGameConfigオブジェクトに変換
    if "game_config" in st.session_state:
        cfg = st.session_state.game_config
        config = GameConfig(
            start_gold=cfg["start_gold"],
            initial_workers=cfg["initial_workers"],
            declaration_bonus_vp=cfg["declaration_bonus_vp"],
            debt_penalty_multiplier=cfg["debt_penalty_multiplier"],
            debt_penalty_cap=cfg["debt_penalty_cap"],
            gold_to_vp_rate=cfg["gold_to_vp_rate"],
            take_gold_instead=cfg["take_gold_instead"],
            rescue_gold_for_4th=cfg["rescue_gold_for_4th"],
        )
    else:
        config = GameConfig()

    st.session_state.game = GameEngine(seed=seed, config=config)
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
        else:
            # CPUの性格を表示
            if p.get("strategy_name"):
                name += f" [{p['strategy_name']}]"
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
            upgrade_short = {"RECRUIT_WAGE_DISCOUNT": "給料軽減"}.get(p["recruit_upgrade"], "")
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

        # チェックボックスで各カードを選択（同じカードが複数あっても対応可能）
        selected_indices = []
        cols = st.columns(len(hand))
        for i, card in enumerate(hand):
            with cols[i]:
                if st.checkbox(card_display(card), key=f"seal_{i}"):
                    selected_indices.append(i)

        selected_count = len(selected_indices)
        if selected_count != need_seal:
            st.warning(f"{need_seal}枚選択してください（現在: {selected_count}枚）")

        if st.button("Seal Cards", type="primary", disabled=selected_count != need_seal):
            sealed_cards = [hand[i] for i in selected_indices]
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
        gold_amount = game.config.take_gold_instead
        options.append(f"Take {gold_amount} Gold instead")

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
