"""
AI Bot for Coven - Uses Anthropic Haiku 4.5 for bot decisions.
Uses Structured Outputs (json_schema) for guaranteed JSON responses.
"""

import json
import os
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

# Load .env file if present
_env_file = Path(__file__).parent / ".env"
if _env_file.exists():
    for line in _env_file.read_text().splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            key, _, value = line.partition("=")
            os.environ.setdefault(key.strip(), value.strip())

# Lazy import
_client = None
_async_client = None
_api_error_shown = False

MODEL = "claude-haiku-4-5-20251001"
MAX_TOKENS = 256

SYSTEM_PROMPT = """あなたはカードゲーム「Coven（魔女協会）」のAIプレイヤーです。
トリックテイキングとワーカープレイスメントを組み合わせたゲームで、勝利を目指して最適な判断をしてください。

## ルール概要
- 4人プレイ、6ラウンド
- 毎ラウンド: 5枚配布→宣言→1枚封印→4トリック→アップグレード選択→ワーカー配置→給料支払い
- トリック: マストフォロー、切り札(★)は最強だがリード不可
- 宣言成功: +1VP, +1恩寵。宣言0成功は追加ボーナスあり
- 0トリック(宣言に関わらず): +1恩寵, +1金
- ゲーム終了時: 2金=1恩寵→5恩寵=3VP→2金=1VP

## 勝利条件
最終VPが最も高いプレイヤーが勝利。"""

# JSON Schemas for Structured Outputs
SCHEMA_DECLARATION = {
    "type": "object",
    "properties": {
        "declaration": {"type": "integer", "description": "宣言トリック数 (0-4)"}
    },
    "required": ["declaration"],
    "additionalProperties": False,
}

SCHEMA_SEAL = {
    "type": "object",
    "properties": {
        "seal": {
            "type": "array",
            "items": {"type": "string"},
            "description": "封印するカードコードのリスト (例: ['S01'])",
        }
    },
    "required": ["seal"],
    "additionalProperties": False,
}

SCHEMA_CARD = {
    "type": "object",
    "properties": {
        "card": {"type": "string", "description": "プレイするカードコード (例: 'S05')"}
    },
    "required": ["card"],
    "additionalProperties": False,
}

SCHEMA_CHOICE = {
    "type": "object",
    "properties": {
        "choice": {"type": "string", "description": "選択肢 (例: 'UP_TRADE', 'GOLD', 'GRACE')"}
    },
    "required": ["choice"],
    "additionalProperties": False,
}

SCHEMA_ACTION = {
    "type": "object",
    "properties": {
        "action": {"type": "string", "description": "アクション名 (例: 'TRADE', 'SPOT:P2:0:UP_HUNT')"}
    },
    "required": ["action"],
    "additionalProperties": False,
}


def get_client():
    """Get or create synchronous Anthropic client."""
    global _client
    if _client is None:
        try:
            import anthropic
            _client = anthropic.Anthropic()
        except Exception:
            return None
    return _client


def get_async_client():
    """Get or create async Anthropic client."""
    global _async_client
    if _async_client is None:
        try:
            import anthropic
            _async_client = anthropic.AsyncAnthropic()
        except Exception:
            return None
    return _async_client


def _call_api(client, user_msg: str, schema: dict) -> Optional[dict]:
    """Call Anthropic API with Structured Outputs."""
    global _api_error_shown
    try:
        response = client.messages.create(
            model=MODEL,
            max_tokens=MAX_TOKENS,
            system=SYSTEM_PROMPT,
            messages=[{"role": "user", "content": user_msg}],
            output_config={
                "format": {
                    "type": "json_schema",
                    "schema": schema,
                }
            },
        )
        text = response.content[0].text
        _api_error_shown = False
        return json.loads(text)
    except Exception as e:
        if not _api_error_shown:
            print(f"[AI Bot] API error (以降のエラーは省略): {e}")
            _api_error_shown = True
        return None


