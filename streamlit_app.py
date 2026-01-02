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

# ======= Mobile Responsive CSS =======
st.markdown("""
<style>
/* モバイル向けレスポンシブスタイル */
@media (max-width: 768px) {
    /* サイドバーを初期状態で閉じる */
    [data-testid="stSidebar"] {
        min-width: 0 !important;
    }

    /* メインコンテンツの余白を調整 */
    .main .block-container {
        padding: 1rem 0.5rem !important;
        max-width: 100% !important;
    }

    /* タイトルを小さく */
    h1 {
        font-size: 1.5rem !important;
    }

    /* サブヘッダーを小さく */
    h2, h3 {
        font-size: 1.2rem !important;
    }

    /* ボタンを大きく（タッチ操作向け） */
    .stButton > button {
        min-height: 48px !important;
        padding: 0.75rem 1rem !important;
        font-size: 1rem !important;
        width: 100% !important;
    }

    /* プライマリボタン */
    .stButton > button[kind="primary"] {
        min-height: 52px !important;
        font-size: 1.1rem !important;
    }

    /* カード選択ボタン */
    .card-button {
        min-width: 60px !important;
        min-height: 70px !important;
        font-size: 1.5rem !important;
    }

    /* チェックボックスのサイズ */
    .stCheckbox {
        padding: 0.5rem !important;
    }

    .stCheckbox label {
        font-size: 1.2rem !important;
    }

    /* セレクトボックスのサイズ */
    .stSelectbox > div > div {
        min-height: 48px !important;
    }

    /* ラジオボタンのサイズ */
    .stRadio > div {
        gap: 0.75rem !important;
    }

    .stRadio label {
        padding: 0.5rem !important;
        font-size: 1rem !important;
    }

    /* カラムの間隔を調整 */
    [data-testid="column"] {
        padding: 0.25rem !important;
    }

    /* テキスト入力を大きく */
    .stTextInput input {
        min-height: 48px !important;
        font-size: 1rem !important;
    }

    /* 数値入力を大きく */
    .stNumberInput input {
        min-height: 48px !important;
    }
}

/* タブレット向け調整 */
@media (max-width: 1024px) and (min-width: 769px) {
    .main .block-container {
        padding: 1rem 1rem !important;
    }
}

/* カード表示用スタイル */
.card-display {
    display: inline-flex;
    align-items: center;
    justify-content: center;
    padding: 0.5rem;
    margin: 0.25rem;
    border-radius: 8px;
    background: #f0f2f6;
    min-width: 50px;
    font-size: 1.2rem;
}

/* プレイヤーカード用スタイル */
.player-card {
    padding: 0.75rem;
    border-radius: 10px;
    background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
    color: white;
    margin-bottom: 0.5rem;
}

.player-card-bot {
    background: linear-gradient(135deg, #4a5568 0%, #2d3748 100%);
}

/* トリック履歴のスタイル */
.trick-result {
    padding: 0.5rem;
    margin: 0.25rem 0;
    border-left: 3px solid #667eea;
    background: #f7fafc;
}
</style>
""", unsafe_allow_html=True)


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
        st.text_input("パスワード", type="password", key="password")
        if st.button("ログイン", type="primary"):
            password_entered()
            st.rerun()
        st.caption("ゲームにアクセスするにはパスワードを入力してください。")
        return False

    # Password incorrect
    if not st.session_state["password_correct"]:
        st.text_input("パスワード", type="password", key="password")
        if st.button("ログイン", type="primary"):
            password_entered()
            st.rerun()
        st.error("パスワードが正しくありません。再度入力してください。")
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
        st.title("魔女協会 - ゲーム終了")
    else:
        st.title(f"魔女協会 - ラウンド {state['round_no'] + 1}/{ROUNDS}")
with col2:
    if st.button("新規ゲーム"):
        init_game()
        st.rerun()

