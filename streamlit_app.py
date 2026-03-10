#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Streamlit GUI for 魔女協会 card game.
Run with: uv run streamlit run streamlit_app.py
"""

import streamlit as st
import random
import time
from main import (
    GameEngine, GameConfig, Card, ROUNDS, TRICKS_PER_ROUND, CARDS_PER_SET,
    ACTIONS, TAKE_GOLD_INSTEAD, upgrade_name, upgrade_description, legal_cards,
    WAGE_CURVE, STRATEGIES,
    START_GOLD, INITIAL_WORKERS, DECLARATION_BONUS_VP,
    DEBT_PENALTY_MULTIPLIER, DEBT_PENALTY_CAP, GOLD_TO_VP_RATE, RESCUE_GOLD_FOR_4TH,
    ALL_UPGRADES, DEFAULT_ENABLED_UPGRADES,
    GRACE_ENABLED, GRACE_VP_PER_N, GRACE_VP_AMOUNT,
    RECRUIT_COST,
    PERSONAL_TRADE_GOLD, PERSONAL_HUNT_VP, PERSONAL_PRAY_GRACE,
    PERSONAL_RITUAL_GRACE, PERSONAL_RITUAL_GOLD,
    SHARED_TRADE_GOLD, SHARED_HUNT_VP, SHARED_PRAY_GRACE,
    WITCH_NEGOTIATE_GRACE_COST, WITCH_NEGOTIATE_GOLD,
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
## 灰の時代（The Age of Ashes）

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
**魔女協会** は、トリックテイキングとワーカープレイスメントを組み合わせた戦略カードゲームです。

- **プレイヤー**: 4人（あなた + Bot 3人）
- **ラウンド数**: 6ラウンド
- **勝利条件**: 最終的に最も多くの **VP（勝利点）** を獲得

**カード構成:**
- 通常カード: 4スート（♠♥♦♣）× ランク1〜5 × 2セット（計80枚）
- 切り札カード: 🌟（数字なし、計2枚）
        """)

    with st.expander("📋 ラウンドの流れ", expanded=False):
        st.markdown("""
**各ラウンドは以下の6フェーズで進行します:**

### 1️⃣ カード配布
毎ラウンド山札をシャッフルし、各プレイヤーに5枚ずつ配布

### 2️⃣ アップグレード公開
今ラウンドで獲得可能なアップグレードが公開される
（ラウンド3は魔女カードが登場）

### 3️⃣ トリックテイキング
1. **宣言**: 手札を見て獲得目標トリック数を宣言（1〜4）
2. **公開封印**: 1枚を公開封印（このラウンドは使用不可、全員に公開）
3. **プレイ**: 残り4枚で4回のトリックを行う

### 4️⃣ アップグレード選択
獲得トリック数の多いプレイヤーから順にアップグレードを選択
- アップグレードは共有ボードに配置（全プレイヤーが使用可能）
- 他プレイヤーがあなたのスポットを使うと、所有者に+1金（銀行から）
- アップグレード辞退時は2金を獲得
- 4位のプレイヤーは救済として+2金 または +1恩寵を選択

### 5️⃣ ワーカープレイスメント
各ワーカーにアクションを割り当てて実行:
| アクション | 効果 |
|-----------|------|
| 交易 | 金貨を獲得（2 + 交易Level） |
| 討伐 | VPを獲得（1 + 討伐Level） |
| 雇用 | ワーカー+1（次ラウンドから稼働、上限5人） |
| 祈り | 恩寵を獲得（1 + 祈りLevel） |
| 儀式※ | 2恩寵 or 2金を選択（アップグレードで解放） |
| 共有スポット | 他プレイヤーのスポットも使用可（所有者に+1金） |

### 6️⃣ 給料支払い
初期ワーカーに給料を支払う（雇用ワーカーは取得時2金払済のため不要）
| ラウンド | 給料 |
|---------|------|
| R1-R2 | 1金/人 |
| R3-R5 | 2金/人 |
| R6 | 3金/人 |

**→ 6ラウンド終了後、最もVPの多いプレイヤーが勝利！**
        """)

    with st.expander("🃏 トリックテイキング詳細", expanded=False):
        st.markdown("""
**トリックの基本ルール:**
- リードスートをフォロー必須（持っていれば）
- リードスートの最高ランクが勝利
- **同ランク時**: 親（リード）に近いプレイヤーが勝利
- 宣言通りのトリック数を獲得すると **+1 VP** ボーナス

**🌟 切り札カード（計2枚、数字なし）:**
- リードスートをフォローできない時のみ使用可能
- 切り札でリードすることはできない
- 切り札 > 通常カード
- **複数の切り札が出た場合**: 親に近いプレイヤーが勝利
        """)

    with st.expander("🏆 アップグレード詳細", expanded=False):
        st.markdown("""
**アップグレード種類:**
| 名前 | 効果 |
|------|------|
| 交易拠点 改善 | TRADE収益 +2金（最大Lv1、2→4金） |
| 魔物討伐 改善 | HUNT収益 +1VP（最大Lv1、1→2VP） |
| 祈りの祭壇 強化 | PRAY恩寵獲得 +1（最大Lv2、Lv2で+2恩寵） |
| 儀式の祭壇 | RITUALアクション解放（2恩寵 or 2金 選択） |
| 魔女カード | 特殊能力を獲得（R3のみ） |

**選択ルール:**
- 獲得トリック数の多い順に選択
- アップグレードは**共有ボード**に配置（全プレイヤーが使用可能）
- 他プレイヤーがあなたのスポットを使うと、所有者に**+1金**（銀行から）
- アップグレードを取らずに **2金** を得ることも可能
- **4位のプレイヤー**: 救済として **+2金** または **+1恩寵** を選択
        """)

    with st.expander("👷 ワーカープレイスメント詳細", expanded=False):
        st.markdown("""
**基本アクション（レベルアップ対応）:**
| アクション | 基本 | Lv1 | Lv2 |
|-----------|------|-----|-----|
| **TRADE** | 2金 | 4金 | 6金 |
| **HUNT** | 1VP | 2VP | 3VP |
| **RECRUIT** | ワーカー+1 | - | - |
| **PRAY** | 1恩寵 | 2恩寵 | 3恩寵 |

**アップグレードで解放されるアクション（共有スポット）:**
| アクション | 解放条件 | 効果 |
|-----------|---------|------|
| **RITUAL** | 儀式の祭壇 | 2恩寵 or 2金（選択） |

※ アップグレードスポットは全プレイヤーが使用可能。他プレイヤーが使用すると所有者に+1金。

**雇用ワーカーの仕組み:**
- RECRUITで雇用（2金消費） → 次ラウンドから稼働

**負債ペナルティ（給料不足時）:**
| 不足額 | ペナルティ |
|-------|-----------|
| 1〜3金 | -1 VP |
| 4〜6金 | -2 VP |
| 7金以上 | -3 VP（上限） |
        """)

    with st.expander("✨ 恩寵システム", expanded=False):
        st.markdown("""
**恩寵ポイント**は魔女協会からの信頼度を表します。ゲーム終了時、まず余った金貨が恩寵に変換され（2金=1恩寵）、その後恩寵がVPに変換されます。

**恩寵の獲得方法:**
| 条件 | 獲得量 |
|------|--------|
| 祈りアクション（PRAY） | 1恩寵（Lv0）〜3恩寵（Lv2） |
| 儀式アクション（RITUAL※） | 2恩寵 or 2金（選択） |
| 宣言成功（ピタリ賞） | +1恩寵 |
| 宣言0成功 | +1恩寵 |
| トリテ0勝 | +1恩寵, +1金 |
| 4位救済（選択時） | +1恩寵 |
| 《祈祷の魔女》 | PRAY実行時 +1恩寵（追加） |

※ アップグレードで解放が必要

**恩寵の消費:**
- 手札交換（シール前）: 1恩寵消費で手札1枚をデッキトップと交換

**ゲーム終了時の変換:**
- 金貨→恩寵: 2金毎に1恩寵（先に適用）
- 恩寵→VP: 5恩寵毎に3VP（端数切り捨て）
        """)

    with st.expander("🎯 攻略のヒント", expanded=False):
        st.markdown("""
**序盤（R1-R2）:**
- TRADEで資金を確保し、給料に備える
- 宣言ボーナス（+1VP）を確実に狙う

**中盤（R3-R4）:**
- R3の魔女獲得を見据えてトリック数を調整
- ワーカー雇用は2金の初期コストを考慮
- アップグレード選択順位のためにトリック獲得を意識

**終盤（R5-R6）:**
- 負債ペナルティは上限-3VPなので、リスクを取れる場面も
- 最終ラウンドは雇用より直接VP獲得が有利
- 恩寵ポイントを5の倍数に近づけてVP変換を意識

**切り札の使い方:**
- 切り札（2枚、数字なし）は「保険」として温存
- 宣言を達成するための最後の手段に
- 同時に切り札が出た場合、親に近い方が勝利

**恩寵ポイント:**
- 5恩寵毎に3VP変換（多く貯めるほど有利）
- 祈り・儀式アクション、宣言成功、宣言0成功、0トリック等で獲得
        """)

    with st.expander("🧙 魔女カード一覧", expanded=False):
        st.markdown("""
**《黒路の魔女》** - パッシブ(交易スポット+1金)
> 交易スポット使用時、追加で+1金獲得
> *かつて閉ざされた交易路を、魔法で「通れるもの」に変えた魔女。*

---
**《血誓の討伐官》** - パッシブ(討伐スポット+1VP)
> 討伐スポット使用時、追加で+1VP獲得
> *討伐の成功は、必ず誓約と引き換えに訪れる。*

---
**《群導の魔女》** - 給料軽減（パッシブ）
> 毎ラウンド給料合計-1
> *見習いたちは彼女の合図ひとつで動く。*

---
**《交渉の魔女》** - 共有スポット(1恩寵→2金)
> 1恩寵を消費して2金獲得（他プレイヤーも使用可、使用時所有者+1金）
> *彼女は言葉だけで金貨を動かす。それが「交渉」だ。*

---
**《祈祷の魔女》** - 毎R+1恩寵（パッシブ）
> 毎ラウンド終了時、+1恩寵
> *彼女の祈りは、誰よりも深く協会に届く。*

---
**《鏡の魔女》** - 他者成功時+1金（パッシブ）
> 他プレイヤーの宣言成功時、+1金
> *鏡に映るのは、他者の栄光。それが彼女の糧となる。*

---
**《慎重な予言者》** - 宣言0成功ボーナス（パッシブ）
> 宣言0成功時、3恩寵/3金/2VPから選択
> *何も取らないと宣言し、それを守る者を彼女は讃える。*
        """)

    st.divider()
    st.header("⚙️ ゲーム設定")

    # 設定をsession_stateで管理
    if "game_config" not in st.session_state:
        st.session_state.game_config = {
            "rounds": ROUNDS,
            "start_gold": START_GOLD,
            "initial_workers": INITIAL_WORKERS,
            "declaration_bonus_vp": DECLARATION_BONUS_VP,
            "debt_penalty_multiplier": DEBT_PENALTY_MULTIPLIER,
            "debt_penalty_cap": DEBT_PENALTY_CAP,
            "gold_to_vp_rate": GOLD_TO_VP_RATE,
            "take_gold_instead": TAKE_GOLD_INSTEAD,
            "rescue_gold_for_4th": RESCUE_GOLD_FOR_4TH,
            "enabled_upgrades": DEFAULT_ENABLED_UPGRADES[:],
        }

    with st.expander("🎲 ゲームモード", expanded=False):
        rounds_options = [4, 6, 8]
        current_rounds = st.session_state.game_config.get("rounds", ROUNDS)
        rounds_index = rounds_options.index(current_rounds) if current_rounds in rounds_options else 1
        st.session_state.game_config["rounds"] = st.radio(
            "ラウンド数",
            options=rounds_options,
            index=rounds_index,
            format_func=lambda x: f"{x}ラウンド（{'ショート' if x == 4 else 'スタンダード' if x == 6 else 'ロング'}）",
            help="4ラウンド: 短時間プレイ、6ラウンド: スタンダード、8ラウンド: 長期戦略",
            horizontal=True
        )

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

    with st.expander("🎴 使用アップグレード", expanded=False):
        st.caption("ゲームに登場するアップグレードカードを選択")

        # 現在の有効なアップグレードを取得
        current_enabled = st.session_state.game_config.get("enabled_upgrades", ALL_UPGRADES[:])

        # 全選択/全解除ボタン
        col_all, col_none = st.columns(2)
        with col_all:
            if st.button("すべて選択", key="select_all_upgrades", use_container_width=True):
                st.session_state.game_config["enabled_upgrades"] = ALL_UPGRADES[:]
                st.rerun()
        with col_none:
            if st.button("すべて解除", key="deselect_all_upgrades", use_container_width=True):
                st.session_state.game_config["enabled_upgrades"] = []
                st.rerun()

        st.divider()

        # 各アップグレードのチェックボックス
        new_enabled = []
        for u in ALL_UPGRADES:
            is_checked = u in current_enabled
            if st.checkbox(
                upgrade_name(u),
                value=is_checked,
                key=f"upgrade_toggle_{u}",
                help=upgrade_description(u)
            ):
                new_enabled.append(u)

        st.session_state.game_config["enabled_upgrades"] = new_enabled

        # 有効なアップグレード数を表示
        count = len(new_enabled)
        if count == 0:
            st.warning("⚠️ 少なくとも1つのアップグレードを選択してください")
        else:
            st.info(f"✅ {count}種類のアップグレードが有効")

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
        enabled_count = len(config.get("enabled_upgrades", ALL_UPGRADES))
        rounds_setting = config.get("rounds", ROUNDS)
        st.markdown(f"""
        - **ラウンド数**: {rounds_setting}R（{'ショート' if rounds_setting == 4 else 'スタンダード' if rounds_setting == 6 else 'ロング'}）
        - **初期金貨**: {config['start_gold']}G
        - **初期ワーカー**: {config['initial_workers']}人
        - **宣言ボーナス**: +{config['declaration_bonus_vp']}VP
        - **アップグレード辞退**: {config['take_gold_instead']}G
        - **4位救済**: +{config['rescue_gold_for_4th']}G
        - **負債ペナルティ**: -{config['debt_penalty_multiplier']}VP/金{' (上限' + str(config['debt_penalty_cap']) + 'VP)' if config['debt_penalty_cap'] else ''}
        - **金貨→VP**: {config['gold_to_vp_rate']}G = 1VP
        - **有効アップグレード**: {enabled_count}種類
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
        # enabled_upgradesが空の場合はNone（エラー防止）
        enabled = cfg.get("enabled_upgrades")
        if enabled is not None and len(enabled) == 0:
            enabled = None
        config = GameConfig(
            rounds=cfg.get("rounds", ROUNDS),
            start_gold=cfg["start_gold"],
            initial_workers=cfg["initial_workers"],
            declaration_bonus_vp=cfg["declaration_bonus_vp"],
            debt_penalty_multiplier=cfg["debt_penalty_multiplier"],
            debt_penalty_cap=cfg["debt_penalty_cap"],
            gold_to_vp_rate=cfg["gold_to_vp_rate"],
            take_gold_instead=cfg["take_gold_instead"],
            rescue_gold_for_4th=cfg["rescue_gold_for_4th"],
            enabled_upgrades=enabled,
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
        # Stop after a card play in a trick for animation
        if game.trick_play_just_happened:
            game.trick_play_just_happened = False
            st.session_state.trick_animating = True
            break


def advance_trick_animation():
    """Advance one step of trick animation."""
    game = st.session_state.game
    game.trick_play_just_happened = False
    # Run until next card play, human input, or game end
    while True:
        if game.get_pending_input() is not None:
            st.session_state.awaiting_input = True
            st.session_state.trick_animating = False
            break
        if not game.step():
            st.session_state.awaiting_input = False
            st.session_state.trick_animating = False
            break
        if game.trick_play_just_happened:
            game.trick_play_just_happened = False
            st.session_state.trick_animating = True
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
        return "🌟切り札"  # ランクなし
    suit_emoji = {"Spade": "♠", "Heart": "♥", "Diamond": "♦", "Club": "♣"}
    return f"{suit_emoji[card.suit]}{card.rank}"


# Initialize session state
if "game" not in st.session_state:
    init_game()

if "trick_animating" not in st.session_state:
    st.session_state.trick_animating = False

game = st.session_state.game
state = game.get_state()
pending = game.get_pending_input()

# Header
col1, col2 = st.columns([4, 1])
with col1:
    if state["game_over"]:
        st.title("魔女協会 - ゲーム終了")
    else:
        st.title(f"魔女協会 - ラウンド {state['round_no'] + 1}/{game.config.rounds}")
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
            # 金貨とVPを1行に（恩寵ポイント有効時は追加）
            if GRACE_ENABLED:
                st.markdown(f"💰 {p['gold']}G  |  🏆 {p['vp']}VP  |  ✨ {p.get('grace_points', 0)}恩寵")
            else:
                st.markdown(f"💰 {p['gold']}G  |  🏆 {p['vp']}VP")
            # ワーカーと給料を1行に
            round_no = state["round_no"]
            if round_no < len(WAGE_CURVE):
                st.caption(f"👷 {p['workers']}人 (給料: 初期{WAGE_CURVE[round_no]}G / 雇用なし)")
            else:
                st.caption(f"👷 {p['workers']}人")
            # 交易・討伐レベルをコンパクトに
            st.caption(f"交易Lv{p['trade_level']} / 討伐Lv{p['hunt_level']}")
            # Show witches (タップで効果表示)
            if p.get("witches"):
                witch_short = {"WITCH_BLACKROAD": "黒路", "WITCH_BLOODHUNT": "血誓", "WITCH_HERD": "群導",
                              "WITCH_NEGOTIATE": "交渉", "WITCH_BLESSING": "祈祷",
                              "WITCH_MIRROR": "鏡", "WITCH_ZERO_MASTER": "予言者"}
                witch_cols = st.columns(len(p["witches"]))
                for wi, w in enumerate(p["witches"]):
                    with witch_cols[wi]:
                        with st.popover(f"🧙 {witch_short.get(w, w)}", help="タップで効果表示"):
                            st.markdown(f"**{upgrade_name(w)}**")
                            st.write(upgrade_description(w))
            # Show declaration info during trick phase
            if "declared_tricks" in p:
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
    with st.expander("🔓 公開封印されたカード", expanded=False):
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

# Shared Board display（共有ボード：全スポットを1行表示）
if state.get("shared_board") and not state["game_over"]:
    board = state["shared_board"]
    if board:
        spot_type_names = {
            "UP_TRADE": "交易", "UP_HUNT": "討伐", "UP_PRAY": "祈り",
            "UP_RITUAL": "儀式", "WITCH_NEGOTIATE": "交渉",
        }
        spot_type_emoji = {
            "UP_TRADE": "💰", "UP_HUNT": "⚔️", "UP_PRAY": "🙏",
            "UP_RITUAL": "✨", "WITCH_NEGOTIATE": "🤝",
        }
        spot_labels = []
        for s in board:
            owner_short = s["owner"].replace("Player ", "P")
            name = spot_type_names.get(s["type"], s["type"])
            emoji = spot_type_emoji.get(s["type"], "")
            lv = f" Lv{s['level']}" if s["level"] >= 2 else ""
            spot_labels.append(f"{emoji}{name}{lv}[{owner_short}]")
        st.markdown(f"**共有ボード**: {' | '.join(spot_labels)}")

# Worker Placement Log（CPU行動の表示）
wp_info = state.get("worker_placement_info")
if wp_info and not state["game_over"]:
    placement_log = wp_info.get("placement_log", [])
    if placement_log:
        with st.expander("👷 配置履歴", expanded=True):
            for msg in placement_log:
                # Playerをショート表記に
                display_msg = msg.replace("Player ", "P")
                st.text(display_msg)

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

# Current Trick Plays - show cards as they are being played
if state["phase"] == "trick" and (state.get("current_trick_plays") or st.session_state.get("trick_animating", False)):
    st.subheader(f"🃏 トリック {state['current_trick'] + 1}")
    plays = state.get("current_trick_plays", [])
    play_cols = st.columns(4)
    trick_leader = state.get("trick_leader", 0)
    for i in range(4):
        with play_cols[i]:
            player_idx = (trick_leader + i) % 4
            player_info = state["players"][player_idx]
            player_name = player_info["name"]
            is_human = not player_info["is_bot"]

            # Check if this player has played
            played_card = None
            for pname, card in plays:
                if pname == player_name:
                    played_card = card
                    break

            if played_card is not None:
                if hasattr(played_card, 'suit'):
                    card_str = card_display(played_card)
                else:
                    card_str = str(played_card)
                marker = " 👤" if is_human else ""
                lead_mark = "⭐" if i == 0 else ""
                st.markdown(
                    f"<div style='text-align:center; padding:1rem; background:#e8f4fd; "
                    f"border-radius:10px; border:2px solid #4a90d9; margin:0.25rem;'>"
                    f"<div style='font-size:0.9rem; color:#333;'>{lead_mark}{player_name}{marker}</div>"
                    f"<div style='font-size:1.8rem; color:#000; margin-top:0.5rem;'>{card_str}</div>"
                    f"</div>",
                    unsafe_allow_html=True
                )
            else:
                marker = " 👤" if is_human else ""
                lead_mark = "⭐" if i == 0 else ""
                st.markdown(
                    f"<div style='text-align:center; padding:1rem; background:#f5f5f5; "
                    f"border-radius:10px; border:2px dashed #ccc; margin:0.25rem;'>"
                    f"<div style='font-size:0.9rem; color:#999;'>{lead_mark}{player_name}{marker}</div>"
                    f"<div style='font-size:1.8rem; color:#ccc; margin-top:0.5rem;'>?</div>"
                    f"</div>",
                    unsafe_allow_html=True
                )

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
            options=list(range(0, TRICKS_PER_ROUND + 1)),
            index=2
        )
        if st.button("🎯 宣言する", type="primary", use_container_width=True):
            game.provide_input(declared)
            run_until_input()
            st.rerun()

    elif req_type == "seal":
        st.subheader(f"🔓 公開封印フェーズ")
        hand = context["hand"]
        need_seal = context["need_seal"]
        st.info(f"📌 {need_seal}枚のカードを選んで公開封印（このラウンドはプレイ不可、全員に公開）")

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

        if st.button("🔓 公開封印する", type="primary", disabled=selected_count != need_seal, use_container_width=True):
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
                st.info("🌟 リード: 切り札")
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
                                game.trick_play_just_happened = False
                                st.session_state.trick_animating = True
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

    elif req_type == "upgrade_level_choice":
        upgrade = context["upgrade"]
        st.subheader(f"📜 {upgrade_name(upgrade)} の強化方法を選択")
        st.info("2枚目のアップグレードを取得しました。強化方法を選んでください。")

        col1, col2 = st.columns(2)
        with col1:
            if st.button("⬆️ Lv2に強化\n(1スポット、効果+1)", type="primary", use_container_width=True):
                game.provide_input(True)
                run_until_input()
                st.rerun()
        with col2:
            if st.button("➕ 別枠配置\n(独立Lv1×2)", type="secondary", use_container_width=True):
                game.provide_input(False)
                run_until_input()
                st.rerun()

    elif req_type == "fourth_place_bonus":
        st.subheader(f"🎁 4位ボーナス")
        gold_amount = context["gold_amount"]
        grace_amount = context["grace_amount"]

        st.info("4位救済ボーナスを選んでください")

        col1, col2 = st.columns(2)
        with col1:
            if st.button(f"💰 {gold_amount} 金貨", type="primary", use_container_width=True):
                game.provide_input("GOLD")
                run_until_input()
                st.rerun()
        with col2:
            if st.button(f"✨ {grace_amount} 恩寵", type="secondary", use_container_width=True):
                game.provide_input("GRACE")
                run_until_input()
                st.rerun()

    elif req_type == "ritual_choice":
        grace_amount = context.get("grace_amount", PERSONAL_RITUAL_GRACE)
        gold_amount = context.get("gold_amount", PERSONAL_RITUAL_GOLD)
        st.subheader("儀式の祭壇")
        st.warning("報酬を選んでください（ワーカー1人を永久消費）")
        col1, col2 = st.columns(2)
        with col1:
            if st.button(f"+{grace_amount} 恩寵", type="secondary", use_container_width=True):
                game.provide_input("grace")
                run_until_input()
                st.rerun()
        with col2:
            if st.button(f"+{gold_amount} 金", type="primary", use_container_width=True):
                game.provide_input("gold")
                run_until_input()
                st.rerun()

    elif req_type == "grace_priority":
        cost = context.get("cost", GRACE_PRIORITY_COST)
        grace = context.get("grace", 0)
        st.subheader("先行権")
        st.info(f"同トリック数のプレイヤーがいます。恩寵 {cost} を消費して先行権を得ますか？（恩寵: {grace}）")
        col1, col2 = st.columns(2)
        with col1:
            if st.button("先行権を使う", type="primary", use_container_width=True):
                game.provide_input(True)
                run_until_input()
                st.rerun()
        with col2:
            if st.button("使わない", type="secondary", use_container_width=True):
                game.provide_input(False)
                run_until_input()
                st.rerun()

    elif req_type == "grace_hand_swap":
        st.subheader(f"🔄 手札全交換")
        hand = context["hand"]
        grace_points = context["grace_points"]
        cost = context["cost"]

        st.info(f"恩寵を{cost}消費して手札{len(hand)}枚を全て引き直せます（現在の恩寵: {grace_points}）")

        # 手札表示
        st.write("現在の手札:")
        cols = st.columns(min(len(hand), 5))
        for idx, card in enumerate(hand):
            with cols[idx % len(cols)]:
                st.markdown(f"**{card_display(card)}**")

        st.divider()
        col1, col2 = st.columns(2)
        with col1:
            if st.button("🔄 全交換する", type="primary", use_container_width=True):
                game.provide_input(True)
                run_until_input()
                st.rerun()
        with col2:
            if st.button("⏭️ スキップ", use_container_width=True):
                game.provide_input(None)
                run_until_input()
                st.rerun()

    elif req_type == "worker_actions":
        st.subheader(f"👷 ワーカー配置 (1人ずつ)")
        num_workers = context["num_workers"]
        available_actions = context.get("available_actions", [])

        st.info(f"残りワーカー: {num_workers}人 — 1つのアクションを選択")

        # アクション名の表示用変換（レベル対応・所有者表示）
        def action_display(act):
            if act.startswith("SPOT:"):
                parts = act.split(":", 3)
                owner_name = parts[1]
                spot_name = parts[3]
                # 所有者のレベル判定
                owner_short = owner_name.replace("Player ", "P")
                owner_data = None
                for p_info in state["players"]:
                    if p_info["name"] == owner_name:
                        owner_data = p_info
                        break
                level = 1
                if owner_data and spot_name in owner_data.get("leveled_spots", []):
                    level = 2
                lv_tag = f" Lv{level}" if level >= 2 else ""
                bonus = level - 1
                names = {
                    "UP_TRADE": f"💰 交易{lv_tag}[{owner_short}]({PERSONAL_TRADE_GOLD + bonus}金)",
                    "UP_HUNT": f"⚔️ 討伐{lv_tag}[{owner_short}]({PERSONAL_HUNT_VP + bonus}VP)",
                    "UP_PRAY": f"🙏 祈り{lv_tag}[{owner_short}]({PERSONAL_PRAY_GRACE + bonus}恩寵)",
                    "UP_RITUAL": f"✨ 儀式{lv_tag}[{owner_short}]({PERSONAL_RITUAL_GRACE + bonus}恩寵 or {PERSONAL_RITUAL_GOLD + bonus}金, ワーカー消費)",
                    "WITCH_NEGOTIATE": f"🤝 交渉の魔女[{owner_short}]({WITCH_NEGOTIATE_GRACE_COST}恩寵→{WITCH_NEGOTIATE_GOLD}金)",
                }
                return names.get(spot_name, spot_name)
            names = {
                "TRADE": f"💰 共通交易({SHARED_TRADE_GOLD}金)",
                "HUNT": f"⚔️ 共通討伐({SHARED_HUNT_VP}VP)",
                "PRAY": f"🙏 共通祈り({SHARED_PRAY_GRACE}恩寵)",
                "RECRUIT": f"🧑‍🤝‍🧑 雇用({RECRUIT_COST}金→+1人)",
            }
            return names.get(act, act)

        action = st.radio(
            "アクション選択",
            options=available_actions,
            format_func=action_display,
            key="wp_action_select",
            label_visibility="collapsed"
        )

        st.divider()
        if st.button("✅ 配置確定", type="primary", use_container_width=True):
            game.provide_input(action)
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
            # 順位ごとの背景色
            bg_colors = {
                1: "linear-gradient(135deg, #ffd700 0%, #ffb347 100%)",
                2: "linear-gradient(135deg, #c0c0c0 0%, #a8a8a8 100%)",
                3: "linear-gradient(135deg, #cd7f32 0%, #b87333 100%)",
            }
            bg = bg_colors.get(i, "#e2e8f0")
            # カードスタイルで表示（文字色は常に黒）
            grace_display = f"  |  ✨ {p.get('grace_points', 0)}恩寵" if GRACE_ENABLED else ""
            st.markdown(f"""
            <div style="padding:0.75rem; margin:0.5rem 0; border-radius:10px;
                        background: {bg}; color: #000;">
                <span style="font-size:1.5rem;">{medal}</span>
                <strong>{i}位 {p['name']}{player_marker}</strong><br>
                🏆 {p['vp']}VP  |  💰 {p['gold']}G{grace_display}
            </div>
            """, unsafe_allow_html=True)

        st.divider()
        if st.button("🔄 もう一度プレイ", type="primary", use_container_width=True):
            init_game()
            st.rerun()
    else:
        st.info(f"フェーズ: {state['phase']}")

# Game log（直近のログを表示）
st.divider()
with st.expander("ゲームログ", expanded=True):
    for msg in reversed(state["log"]):
        st.text(msg)

# Auto-advance trick animation
if st.session_state.get('trick_animating', False):
    time.sleep(1.0)
    advance_trick_animation()
    st.rerun()
