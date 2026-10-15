"""
zTranzlator - Multi-Engine AI Translation System (Phase 5)
- 内蔵スマート辞書 & UI短縮ルール (完全オフライン / 超高速)
- Ollama ローカルLLM (モデル動的選択 & ワンクリック自動ダウンロード & 直接指定DL)
- Google Gemini API (GPU不要 / 無料枠あり / 超高速)
- OpenAI 互換 API (OpenAI / Groq / DeepSeek / OpenRouter 等に完全対応)
"""

import json
import os
import re
import shutil
import subprocess
import sys
import time
import threading
import urllib.request
import urllib.error
from pathlib import Path
from typing import List, Dict, Tuple, Optional, Callable, Any


def get_system_prompt(target_lang: str = "JP", has_placeholders: bool = False) -> str:
    from i18n import SUPPORTED_TARGET_LANGUAGES
    meta = SUPPORTED_TARGET_LANGUAGES.get(target_lang, {"name": "日本語", "en_name": "Japanese"})
    lang_name = meta["name"]
    lang_en = meta["en_name"]

    ph_ja = "\n3. 原文に含まれる __PH0__, __PH1__ などのプレースホルダー記号は変更せず、そのまま適切な位置に残すこと。" if has_placeholders else ""
    ph_en = "\n3. Strictly preserve placeholders like __PH0__, %s without modifying them." if has_placeholders else ""

    if target_lang == "JP":
        return f"""あなたはサバイバルゲーム「Project Zomboid」の専門翻訳者です。
与えられたゲームUI、設定項目、アイテム名、台詞、説明文を、自然かつ簡潔な日本語に翻訳してください。

【厳格な翻訳ルール】
1. UI枠からはみ出さないよう、極限まで短く簡潔に訳すこと。冗長なカタカナ語を避け、引き締まった表現にすること。
2. 数字・英字・記号（:, (), [], / 等）は半角を維持すること。{ph_ja}
4. 思考プロセス（thinking）や解説、補足、挨拶、引用符（"や'）は一切出力せず、翻訳結果の1行のみを直接返してください。"""

    return f"""You are a professional localization expert for the survival game "Project Zomboid".
Translate the given game UI texts, settings, item names, or dialogue strictly into concise {lang_en} ({lang_name}).

【CRITICAL RULES】
1. Extremely concise: Keep text as short as possible to prevent UI text overflow in fixed-width buttons and tables.
2. Character set: Keep numbers (0-9), alphabets (A-Z), and symbols in standard half-width.{ph_en}
4. Output: Return ONLY the translated string in a single line. Do NOT output thinking processes, reasoning, quotes, explanations, or notes."""


def estimate_text_width(text: str) -> float:
    """推定描画幅を計算（半角英数記号=1.0, 全角日本語/CJK=2.0）"""
    w = 0.0
    for ch in text:
        if ord(ch) < 128 or (0xFF61 <= ord(ch) <= 0xFF9F):
            w += 1.0
        else:
            w += 2.0
    return w


def check_overflow_risk(orig_en: str, trans_jp: str) -> Tuple[bool, float]:
    """
    原文に対して訳文がUI枠をはみ出すリスクが高いかを判定。
    戻り値: (is_overflow_risk, ratio)
    ・原文が比較的短いUIラベル（幅45以下）
    ・かつ、訳文幅が原文幅の 1.45 倍（145%）を超えている場合
    """
    if not orig_en or not trans_jp:
        return False, 1.0
    en_w = estimate_text_width(orig_en)
    jp_w = estimate_text_width(trans_jp)
    if en_w <= 0:
        return False, 1.0
    ratio = jp_w / en_w
    is_risk = (en_w <= 45 and ratio > 1.45)
    return is_risk, ratio


CONFIG_FILE = Path(__file__).parent / "config.json"

DEFAULT_CONFIG = {
    "ui_language": "ja",              # "ja" | "en" | "ko" | "zh-CN" | "es"
    "target_language": "JP",           # "JP" | "KO" | "CN" | "CH" | "ES" | "RU" | "FR" | "DE" | "PL" | "PTBR" | "IT"
    "engine_type": "smart_dict",       # "smart_dict" | "ollama" | "api"
    "ollama_model": "qwen2.5:3b",
    "api_provider": "gemini",         # "gemini" | "openai"
    "gemini_api_key": "",
    "gemini_model": "gemini-1.5-flash",
    "openai_base_url": "https://api.openai.com/v1",
    "openai_api_key": "",
    "openai_model": "gpt-4o-mini",
}


class ConfigManager:
    """設定ファイルの永続化管理"""
    @classmethod
    def load(cls) -> dict:
        config = DEFAULT_CONFIG.copy()
        if CONFIG_FILE.is_file():
            try:
                with open(CONFIG_FILE, "r", encoding="utf-8-sig") as f:
                    saved = json.load(f)
                    config.update(saved)
            except Exception:
                pass
        return config

    @classmethod
    def save(cls, config: dict):
        try:
            with open(CONFIG_FILE, "w", encoding="utf-8") as f:
                json.dump(config, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"[Error] 設定保存失敗: {e}")