# Player status - 2x2 grid for mobile
st.subheader("プレイヤー")
# 2行に分割（モバイルで見やすく）
for row in range(2):
    cols = st.columns(2)
    for col in range(2):
        i = row * 2 + col
        p = state["players"][i]
        with cols[col]:
            name = p["name"]
            is_human = not p["is_bot"]
            if is_human:
                name += " 👤"

            # コンパクトな表示
            st.markdown(f"**{name}**")
            # 金貨とVPを1行に
            st.markdown(f"💰 {p['gold']}G  |  🏆 {p['vp']}VP")
            # ワーカーと給料を1行に
            round_no = state["round_no"]
            if round_no < len(WAGE_CURVE):
                st.caption(f"👷 {p['workers']}人 (給料: {WAGE_CURVE[round_no]}G/{UPGRADED_WAGE_CURVE[round_no]}G)")
            else:
                st.caption(f"👷 {p['workers']}人")
            # 交易・討伐レベルをコンパクトに
            st.caption(f"交易Lv{p['trade_level']} / 討伐Lv{p['hunt_level']}")
            # Show recruit upgrade (タップで効果表示)
            if p.get("recruit_upgrade"):
                u = p["recruit_upgrade"]
                with st.popover(f"📦 {upgrade_name(u)}", help="タップで効果表示"):
                    st.write(upgrade_description(u))
            # Show witches (タップで効果表示)
            if p.get("witches"):
                witch_short = {"WITCH_BLACKROAD": "黒路", "WITCH_BLOODHUNT": "血誓", "WITCH_HERD": "群導",
                              "WITCH_RITUAL": "大儀式", "WITCH_BARRIER": "結界"}
                witch_cols = st.columns(len(p["witches"]))
                for wi, w in enumerate(p["witches"]):
                    with witch_cols[wi]:
                        with st.popover(f"🧙 {witch_short.get(w, w)}", help="タップで効果表示"):
                            st.markdown(f"**{upgrade_name(w)}**")
                            st.write(upgrade_description(w))
            # Show declaration info during trick phase
            if p.get("declared_tricks", 0) > 0 or p.get("tricks_won", 0) > 0:
                st.markdown(f"🎯 宣言 {p['declared_tricks']} / 獲得 {p['tricks_won']}")