async def _call_api_async(client, user_msg: str, schema: dict) -> Optional[dict]:
    """Call Anthropic API asynchronously with Structured Outputs."""
    global _api_error_shown
    try:
        response = await client.messages.create(
            model=MODEL,
            max_tokens=MAX_TOKENS,
            system=SYSTEM_PROMPT,
            messages=[{"role": "user", "content": user_msg}],
            output_config={
                "format": {
                    "type": "json_schema",
                    "schema": schema,
                }
            },
        )
        text = response.content[0].text
        _api_error_shown = False
        return json.loads(text)
    except Exception as e:
        if not _api_error_shown:
            print(f"[AI Bot] API error (以降のエラーは省略): {e}")
            _api_error_shown = True
        return None


def _card_code(card) -> str:
    """Convert Card to string code like 'S05', 'H03', 'T01'."""
    suit_map = {"Spade": "S", "Heart": "H", "Diamond": "D", "Club": "C", "Trump": "T"}
    return f"{suit_map.get(card.suit, '?')}{card.rank:02d}"


def _format_hand(cards) -> str:
    """Format a list of cards for prompt."""
    return ", ".join(_card_code(c) for c in cards)


def _player_summary(player, all_players=None) -> str:
    """Build a summary of player state for prompts."""
    lines = [
        f"あなた: {player.name}",
        f"  金貨: {player.gold}, VP: {player.vp}, 恩寵: {player.grace_points}",
        f"  ワーカー: {player.basic_workers_total}, 負債: {player.accumulated_debt}",
        f"  魔女: {', '.join(player.witches) if player.witches else 'なし'}",
        f"  共有スポット: {', '.join(player.personal_spots) if player.personal_spots else 'なし'}",
    ]
    if all_players:
        lines.append("\n他プレイヤー:")
        for p in all_players:
            if p.name != player.name:
                lines.append(
                    f"  {p.name}: 金{p.gold}, VP{p.vp}, 恩寵{p.grace_points}, "
                    f"ワーカー{p.basic_workers_total}, 魔女[{','.join(p.witches)}]"
                )
    return "\n".join(lines)


def _parse_card_code(code_str):
    """Parse a card code string like 'S05' into a Card object, or None."""
    from main import Card
    suit_map = {"S": "Spade", "H": "Heart", "D": "Diamond", "C": "Club", "T": "Trump"}
    code = str(code_str).upper()
    if len(code) >= 2 and code[0] in suit_map:
        try:
            rank = int(code[1:])
            return Card(suit_map[code[0]], rank)
        except (ValueError, IndexError):
            pass
    return None


# ============================================================
# Decision functions (synchronous - for CLI / simulation)
# ============================================================

def ai_declare_tricks(player, hand, set_index, all_players=None) -> Optional[int]:
    """AI declaration: how many tricks to win."""
    client = get_client()
    if client is None:
        return None

    prompt = f"""{_player_summary(player, all_players)}

手札: {_format_hand(hand)}
(★=切り札、最強だがリード不可。マストフォロー。)

何トリック取れそうですか？ (0-4)
戦略的に考えて宣言してください。宣言成功で+1VP+1恩寵。0トリックでも+1恩寵+1金。"""

    result = _call_api(client, prompt, SCHEMA_DECLARATION)
    if result and "declaration" in result:
        v = int(result["declaration"])
        return max(0, min(4, v))
    return None


def ai_seal_cards(player, hand, declared_tricks, all_players=None) -> Optional[list]:
    """AI seal: choose 1 card to remove from play."""
    client = get_client()
    if client is None:
        return None

    from main import CARDS_PER_SET, TRICKS_PER_ROUND
    need_seal = CARDS_PER_SET - TRICKS_PER_ROUND
    if need_seal <= 0:
        return []

    prompt = f"""{_player_summary(player, all_players)}

手札: {_format_hand(hand)}
宣言: {declared_tricks}トリック

{need_seal}枚を封印（プレイ不可）してください。
残りの{TRICKS_PER_ROUND}枚でトリックを戦います。宣言達成に不要なカードを封印しましょう。
例: ["S01"]"""

    result = _call_api(client, prompt, SCHEMA_SEAL)
    if result and "seal" in result:
        seal_codes = result["seal"]
        if not isinstance(seal_codes, list):
            seal_codes = [seal_codes]

        sealed = []
        for code in seal_codes[:need_seal]:
            card = _parse_card_code(code)
            if card and card in hand and card not in sealed:
                sealed.append(card)

        if len(sealed) == need_seal:
            return sealed
    return None