class MaskingEngine:
    """プレースホルダー（%d, %s, タグ等）を保護するためのマスキング機構"""
    PATTERNS = [
        re.compile(r'%[0-9]*[a-zA-Z]'),
        re.compile(r'\{[0-9]+\}'),
        re.compile(r'<[^>]+>'),
        re.compile(r'\\n'),
    ]

    @classmethod
    def mask(cls, text: str) -> Tuple[str, List[str]]:
        placeholders = []
        def repl(match):
            idx = len(placeholders)
            placeholders.append(match.group(0))
            return f"__PH{idx}__"

        masked_text = text
        for pat in cls.PATTERNS:
            masked_text = pat.sub(repl, masked_text)
        return masked_text, placeholders

    @classmethod
    def unmask(cls, text: str, placeholders: List[str]) -> str:
        unmasked = text
        for idx, original in enumerate(placeholders):
            unmasked = unmasked.replace(f"__PH{idx}__", original)
        return unmasked


class RuleBasedTranslator:
    """ローカルLLM未起動時や高速処理用のUI特化ルールベース翻訳"""
    BUILTIN_RULES = {
        # 視点・カメラ基本
        "First person": "1人称視点",
        "Third person": "3人称視点",
        "Isometric view": "通常視点 (斜め)",
        "Over the shoulder": "肩越し視点",
        "Camera behind": "後方カメラ",
        "CameraBehind": "後方カメラ",
        "Third person: camera behind": "3人称: 後方カメラ",
        "Third person: swap shoulders": "3人称: 肩越し視点反転",
        "Third person on foot": "徒歩時の3人称視点",
        "Third person in a vehicle": "乗車時の3人称視点",
        "First or third person": "1人称/3人称の切り替え",
        "First person on or off": "1人称視点 ON/OFF",
        "Free camera on or off": "自由カメラ ON/OFF",
        "Physical free camera on or off": "物理自由カメラ ON/OFF",
        "Free look (hold)": "フリールック (長押し)",
        "Views": "各種視点",
        "Free camera": "自由カメラ",
        "Loot menu": "探索メニュー",
        "Swap shoulder": "肩越し視点の切り替え",
        "Record a camera trace": "カメラ軌跡の記録",
        "Vehicle camera distance": "車両カメラ距離",
        "Vehicle camera height": "車両カメラ高さ",
        "Vehicle camera returns behind": "車両カメラを後方へ戻す",
        "Vehicle camera side offset": "車両カメラ左右オフセット",
        "Viewpoint": "視点 (Viewpoint)",
        "Viewpoint screenshot": "Viewpoint スクリーンショット",
        "Viewpoint settings window": "Viewpoint 設定ウィンドウ",
        # 自由カメラ操作
        "Free camera: forward": "自由カメラ: 前進",
        "Free camera: back": "自由カメラ: 後退",
        "Free camera: left": "自由カメラ: 左移動",
        "Free camera: right": "自由カメラ: 右移動",
        "Free camera: up": "自由カメラ: 上昇",
        "Free camera: down": "自由カメラ: 下降",
        "Free camera: four times as fast": "自由カメラ: 4倍速",
        "Free camera: back to the player": "自由カメラ: 自キャラへ戻す",
        # グラフィック・エフェクト・デバッグ
        "Field of view effects": "視野角(FOV)エフェクト",
        "Level-of-detail view": "LOD(詳細度)表示",
        "Performance overlay": "パフォーマンス表示",
        "Weapon recoil": "武器の反動",
        "Melee hit pause": "近接ヒット時の一時停止",
        "Melee impact": "近接攻撃の衝撃",
        "Plants and trees dissolve too": "草木も透過表示する",
        "Minecraft shader packs": "Minecraftシェーダーパック",
        "Next debug view": "次のデバッグ表示",
        "Next effect off": "次のエフェクトを無効化",
        "Right button": "右ボタン",
        "Rooms' culling": "部屋のカリング(非表示化)",
        "Capture profile": "プロファイル取得",
        "Check the mesher": "メッシャー確認",
        "Record the mesher": "メッシャー記録",
        "Dev mode only.": "開発モード専用",
        "Changed: Apply to see it": "変更あり: 適用で反映",
        "Choose in the loot menu while it shows": "表示中の探索メニューから選択",
        "Switch to the pad as it is used": "使用時にコントローラーへ自動切替",
        "Press a key or a button...": "キーまたはボタンを押してください...",
        "Shows or hides this window.": "このウィンドウを表示または非表示にします。",
        "Saves the view to Zomboid/viewpoint-shots.": "Zomboid/viewpoint-shots に視点を保存します。",
        "Loot menu: open the loot window": "探索メニュー: 探索ウィンドウを開く",
        "Loot menu: take all": "探索メニュー: 全て取得",
        "Loot menu: take or do": "探索メニュー: 取得または実行",
        "Takes everything the loot menu shows.": "探索メニュー内の全アイテムを取得します。",
        "no key binding": "キー割り当てなし",
        "enabled, none connected was": "有効 (未接続)",
        "is not a number, a toggle or a choice": "無効な値形式です",
        "declared twice: the window lists both": "重複定義: 両方を一覧表示",
        # UI・設定
        "Show the loot menu": "探索UIを表示",
        "Press a button of your pad for": "割り当てるボタンを押してください:",
        "While aiming only": "照準時のみ",
        "Same as in-game": "ゲーム内設定に連動",
        "Menu framerate": "メニュー画面FPS",
        "Controller": "コントローラー",
        "Default": "初期値",
        "Clear": "解除",
        "Cancel": "キャンセル",
        "Apply": "適用",
        "Enabled": "有効",
        "Disabled": "無効",
        "Toggle": "切り替え",
        "Sensitivity": "感度",
        "Distance": "距離",
        "Smoothness": "滑らかさ",
        "Keybindings": "キー割り当て",
        "Options": "設定",
        "Settings": "設定",
        "Screenshot": "スクリーンショット",
        "Aim sensitivity": "照準感度",
        "Camera distance": "カメラ距離",
        "Camera height": "カメラの高さ",
        "Camera height aiming": "照準時のカメラ高さ",
        "Camera motion": "カメラモーション",
        "Camera recoil": "反動時のカメラ揺れ",
        "Camera shake": "画面の揺れ",
        "Camera side offset": "カメラ左右オフセット",
        "Camera side offset aiming": "照準時左右オフセット",
        "Automatic shoulder swap": "肩越し視点の自動反転",
        "Back to shipped": "初期設定に戻す",
        "Cursor free or locked": "カーソル固定/解除",
        # Viewpoint 長文説明文
        "Driving, in first and third person, the view goes back to the way the vehicle goes when the mouse has been still a while. Moving the mouse takes it back at once.": "運転中(1人称/3人称)、マウスを一定時間動かさないと視線が車両の進行方向へ戻ります。マウスを動かすと即座に戻ります。",
        "Finds the packs dropped into Zomboid/viewpoint-shaderpacks since the game started.": "ゲーム起動後に Zomboid/viewpoint-shaderpacks に追加されたシェーダーパックを検出します。",
        "Held while the free camera flies.": "自由カメラの飛行中に長押しします。",
        "How far behind the character the camera stands, in every state. The character keeps its size on the screen whatever the third-person field of view.": "各状態におけるキャラクター後方からのカメラ距離。3人称時の視野角(FOV)に関わらず画面上のキャラクターサイズが一定に保たれます。",
        "How fast the view turns while aiming, on top of the zoom's own: 1 keeps a turn the same across the screen however far the view is zoomed in. A pad's stick takes it in first person too.": "照準時のカメラ旋回速度(ズーム倍率補正込み)。1にするとズーム倍率に関わらず画面上の旋回速度が均一になります。コントローラースティックでも有効。",
        "How long your character's animation pauses when a melee blow lands, so the blow has weight. The time is made up at once after, so attacks last as long as without it. 0 turns it off.": "近接攻撃命中時のヒットストップ(アニメーション一時停止)時間。手応えを演出します(直後に巻き戻るため総攻撃時間は変わりません)。0で無効。",
        "How much a melee swing moves the camera, and how hard a blow jolts it when it lands, in first and third person.": "近接攻撃のスイング時のカメラ挙動、および命中時の画面揺れの強さ(1人称/3人称)。",
        "How much a shot kicks the camera, in first and third person. Where the shot goes does not change.": "銃撃時のカメラの跳ね上がり(反動)の強さ(1人称/3人称)。着弾位置自体は変わりません。",
        "How much a shot kicks the gun and the arms that hold it, in first and third person. Where the shot goes does not change.": "銃撃時の銃と腕の反動アニメーションの強さ(1人称/3人称)。着弾位置自体は変わりません。",
        "How much the camera moves on its own: the drift of a camera held by hand, the bob of the steps and the lean into turns. Lower it if the motion makes you feel unwell.": "カメラ独自の揺れ(手持ちのブレ、歩行時の上下動、旋回時の傾き)。酔いやすい場合は数値を下げてください。",
        "How much the camera shakes when you are hit, bitten or land hard, and with explosions and thunder near, in first and third person.": "被弾・噛まれ・高所着地・爆発や雷の際の画面の揺れ幅(1人称/3人称)。",
        "How much the field of view changes: wider when running, narrower when aiming.": "視野角(FOV)の変動幅: ダッシュ時に広く、照準時に狭くなります。",
        "How tall the relief stands, times the real ground's. The roads' and banks' limits hold at the height the relief was built at: rebake to hold them at another.": "起伏の高さ倍率。道路や傾斜の境界は構築時の高さに固定されます。",
        "In a vehicle: how far behind it the camera stands. The vehicle keeps its size on the screen whatever the third-person field of view.": "乗車時の車両後方からのカメラ距離。3人称視野角(FOV)に関わらず画面上の車両サイズが一定に保たれます。",
        "In third person: the camera over the other shoulder.": "3人称時: 反対側の肩越しカメラに切り替えます。",
        "In third person: the camera turns back behind the character.": "3人称時: カメラをキャラクターの正面・真後ろへ向け直します。",
        "Links the shader pack again with the options as they are now: it takes seconds.": "現在の設定でシェーダーパックを再リンクします(数秒かかります)。",
        "Normal, the art only, the light only, the volumetric light, the bounce light, the lamps' shadows, the sun's maps.": "通常、アートのみ、ライティングのみ、ボリュームライト、バウンス光、照明の影、太陽マップ。",
        "Playing alone, a pad's button or stick makes it the player's, and a key or the mouse gives the player back to the keyboard and mouse. Turn it off for split-screen with the keyboard: a second pad's press then joins as the game's.": "ソロプレイ時、パッド入力でパッド操作へ、キー/マウス入力でキーボード＆マウス操作へ自動切替します。キーボード併用の画面分割プレイ時は無効にしてください。",
        "Puts the rules above back to the build's and draws the relief the build made again.": "上記の設定をビルド時のデフォルトに戻し、起伏を再描画します。",
        "Squares the real ground is smoothed over before anything is built on it, away from towns: the hills keep their shape.": "郊外の地形起伏の平滑化範囲。丘陵の形状を保ちます。",
        "The camera moves to the other shoulder when a wall is in the way, and back when it clears. Never while aiming.": "壁が視界を遮る際にカメラが反対側の肩へ自動回避し、開けると戻ります(照準時は無効)。",
        "The culling of the rooms no one can see: on, frozen, off.": "視界外の部屋のカリング(描画省略): 有効、固定、無効。",
        "The first-person view on or off.": "1人称視点の有効/無効を切り替えます。",
        "The free camera back at the player's eyes.": "自由カメラをプレイヤーの視点位置へ戻します。",
        "The game's own menu on what the cursor points at, with the cursor free": "カーソル解除時にカーソル位置のゲーム内メニューを表示します。",
        "The overlay's next mode: full, compact, the graph alone, off.": "オーバーレイの表示モード切替: フル、コンパクト、グラフのみ、OFF。",
        "The same in towns, where much of the ground about is built on: gentler ground under the streets and houses, blended to the open's at a town's edge.": "街中の地形平滑化。市街地や住宅周辺の地面を滑らかにし、郊外と自然に接続します。",
        "The same while aiming: the camera moves between the two as aiming starts and ends.": "照準時も同様: 照準開始・終了に合わせてカメラ位置がスムーズに移動します。",
        "Whether the view is behind the shoulder or at the eyes on foot. The key that switches the camera sets it, and a vehicle keeps a choice of its own.": "徒歩時の視点を肩越し(3人称)にするか視線(1人称)にするかの初期設定。キー操作で随時切り替え可能。",
        "Whether the view is behind the vehicle or at the eyes while seated in one. The key that switches the camera sets it while seated.": "乗車時の視点を車両後方(3人称)にするか視線(1人称)にするかの初期設定。乗車中のキー操作で切り替え可能。",
        "Which shoulder the camera looks over. The shoulder key swaps it while playing.": "左右どちらの肩越しに視点を置くか。プレイ中にキーで左右反転できます。",
        # 車両・部品・共通名詞
        "Windshield": "フロントガラス",
        "Front Windshield": "フロントガラス",
        "Rear Windshield": "リアガラス",
        "Tire": "タイヤ",
        "Engine": "エンジン",
        "Battery": "バッテリー",
        "Brakes": "ブレーキ",
        "Suspension": "サスペンション",
        "Muffler": "マフラー",
        "Gas Tank": "燃料タンク",
        "Trunk": "トランク",
        "Glove Box": "グローブボックス",
        # アクション・状態 (Bandits/サバイバル共通)
        "Guard": "警備・護衛",
        "Hostile": "敵対的",
        "Friendly": "友好的",
        "Neutral": "中立",
        "Load": "装填・読み込み",
        "Loot": "戦利品・物資",
        "Main": "メイン",
        "Male": "男性",
        "Female": "女性",
        "NEW": "新規",
        "Over here!": "こっちだ!",
        "Rack": "コッキングする",
        "Raid": "レイド・襲撃",
        "Run": "走る",
        "Shouting": "大声で叫ぶ",
        "Shrug": "肩をすくめる",
        "Single": "単発",
        "Sleep": "寝る",
        "Smoke": "タバコを吸う",
        "Surrender": "降伏する",
        "Time": "時間",
        "Unbarricade": "バリケード解体",
        "Unequip": "装備解除",
        "Uninstall": "取り外す",
        "Walk": "歩く",
        "Wash": "洗う",
        # 叫び声・感嘆詞
        "Aaaaaargh!": "ぎゃあああ!",
        "Aaargh!": "あああ!",
        "Aaargh! Aaaaaargh! Aaaaaaaaaaargh!": "あああ! ぎゃあああ! うわあああ!",
        "Aaargh! F***k!": "あああ! クソッ!",
        "A... a...!": "あ... あ...!",
        "A.. a..!": "あ... あ...!",
        "Aa!": "ああ!",
        "A!": "あっ!",
        "Ała!": "痛っ!",
        "Ała! Kurwa!": "痛っ! クソが!",
        "!": "!",
        "!!!": "!!!",
        "...": "...",
        "...!": "...!",
        # 施設・組織
        "Gun Club": "射撃クラブ",
        "Speedway": "スピードウェイ",
    }

    CATEGORY_PREFIX_MAP = {
        "Controls": "操作",
        "Debug": "デバッグ",
        "Keys": "キー設定",
        "Controller": "コントローラー",
        "Graphics": "グラフィック",
        "World": "ワールド",
        "Audio": "オーディオ",
        "Sound": "サウンド",
        "Video": "画面・映像",
        "Display": "ディスプレイ",
        "Settings": "設定",
        "Options": "オプション",
        "General": "全般",
        "UI": "UI",
        "Camera": "カメラ",
        "Gameplay": "ゲームプレイ",
        "Keybindings": "キー割り当て",
    }

    SUB_TERMS = {
        # 視点・カメラ
        "Camera": "カメラ設定",
        "Camera profiles": "カメラプロファイル",
        "Free camera": "自由カメラ",
        "Third person": "3人称視点",
        "First person": "1人称視点",
        "View": "視点設定",
        "Views": "視点一覧",
        "Seated eye": "着席時視点",
        "Look": "視線・旋回",
        # コントローラー・操作
        "Aim assist": "エイムアシスト",
        "Buttons": "ボタン設定",
        "Loot menu": "探索メニュー",
        "Switching": "自動切り替え",
        "Mouse": "マウス設定",
        "Movement": "移動操作",
        "Gunplay": "銃撃・射撃",
        "Impact": "衝撃・ヒット演出",
        "Shooting": "射撃テスト",
        # グラフィック・システム・デバッグ
        "Advanced": "詳細設定",
        "General": "一般設定",
        "Shaders": "シェーダー",
        "Debug": "デバッグ",
        "Fixes": "修正機能",
        "Profiling": "プロファイリング",
        "Setup": "セットアップ",
        "Corpses": "死体描画",
        # ワールド・マップ
        "Relief": "地形起伏",
        "Chunks": "チャンク",
        "Far world": "遠景描画",
        "Floor preview": "フロアプレビュー",
        "Floors": "フロア・階層",
        "Levels of detail": "LOD(詳細度)",
        "Memory": "メモリ管理",
    }

    PHRASE_MAPPINGS = [
        ("Press a button of your pad for ", "コントローラーのボタンを押して割り当て: "),
        ("Press a key for ", "キーを押して割り当て: "),
        ("Toggle ", "切り替え: "),
        ("Enable ", "有効化: "),
        ("Disable ", "無効化: "),
    ]

    @classmethod
    def translate(cls, text: str, vanilla_dict: Optional[Dict[str, str]] = None) -> Optional[str]:
        # 1. 完全一致
        if text in cls.BUILTIN_RULES:
            return cls.BUILTIN_RULES[text]

        # 2. カテゴリプレフィックス (例: Controls/Camera, Controller/Aim assist, Keys/Swap shoulder)
        if "/" in text:
            parts = text.split("/", 1)
            cat, sub = parts[0], parts[1]
            if cat in cls.CATEGORY_PREFIX_MAP:
                cat_jp = cls.CATEGORY_PREFIX_MAP[cat]
                # サブタームの照合 (BUILTIN_RULES -> SUB_TERMS -> vanilla_dict)
                sub_tr = cls.BUILTIN_RULES.get(sub) or cls.SUB_TERMS.get(sub)
                if not sub_tr and vanilla_dict:
                    sub_tr = vanilla_dict.get(sub)

                if not sub_tr:
                    # サブテキストのフレーズマッチング
                    for en_prefix, jp_prefix in cls.PHRASE_MAPPINGS:
                        if sub.startswith(en_prefix):
                            rest = sub[len(en_prefix):].strip()
                            rest_tr = cls.BUILTIN_RULES.get(rest) or cls.SUB_TERMS.get(rest)
                            if not rest_tr and vanilla_dict:
                                rest_tr = vanilla_dict.get(rest)
                            if rest_tr:
                                sub_tr = f"{jp_prefix}{rest_tr}"
                                break

                if sub_tr:
                    return f"{cat_jp}/{sub_tr}"
                else:
                    # 未登録サブキーでもカテゴリ部分だけは確実に日本語化
                    return f"{cat_jp}/{sub}"

        # 3. 定型フレーズ (後続が日本語に翻訳できた場合のみ適用し、英語が残るならAI翻訳に任せる)
        for en_prefix, jp_prefix in cls.PHRASE_MAPPINGS:
            if text.startswith(en_prefix):
                rest = text[len(en_prefix):].strip()
                rest_trans = cls.BUILTIN_RULES.get(rest) or cls.SUB_TERMS.get(rest)
                if not rest_trans and vanilla_dict:
                    rest_trans = vanilla_dict.get(rest)
                if rest_trans:
                    return f"{jp_prefix}{rest_trans}"

        # 4. 複合名詞・施設名ルール (例: Irvington Gun Club -> Irvington 射撃クラブ)
        for term, jp_term in [
            ("Gun Club", "射撃クラブ"),
            ("Speedway", "スピードウェイ"),
            ("Police Department", "警察署"),
            ("Fire Department", "消防署"),
            ("Medical Center", "医療センター"),
            ("Community Center", "コミュニティセンター"),
        ]:
            if text.endswith(f" {term}"):
                prefix_name = text[:-len(term)-1].strip()
                return f"{prefix_name} {jp_term}"

        # 5. Bandits MOD Sandbox 定型文
        if text.startswith("BANDIT: "):
            role = text[8:].strip()
            role_map = {
                "GUARD": "警備",
                "RAIDER": "襲撃者",
                "RANDOM": "ランダム",
                "RANDOM (NO-RAIDER)": "ランダム (襲撃者なし)",
                "THIEF": "泥棒",
                "WANDERER": "放浪者",
            }
            return f"敵対勢力: {role_map.get(role, role)}"

        clan_match = re.match(r"^Bandits\s+Clan\s+(\d+)$", text, re.IGNORECASE)
        if clan_match:
            return f"敵対勢力 クラン {clan_match.group(1)}"

        # 6. 部分一致ルール
        if "what you aim at within reach is outlined" in text.lower():
            return "1人称/3人称時に手の届く範囲の対象を枠線強調しアイテム一覧を表示。OFF時は通常探索ウィンドウのみ。"
        if "how fast the camera moves" in text.lower():
            return "カメラの移動速度を調整します。"
        if "bushes and trees between the camera" in text.lower():
            return "カメラとキャラクターの間の草木を透過表示します。"

        return None