# Revealed Upgrades display（2列表示でモバイル対応）
if state["revealed_upgrades"] and not state["game_over"]:
    with st.expander("📜 今ラウンドのアップグレード", expanded=False):
        upgrades = state["revealed_upgrades"]
        for row in range((len(upgrades) + 1) // 2):
            cols = st.columns(2)
            for col in range(2):
                idx = row * 2 + col
                if idx < len(upgrades):
                    u = upgrades[idx]
                    with cols[col]:
                        st.markdown(f"**{upgrade_name(u)}**")
                        st.caption(upgrade_description(u))

# Sealed Cards display（2x2グリッドでモバイル対応）
if state.get("sealed_by_player"):
    with st.expander("🔒 封印されたカード", expanded=False):
        players = list(state["sealed_by_player"].items())
        for row in range(2):
            cols = st.columns(2)
            for col in range(2):
                idx = row * 2 + col
                if idx < len(players):
                    pname, sealed_cards = players[idx]
                    with cols[col]:
                        st.markdown(f"**{pname}**")
                        st.text(", ".join(sealed_cards) if sealed_cards else "-")

# Trick History display（コンパクト表示）
if state["trick_history"]:
    with st.expander(f"🎴 トリック結果 ({len(state['trick_history'])}/{TRICKS_PER_ROUND})", expanded=True):
        for trick in state["trick_history"]:
            # 各トリックを1行にコンパクトに
            plays_display = []
            for pname, card in trick["plays"]:
                short_name = pname.replace("Player ", "P")
                plays_display.append(f"{short_name}:{card}")
            plays_str = " | ".join(plays_display)
            winner_short = trick['winner'].replace("Player ", "P")
            st.markdown(f"**T{trick['trick_no']}**: {plays_str} → 🏆 **{winner_short}**")

st.divider()

# Current phase display and input
if pending is not None:
    req_type = pending.type
    player = pending.player
    context = pending.context

    if req_type == "declaration":
        st.subheader(f"🎴 宣言フェーズ")
        hand = context["hand"]
        st.write("手札:")
        # 3列×2行のグリッドで表示（モバイル向け）
        for row in range(2):
            cols = st.columns(3)
            for col in range(3):
                idx = row * 3 + col
                if idx < len(hand):
                    with cols[col]:
                        st.markdown(f"<div style='text-align:center; font-size:1.5rem; padding:0.5rem; background:#f0f2f6; border-radius:8px; margin:0.25rem; color:#000;'>{card_display(hand[idx])}</div>", unsafe_allow_html=True)

        st.divider()
        declared = st.selectbox(
            "何トリック取る？",
            options=list(range(1, TRICKS_PER_ROUND + 1)),
            index=1
        )
        if st.button("🎯 宣言する", type="primary", use_container_width=True):
            game.provide_input(declared)
            run_until_input()
            st.rerun()

    elif req_type == "seal":
        st.subheader(f"🔒 封印フェーズ")
        hand = context["hand"]
        need_seal = context["need_seal"]
        st.info(f"📌 {need_seal}枚のカードを選んで封印（このラウンドはプレイ不可）")

        # 3列×2行のグリッドで表示（モバイル向け）
        selected_indices = []
        for row in range(2):
            cols = st.columns(3)
            for col in range(3):
                idx = row * 3 + col
                if idx < len(hand):
                    with cols[col]:
                        card = hand[idx]
                        # 大きなチェックボックス付きカード表示
                        if st.checkbox(card_display(card), key=f"seal_{idx}"):
                            selected_indices.append(idx)

        selected_count = len(selected_indices)
        st.divider()

        if selected_count != need_seal:
            st.warning(f"あと {need_seal - selected_count} 枚選んでください（選択中: {selected_count}枚）")

        if st.button("🔒 封印する", type="primary", disabled=selected_count != need_seal, use_container_width=True):
            sealed_cards = [hand[i] for i in selected_indices]
            game.provide_input(sealed_cards)
            run_until_input()
            st.rerun()

    elif req_type == "choose_card":
        st.subheader(f"🃏 カードを選択")

        # リード情報を目立つように表示
        lead = context["lead_card"]
        if lead:
            if lead.is_trump():
                st.info(f"🌟 リード: 切り札{lead.rank}")
            else:
                suit_emoji = {"Spade": "♠", "Heart": "♥", "Diamond": "♦", "Club": "♣"}
                st.info(f"{suit_emoji.get(lead.suit, '')} リード: {lead.suit}（マストフォロー）")
        else:
            st.info("📢 あなたがリードです（切り札でリード不可）")

        # 既出のカードを表示
        plays = context["plays_so_far"]
        if plays:
            st.write("既出:")
            # 2列で表示
            play_cols = st.columns(min(len(plays), 2))
            for i, (pname, card_str) in enumerate(plays):
                with play_cols[i % 2]:
                    st.markdown(f"**{pname}**: {card_str}")

        st.divider()
        hand = context["hand"]
        legal = context["legal"]

        st.write("カードを選んでプレイ:")
        # 2列×2行のグリッド（残り手札は最大4枚）
        num_cards = len(hand)
        cols_per_row = 2
        rows = (num_cards + cols_per_row - 1) // cols_per_row
        for row in range(rows):
            cols = st.columns(cols_per_row)
            for col in range(cols_per_row):
                idx = row * cols_per_row + col
                if idx < num_cards:
                    card = hand[idx]
                    with cols[col]:
                        display_str = card_display(card)
                        is_legal = card in legal
                        if is_legal:
                            if st.button(display_str, key=f"card_{idx}", type="primary", use_container_width=True):
                                game.provide_input(card)
                                run_until_input()
                                st.rerun()
                        else:
                            st.button(display_str, key=f"card_{idx}", disabled=True, use_container_width=True)

    elif req_type == "upgrade":
        st.subheader(f"📜 報酬を選択")
        available = context["available"]

        st.info("トリック獲得順に選択できます")

        # 各アップグレードをボタンで選択（タップしやすく）
        for u in available:
            col1, col2 = st.columns([3, 1])
            with col1:
                st.markdown(f"**{upgrade_name(u)}**")
                st.caption(upgrade_description(u))
            with col2:
                if st.button("選択", key=f"upgrade_{u}", use_container_width=True):
                    game.provide_input(u)
                    run_until_input()
                    st.rerun()

        st.divider()
        # 金貨オプション
        gold_amount = game.config.take_gold_instead
        col1, col2 = st.columns([3, 1])
        with col1:
            st.markdown(f"**💰 {gold_amount} 金貨を取る**")
            st.caption("アップグレードを取らない")
        with col2:
            if st.button("選択", key="upgrade_gold", use_container_width=True):
                game.provide_input("GOLD")
                run_until_input()
                st.rerun()

    elif req_type == "worker_actions":
        st.subheader(f"👷 ワーカー配置")
        num_workers = context["num_workers"]
        can_use_ritual = context.get("can_use_ritual", False)

        st.info(f"{num_workers}人のワーカーにアクションを割り当て")

        # アクションの説明
        action_info = {
            "TRADE": "💰 交易（金貨を獲得）",
            "HUNT": "⚔️ 討伐（VPを獲得）",
            "RECRUIT": "🧑‍🤝‍🧑 雇用（次ラウンドからワーカー+1）"
        }

        actions = []
        for i in range(num_workers):
            st.markdown(f"**ワーカー {i+1}**")
            # ラジオボタンで横並び（モバイルでタップしやすく）
            action = st.radio(
                f"ワーカー{i+1}のアクション",
                options=ACTIONS,
                format_func=lambda x: action_info.get(x, x),
                key=f"worker_{i}",
                horizontal=True,
                label_visibility="collapsed"
            )
            actions.append(action)

        # WITCH_RITUAL: 追加アクション
        ritual_action = None
        if can_use_ritual:
            st.divider()
            st.markdown("🔮 **《大儀式の執行者》** - 追加アクション実行可能")
            use_ritual = st.checkbox("追加アクションを実行する", key="use_ritual")
            if use_ritual:
                ritual_action = st.radio(
                    "追加で実行するアクション:",
                    options=ACTIONS,
                    format_func=lambda x: action_info.get(x, x),
                    key="ritual_action",
                    horizontal=True
                )

        st.divider()
        if st.button("✅ アクション確定", type="primary", use_container_width=True):
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
        st.subheader("🏁 最終結果")
        # Get sorted players
        sorted_players = sorted(
            state["players"],
            key=lambda p: (p["vp"], p["gold"]),
            reverse=True
        )
        for i, p in enumerate(sorted_players, start=1):
            medal = {1: "🥇", 2: "🥈", 3: "🥉"}.get(i, "  ")
            is_human = not p["is_bot"]
            player_marker = " 👤" if is_human else ""
            # カードスタイルで表示
            st.markdown(f"""
            <div style="padding:0.75rem; margin:0.5rem 0; border-radius:10px;
                        background: {'linear-gradient(135deg, #ffd700 0%, #ffb347 100%)' if i == 1 else '#f0f2f6'};">
                <span style="font-size:1.5rem;">{medal}</span>
                <strong>{i}位 {p['name']}{player_marker}</strong><br>
                🏆 {p['vp']}VP  |  💰 {p['gold']}G
            </div>
            """, unsafe_allow_html=True)

        st.divider()
        if st.button("🔄 もう一度プレイ", type="primary", use_container_width=True):
            init_game()
            st.rerun()
    else:
        st.info(f"フェーズ: {state['phase']}")

# Game log
st.divider()
with st.expander("ゲームログ", expanded=False):
    for msg in reversed(state["log"]):
        st.text(msg)