def ai_choose_card(player, lead_card, hand, legal_cards, trick_plays=None, all_players=None) -> Optional[Any]:
    """AI card play: choose which card to play."""
    client = get_client()
    if client is None:
        return None

    plays_str = ""
    if trick_plays:
        plays_str = "\n場のカード: " + ", ".join(
            f"{p.name if hasattr(p, 'name') else p}:{_card_code(c)}" for p, c in trick_plays
        )

    lead_str = f"\nリードスーツ: {_card_code(lead_card)}" if lead_card else "\nあなたがリード（切り札でリード不可）"

    prompt = f"""{_player_summary(player, all_players)}

手札: {_format_hand(hand)}
出せるカード: {_format_hand(legal_cards)}{lead_str}{plays_str}
宣言: {player.declared_tricks}, 現在獲得: {player.tricks_won_this_round}

どのカードを出しますか？"""

    result = _call_api(client, prompt, SCHEMA_CARD)
    if result and "card" in result:
        card = _parse_card_code(result["card"])
        if card and card in legal_cards:
            return card
    return None


def ai_choose_upgrade(player, revealed, available, round_no, all_players=None) -> Optional[str]:
    """AI upgrade selection."""
    client = get_client()
    if client is None:
        return None

    from main import upgrade_name, TAKE_GOLD_INSTEAD

    upgrades_str = "\n".join(
        f"  - {u} ({upgrade_name(u)})" + (" [取得済]" if u not in available else "")
        for u in revealed
    )
    available_str = ", ".join(available) if available else "なし"

    prompt = f"""{_player_summary(player, all_players)}
ラウンド: {round_no + 1}

公開されたアップグレード:
{upgrades_str}

選択可能: {available_str}
または "GOLD" で {TAKE_GOLD_INSTEAD}金貨を獲得

アップグレードはボード上の共有スポットになります（全員使用可、他者使用時に所有者+1金）。"""

    result = _call_api(client, prompt, SCHEMA_CHOICE)
    if result and "choice" in result:
        choice = str(result["choice"]).upper()
        if choice in ("GOLD", "TAKE_GOLD"):
            return "GOLD"
        if choice in available:
            return choice
    return None


def ai_choose_worker_action(player, available_actions, round_no, all_players=None) -> Optional[str]:
    """AI worker placement action."""
    client = get_client()
    if client is None:
        return None

    actions_str = "\n".join(f"  - {a}" for a in available_actions)

    prompt = f"""{_player_summary(player, all_players)}
ラウンド: {round_no + 1}

配置可能なアクション:
{actions_str}

TRADE=+2金, HUNT=+1VP, PRAY=+1恩寵, RECRUIT=2金消費→+1ワーカー
SPOT:所有者:idx:タイプ = 共有スポット（他者所有なら所有者+1金）"""

    result = _call_api(client, prompt, SCHEMA_ACTION)
    if result and "action" in result:
        action = str(result["action"])
        if action in available_actions:
            return action
        # Fuzzy match for SPOT actions
        for a in available_actions:
            if action.upper() in a.upper() or a.upper() in action.upper():
                return a
    return None


def ai_choose_4th_place_bonus(player, gold_amount, grace_amount, all_players=None) -> Optional[str]:
    """AI 4th place bonus choice."""
    client = get_client()
    if client is None:
        return None

    prompt = f"""{_player_summary(player, all_players)}

4位ボーナス: {gold_amount}金貨 または {grace_amount}恩寵 を選択してください。
(ゲーム終了時: 5恩寵=3VP)"""

    result = _call_api(client, prompt, SCHEMA_CHOICE)
    if result and "choice" in result:
        choice = str(result["choice"]).upper()
        if choice in ("GOLD", "GRACE"):
            return choice
    return None


# ============================================================
# Async wrappers (for Rich UI / GameEngine)
# ============================================================

async def ai_declare_tricks_async(player, hand, set_index, all_players=None) -> Optional[int]:
    client = get_async_client()
    if client is None:
        return None

    prompt = f"""{_player_summary(player, all_players)}

手札: {_format_hand(hand)}
(★=切り札、最強だがリード不可。マストフォロー。)

何トリック取れそうですか？ (0-4)
戦略的に考えて宣言してください。宣言成功で+1VP+1恩寵。0トリックでも+1恩寵+1金。"""

    result = await _call_api_async(client, prompt, SCHEMA_DECLARATION)
    if result and "declaration" in result:
        v = int(result["declaration"])
        return max(0, min(4, v))
    return None