class OllamaClient:
    """Ollama APIクライアント (自動起動・モデル一覧取得・ダウンロード・推論)"""
    def __init__(self, host: str = "http://127.0.0.1:11434"):
        self.host = host.rstrip("/")

    @staticmethod
    def find_ollama_executable() -> Optional[str]:
        """PC内の ollama.exe のパスを検索"""
        p = shutil.which("ollama")
        if p:
            return p
        local_app = Path(os.environ.get("LOCALAPPDATA", "")) / "Programs" / "Ollama" / "ollama.exe"
        if local_app.is_file():
            return str(local_app)
        prog_files = Path(os.environ.get("ProgramFiles", "")) / "Ollama" / "ollama.exe"
        if prog_files.is_file():
            return str(prog_files)
        return None

    def ensure_started(self, timeout_sec: float = 6.0) -> bool:
        """Ollamaが未起動ならバックグラウンドで自動起動し、接続確認まで待機"""
        if self.is_available():
            return True

        exe_path = self.find_ollama_executable()
        if not exe_path:
            return False

        try:
            creationflags = 0
            if sys.platform == "win32":
                creationflags = 0x08000000  # CREATE_NO_WINDOW
            subprocess.Popen([exe_path, "serve"], creationflags=creationflags, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

            start_time = time.time()
            while time.time() - start_time < timeout_sec:
                time.sleep(0.4)
                if self.is_available():
                    return True
        except Exception as e:
            print(f"[Warn] Ollama自動起動失敗: {e}")
        return False

    def is_available(self) -> bool:
        try:
            req = urllib.request.Request(f"{self.host}/api/tags", method="GET")
            with urllib.request.urlopen(req, timeout=1.5) as resp:
                return resp.status == 200
        except Exception:
            return False

    def get_models(self) -> List[str]:
        try:
            req = urllib.request.Request(f"{self.host}/api/tags", method="GET")
            with urllib.request.urlopen(req, timeout=2.0) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                return [m["name"] for m in data.get("models", [])]
        except Exception:
            return []

    def list_installed_models(self) -> List[str]:
        """list_installed_models のエイリアス"""
        return self.get_models()

    def get_detailed_models(self) -> List[Dict[str, Any]]:
        """保持しているモデルの詳細一覧（名前・サイズGB等）を取得"""
        try:
            req = urllib.request.Request(f"{self.host}/api/tags", method="GET")
            with urllib.request.urlopen(req, timeout=2.5) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                result = []
                for m in data.get("models", []):
                    size_bytes = m.get("size", 0)
                    size_gb = round(size_bytes / (1024 ** 3), 2)
                    result.append({
                        "name": m.get("name", ""),
                        "size_gb": size_gb,
                    })
                return result
        except Exception:
            return []

    def pull_model(self, model_name: str, progress_callback: Optional[Callable[[str, float], None]] = None) -> bool:
        """モデルを自動ダウンロード (進捗ストリーミング)"""
        url = f"{self.host}/api/pull"
        payload = json.dumps({"name": model_name, "stream": True}).encode("utf-8")
        try:
            req = urllib.request.Request(url, data=payload, headers={"Content-Type": "application/json"}, method="POST")
            with urllib.request.urlopen(req, timeout=1200.0) as resp:
                for line in resp:
                    if not line:
                        continue
                    try:
                        chunk = json.loads(line.decode("utf-8"))
                        status = chunk.get("status", "")
                        total = chunk.get("total", 0)
                        completed = chunk.get("completed", 0)
                        pct = (completed / total) if total > 0 else 0.0
                        if progress_callback:
                            progress_callback(status, pct)
                    except Exception:
                        pass
            return True
        except Exception as e:
            print(f"[Error] Ollama pull failed: {e}")
            return False

    def translate_text(self, text: str, model: str, stop_event: Optional[threading.Event] = None, target_lang: str = "JP", has_placeholders: bool = False) -> Optional[str]:
        url = f"{self.host}/api/generate"
        sys_prompt = get_system_prompt(target_lang, has_placeholders=has_placeholders)
        payload = {
            "model": model,
            "system": sys_prompt,
            "prompt": f"English: {text}\nTranslation:",
            "stream": True,
            "options": {
                "temperature": 0.2,
                "top_p": 0.9,
                "num_predict": 1536,
            }
        }
        try:
            data = json.dumps(payload).encode("utf-8")
            req = urllib.request.Request(url, data=data, headers={"Content-Type": "application/json"}, method="POST")
            chunks = []
            with urllib.request.urlopen(req, timeout=45.0) as resp:
                for line in resp:
                    if stop_event and stop_event.is_set():
                        return None
                    if not line:
                        continue
                    try:
                        chunk = json.loads(line.decode("utf-8"))
                        piece = chunk.get("response", "")
                        chunks.append(piece)
                        if chunk.get("done", False):
                            break
                    except Exception:
                        pass
            full_text = "".join(chunks).strip()
            full_text = full_text.strip('"`\'')
            full_text = re.sub(r'<think>.*?</think>', '', full_text, flags=re.DOTALL).strip()
            
            # 万が一推論思考等で空文字になった場合の簡易リトライ
            if not full_text and not (stop_event and stop_event.is_set()):
                retry_payload = {
                    "model": model,
                    "prompt": f"サバイバルゲーム「Project Zomboid」のUI翻訳です。思考・解説をせず翻訳単語のみ出力してください。\nEnglish: {text}\n日本語訳:",
                    "stream": False,
                    "options": {"temperature": 0.1, "num_predict": 1024}
                }
                req_retry = urllib.request.Request(url, data=json.dumps(retry_payload).encode("utf-8"), headers={"Content-Type": "application/json"}, method="POST")
                with urllib.request.urlopen(req_retry, timeout=20.0) as resp_retry:
                    res_json = json.loads(resp_retry.read().decode("utf-8"))
                    full_text = res_json.get("response", "").strip().strip('"`\'')

            return full_text if full_text else None
        except urllib.error.HTTPError as e:
            err_msg = ""
            try:
                err_msg = e.read().decode("utf-8")
            except Exception:
                pass
            print(f"[Ollama Error] HTTP {e.code} for model '{model}': {err_msg}")
            return None
        except Exception as e:
            print(f"[Ollama Error] {e}")
            return None


class GeminiClient:
    """Google Gemini REST API クライアント (標準ライブラリのみで動作)"""
    @classmethod
    def test_key(cls, api_key: str, model: str = "gemini-1.5-flash") -> bool:
        if not api_key:
            return False
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={api_key}"
        payload = {
            "contents": [{"parts": [{"text": "Say Hello"}]}],
            "generationConfig": {"maxOutputTokens": 5}
        }
        try:
            data = json.dumps(payload).encode("utf-8")
            req = urllib.request.Request(url, data=data, headers={"Content-Type": "application/json"}, method="POST")
            with urllib.request.urlopen(req, timeout=6.0) as resp:
                return resp.status == 200
        except Exception:
            return False

    @classmethod
    def translate_text(cls, text: str, api_key: str, model: str = "gemini-1.5-flash", target_lang: str = "JP") -> Optional[str]:
        if not api_key:
            return None
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={api_key}"
        sys_prompt = get_system_prompt(target_lang)
        prompt = f"{sys_prompt}\n\nEnglish:\n{text}\n\nTranslation:"
        payload = {
            "contents": [{"parts": [{"text": prompt}]}],
            "generationConfig": {
                "temperature": 0.2,
                "maxOutputTokens": 200,
            }
        }
        try:
            data = json.dumps(payload).encode("utf-8")
            req = urllib.request.Request(url, data=data, headers={"Content-Type": "application/json"}, method="POST")
            with urllib.request.urlopen(req, timeout=12.0) as resp:
                result = json.loads(resp.read().decode("utf-8"))
                candidates = result.get("candidates", [])
                if candidates:
                    parts = candidates[0].get("content", {}).get("parts", [])
                    if parts:
                        trans = parts[0].get("text", "").strip()
                        return trans.strip('"`\'')
        except Exception as e:
            print(f"[Error] Gemini API translate failed: {e}")
        return None


class OpenAICompatibleClient:
    """OpenAI / Groq / DeepSeek / OpenRouter 等の OpenAI 互換 Chat API クライアント"""
    @classmethod
    def test_key(cls, base_url: str, api_key: str, model: str) -> bool:
        if not api_key:
            return False
        url = f"{base_url.rstrip('/')}/chat/completions"
        payload = {
            "model": model,
            "messages": [{"role": "user", "content": "Hi"}],
            "max_tokens": 5
        }
        try:
            data = json.dumps(payload).encode("utf-8")
            req = urllib.request.Request(
                url, data=data,
                headers={"Content-Type": "application/json", "Authorization": f"Bearer {api_key}"},
                method="POST"
            )
            with urllib.request.urlopen(req, timeout=6.0) as resp:
                return resp.status == 200
        except Exception:
            return False

    @classmethod
    def translate_text(cls, text: str, base_url: str, api_key: str, model: str, target_lang: str = "JP") -> Optional[str]:
        if not api_key:
            return None
        url = f"{base_url.rstrip('/')}/chat/completions"
        sys_prompt = get_system_prompt(target_lang)
        payload = {
            "model": model,
            "messages": [
                {"role": "system", "content": sys_prompt},
                {"role": "user", "content": f"Translate to target language:\n{text}"}
            ],
            "temperature": 0.2,
            "max_tokens": 200
        }
        try:
            data = json.dumps(payload).encode("utf-8")
            req = urllib.request.Request(
                url, data=data,
                headers={"Content-Type": "application/json", "Authorization": f"Bearer {api_key}"},
                method="POST"
            )
            with urllib.request.urlopen(req, timeout=15.0) as resp:
                result = json.loads(resp.read().decode("utf-8"))
                choices = result.get("choices", [])
                if choices:
                    content = choices[0].get("message", {}).get("content", "").strip()
                    content = re.sub(r'<think>.*?</think>', '', content, flags=re.DOTALL).strip()
                    return content.strip('"`\'')
        except Exception as e:
            print(f"[Error] OpenAI-compatible translate failed: {e}")
        return None


def run_translation_pipeline(
    items: List[Dict],
    vanilla_dict: Dict[str, str],
    progress_callback: Optional[Callable[[int, int, str], None]] = None,
    config: Optional[dict] = None,
    stop_event: Optional[threading.Event] = None
) -> Dict[str, str]:
    if config is None:
        config = ConfigManager.load()

    target_lang = config.get("target_language", "JP")
    engine_type = config.get("engine_type", "smart_dict")
    ollama_model = config.get("ollama_model", "qwen2.5:3b")
    api_provider = config.get("api_provider", "gemini")

    gemini_key = config.get("gemini_api_key", "").strip()
    gemini_model = config.get("gemini_model", "gemini-1.5-flash")

    openai_url = config.get("openai_base_url", "https://api.openai.com/v1").strip()
    openai_key = config.get("openai_api_key", "").strip()
    openai_model = config.get("openai_model", "gpt-4o-mini").strip()

    ollama = OllamaClient()
    ollama_ready = ollama.is_available()
    if engine_type == "ollama" and not ollama_ready:
        if ollama.ensure_started(timeout_sec=5.0):
            ollama_ready = True

    results = {}
    total = len(items)

    for idx, item in enumerate(items):
        if stop_event and stop_event.is_set():
            break

        en = item["en"] if isinstance(item, dict) else item
        masked_en, placeholders = MaskingEngine.mask(en)

        # 1. 公式バニラ対訳（完全無料・最優先・完全一致）
        translated = vanilla_dict.get(masked_en)

        # 2. 定番UI短縮ルール (日本語対象時)
        if not translated and target_lang == "JP":
            translated = RuleBasedTranslator.translate(masked_en, vanilla_dict=vanilla_dict)

        # 3. 指定されたAIエンジンによる翻訳
        if not translated:
            if stop_event and stop_event.is_set():
                break
            if engine_type == "api":
                if api_provider == "gemini" and gemini_key:
                    translated = GeminiClient.translate_text(masked_en, gemini_key, gemini_model, target_lang=target_lang)
                elif api_provider == "openai" and openai_key:
                    translated = OpenAICompatibleClient.translate_text(masked_en, openai_url, openai_key, openai_model, target_lang=target_lang)
            elif engine_type == "ollama" and ollama_ready:
                has_ph = len(placeholders) > 0
                translated = OllamaClient().translate_text(masked_en, ollama_model, stop_event=stop_event, target_lang=target_lang, has_placeholders=has_ph)

        if stop_event and stop_event.is_set():
            break

        # 4. フォールバック: 翻訳が見つからなかった項目は原文で偽装せず未翻訳のまま維持
        if not translated:
            continue

        # プレースホルダー幻覚ガード: 原文にない __PH が紛れ込んだ場合は弾く
        if len(placeholders) == 0 and "__PH" in translated:
            continue

        # マスキング復元
        final_text = MaskingEngine.unmask(translated, placeholders)

        # 全角英数字記号を半角に正規化 (UI文字幅対策)
        final_text = final_text.translate(str.maketrans(
            "０１２３４５６７８９ＡＢＣＤＥＦＧＨＩＪＫＬＭＮＯＰＱＲＳＴＵＶＷＸＹＺａｂｃｄｅｆｇｈｉｊｋｌｍｎｏｐｑｒｓｔｕｖｗｘｙｚ：／（）［］",
            "0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz:/()[]"
        ))

        results[en] = final_text

        if progress_callback:
            progress_callback(idx + 1, total, f"{en} ➡ {final_text}")

    return results