async def ai_seal_cards_async(player, hand, declared_tricks, all_players=None) -> Optional[list]:
    client = get_async_client()
    if client is None:
        return None

    from main import CARDS_PER_SET, TRICKS_PER_ROUND
    need_seal = CARDS_PER_SET - TRICKS_PER_ROUND
    if need_seal <= 0:
        return []

    prompt = f"""{_player_summary(player, all_players)}

手札: {_format_hand(hand)}
宣言: {declared_tricks}トリック

{need_seal}枚を封印してください。"""

    result = await _call_api_async(client, prompt, SCHEMA_SEAL)
    if result and "seal" in result:
        seal_codes = result["seal"]
        if not isinstance(seal_codes, list):
            seal_codes = [seal_codes]
        sealed = []
        for code in seal_codes[:need_seal]:
            card = _parse_card_code(code)
            if card and card in hand and card not in sealed:
                sealed.append(card)
        if len(sealed) == need_seal:
            return sealed
    return None


async def ai_choose_card_async(player, lead_card, hand, legal_cards, trick_plays=None, all_players=None) -> Optional[Any]:
    client = get_async_client()
    if client is None:
        return None

    plays_str = ""
    if trick_plays:
        plays_str = "\n場のカード: " + ", ".join(
            f"{p.name if hasattr(p, 'name') else p}:{_card_code(c)}" for p, c in trick_plays
        )
    lead_str = f"\nリードスーツ: {_card_code(lead_card)}" if lead_card else "\nあなたがリード（切り札でリード不可）"

    prompt = f"""{_player_summary(player, all_players)}

手札: {_format_hand(hand)}
出せるカード: {_format_hand(legal_cards)}{lead_str}{plays_str}
宣言: {player.declared_tricks}, 現在獲得: {player.tricks_won_this_round}

どのカードを出しますか？"""

    result = await _call_api_async(client, prompt, SCHEMA_CARD)
    if result and "card" in result:
        card = _parse_card_code(result["card"])
        if card and card in legal_cards:
            return card
    return None


async def ai_choose_upgrade_async(player, revealed, available, round_no, all_players=None) -> Optional[str]:
    client = get_async_client()
    if client is None:
        return None

    from main import upgrade_name, TAKE_GOLD_INSTEAD
    upgrades_str = "\n".join(
        f"  - {u} ({upgrade_name(u)})" + (" [取得済]" if u not in available else "")
        for u in revealed
    )

    prompt = f"""{_player_summary(player, all_players)}
ラウンド: {round_no + 1}

公開: {upgrades_str}
選択可能: {', '.join(available) if available else 'なし'}
または "GOLD" で {TAKE_GOLD_INSTEAD}金貨"""

    result = await _call_api_async(client, prompt, SCHEMA_CHOICE)
    if result and "choice" in result:
        choice = str(result["choice"]).upper()
        if choice in ("GOLD", "TAKE_GOLD"):
            return "GOLD"
        if choice in available:
            return choice
    return None


async def ai_choose_worker_action_async(player, available_actions, round_no, all_players=None) -> Optional[str]:
    client = get_async_client()
    if client is None:
        return None

    actions_str = "\n".join(f"  - {a}" for a in available_actions)

    prompt = f"""{_player_summary(player, all_players)}
ラウンド: {round_no + 1}

配置可能:
{actions_str}"""

    result = await _call_api_async(client, prompt, SCHEMA_ACTION)
    if result and "action" in result:
        action = str(result["action"])
        if action in available_actions:
            return action
        for a in available_actions:
            if action.upper() in a.upper() or a.upper() in action.upper():
                return a
    return None


async def ai_choose_4th_place_bonus_async(player, gold_amount, grace_amount, all_players=None) -> Optional[str]:
    client = get_async_client()
    if client is None:
        return None

    prompt = f"""{_player_summary(player, all_players)}

4位ボーナス: {gold_amount}金貨 or {grace_amount}恩寵?"""

    result = await _call_api_async(client, prompt, SCHEMA_CHOICE)
    if result and "choice" in result:
        choice = str(result["choice"]).upper()
        if choice in ("GOLD", "GRACE"):
            return choice
    return None
