"""
zTranzlator - Modern Minimalist Desktop Application (Phase 4)
Project Zomboid Build 42 Mod Translator
Built with CustomTkinter & Meiryo UI for clean, legible Japanese typography.
Supports: Smart Dictionary, Dynamic Ollama Models (w/ auto-pull), and Google Gemini REST API.
"""

import json
import os
import shutil
import subprocess
import sys
import threading
try:
    import psutil
except ImportError:
    psutil = None
import webbrowser
import tkinter as tk
from tkinter import ttk, messagebox, filedialog
from pathlib import Path
from typing import Dict, List, Optional

import customtkinter as ctk

# 自作モジュール
from dict_builder import find_pz_directory, build_master_dictionary
from mod_scanner import scan_mod, load_vanilla_dict
from translator_engine import (
    run_translation_pipeline, OllamaClient, GeminiClient, ConfigManager,
    estimate_text_width, check_overflow_risk
)
from mod_generator import generate_patch_mod
from i18n import t, set_ui_language, get_ui_language, SUPPORTED_UI_LANGUAGES, SUPPORTED_TARGET_LANGUAGES


# フォント設定 (メイリオ / Meiryo UI で統一)
FONT_FAMILY = "Meiryo UI"
FONT_LOGO = (FONT_FAMILY, 16, "bold")
FONT_TITLE = (FONT_FAMILY, 13, "bold")
FONT_LABEL_BOLD = (FONT_FAMILY, 11, "bold")
FONT_NORMAL = (FONT_FAMILY, 11)
FONT_BUTTON = (FONT_FAMILY, 11, "bold")
FONT_HERO_BUTTON = (FONT_FAMILY, 12, "bold")
FONT_BADGE = (FONT_FAMILY, 10, "bold")
FONT_SMALL = (FONT_FAMILY, 9)
FONT_TABLE = (FONT_FAMILY, 10)
FONT_TABLE_HEAD = (FONT_FAMILY, 10, "bold")
FONT_STATUS = (FONT_FAMILY, 11, "bold")
FONT_STATUS_NORMAL = (FONT_FAMILY, 11)

# CustomTkinter テーマ設定
ctk.set_appearance_mode("Dark")
ctk.set_default_color_theme("blue")

def find_default_workshop_path() -> Path:
    """Steam Workshop (108600) フォルダを全ドライブ・ライブラリから自動検出"""
    candidates = [
        Path(r"C:\Program Files (x86)\Steam\steamapps\workshop\content\108600"),
        Path(r"C:\Program Files\Steam\steamapps\workshop\content\108600"),
        Path(r"D:\SteamLibrary\steamapps\workshop\content\108600"),
        Path(r"E:\SteamLibrary\steamapps\workshop\content\108600"),
        Path(r"F:\SteamLibrary\steamapps\workshop\content\108600"),
    ]
    pz = find_pz_directory()
    if pz:
        try:
            ws = pz.parent.parent / "workshop" / "content" / "108600"
            if ws.is_dir() and ws not in candidates:
                candidates.insert(0, ws)
        except Exception:
            pass

    for p in candidates:
        if p.is_dir():
            return p
    return candidates[0]


DEFAULT_WORKSHOP_PATH = find_default_workshop_path()
DEFAULT_USER_MODS_PATH = Path.home() / "Zomboid" / "mods"


def get_item_row_meta(en: str, jp: str, base_status: str) -> tuple:
    """ステータス表示文字列と色タグを算出 (幅過大警告を自動判定)"""
    if not jp:
        return "未翻訳", "untranslated"

    is_risk, _ = check_overflow_risk(en, jp)
    status_str = f"{base_status} ⚠️" if is_risk else base_status

    if is_risk:
        tag = "overflow"
    elif base_status == "手動修正":
        tag = "custom"
    elif base_status == "公式一致":
        tag = "matched"
    elif base_status == "既存継承":
        tag = "inherited"
    elif base_status == "AI翻訳":
        tag = "ai"
    elif base_status == "辞書翻訳":
        tag = "dict_trans"
    elif base_status == "廃止キー":
        tag = "deprecated"
    else:
        tag = "matched"
    return status_str, tag


class ModernEditDialog(ctk.CTkToplevel):
    """セルダブルクリック時に開く手動編集モーダル (文字幅推定・UIはみ出し警告アシスト付き)"""
    def __init__(self, parent, original_text: str, current_translation: str):
        super().__init__(parent)
        self.title("✏️ 訳文の手動編集 (UI幅アシスト)")
        self.geometry("580x330")
        self.resizable(False, False)
        self.transient(parent)
        self.grab_set()

        self.configure(fg_color="#14171f")
        self.result = None
        self.original_text = original_text

        main_frame = ctk.CTkFrame(self, fg_color="transparent")
        main_frame.pack(fill="both", expand=True, padx=24, pady=18)

        # 原文表示
        ctk.CTkLabel(main_frame, text="原文 (English)", font=FONT_LABEL_BOLD, text_color="#94a3b8").pack(anchor="w")
        orig_box = ctk.CTkLabel(
            main_frame, text=original_text, wraplength=520, justify="left", anchor="w",
            font=FONT_NORMAL, text_color="#f8fafc", fg_color="#22252d",
            corner_radius=8, padx=12, pady=8
        )
        orig_box.pack(fill="x", pady=(4, 10))

        # 訳文入力
        ctk.CTkLabel(main_frame, text="訳文 (日本語)", font=FONT_LABEL_BOLD, text_color="#94a3b8").pack(anchor="w")
        self.entry = ctk.CTkEntry(
            main_frame, width=520, height=36, font=FONT_NORMAL,
            fg_color="#22252d", border_color="#334155", corner_radius=8
        )
        self.entry.insert(0, current_translation)
        self.entry.pack(fill="x", pady=(4, 4))
        self.entry.focus_set()

        # リアルタイム幅計算・警告ラベル
        self.width_info_lbl = ctk.CTkLabel(main_frame, text="", font=FONT_SMALL, justify="left", anchor="w")
        self.width_info_lbl.pack(fill="x", pady=(0, 10))
        self.entry.bind("<KeyRelease>", self.on_text_changed)
        self.on_text_changed()

        # ボタンバー
        btn_frame = ctk.CTkFrame(main_frame, fg_color="transparent")
        btn_frame.pack(fill="x")

        save_btn = ctk.CTkButton(
            btn_frame, text="保存する", width=110, height=34, font=FONT_BUTTON,
            fg_color="#3b82f6", hover_color="#2563eb", corner_radius=8, command=self.on_save
        )
        save_btn.pack(side="right", padx=(8, 0))

        cancel_btn = ctk.CTkButton(
            btn_frame, text="キャンセル", width=90, height=34, font=FONT_NORMAL,
            fg_color="#334155", hover_color="#475569", corner_radius=8, command=self.destroy
        )
        cancel_btn.pack(side="right")

        self.bind("<Return>", lambda e: self.on_save())
        self.bind("<Escape>", lambda e: self.destroy())

    def on_text_changed(self, event=None):
        text = self.entry.get().strip()
        en_w = estimate_text_width(self.original_text)
        jp_w = estimate_text_width(text)
        ratio = (jp_w / en_w * 100) if en_w > 0 else 100

        is_risk, _ = check_overflow_risk(self.original_text, text)
        if is_risk:
            self.width_info_lbl.configure(
                text=f"⚠️ 幅比率: {int(ratio)}% (原文: {int(en_w)} / 訳: {int(jp_w)}) ➡ ボタン枠外へはみ出す可能性大。漢字化や短縮を推奨。",
                text_color="#fbbf24"
            )
        else:
            self.width_info_lbl.configure(
                text=f"✅ 幅比率: {int(ratio)}% (原文: {int(en_w)} / 訳: {int(jp_w)}) ➡ UI枠内に適した良好な文字幅です。",
                text_color="#34d399"
            )

    def on_save(self):
        self.result = self.entry.get().strip()
        self.destroy()


class ModernSettingsDialog(ctk.CTkToplevel):
    """翻訳エンジン設定モーダル (Ollamaリンク/モデル一覧/直接DL ＆ Gemini / OpenAI互換API設定)"""
    def __init__(self, parent):
        super().__init__(parent)
        self.title("⚙️ 翻訳エンジン設定")
        self.geometry("740x740")
        self.resizable(False, False)
        self.transient(parent)
        self.grab_set()

        self.configure(fg_color="#14171f")
        self.protocol("WM_DELETE_WINDOW", self.on_window_close)
        self.parent = parent
        self.config = ConfigManager.load()
        self.ollama = OllamaClient()

        self.engine_var = tk.StringVar(value=self.config.get("engine_type", "smart_dict"))
        self.api_provider_var = tk.StringVar(value=self.config.get("api_provider", "gemini"))

        main_box = ctk.CTkFrame(self, fg_color="transparent")
        main_box.pack(fill="both", expand=True, padx=24, pady=16)

        # --- 言語設定カード (UI言語 & 翻訳先言語) ---
        lang_card = ctk.CTkFrame(main_box, fg_color="#181c26", corner_radius=10, border_width=1, border_color="#2b3242")
        lang_card.pack(fill="x", pady=(0, 10), ipadx=8, ipady=6)

        ctk.CTkLabel(lang_card, text=f"🌐 {t('sec_lang_settings')}", font=FONT_TITLE, text_color="#38bdf8").pack(anchor="w", padx=12, pady=(4, 4))

        lang_row = ctk.CTkFrame(lang_card, fg_color="transparent")
        lang_row.pack(fill="x", padx=12, pady=2)

        # 1. UI表示言語
        ui_box = ctk.CTkFrame(lang_row, fg_color="transparent")
        ui_box.pack(side="left", padx=(0, 16))
        ctk.CTkLabel(ui_box, text=t("lbl_ui_lang"), font=FONT_SMALL, text_color="#cbd5e1").pack(anchor="w", pady=(0, 2))
        
        ui_options = list(SUPPORTED_UI_LANGUAGES.values())
        cur_ui_code = self.config.get("ui_language", "ja")
        cur_ui_label = SUPPORTED_UI_LANGUAGES.get(cur_ui_code, "日本語 (Japanese)")
        self.ui_lang_menu = ctk.CTkOptionMenu(
            ui_box, values=ui_options, width=190, height=28, font=FONT_NORMAL, dropdown_font=FONT_NORMAL,
            fg_color="#2e384d", button_color="#3b82f6", corner_radius=6,
            dropdown_fg_color="#1e222b", dropdown_hover_color="#334155"
        )
        self.ui_lang_menu.set(cur_ui_label)
        self.ui_lang_menu.pack(anchor="w")

        # 2. MOD翻訳先言語
        target_box = ctk.CTkFrame(lang_row, fg_color="transparent")
        target_box.pack(side="left")
        ctk.CTkLabel(target_box, text=t("lbl_target_lang"), font=FONT_SMALL, text_color="#cbd5e1").pack(anchor="w", pady=(0, 2))

        target_options = [f"{k}: {v['name']} ({v['en_name']})" for k, v in SUPPORTED_TARGET_LANGUAGES.items()]
        cur_target_code = self.config.get("target_language", "JP")
        cur_target_meta = SUPPORTED_TARGET_LANGUAGES.get(cur_target_code, SUPPORTED_TARGET_LANGUAGES["JP"])
        cur_target_label = f"{cur_target_code}: {cur_target_meta['name']} ({cur_target_meta['en_name']})"
        self.target_lang_menu = ctk.CTkOptionMenu(
            target_box, values=target_options, width=250, height=28, font=FONT_NORMAL, dropdown_font=FONT_NORMAL,
            fg_color="#2e384d", button_color="#10b981", corner_radius=6,
            dropdown_fg_color="#1e222b", dropdown_hover_color="#334155"
        )
        self.target_lang_menu.set(cur_target_label)
        self.target_lang_menu.pack(anchor="w")

        ctk.CTkLabel(lang_card, text=t("note_target_lang"), font=FONT_SMALL, text_color="#64748b").pack(anchor="w", padx=12, pady=(4, 2))

        ctk.CTkLabel(main_box, text=t("sec_engine_settings"), font=FONT_TITLE, text_color="#f8fafc").pack(anchor="w", pady=(6, 8))

        # --- オプション 1: 内蔵スマート辞書 ---
        box1 = ctk.CTkFrame(main_box, fg_color="#1b1f2b", corner_radius=10, border_width=1, border_color="#282e3d")
        box1.pack(fill="x", pady=4, ipadx=10, ipady=6)
        rb1 = ctk.CTkRadioButton(
            box1, text="内蔵スマート辞書 (完全オフライン / 超高速)", variable=self.engine_var, value="smart_dict",
            font=FONT_LABEL_BOLD, text_color="#f1f5f9"
        )
        rb1.pack(anchor="w", padx=12, pady=(4, 2))
        ctk.CTkLabel(box1, text="公式バニラ対訳 35,000語 ＋ ゲームUI特化の短縮漢字ルール。GPU・APIキー不要で即動作。", font=FONT_SMALL, text_color="#94a3b8").pack(anchor="w", padx=36, pady=(0, 4))

        # --- オプション 2: Ollama (ローカルLLM) ---
        box2 = ctk.CTkFrame(main_box, fg_color="#1b1f2b", corner_radius=10, border_width=1, border_color="#282e3d")
        box2.pack(fill="x", pady=4, ipadx=10, ipady=6)
        rb2 = ctk.CTkRadioButton(
            box2, text="Ollama ローカルLLM (完全プライベート / GPU推奨)", variable=self.engine_var, value="ollama",
            font=FONT_LABEL_BOLD, text_color="#f1f5f9"
        )
        rb2.pack(anchor="w", padx=12, pady=(4, 2))

        ollama_frame = ctk.CTkFrame(box2, fg_color="transparent")
        ollama_frame.pack(fill="x", padx=36, pady=(2, 6))

        # 状態表示・再検出ボタン・リンク行
        top_row = ctk.CTkFrame(ollama_frame, fg_color="transparent")
        top_row.pack(fill="x", pady=(0, 4))

        self.ollama_status_lbl = ctk.CTkLabel(
            top_row, text="🔄 Ollama 接続確認中...", font=FONT_SMALL, text_color="#38bdf8"
        )
        self.ollama_status_lbl.pack(side="left", padx=(0, 10))

        ctk.CTkButton(
            top_row, text="🔄 再検出 / 起動", width=105, height=24, font=FONT_SMALL,
            fg_color="#0284c7", hover_color="#0369a1", corner_radius=5,
            command=lambda: self.refresh_ollama_models(auto_start=True)
        ).pack(side="left", padx=(0, 6))

        ctk.CTkButton(
            top_row, text="🌐 公式サイト", width=85, height=24, font=FONT_SMALL,
            fg_color="#1e293b", hover_color="#334155", corner_radius=5,
            command=lambda: webbrowser.open("https://ollama.com")
        ).pack(side="left", padx=(0, 6))

        ctk.CTkButton(
            top_row, text="📚 モデル検索", width=85, height=24, font=FONT_SMALL,
            fg_color="#1e293b", hover_color="#334155", corner_radius=5,
            command=lambda: webbrowser.open("https://ollama.com/library")
        ).pack(side="left")

        # 使用モデル選択行
        model_row = ctk.CTkFrame(ollama_frame, fg_color="transparent")
        model_row.pack(fill="x", pady=4)
        ctk.CTkLabel(model_row, text="使用モデル:", font=FONT_NORMAL, text_color="#cbd5e1").pack(side="left", padx=(0, 8))

        self.model_dropdown = ctk.CTkOptionMenu(
            model_row, values=["(検出中...)"], width=300, height=28, font=FONT_NORMAL, dropdown_font=FONT_NORMAL,
            fg_color="#2e384d", button_color="#3b82f6", corner_radius=6,
            dropdown_fg_color="#1e222b", dropdown_hover_color="#334155"
        )
        self.model_dropdown.pack(side="left")

        # 保有モデル一覧表示エリア
        models_box = ctk.CTkFrame(ollama_frame, fg_color="#141824", corner_radius=8, border_width=1, border_color="#262f40")
        models_box.pack(fill="x", pady=(4, 6), padx=2, ipady=4)

        models_head = ctk.CTkFrame(models_box, fg_color="transparent")
        models_head.pack(fill="x", padx=8, pady=(2, 2))
        ctk.CTkLabel(models_head, text="📦 インストール済みモデル一覧 (クリックで即時選択):", font=FONT_SMALL, text_color="#94a3b8").pack(side="left")

        self.owned_models_scroll = ctk.CTkScrollableFrame(
            models_box, height=52, fg_color="transparent", orientation="horizontal"
        )
        self.owned_models_scroll.pack(fill="x", padx=6, pady=(0, 2))

        # おすすめモデル導入行
        rec_row = ctk.CTkFrame(ollama_frame, fg_color="transparent")
        rec_row.pack(fill="x", pady=(4, 2))
        ctk.CTkLabel(rec_row, text="おすすめ導入:", font=FONT_SMALL, text_color="#94a3b8").pack(side="left", padx=(0, 6))

        self.rec_model_var = ctk.StringVar(value="gemma4:e4b")
        rec_menu = ctk.CTkOptionMenu(
            rec_row,
            values=[
                "gemma4:e4b (★イチオシ推奨・約6.1GB)",
                "qwen2.5:7b (高精度標準・約4.7GB)",
                "qwen2.5:3b (超軽量版・約2.0GB)",
                "qwen2.5:1.5b (超軽量/CPU・約1.0GB)",
                "gemma2:2b (Google軽量・約1.6GB)",
                "llama3.2:3b (Meta最新・約2.0GB)",
            ],
            variable=self.rec_model_var, width=240, height=26, font=FONT_SMALL, dropdown_font=FONT_SMALL,
            fg_color="#1e293b", button_color="#0284c7", corner_radius=6,
            dropdown_fg_color="#1e222b", dropdown_hover_color="#334155"
        )
        rec_menu.pack(side="left", padx=(0, 6))

        rec_dl_btn = ctk.CTkButton(
            rec_row, text="導入実行", width=80, height=26, font=FONT_SMALL,
            fg_color="#0284c7", hover_color="#0369a1", corner_radius=6, command=self.on_pull_selected_rec
        )
        rec_dl_btn.pack(side="left")

        # モデル名直接入力行
        direct_row = ctk.CTkFrame(ollama_frame, fg_color="transparent")
        direct_row.pack(fill="x", pady=(4, 2))
        ctk.CTkLabel(direct_row, text="モデル名直接DL:", font=FONT_SMALL, text_color="#94a3b8").pack(side="left", padx=(0, 6))
        self.custom_pull_entry = ctk.CTkEntry(
            direct_row, width=240, height=26, font=FONT_SMALL, placeholder_text="例: deepseek-r1:8b",
            fg_color="#181c26", border_color="#334155", corner_radius=6
        )
        self.custom_pull_entry.pack(side="left", padx=(0, 6))

        direct_dl_btn = ctk.CTkButton(
            direct_row, text="直接DL", width=80, height=26, font=FONT_SMALL,
            fg_color="#334155", hover_color="#475569", corner_radius=6, command=self.on_pull_custom
        )
        direct_dl_btn.pack(side="left")

        self.pull_status_lbl = ctk.CTkLabel(ollama_frame, text="", font=FONT_SMALL, text_color="#38bdf8")
        self.pull_status_lbl.pack(anchor="w", pady=(2, 0))

        # --- オプション 3: クラウドAI API ---
        box3 = ctk.CTkFrame(main_box, fg_color="#1b1f2b", corner_radius=10, border_width=1, border_color="#282e3d")
        box3.pack(fill="x", pady=4, ipadx=10, ipady=6)
        rb3 = ctk.CTkRadioButton(
            box3, text="クラウドAI API (低スペックPCでも超高速 / 無料枠あり)", variable=self.engine_var, value="api",
            font=FONT_LABEL_BOLD, text_color="#f1f5f9"
        )
        rb3.pack(anchor="w", padx=12, pady=(4, 2))

        api_frame = ctk.CTkFrame(box3, fg_color="transparent")
        api_frame.pack(fill="x", padx=36, pady=(2, 6))

        # プロバイダ選択
        prov_row = ctk.CTkFrame(api_frame, fg_color="transparent")
        prov_row.pack(fill="x", pady=3)
        ctk.CTkLabel(prov_row, text="プロバイダ:", font=FONT_NORMAL, text_color="#cbd5e1").pack(side="left", padx=(0, 8))
        self.provider_menu = ctk.CTkOptionMenu(
            prov_row, values=["Google Gemini API (無料枠あり)", "OpenAI 互換 (Groq / DeepSeek / OpenAI)"],
            command=self.on_provider_changed, width=280, height=28, font=FONT_NORMAL, dropdown_font=FONT_NORMAL,
            fg_color="#2e384d", button_color="#3b82f6", corner_radius=6,
            dropdown_fg_color="#1e222b", dropdown_hover_color="#334155"
        )
        init_prov = "Google Gemini API (無料枠あり)" if self.config.get("api_provider", "gemini") == "gemini" else "OpenAI 互換 (Groq / DeepSeek / OpenAI)"
        self.provider_menu.set(init_prov)
        self.provider_menu.pack(side="left")

        # Gemini用設定コンテナ
        self.gemini_box = ctk.CTkFrame(api_frame, fg_color="transparent")
        key_row = ctk.CTkFrame(self.gemini_box, fg_color="transparent")
        key_row.pack(fill="x", pady=2)
        ctk.CTkLabel(key_row, text="Gemini APIキー:", font=FONT_SMALL, text_color="#cbd5e1").pack(side="left", padx=(0, 6))
        self.gemini_key_entry = ctk.CTkEntry(
            key_row, width=280, height=28, font=FONT_SMALL,
            placeholder_text="AIzaSy...", fg_color="#181c26", border_color="#334155", corner_radius=6
        )
        self.gemini_key_entry.insert(0, self.config.get("gemini_api_key", ""))
        self.gemini_key_entry.pack(side="left", padx=(0, 6))
        ctk.CTkButton(
            key_row, text="接続テスト", width=75, height=28, font=FONT_SMALL,
            fg_color="#334155", hover_color="#475569", corner_radius=6, command=self.on_test_gemini
        ).pack(side="left")

        g_model_row = ctk.CTkFrame(self.gemini_box, fg_color="transparent")
        g_model_row.pack(fill="x", pady=2)
        ctk.CTkLabel(g_model_row, text="モデル名 (自由入力可):", font=FONT_SMALL, text_color="#94a3b8").pack(side="left", padx=(0, 6))
        self.gemini_model_entry = ctk.CTkComboBox(
            g_model_row, values=["gemini-1.5-flash", "gemini-2.0-flash", "gemini-1.5-pro", "gemini-2.0-flash-lite"],
            width=200, height=26, font=FONT_SMALL, fg_color="#181c26", border_color="#334155", corner_radius=6
        )
        self.gemini_model_entry.set(self.config.get("gemini_model", "gemini-1.5-flash"))
        self.gemini_model_entry.pack(side="left", padx=(0, 10))
        ctk.CTkButton(
            g_model_row, text="🔑 無料APIキーを取得 (Google AI Studio)", width=220, height=26, font=FONT_SMALL,
            fg_color="transparent", text_color="#38bdf8", hover_color="#1e293b",
            command=lambda: webbrowser.open("https://aistudio.google.com/app/apikey")
        ).pack(side="left")

        # OpenAI互換用設定コンテナ
        self.openai_box = ctk.CTkFrame(api_frame, fg_color="transparent")
        url_row = ctk.CTkFrame(self.openai_box, fg_color="transparent")
        url_row.pack(fill="x", pady=2)
        ctk.CTkLabel(url_row, text="Base URL:", font=FONT_SMALL, text_color="#cbd5e1").pack(side="left", padx=(0, 6))
        self.openai_url_entry = ctk.CTkComboBox(
            url_row, values=[
                "https://api.openai.com/v1",
                "https://api.groq.com/openai/v1",
                "https://api.deepseek.com",
                "https://openrouter.ai/api/v1"
            ], width=260, height=26, font=FONT_SMALL, fg_color="#181c26", border_color="#334155", corner_radius=6
        )
        self.openai_url_entry.set(self.config.get("openai_base_url", "https://api.openai.com/v1"))
        self.openai_url_entry.pack(side="left")

        o_key_row = ctk.CTkFrame(self.openai_box, fg_color="transparent")
        o_key_row.pack(fill="x", pady=2)
        ctk.CTkLabel(o_key_row, text="APIキー:   ", font=FONT_SMALL, text_color="#cbd5e1").pack(side="left", padx=(0, 6))
        self.openai_key_entry = ctk.CTkEntry(
            o_key_row, width=260, height=26, font=FONT_SMALL,
            placeholder_text="sk-...", fg_color="#181c26", border_color="#334155", corner_radius=6
        )
        self.openai_key_entry.insert(0, self.config.get("openai_api_key", ""))
        self.openai_key_entry.pack(side="left", padx=(0, 6))
        ctk.CTkButton(
            o_key_row, text="接続テスト", width=75, height=26, font=FONT_SMALL,
            fg_color="#334155", hover_color="#475569", corner_radius=6, command=self.on_test_openai
        ).pack(side="left")

        o_model_row = ctk.CTkFrame(self.openai_box, fg_color="transparent")
        o_model_row.pack(fill="x", pady=2)
        ctk.CTkLabel(o_model_row, text="モデル名: ", font=FONT_SMALL, text_color="#cbd5e1").pack(side="left", padx=(0, 6))
        self.openai_model_entry = ctk.CTkComboBox(
            o_model_row, values=["gpt-4o-mini", "deepseek-chat", "llama-3.3-70b-versatile", "gpt-4o"],
            width=260, height=26, font=FONT_SMALL, fg_color="#181c26", border_color="#334155", corner_radius=6
        )
        self.openai_model_entry.set(self.config.get("openai_model", "gpt-4o-mini"))
        self.openai_model_entry.pack(side="left")

        # 初期表示の切り替え
        self.on_provider_changed(self.provider_menu.get())

        # Ollamaモデルの初期ロード（未起動なら自動起動）
        self.refresh_ollama_models(auto_start=True)

        # --- 下部アクションバー ---
        action_bar = ctk.CTkFrame(main_box, fg_color="transparent")
        action_bar.pack(fill="x", side="bottom", pady=(12, 0))

        save_btn = ctk.CTkButton(
            action_bar, text="設定を保存", width=120, height=36, font=FONT_BUTTON,
            fg_color="#10b981", hover_color="#059669", corner_radius=8, command=self.on_save
        )
        save_btn.pack(side="right", padx=(8, 0))

        cancel_btn = ctk.CTkButton(
            action_bar, text="キャンセル", width=90, height=36, font=FONT_NORMAL,
            fg_color="#334155", hover_color="#475569", corner_radius=8, command=self.destroy
        )
        cancel_btn.pack(side="right")

    def refresh_ollama_models(self, auto_start: bool = True, select_model: Optional[str] = None):
        """Ollamaの起動確認・自動起動およびインストール済みモデル一覧の同期"""
        self.ollama_status_lbl.configure(text="🔄 接続確認・モデル情報取得中...", text_color="#38bdf8")

        def worker():
            is_up = self.ollama.is_available()
            if not is_up and auto_start:
                exe = self.ollama.find_ollama_executable()
                if exe:
                    self.after(0, lambda: self.ollama_status_lbl.configure(text="🔄 Ollama を自動起動中...", text_color="#f59e0b"))
                    self.ollama.ensure_started(timeout_sec=6.0)
                    is_up = self.ollama.is_available()

            detailed = self.ollama.get_detailed_models() if is_up else []
            self.after(0, lambda: self._apply_ollama_models_ui(is_up, detailed, select_model))

        threading.Thread(target=worker, daemon=True).start()

    def _apply_ollama_models_ui(self, is_up: bool, detailed_models: list, select_model: Optional[str] = None):
        """取得したモデル一覧をドロップダウンと保有モデルエリアへ反映"""
        for w in self.owned_models_scroll.winfo_children():
            w.destroy()

        if not is_up:
            exe = self.ollama.find_ollama_executable()
            if exe:
                self.ollama_status_lbl.configure(text="⚠️ Ollama停止中 (再検出を押すと自動起動します)", text_color="#f59e0b")
            else:
                self.ollama_status_lbl.configure(text="❌ Ollama未検出 (公式サイトからインストールしてください)", text_color="#ef4444")
            self.model_dropdown.configure(values=["(Ollama未起動)"])
            self.model_dropdown.set("(Ollama未起動)")
            ctk.CTkLabel(self.owned_models_scroll, text="Ollamaが起動していないためモデルを表示できません", font=FONT_SMALL, text_color="#64748b").pack(padx=8, pady=4)
            return

        count = len(detailed_models)
        self.ollama_status_lbl.configure(text=f"🟢 接続成功 (自動起動済 | 保有モデル: {count} 件)", text_color="#10b981")

        if not detailed_models:
            self.model_dropdown.configure(values=["(モデル未導入 - 下記から導入してください)"])
            self.model_dropdown.set("(モデル未導入 - 下記から導入してください)")
            ctk.CTkLabel(self.owned_models_scroll, text="インストール済みモデルはありません (下記のおすすめ導入からダウンロードしてください)", font=FONT_SMALL, text_color="#94a3b8").pack(padx=8, pady=4)
            return

        dropdown_items = []
        target_selection = None
        saved_model = select_model or self.config.get("ollama_model", "qwen2.5:3b")

        for m in detailed_models:
            name = m["name"]
            size_gb = m["size_gb"]
            display_text = f"{name} ({size_gb} GB)"
            dropdown_items.append(display_text)

            if name == saved_model or display_text == saved_model:
                target_selection = display_text

            # 保有モデルバッジ (クリックでドロップダウン即時選択)
            def make_badge(d_text):
                btn = ctk.CTkButton(
                    self.owned_models_scroll, text=d_text, height=24, font=FONT_SMALL,
                    fg_color="#1e293b", hover_color="#334155", corner_radius=5,
                    command=lambda: self.model_dropdown.set(d_text)
                )
                btn.pack(side="left", padx=3, pady=2)
            make_badge(display_text)

        self.model_dropdown.configure(values=dropdown_items)
        if target_selection:
            self.model_dropdown.set(target_selection)
        elif dropdown_items:
            self.model_dropdown.set(dropdown_items[0])

    def on_provider_changed(self, choice: str):
        if "Gemini" in choice:
            self.openai_box.pack_forget()
            self.gemini_box.pack(fill="x", pady=(4, 0))
        else:
            self.gemini_box.pack_forget()
            self.openai_box.pack(fill="x", pady=(4, 0))

    def on_pull_selected_rec(self):
        val = self.rec_model_var.get()
        model_name = val.split(" ")[0].strip()
        self.execute_pull(model_name)

    def on_pull_custom(self):
        model_name = self.custom_pull_entry.get().strip()
        if not model_name:
            messagebox.showwarning("警告", "ダウンロードするモデル名を入力してください。")
            return
        self.execute_pull(model_name)

    def execute_pull(self, model_name: str):
        if not self.ollama.is_available():
            messagebox.showerror("エラー", "Ollama が起動していません。Ollama を起動してから再試行してください。")
            return

        self.pull_status_lbl.configure(text=f"ダウンロード中: {model_name} (取得中...)")

        def worker():
            def cb(status, pct):
                pct_str = f" ({int(pct*100)}%)" if pct > 0 else ""
                self.after(0, lambda: self.pull_status_lbl.configure(text=f"進捗: {status}{pct_str}"))

            success = self.ollama.pull_model(model_name, cb)
            if success:
                self.after(0, lambda: self.finish_pull(model_name))
            else:
                self.after(0, lambda: self.pull_status_lbl.configure(text=f"❌ {model_name} のダウンロードに失敗しました。"))

        threading.Thread(target=worker, daemon=True).start()

    def finish_pull(self, model_name: str):
        self.pull_status_lbl.configure(text=f"✅ {model_name} の導入が完了しました！")
        self.refresh_ollama_models(auto_start=False, select_model=model_name)

    def on_test_gemini(self):
        key = self.gemini_key_entry.get().strip()
        model = self.gemini_model_entry.get().strip()
        if not key:
            messagebox.showwarning("警告", "Gemini APIキーを入力してください。")
            return
        ok = GeminiClient.test_key(key, model)
        if ok:
            messagebox.showinfo("成功", f"Gemini API 接続に成功しました！\nモデル: {model}")
        else:
            messagebox.showerror("エラー", "Gemini API 接続に失敗しました。APIキーまたはモデル名をご確認ください。")

    def on_test_openai(self):
        url = self.openai_url_entry.get().strip()
        key = self.openai_key_entry.get().strip()
        model = self.openai_model_entry.get().strip()
        if not key:
            messagebox.showwarning("警告", "APIキーを入力してください。")
            return
        from translator_engine import OpenAICompatibleClient
        ok = OpenAICompatibleClient.test_key(url, key, model)
        if ok:
            messagebox.showinfo("成功", f"OpenAI互換API 接続に成功しました！\nURL: {url}\nモデル: {model}")
        else:
            messagebox.showerror("エラー", "API接続に失敗しました。Base URL、APIキー、モデル名をご確認ください。")

    def on_window_close(self):
        """ウィンドウ右上の×ボタンで閉じられた場合も、現在の変更内容を保存して反映"""
        self.on_save(silent=True)

    def on_save(self, silent: bool = False):
        # 1. UI言語
        sel_ui_label = self.ui_lang_menu.get()
        ui_code = "ja"
        for code, label in SUPPORTED_UI_LANGUAGES.items():
            if label == sel_ui_label:
                ui_code = code
                break
        self.config["ui_language"] = ui_code
        set_ui_language(ui_code)

        # 2. ターゲット言語
        sel_target_label = self.target_lang_menu.get()
        target_code = sel_target_label.split(":")[0].strip() if ":" in sel_target_label else "JP"
        old_target = getattr(self.parent, "target_lang", "JP")
        self.config["target_language"] = target_code

        # 3. エンジン設定
        self.config["engine_type"] = self.engine_var.get()
        sel = self.model_dropdown.get()
        clean_model = sel.split(" (")[0].strip() if " (" in sel else sel.strip()
        if clean_model and not clean_model.startswith("("):
            self.config["ollama_model"] = clean_model

        prov_choice = self.provider_menu.get()
        self.config["api_provider"] = "gemini" if "Gemini" in prov_choice else "openai"

        self.config["gemini_api_key"] = self.gemini_key_entry.get().strip()
        self.config["gemini_model"] = self.gemini_model_entry.get().strip()

        self.config["openai_base_url"] = self.openai_url_entry.get().strip()
        self.config["openai_api_key"] = self.openai_key_entry.get().strip()
        self.config["openai_model"] = self.openai_model_entry.get().strip()

        ConfigManager.save(self.config)
        self.parent.on_settings_updated(ui_changed=(ui_code != getattr(self.parent, "ui_lang", "ja")), target_changed=(target_code != old_target))
        if not silent:
            messagebox.showinfo(t("status_ready"), t("msg_settings_saved"))
        self.destroy()


class QuickStartDialog(ctk.CTkToplevel):
    """かんたん初期セットアップダイアログ (初回起動時 / いつでも実行可能)"""
    def __init__(self, parent):
        super().__init__(parent)
        self.parent = parent
        self.config = ConfigManager.load()
        self.ollama = OllamaClient()

        self.title(t("quickstart_title"))
        self.geometry("640x600")
        self.resizable(False, False)
        self.transient(parent)
        self.grab_set()
        self.configure(fg_color="#14171f")
        self.protocol("WM_DELETE_WINDOW", self.on_close)

        # メインコンテナ
        main_box = ctk.CTkFrame(self, fg_color="transparent")
        main_box.pack(fill="both", expand=True, padx=24, pady=20)

        # ヘッダー
        ctk.CTkLabel(main_box, text=t("quickstart_title"), font=FONT_TITLE, text_color="#f8fafc").pack(anchor="w")
        ctk.CTkLabel(main_box, text=t("quickstart_sub"), font=FONT_SMALL, text_color="#94a3b8").pack(anchor="w", pady=(2, 14))

        # 1. ローカルAI (Ollama) カード (推奨)
        ollama_models = []
        ollama_ok = False
        try:
            if self.ollama.is_available():
                ollama_ok = True
                ollama_models = self.ollama.get_models()
        except Exception:
            pass

        best_model = None
        for pref in ["gemma4:e4b", "qwen2.5:7b", "llama3.1:8b", "qwen2.5:3b"]:
            for m in ollama_models:
                if pref in m:
                    best_model = m
                    break
            if best_model:
                break
        if not best_model and ollama_models:
            best_model = ollama_models[0]
        self.best_model = best_model or "gemma4:e4b"

        card1 = ctk.CTkFrame(main_box, fg_color="#182232", corner_radius=10, border_width=2, border_color="#2563eb")
        card1.pack(fill="x", pady=(0, 10), ipadx=12, ipady=10)

        card1_top = ctk.CTkFrame(card1, fg_color="transparent")
        card1_top.pack(fill="x")
        ctk.CTkLabel(card1_top, text="🦙 ローカルAI (Ollama)", font=FONT_LABEL_BOLD, text_color="#f8fafc").pack(side="left")
        ctk.CTkLabel(card1_top, text="⭐ おすすめ・完全無料", font=FONT_BADGE, text_color="#38bdf8", fg_color="#1e3a8a", corner_radius=4, padx=6, pady=2).pack(side="left", padx=8)

        if ollama_ok and best_model:
            status_text = f"✅ PC内に利用可能モデルを検出: {best_model}"
            status_color = "#34d399"
            btn1_text = f"👉 ローカルAIで翻訳を始める ({best_model})"
            btn1_cmd = lambda: self.select_ollama(best_model)
        elif ollama_ok:
            status_text = "⚠️ Ollama は起動していますが、翻訳モデルが未導入です"
            status_color = "#fbbf24"
            btn1_text = "📥 推奨モデル (gemma4:e4b / 6.1GB) を取得して始める"
            btn1_cmd = self.pull_and_start_ollama
        else:
            status_text = "⚠️ Ollama が未起動です (インストールするとPC完結で完全無料で利用可能)"
            status_color = "#94a3b8"
            btn1_text = "🌐 Ollama 公式サイトを開く"
            btn1_cmd = lambda: webbrowser.open("https://ollama.com/")

        ctk.CTkLabel(card1, text=status_text, font=FONT_SMALL, text_color=status_color).pack(anchor="w", pady=(4, 2))
        ctk.CTkLabel(card1, text="MOD独自の台詞・設定項目・長文も、PC内のAIが自然に自動翻訳します。", font=FONT_SMALL, text_color="#94a3b8").pack(anchor="w", pady=(0, 8))

        btn1 = ctk.CTkButton(
            card1, text=btn1_text, height=36, font=FONT_BUTTON,
            fg_color="#2563eb", hover_color="#1d4ed8", corner_radius=8, command=btn1_cmd
        )
        btn1.pack(fill="x")

        # 2. Google Gemini API カード
        card2 = ctk.CTkFrame(main_box, fg_color="#1b1f2b", corner_radius=10, border_width=1, border_color="#282e3d")
        card2.pack(fill="x", pady=(0, 10), ipadx=12, ipady=10)

        card2_top = ctk.CTkFrame(card2, fg_color="transparent")
        card2_top.pack(fill="x")
        ctk.CTkLabel(card2_top, text="⚡ Google Gemini API", font=FONT_LABEL_BOLD, text_color="#f8fafc").pack(side="left")
        ctk.CTkLabel(card2_top, text="超高速クラウド (無料枠あり)", font=FONT_BADGE, text_color="#a855f7", fg_color="#3b1d54", corner_radius=4, padx=6, pady=2).pack(side="left", padx=8)

        ctk.CTkLabel(card2, text="Googleの高性能モデル (Gemini 1.5 Flash) を利用。GPUがないPCでも高速。", font=FONT_SMALL, text_color="#94a3b8").pack(anchor="w", pady=(4, 4))
        
        gemini_input_row = ctk.CTkFrame(card2, fg_color="transparent")
        gemini_input_row.pack(fill="x", pady=(2, 6))
        self.gemini_key_entry = ctk.CTkEntry(
            gemini_input_row, placeholder_text="Gemini APIキー (AI Studioで無料取得)", height=32, font=FONT_SMALL,
            fg_color="#22252d", border_color="#334155", corner_radius=6
        )
        cur_key = self.config.get("gemini_api_key", "")
        if cur_key:
            self.gemini_key_entry.insert(0, cur_key)
        self.gemini_key_entry.pack(side="left", fill="x", expand=True, padx=(0, 8))

        btn2 = ctk.CTkButton(
            gemini_input_row, text="Gemini で始める", width=130, height=32, font=FONT_BUTTON,
            fg_color="#8b5cf6", hover_color="#7c3aed", corner_radius=6, command=self.select_gemini
        )
        btn2.pack(side="right")

        # 3. 公式スマート辞書のみ カード
        card3 = ctk.CTkFrame(main_box, fg_color="#1b1f2b", corner_radius=10, border_width=1, border_color="#282e3d")
        card3.pack(fill="x", pady=(0, 8), ipadx=12, ipady=8)

        card3_top = ctk.CTkFrame(card3, fg_color="transparent")
        card3_top.pack(fill="x")
        ctk.CTkLabel(card3_top, text="📖 内蔵スマート辞書のみ", font=FONT_LABEL_BOLD, text_color="#cbd5e1").pack(side="left")
        ctk.CTkLabel(card3_top, text="AI不使用", font=FONT_BADGE, text_color="#94a3b8", fg_color="#334155", corner_radius=4, padx=6, pady=2).pack(side="left", padx=8)

        ctk.CTkLabel(card3, text="ゲーム公式のアイテム名・UIのみ一致（※MOD独自の会話や長文は未翻訳のまま維持されます）。", font=FONT_SMALL, text_color="#64748b").pack(anchor="w", pady=(2, 6))

        btn3 = ctk.CTkButton(
            card3, text="辞書のみで始める", height=30, font=FONT_NORMAL,
            fg_color="#334155", hover_color="#475569", corner_radius=6, command=self.select_dict
        )
        btn3.pack(fill="x")

        # 注意書き (ローカルLLMの性質と手動修正について)
        notice_box = ctk.CTkFrame(main_box, fg_color="#181c24", corner_radius=8, border_width=1, border_color="#2b3242")
        notice_box.pack(fill="x", pady=(8, 0), padx=2, ipady=4)
        ctk.CTkLabel(
            notice_box,
            text="⚠️【注意点】ローカルLLMの性質上、翻訳精度は使用するモデルの性能に依存します。\n誤った翻訳をされる場合もありますので、気になる箇所は一覧のセルをダブルクリックして手動修正してください。",
            font=FONT_SMALL, text_color="#94a3b8", justify="left"
        ).pack(anchor="w", padx=10, pady=4)

    def select_ollama(self, model: str):
        self.config["engine_type"] = "ollama"
        self.config["ollama_model"] = model
        self.finish_selection(f"🦙 ローカルAI ({model}) に設定しました！「一括AI翻訳を実行」ですぐに翻訳できます。")

    def pull_and_start_ollama(self):
        self.config["engine_type"] = "ollama"
        self.config["ollama_model"] = "gemma4:e4b"
        self.finish_selection("📥 推奨モデル (gemma4:e4b) で設定しました。「⚙️ 翻訳設定」からダウンロード状況を確認できます。")

    def select_gemini(self):
        key = self.gemini_key_entry.get().strip()
        self.config["engine_type"] = "gemini"
        self.config["api_provider"] = "gemini"
        if key:
            self.config["gemini_api_key"] = key
        self.finish_selection("⚡ Gemini API に設定しました！「一括AI翻訳を実行」ですぐに翻訳できます。")

    def select_dict(self):
        self.config["engine_type"] = "smart_dict"
        self.finish_selection("📖 内蔵スマート辞書に設定しました。公式一致テキストのみ翻訳されます。")

    def finish_selection(self, status_msg: str):
        self.config["setup_completed"] = True
        ConfigManager.save(self.config)
        self.parent.on_settings_updated()
        self.parent.status_var.set(status_msg)
        self.destroy()

    def on_close(self):
        self.config["setup_completed"] = True
        ConfigManager.save(self.config)
        self.destroy()


class ModernZTranzlatorApp(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.config = ConfigManager.load()
        self.ui_lang = self.config.get("ui_language", "ja")
        set_ui_language(self.ui_lang)
        self.target_lang = self.config.get("target_language", "JP")

        self.title(t("app_title"))
        self.geometry("1380x840")
        self.minsize(1080, 680)
        self.configure(fg_color="#0f1115")

        self.base_dir = Path(__file__).parent
        self.pz_dir = find_pz_directory()
        self.workshop_dir = DEFAULT_WORKSHOP_PATH
        self.user_mods_dir = DEFAULT_USER_MODS_PATH

        self.vanilla_dict = {}
        self.all_mods = []
        self.current_mod = None
        self.current_items = []
        self.cache_file = self.base_dir / "mod_progress_cache.json"
        self.mod_progress_cache = self.load_progress_cache()
        self.draft_cache_file = self.base_dir / "mod_draft_cache.json"
        self.mod_draft_cache = self.load_draft_cache()
        self.stop_event = threading.Event()
        self.sort_column = None
        self.sort_reverse = False

        self.anim_is_running = False
        self.anim_current_progress = 0.0
        self.anim_target_progress = 0.0
        self.anim_spinner_idx = 0
        self.anim_pulse_tick = 0
        self.anim_active_text = ""

        self.setup_styles()
        self.setup_ui()
        self.load_dictionary_cache()
        self.scan_installed_mods()
        self.update_engine_status()

        self._closing = False
        self.protocol("WM_DELETE_WINDOW", self.on_main_window_close)
        self.start_telemetry_monitor()

        if not self.config.get("setup_completed", False):
            self.after(300, self.open_quickstart_dialog)

    def get_patch_suffix(self) -> str:
        meta = SUPPORTED_TARGET_LANGUAGES.get(self.target_lang, {"suffix": f"_{self.target_lang}"})
        return meta.get("suffix", f"_{self.target_lang}")

    def load_progress_cache(self) -> dict:
        """各MODの翻訳進捗キャッシュをロード"""
        if self.cache_file.is_file():
            try:
                with open(self.cache_file, "r", encoding="utf-8-sig") as f:
                    return json.load(f)
            except Exception:
                pass
        return {}

    def save_progress_cache(self):
        """各MODの翻訳進捗キャッシュを保存"""
        try:
            with open(self.cache_file, "w", encoding="utf-8") as f:
                json.dump(self.mod_progress_cache, f, ensure_ascii=False, indent=2)
        except Exception:
            pass

    def load_draft_cache(self) -> dict:
        """各MODのドラフト（作業中）訳文キャッシュをロード"""
        if hasattr(self, "draft_cache_file") and self.draft_cache_file.is_file():
            try:
                with open(self.draft_cache_file, "r", encoding="utf-8-sig") as f:
                    return json.load(f)
            except Exception:
                pass
        return {}

    def save_draft_cache(self):
        """各MODのドラフト訳文キャッシュを保存"""
        try:
            with open(self.draft_cache_file, "w", encoding="utf-8") as f:
                json.dump(self.mod_draft_cache, f, ensure_ascii=False, indent=2)
        except Exception:
            pass

    def get_draft_for_mod(self, mod_id: str) -> dict:
        """指定MODのドラフト訳文マップ {en: {"jp": ..., "status": ...}} を取得"""
        key = f"{mod_id}_{self.target_lang}"
        return self.mod_draft_cache.get(key, {})

    def save_current_draft(self):
        """現在選択中のMODの翻訳内容をドラフトキャッシュに保存"""
        if not self.current_mod or not self.current_items:
            return
        mod_id = self.current_mod["id"]
        key = f"{mod_id}_{self.target_lang}"
        draft_map = {}
        for it in self.current_items:
            en = it.get("en", "")
            jp = it.get("jp", "")
            status = it.get("status", "")
            if en and jp:
                draft_map[en] = {"jp": jp, "status": status}
        if draft_map:
            self.mod_draft_cache[key] = draft_map
            self.save_draft_cache()

    def get_mod_progress_info(self, mod_id: str) -> tuple:
        """MODの進捗テキストとカラータグを返す (prog_text, tag)"""
        suffix = self.get_patch_suffix()
        user_patch = self.user_mods_dir / f"{mod_id}{suffix}"
        output_patch = self.base_dir / "output" / f"{mod_id}{suffix}"
        is_patched = user_patch.is_dir() or output_patch.is_dir()

        cache = self.mod_progress_cache.get(f"{mod_id}_{self.target_lang}") or self.mod_progress_cache.get(mod_id)
        if cache:
            pct = cache.get("percent", 0)
            if pct >= 100:
                return (f"{pct}% (適用済)" if is_patched else f"{pct}% (完了)"), "mod_done"
            elif pct > 0:
                return (f"{pct}% (適用済)" if is_patched else f"{pct}%"), "mod_partial"
            else:
                return ("0% (適用済)" if is_patched else "未着手"), "mod_none"
        else:
            if is_patched:
                return "適用済", "mod_done"
            return "未着手", "mod_none"

    def update_mod_list_progress(self, mod_id: str, percent: int):
        """MODの進捗率を更新・保存し、左側Treeviewの表示を同期"""
        suffix = self.get_patch_suffix()
        user_patch = self.user_mods_dir / f"{mod_id}{suffix}"
        output_patch = self.base_dir / "output" / f"{mod_id}{suffix}"
        is_patched = user_patch.is_dir() or output_patch.is_dir()

        self.mod_progress_cache[f"{mod_id}_{self.target_lang}"] = {
            "percent": percent,
            "is_patched": is_patched
        }
        self.save_progress_cache()

        prog_text, tag = self.get_mod_progress_info(mod_id)
        for item_iid in self.mod_tree.get_children():
            vals = self.mod_tree.item(item_iid, "values")
            if vals and len(vals) >= 3 and vals[2] == mod_id:
                self.mod_tree.item(item_iid, values=(vals[0], prog_text, vals[2]), tags=(tag,))
                break

    def setup_styles(self):
        """Treeview 等の Tkinter 標準コンポーネントをメイリオ＆ダークモダンにカスタマイズ"""
        style = ttk.Style(self)
        style.theme_use("clam")

        style.configure(
            "Modern.Treeview",
            background="#16181f",
            foreground="#f1f5f9",
            fieldbackground="#16181f",
            borderwidth=0,
            rowheight=30,
            font=FONT_TABLE
        )
        style.configure(
            "Modern.Treeview.Heading",
            background="#1e222b",
            foreground="#94a3b8",
            borderwidth=0,
            font=FONT_TABLE_HEAD,
            relief="flat",
            padding=(8, 8)
        )
        style.map(
            "Modern.Treeview.Heading",
            background=[("active", "#282e3a")]
        )
        style.map(
            "Modern.Treeview",
            background=[("selected", "#2563eb")],
            foreground=[("selected", "#ffffff")]
        )

    def setup_ui(self):
        # 1. 最上部ヘッダーバー
        header = ctk.CTkFrame(self, height=56, fg_color="#14171f", corner_radius=0)
        header.pack(fill="x", side="top")

        # ブランドロゴ
        brand_frame = ctk.CTkFrame(header, fg_color="transparent")
        brand_frame.pack(side="left", padx=18)
        logo_lbl = ctk.CTkLabel(brand_frame, text="zTranzlator", font=FONT_LOGO, text_color="#f8fafc")
        logo_lbl.pack(side="left")
        badge_lbl = ctk.CTkLabel(
            brand_frame, text="B42 READY", font=FONT_BADGE,
            text_color="#38bdf8", fg_color="#0369a1", corner_radius=6, padx=6, pady=2
        )
        badge_lbl.pack(side="left", padx=8)

        # ステータスインジケーター群
        status_frame = ctk.CTkFrame(header, fg_color="transparent")
        status_frame.pack(side="left", padx=16)

        pz_status_text = f"PZ: {self.pz_dir.name}" if self.pz_dir else "PZ: 未検出"
        pz_color = "#10b981" if self.pz_dir else "#f43f5e"
        ctk.CTkLabel(status_frame, text="●", text_color=pz_color, font=FONT_SMALL).pack(side="left", padx=(0, 4))
        ctk.CTkLabel(status_frame, text=pz_status_text, font=FONT_NORMAL, text_color="#94a3b8").pack(side="left", padx=(0, 16))

        # エンジンステータス表示
        self.engine_dot = ctk.CTkLabel(status_frame, text="●", text_color="#10b981", font=FONT_SMALL)
        self.engine_dot.pack(side="left", padx=(0, 4))
        self.engine_lbl = ctk.CTkLabel(status_frame, text="エンジン: 内蔵スマート辞書", font=FONT_NORMAL, text_color="#94a3b8")
        self.engine_lbl.pack(side="left")

        # ヘッダー右側のアクションボタン
        header_actions = ctk.CTkFrame(header, fg_color="transparent")
        header_actions.pack(side="right", padx=16)

        self.quickstart_btn = ctk.CTkButton(
            header_actions, text=t("btn_quickstart"), width=110, height=30, font=FONT_NORMAL,
            fg_color="#8b5cf6", hover_color="#7c3aed", corner_radius=6, command=self.open_quickstart_dialog
        )
        self.quickstart_btn.pack(side="left", padx=4)

        self.settings_btn = ctk.CTkButton(
            header_actions, text=t("btn_settings"), width=105, height=30, font=FONT_NORMAL,
            fg_color="#3b82f6", hover_color="#2563eb", corner_radius=6, command=self.on_open_settings
        )
        self.settings_btn.pack(side="left", padx=4)

        self.manual_btn = ctk.CTkButton(
            header_actions, text=t("btn_manual"), width=110, height=30, font=FONT_NORMAL,
            fg_color="#0284c7", hover_color="#0369a1", corner_radius=6, command=self.on_open_manual
        )
        self.manual_btn.pack(side="left", padx=4)

        self.import_btn = ctk.CTkButton(
            header_actions, text=t("btn_import_zip"), width=100, height=30, font=FONT_NORMAL,
            fg_color="#1e293b", hover_color="#334155", corner_radius=6, command=self.on_import_zip
        )
        self.import_btn.pack(side="left", padx=4)

        self.rescan_btn = ctk.CTkButton(
            header_actions, text=t("btn_rescan"), width=80, height=30, font=FONT_NORMAL,
            fg_color="#1e293b", hover_color="#334155", corner_radius=6, command=self.scan_installed_mods
        )
        self.rescan_btn.pack(side="left", padx=4)

        # 2. メインコンテンツ領域 (左右2ペイン)
        content_frame = ctk.CTkFrame(self, fg_color="transparent")
        content_frame.pack(fill="both", expand=True, padx=16, pady=12)

        # --- 左サイドバー: MOD一覧 ---
        left_card = ctk.CTkFrame(content_frame, width=370, fg_color="#14171f", corner_radius=12)
        left_card.pack(side="left", fill="y", padx=(0, 10))
        left_card.pack_propagate(False)

        # 検索バー
        search_box = ctk.CTkFrame(left_card, fg_color="transparent")
        search_box.pack(fill="x", padx=12, pady=(12, 6))
        self.search_entry = ctk.CTkEntry(
            search_box, placeholder_text=t("search_placeholder"), height=34, font=FONT_NORMAL,
            fg_color="#1e222b", border_color="#282e3a", corner_radius=8
        )
        self.search_entry.pack(fill="x")
        self.search_entry.bind("<KeyRelease>", self.on_search_mod)

        # 複数MODクイック選択バー
        mod_sel_box = ctk.CTkFrame(left_card, fg_color="transparent")
        mod_sel_box.pack(fill="x", padx=12, pady=(0, 8))

        self.btn_select_all = ctk.CTkButton(
            mod_sel_box, text="全選択", width=60, height=24, font=FONT_SMALL,
            fg_color="#1e222b", hover_color="#282e3a", corner_radius=6,
            command=self.select_all_mods
        )
        self.btn_select_all.pack(side="left", padx=(0, 4))

        self.btn_select_untrans = ctk.CTkButton(
            mod_sel_box, text="未完了を選択", width=84, height=24, font=FONT_SMALL,
            fg_color="#1e222b", hover_color="#282e3a", corner_radius=6,
            command=self.select_untranslated_mods
        )
        self.btn_select_untrans.pack(side="left", padx=(0, 4))

        self.btn_deselect_all = ctk.CTkButton(
            mod_sel_box, text="解除", width=45, height=24, font=FONT_SMALL,
            fg_color="#1e222b", hover_color="#282e3a", corner_radius=6,
            command=self.deselect_all_mods
        )
        self.btn_deselect_all.pack(side="left")

        # MODツリービュー
        mod_tree_frame = tk.Frame(left_card, bg="#14171f")
        mod_tree_frame.pack(fill="both", expand=True, padx=12, pady=(0, 12))

        columns = ("name", "progress", "id")
        self.mod_tree = ttk.Treeview(
            mod_tree_frame, columns=columns, show="headings",
            selectmode="extended", style="Modern.Treeview"
        )
        self.mod_tree.heading("name", text=t("col_mod_name"))
        self.mod_tree.heading("progress", text=t("col_progress"))
        self.mod_tree.heading("id", text=t("col_id"))
        self.mod_tree.column("name", width=160)
        self.mod_tree.column("progress", width=95, anchor="center")
        self.mod_tree.column("id", width=95)

        # MODツリービュー用カラータグ
        self.mod_tree.tag_configure("mod_done", foreground="#34d399")
        self.mod_tree.tag_configure("mod_partial", foreground="#38bdf8")
        self.mod_tree.tag_configure("mod_none", foreground="#94a3b8")

        mod_scroll = ttk.Scrollbar(mod_tree_frame, orient="vertical", command=self.mod_tree.yview)
        self.mod_tree.configure(yscrollcommand=mod_scroll.set)
        mod_scroll.pack(side="right", fill="y")
        self.mod_tree.pack(fill="both", expand=True)
        self.mod_tree.bind("<<TreeviewSelect>>", self.on_mod_selected)

        # --- 右メインペイン: 翻訳グリッドエディタ ---
        right_card = ctk.CTkFrame(content_frame, fg_color="#14171f", corner_radius=12)
        right_card.pack(side="right", fill="both", expand=True)

        # サマリー統計バー
        self.stats_bar = ctk.CTkFrame(right_card, height=44, fg_color="transparent")
        self.stats_bar.pack(fill="x", padx=16, pady=(12, 4))

        self.stat_target_lbl = ctk.CTkLabel(self.stats_bar, text="MODを選択してください", font=FONT_TITLE, text_color="#f8fafc")
        self.stat_target_lbl.pack(side="left")

        self.stat_badges = ctk.CTkFrame(self.stats_bar, fg_color="transparent")
        self.stat_badges.pack(side="right")

        self.badge_total = self.create_badge(self.stat_badges, "総項目: 0", "#334155", "#94a3b8")
        self.badge_inherited = self.create_badge(self.stat_badges, "既存継承: 0", "#0e7490", "#22d3ee")
        self.badge_matched = self.create_badge(self.stat_badges, "公式一致: 0", "#065f46", "#34d399")
        self.badge_unmatched = self.create_badge(self.stat_badges, "未翻訳: 0", "#881337", "#fb7185")
        self.badge_overflow = self.create_badge(self.stat_badges, "⚠️幅注意: 0", "#78350f", "#fbbf24")

        # MOD内 検索・フィルターツールバー
        self.grid_filter_bar = ctk.CTkFrame(right_card, height=36, fg_color="transparent")
        self.grid_filter_bar.pack(fill="x", padx=16, pady=(2, 6))

        self.grid_search_entry = ctk.CTkEntry(
            self.grid_filter_bar,
            placeholder_text=t("grid_search_placeholder"),
            width=280, height=32, font=FONT_NORMAL,
            fg_color="#1e222b", border_color="#334155", corner_radius=6
        )
        self.grid_search_entry.pack(side="left", padx=(0, 8))
        self.grid_search_entry.bind("<KeyRelease>", lambda e: self.render_grid_items())

        self.grid_filter_menu = ctk.CTkOptionMenu(
            self.grid_filter_bar,
            values=[
                "すべて表示",
                "未翻訳のみ",
                "AI翻訳・手動のみ",
                "公式一致・継承のみ",
                "幅注意のみ",
                "公式JSONのみ",
                "Lua/UIのみ",
                "printMediaのみ",
            ],
            width=175, height=32, font=FONT_NORMAL, dropdown_font=FONT_NORMAL,
            fg_color="#1e222b", button_color="#334155",
            dropdown_fg_color="#1e222b", dropdown_hover_color="#334155", dropdown_text_color="#f8fafc",
            command=lambda _: self.render_grid_items()
        )
        self.grid_filter_menu.pack(side="left", padx=(0, 8))

        self.grid_clear_btn = ctk.CTkButton(
            self.grid_filter_bar, text=t("btn_clear"), width=70, height=32, font=FONT_SMALL,
            fg_color="#22252d", hover_color="#334155", text_color="#94a3b8", corner_radius=6,
            command=self.on_clear_grid_filter
        )
        self.grid_clear_btn.pack(side="left")

        self.grid_count_lbl = ctk.CTkLabel(
            self.grid_filter_bar, text="", font=FONT_SMALL, text_color="#64748b"
        )
        self.grid_count_lbl.pack(side="right")

        # 翻訳テーブル
        grid_frame = tk.Frame(right_card, bg="#14171f")
        grid_frame.pack(fill="both", expand=True, padx=16, pady=(2, 8))

        columns = ("en", "jp", "arch", "status", "file")
        self.grid_tree = ttk.Treeview(
            grid_frame, columns=columns, show="headings",
            selectmode="browse", style="Modern.Treeview"
        )
        self.update_grid_headings()

        self.grid_tree.column("en", width=290)
        self.grid_tree.column("jp", width=290)
        self.grid_tree.column("arch", width=85, anchor="center")
        self.grid_tree.column("status", width=110, anchor="center")
        self.grid_tree.column("file", width=120)

        grid_scroll = ttk.Scrollbar(grid_frame, orient="vertical", command=self.grid_tree.yview)
        self.grid_tree.configure(yscrollcommand=grid_scroll.set)
        grid_scroll.pack(side="right", fill="y")
        self.grid_tree.pack(fill="both", expand=True)
        self.grid_tree.bind("<Double-1>", self.on_grid_double_click)

        # カラータグ
        self.grid_tree.tag_configure("inherited", foreground="#22d3ee")
        self.grid_tree.tag_configure("matched", foreground="#34d399")
        self.grid_tree.tag_configure("ai", foreground="#a855f7")
        self.grid_tree.tag_configure("dict_trans", foreground="#38bdf8")
        self.grid_tree.tag_configure("custom", foreground="#fcd34d")
        self.grid_tree.tag_configure("untranslated", foreground="#fb7185")
        self.grid_tree.tag_configure("deprecated", foreground="#64748b")
        self.grid_tree.tag_configure("overflow", foreground="#fbbf24")

        # プログレスバー & 進行状況アニメーション表示 (太さ14px・角丸・ボーダー)
        self.progress_container = ctk.CTkFrame(right_card, fg_color="transparent")
        self.progress_container.pack(fill="x", padx=16, pady=(4, 10))

        # 進捗情報ヘッダー (左: スピナー&処理中テキスト, 右: パーセント&件数)
        self.progress_info_frame = ctk.CTkFrame(self.progress_container, fg_color="transparent")
        self.progress_info_frame.pack(fill="x", pady=(0, 4))

        self.progress_status_lbl = ctk.CTkLabel(
            self.progress_info_frame, text="", font=FONT_STATUS_NORMAL, text_color="#38bdf8", anchor="w"
        )
        self.progress_status_lbl.pack(side="left")

        self.progress_pct_lbl = ctk.CTkLabel(
            self.progress_info_frame, text="", font=FONT_STATUS, text_color="#cbd5e1", anchor="e"
        )
        self.progress_pct_lbl.pack(side="right")

        # 太めのプログレスバー本体
        self.progress_bar = ctk.CTkProgressBar(
            self.progress_container, height=14, corner_radius=7,
            fg_color="#12151e", progress_color="#3b82f6",
            border_width=1, border_color="#222634"
        )
        self.progress_bar.set(0)
        self.progress_bar.pack(fill="x")

        # スマート提案バナー (未翻訳項目があり、エンジンがスマート辞書の時のみ表示)
        self.suggestion_banner = ctk.CTkFrame(
            right_card, fg_color="#182232", corner_radius=8, border_width=1, border_color="#2563eb"
        )
        self.banner_lbl = ctk.CTkLabel(
            self.suggestion_banner, text="", font=FONT_SMALL, text_color="#38bdf8"
        )
        self.banner_lbl.pack(side="left", padx=12, pady=6)
        self.banner_btn = ctk.CTkButton(
            self.suggestion_banner, text="🦙 ローカルAIに切り替える", width=180, height=28, font=FONT_BUTTON,
            fg_color="#2563eb", hover_color="#1d4ed8", corner_radius=6, command=self.on_switch_to_ollama_banner
        )
        self.banner_btn.pack(side="right", padx=8, pady=6)

        # アクションバー (中央に特別感のあるローカルMOD適用ボタンを配置)
        self.action_bar = ctk.CTkFrame(right_card, height=54, fg_color="transparent")
        self.action_bar.pack(fill="x", padx=16, pady=(0, 12))

        # 3カラムグリッド設定 (左右余白を均等配分して中央ボタンをセンタリングし、縮小時の重なりを完全防止)
        self.action_bar.grid_columnconfigure(0, weight=1)
        self.action_bar.grid_columnconfigure(1, weight=0)
        self.action_bar.grid_columnconfigure(2, weight=1)
        self.action_bar.grid_rowconfigure(0, weight=1)

        # 左側アクション: AI翻訳 & 中断
        action_left = ctk.CTkFrame(self.action_bar, fg_color="transparent")
        action_left.grid(row=0, column=0, sticky="w")

        self.btn_translate = ctk.CTkButton(
            action_left, text="一括AI翻訳を実行", width=150, height=38, font=FONT_BUTTON,
            fg_color="#3b82f6", hover_color="#2563eb", corner_radius=8, command=self.on_translate_all
        )
        self.btn_translate.pack(side="left", padx=(0, 8))

        self.btn_stop_translate = ctk.CTkButton(
            action_left, text="⏹️ 中断 (停止)", width=105, height=38, font=FONT_BUTTON,
            fg_color="#334155", hover_color="#dc2626", corner_radius=8,
            command=self.on_stop_translation, state="disabled"
        )
        self.btn_stop_translate.pack(side="left")

        # 中央メインアクション (Hero CTA): ゲームへ即時反映 (ローカルMOD適用)
        # grid配置により、ウィンドウ縮小時にも他ボタンと物理的に重ならずスマートに配置
        self.btn_apply = ctk.CTkButton(
            self.action_bar,
            text=t("btn_apply_local"),
            width=260,
            height=44,
            font=FONT_HERO_BUTTON,
            fg_color="#059669",
            hover_color="#10b981",
            border_width=2,
            border_color="#34d399",
            corner_radius=10,
            command=self.on_apply_local
        )
        self.btn_apply.grid(row=0, column=1, padx=8)

        # 右側アクション: 配布用エクスポート
        action_right = ctk.CTkFrame(self.action_bar, fg_color="transparent")
        action_right.grid(row=0, column=2, sticky="e")

        self.btn_export = ctk.CTkButton(
            action_right, text="配布用ZIPエクスポート", width=160, height=38, font=FONT_BUTTON,
            fg_color="#1e293b", hover_color="#334155", border_width=1, border_color="#475569",
            corner_radius=8, command=self.on_export_zip
        )
        self.btn_export.pack(side="right")

        # 3. 最下部ステータスバー (視認性向上のため高さとフォントを拡大)
        self.status_var = tk.StringVar(value="準備完了")
        status_bar = ctk.CTkFrame(self, height=36, fg_color="#0a0c0e", corner_radius=0)
        status_bar.pack(fill="x", side="bottom")

        self.status_lbl = ctk.CTkLabel(status_bar, textvariable=self.status_var, font=FONT_STATUS_NORMAL, text_color="#cbd5e1")
        self.status_lbl.pack(side="left", padx=16, pady=4)

        # ハードウェアリソースモニター (CPU, RAM, GPU, VRAM)
        self.hw_monitor_frame = ctk.CTkFrame(status_bar, fg_color="transparent")
        self.hw_monitor_frame.pack(side="right", padx=16, pady=4)

        self.hw_cpu_lbl = ctk.CTkLabel(self.hw_monitor_frame, text="💻 CPU: --%", font=FONT_STATUS, text_color="#e2e8f0")
        self.hw_cpu_lbl.pack(side="left", padx=(0, 14))

        self.hw_ram_lbl = ctk.CTkLabel(self.hw_monitor_frame, text="🧠 RAM: --%", font=FONT_STATUS, text_color="#e2e8f0")
        self.hw_ram_lbl.pack(side="left", padx=(0, 14))

        self.hw_gpu_lbl = ctk.CTkLabel(self.hw_monitor_frame, text="🎮 GPU: --%", font=FONT_STATUS, text_color="#e2e8f0")
        self.hw_gpu_lbl.pack(side="left", padx=(0, 14))

        self.hw_vram_lbl = ctk.CTkLabel(self.hw_monitor_frame, text="⚡ VRAM: --%", font=FONT_STATUS, text_color="#e2e8f0")
        self.hw_vram_lbl.pack(side="left")

    def on_settings_updated(self, ui_changed=False, target_changed=False):
        self.config = ConfigManager.load()
        self.ui_lang = self.config.get("ui_language", "ja")
        set_ui_language(self.ui_lang)
        self.target_lang = self.config.get("target_language", "JP")

        if target_changed:
            self.load_dictionary_cache()
            if self.current_mod:
                self.on_mod_selected(None)

        self.update_engine_status()
        self.refresh_ui_text()

    def refresh_ui_text(self):
        self.title(t("app_title"))
        self.quickstart_btn.configure(text=t("btn_quickstart"))
        self.settings_btn.configure(text=t("btn_settings"))
        self.manual_btn.configure(text=t("btn_manual"))
        self.import_btn.configure(text=t("btn_import_zip"))
        self.rescan_btn.configure(text=t("btn_rescan"))
        self.search_entry.configure(placeholder_text=t("search_placeholder"))

        self.mod_tree.heading("name", text=t("col_mod_name"))
        self.mod_tree.heading("progress", text=t("col_progress"))
        self.mod_tree.heading("id", text=t("col_id"))

        self.update_grid_headings()
        if hasattr(self, "grid_search_entry"):
            self.grid_search_entry.configure(placeholder_text=t("grid_search_placeholder"))
        if hasattr(self, "grid_clear_btn"):
            self.grid_clear_btn.configure(text=t("btn_clear"))

        self.btn_stop_translate.configure(text=t("btn_stop"))
        self.btn_apply.configure(text=t("btn_apply_local"))
        self.btn_export.configure(text=t("btn_export_zip"))

    def update_engine_status(self):
        """現在の翻訳エンジンのステータス表示およびアクションボタンの同期"""
        self.config = ConfigManager.load()
        engine = self.config.get("engine_type", "smart_dict")
        target = self.target_lang

        if engine in ("api", "gemini"):
            prov = self.config.get("api_provider", "gemini")
            if prov == "gemini":
                self.engine_dot.configure(text_color="#a855f7")  # Purple
                model = self.config.get("gemini_model", "gemini-1.5-flash")
                self.engine_lbl.configure(text=f"Gemini ({model}) ➡ {target}")
                self.btn_translate.configure(text=t("btn_translate_gemini"), fg_color="#8b5cf6", hover_color="#7c3aed")
            else:
                self.engine_dot.configure(text_color="#34d399")  # Emerald
                model = self.config.get("openai_model", "gpt-4o-mini")
                self.engine_lbl.configure(text=f"OpenAI ({model}) ➡ {target}")
                self.btn_translate.configure(text=t("btn_translate_openai"), fg_color="#10b981", hover_color="#059669")
        elif engine == "ollama":
            self.engine_dot.configure(text_color="#38bdf8")  # Blue
            model = self.config.get("ollama_model", "qwen2.5:3b")
            self.engine_lbl.configure(text=f"Ollama ({model}) ➡ {target}")
            self.btn_translate.configure(text=t("btn_translate_ollama"), fg_color="#3b82f6", hover_color="#2563eb")
            def auto_start_worker():
                ollama = OllamaClient()
                if not ollama.is_available():
                    ollama.ensure_started(timeout_sec=5.0)
            threading.Thread(target=auto_start_worker, daemon=True).start()
        else:
            self.engine_dot.configure(text_color="#10b981")  # Green
            self.engine_lbl.configure(text=f"Smart Dict ➡ {target}")
            self.btn_translate.configure(text=t("btn_translate_dict"), fg_color="#0284c7", hover_color="#0369a1")

    def create_badge(self, parent, text, bg_color, text_color):
        badge = ctk.CTkLabel(
            parent, text=text, font=FONT_BADGE,
            fg_color=bg_color, text_color=text_color,
            corner_radius=6, padx=8, pady=2
        )
        badge.pack(side="left", padx=3)
        return badge

    def load_dictionary_cache(self):
        target_lang = self.target_lang
        dict_file = self.base_dir / f"vanilla_dict_{target_lang}.json"
        if not dict_file.is_file() and target_lang == "JP":
            dict_file = self.base_dir / "vanilla_dict.json"

        # 存在しない場合はゲーム本体から自動ビルド
        if not dict_file.is_file() and self.pz_dir:
            self.status_var.set(f"公式{target_lang}辞書を抽出生成中...")
            self.update_idletasks()
            built_path = build_master_dictionary(self.pz_dir, self.base_dir, target_lang=target_lang)
            if built_path and built_path.is_file():
                dict_file = built_path

        if dict_file.is_file():
            self.vanilla_dict = load_vanilla_dict(dict_file)
            self.status_var.set(f"公式{target_lang}対訳辞書をロード: {len(self.vanilla_dict):,} 項目")
        else:
            self.status_var.set(f"公式{target_lang}辞書が見つかりません。")

    def scan_installed_mods(self):
        self.mod_tree.delete(*self.mod_tree.get_children())
        self.all_mods = []
        found_ids = set()

        scan_dirs = []
        if self.workshop_dir.is_dir():
            scan_dirs.extend(list(self.workshop_dir.glob("*/mods/*")))
            scan_dirs.extend(list(self.workshop_dir.glob("*")))
        if self.user_mods_dir.is_dir():
            scan_dirs.extend(list(self.user_mods_dir.glob("*")))

        for mod_path in scan_dirs:
            if not mod_path.is_dir():
                continue
            info_files = list(mod_path.glob("**/mod.info"))
            if not info_files:
                continue

            info_file = info_files[0]
            name, mod_id = mod_path.name, mod_path.name
            try:
                with open(info_file, "r", encoding="utf-8", errors="ignore") as f:
                    for line in f:
                        if line.startswith("name="):
                            name = line.split("=", 1)[1].strip()
                        elif line.startswith("id="):
                            mod_id = line.split("=", 1)[1].strip()
            except Exception:
                pass

            if mod_id in found_ids or mod_id.endswith("_JA"):
                continue
            found_ids.add(mod_id)

            # Build 42 MOD構造対応 (mod.info が common/ または 42/ にある場合は MODルートに解決)
            mod_root = info_file.parent
            if mod_root.name.lower() in ("common", "42"):
                mod_root = mod_root.parent

            self.all_mods.append({
                "name": name,
                "id": mod_id,
                "path": mod_root,
            })

        self.all_mods.sort(key=lambda x: x["name"].lower())
        self.render_mod_list(self.all_mods)
        self.status_var.set(f"スキャン完了: {len(self.all_mods)} 件のMODを検出")

    def render_mod_list(self, mods):
        self.mod_tree.delete(*self.mod_tree.get_children())
        for idx, m in enumerate(mods):
            mod_id = m["id"]
            prog_text, tag = self.get_mod_progress_info(mod_id)
            self.mod_tree.insert("", "end", values=(m["name"], prog_text, mod_id), iid=str(idx), tags=(tag,))

    def on_search_mod(self, event=None):
        query = self.search_entry.get().strip().lower()
        if not query:
            self.render_mod_list(self.all_mods)
            return
        filtered = [m for m in self.all_mods if query in m["name"].lower() or query in m["id"].lower()]
        self.render_mod_list(filtered)

    def select_all_mods(self):
        """全MODを選択"""
        children = self.mod_tree.get_children()
        if children:
            self.mod_tree.selection_set(children)
            self.on_mod_selected(None)

    def select_untranslated_mods(self):
        """進捗率100%未満のMODのみを一括選択"""
        targets = []
        for iid in self.mod_tree.get_children():
            vals = self.mod_tree.item(iid, "values")
            mod_id = vals[2]
            prog_text, tag = self.get_mod_progress_info(mod_id)
            if tag in ("mod_partial", "mod_none"):
                targets.append(iid)
        if targets:
            self.mod_tree.selection_set(targets)
            self.on_mod_selected(None)
        else:
            messagebox.showinfo("案内", "未完了のMODはありません。すべてのMODが翻訳済みです。")

    def deselect_all_mods(self):
        """MODの選択を全解除"""
        self.mod_tree.selection_remove(self.mod_tree.selection())
        self.stat_target_lbl.configure(text="MODを選択してください")
        self.status_var.set("MODの選択を解除しました。")
        self.update_engine_status()

    def on_mod_selected(self, event):
        selected = self.mod_tree.selection()
        if not selected:
            return

        # 複数MOD選択されている場合の表示処理
        if len(selected) > 1:
            self.stat_target_lbl.configure(text=f"複数MOD選択中: {len(selected)} 件")
            self.status_var.set(f"複数MOD選択中 ({len(selected)} 件)。「一括AI翻訳」を押すと全選択MODを連続翻訳します。")
            engine = self.config.get("engine_type", "smart_dict")
            if engine == "ollama":
                model = self.config.get("ollama_model", "gemma4:e4b")
                self.btn_translate.configure(text=f"選択した {len(selected)} 件を一括翻訳 ({model})")
            else:
                self.btn_translate.configure(text=f"選択した {len(selected)} 件を一括翻訳")
        else:
            self.update_engine_status()

        # 詳細テーブルには末尾にクリックされたMODを表示
        vals = self.mod_tree.item(selected[-1], "values")
        mod_id = vals[2]
        mod = next((m for m in self.all_mods if m["id"] == mod_id), None)
        if not mod:
            return

        # 切り替え前のMODの作業中内容を自動ドラフト保存
        self.save_current_draft()

        self.current_mod = mod
        if len(selected) == 1:
            self.stat_target_lbl.configure(text=f"{mod['name']} ({mod['id']})")
            self.status_var.set(f"解析中: {mod['name']}...")
        self.update_idletasks()

        if hasattr(self, "grid_search_entry"):
            self.grid_search_entry.delete(0, tk.END)
        if hasattr(self, "grid_filter_menu"):
            self.grid_filter_menu.set("すべて表示")

        self.current_items = []

        existing_patch = None
        suffix = self.get_patch_suffix()
        user_patch = self.user_mods_dir / f"{mod_id}{suffix}"
        output_patch = self.base_dir / "output" / f"{mod_id}{suffix}"
        if user_patch.is_dir():
            existing_patch = user_patch
        elif output_patch.is_dir():
            existing_patch = output_patch

        scan_result = scan_mod(
            mod["path"],
            self.vanilla_dict,
            existing_patch_dir=existing_patch,
            workshop_dir=self.workshop_dir,
            mod_id=mod.get("id", ""),
            mod_name=mod.get("name", ""),
            target_lang=self.target_lang
        )

        # 1. 既存継承
        for inh in scan_result.get("inherited", []):
            arch_label = "公式JSON" if inh.get("file_type") in ("json", "txt") else ("printMedia" if inh.get("file_type") == "printMedia" else "Lua/UI")
            item = {
                "en": inh["en"], "jp": inh["jp"], "key": inh.get("key", ""), "keys": inh.get("keys", []),
                "file_type": inh.get("file_type", ""), "rel_path": inh.get("rel_path", ""),
                "file": inh.get("file", ""), "arch": arch_label, "status": "既存継承"
            }
            self.current_items.append(item)

        # 2. バニラ一致
        for m in scan_result.get("matched", []):
            arch_label = "公式JSON" if m.get("file_type") in ("json", "txt") else ("printMedia" if m.get("file_type") == "printMedia" else "Lua/UI")
            item = {
                "en": m["en"], "jp": m["jp"], "key": m.get("key", ""), "keys": m.get("keys", []),
                "file_type": m.get("file_type", ""), "rel_path": m.get("rel_path", ""),
                "file": m.get("file", ""), "arch": arch_label, "status": "公式一致"
            }
            self.current_items.append(item)

        # 3. 未翻訳
        for u in scan_result.get("unmatched", []):
            arch_label = "公式JSON" if u.get("file_type") in ("json", "txt") else ("printMedia" if u.get("file_type") == "printMedia" else "Lua/UI")
            item = {
                "en": u["en"], "jp": "", "key": u.get("key", ""), "keys": u.get("keys", []),
                "file_type": u.get("file_type", ""), "rel_path": u.get("rel_path", ""),
                "file": u.get("file", ""), "arch": arch_label, "status": "未翻訳"
            }
            self.current_items.append(item)

        # 4. 廃止キー
        for dep in scan_result.get("deprecated", []):
            item = {
                "en": dep["en"], "jp": dep["jp"], "key": dep.get("key", ""), "keys": dep.get("keys", []),
                "file_type": dep.get("file_type", ""), "rel_path": dep.get("rel_path", ""),
                "file": dep.get("file", ""), "arch": "旧データ", "status": "廃止キー"
            }
            self.current_items.append(item)

        # 5. ドラフト（作業中保存データ）の完全復元
        draft_map = self.get_draft_for_mod(mod_id)
        if draft_map:
            for it in self.current_items:
                en = it.get("en", "")
                if en in draft_map:
                    saved_jp = draft_map[en].get("jp", "")
                    saved_status = draft_map[en].get("status", "AI翻訳")
                    if saved_jp:
                        it["jp"] = saved_jp
                        it["status"] = saved_status

        self.render_grid_items()
        self.update_stat_badges()
        tot = len(self.current_items)
        trans = sum(1 for it in self.current_items if it.get("jp"))
        pct = int(trans / tot * 100) if tot > 0 else 0
        self.update_mod_list_progress(mod_id, pct)
        if len(selected) == 1:
            self.status_var.set(f"解析完了: {mod['name']} (計 {tot} 項目 | 日本語率: {pct}%)")

        # プログレスバーの初期表示
        self.anim_is_running = False
        self.progress_bar.set(pct / 100.0)
        self.progress_bar.configure(progress_color="#10b981" if pct == 100 else "#3b82f6")
        self.progress_status_lbl.configure(text=f"MOD: {mod['name']}", text_color="#cbd5e1")
        self.progress_pct_lbl.configure(text=f"日本語率: {pct}% ({trans} / {tot})", text_color="#38bdf8" if pct > 0 else "#94a3b8")

    def update_stat_badges(self):
        tot_cnt = len(self.current_items)
        inh_cnt = sum(1 for it in self.current_items if it.get("status", "").startswith("既存継承"))
        mat_cnt = sum(1 for it in self.current_items if it.get("status", "").startswith("公式一致"))
        unm_cnt = sum(1 for it in self.current_items if not it.get("jp"))
        over_cnt = sum(1 for it in self.current_items if it.get("jp") and check_overflow_risk(it["en"], it["jp"])[0])

        self.badge_total.configure(text=f"総項目: {tot_cnt}")
        self.badge_inherited.configure(text=f"既存継承: {inh_cnt}")
        self.badge_matched.configure(text=f"公式一致: {mat_cnt}")
        self.badge_unmatched.configure(text=f"未翻訳: {unm_cnt}")
        self.badge_overflow.configure(text=f"⚠️幅注意: {over_cnt}")

        # スマート提案バナー (未翻訳項目があり、エンジンがスマート辞書の場合)
        engine = self.config.get("engine_type", "smart_dict")
        if unm_cnt > 0 and engine == "smart_dict":
            self.banner_lbl.configure(
                text=f"💡 MOD独自文章の未翻訳が {unm_cnt} 件あります。ローカルAI (Ollama) を有効にすると一括翻訳できます。"
            )
            self.suggestion_banner.pack(fill="x", padx=16, pady=(0, 8), before=self.action_bar)
        else:
            self.suggestion_banner.pack_forget()

    def update_grid_headings(self):
        col_names = {
            "en": t("col_en"),
            "jp": t("col_trans", lang=self.target_lang),
            "arch": t("col_arch"),
            "status": t("col_status"),
            "file": t("col_file"),
        }
        for col, base_text in col_names.items():
            arrow = ""
            if self.sort_column == col:
                arrow = " ▲" if not self.sort_reverse else " ▼"
            self.grid_tree.heading(col, text=f"{base_text}{arrow}", command=lambda c=col: self.on_grid_sort_column(c))

    def on_grid_sort_column(self, col: str):
        if self.sort_column == col:
            self.sort_reverse = not self.sort_reverse
        else:
            self.sort_column = col
            self.sort_reverse = False
        self.update_grid_headings()
        self.render_grid_items()

    def on_clear_grid_filter(self):
        self.grid_search_entry.delete(0, tk.END)
        self.grid_filter_menu.set("すべて表示")
        self.render_grid_items()

    def render_grid_items(self):
        self.grid_tree.delete(*self.grid_tree.get_children())
        if not self.current_items:
            if hasattr(self, "grid_count_lbl"):
                self.grid_count_lbl.configure(text="")
            return

        query = self.grid_search_entry.get().strip().lower() if hasattr(self, "grid_search_entry") else ""
        filter_opt = self.grid_filter_menu.get() if hasattr(self, "grid_filter_menu") else "すべて表示"

        filtered = []
        for it in self.current_items:
            en = it.get("en", "")
            jp = it.get("jp", "")
            arch = it.get("arch", "")
            st = it.get("status", "")
            fl = it.get("file", "")
            key = it.get("key", "")

            # フィルター条件の判定
            if filter_opt in ("未翻訳のみ", "Untranslated Only") and jp:
                continue
            elif filter_opt in ("AI翻訳・手動のみ", "AI / Manual Only") and st not in ("AI翻訳", "手動修正", "辞書翻訳"):
                continue
            elif filter_opt in ("公式一致・継承のみ", "Official / Inherited Only") and st not in ("公式一致", "既存継承"):
                continue
            elif filter_opt in ("幅注意のみ", "⚠️幅注意のみ", "Overflow Only", "⚠️ Overflow Only"):
                if not jp or not check_overflow_risk(en, jp)[0]:
                    continue
            elif "公式JSON" in filter_opt and arch != "公式JSON":
                continue
            elif "Lua/UI" in filter_opt and arch != "Lua/UI":
                continue
            elif "printMedia" in filter_opt and arch != "printMedia":
                continue

            # 検索文字列の部分一致 (原文・訳文・タイプ・ステータス・ファイル名・内部キー)
            if query:
                search_blob = f"{en} {jp} {arch} {st} {fl} {key}".lower()
                if query not in search_blob:
                    continue

            filtered.append(it)

        # 列ヘッダーソートの適用
        if self.sort_column:
            col = self.sort_column
            def get_sort_val(item):
                if col == "en":
                    return item.get("en", "").lower()
                elif col == "jp":
                    val = item.get("jp", "").strip().lower()
                    has_val = 0 if val else 1
                    if self.sort_reverse:
                        has_val = 1 if val else 0
                    return (has_val, val)
                elif col == "arch":
                    return item.get("arch", "").lower()
                elif col == "status":
                    disp, _ = get_item_row_meta(item.get("en", ""), item.get("jp", ""), item.get("status", ""))
                    return disp.lower()
                elif col == "file":
                    return item.get("file", "").lower()
                return ""

            filtered.sort(key=get_sort_val, reverse=self.sort_reverse)

        for it in filtered:
            disp_status, tag = get_item_row_meta(it.get("en", ""), it.get("jp", ""), it.get("status", ""))
            self.grid_tree.insert(
                "", "end",
                values=(it.get("en", ""), it.get("jp", ""), it.get("arch", ""), disp_status, it.get("file", "")),
                tags=(tag,)
            )

        tot = len(self.current_items)
        cnt = len(filtered)
        if hasattr(self, "grid_count_lbl"):
            if cnt == tot:
                self.grid_count_lbl.configure(text=f"全 {tot} 件")
            else:
                self.grid_count_lbl.configure(text=f"表示中: {cnt} / {tot} 件")

    def on_grid_double_click(self, event):
        selected = self.grid_tree.selection()
        if not selected:
            return
        item_id = selected[0]
        vals = self.grid_tree.item(item_id, "values")
        orig_en, current_jp, arch, status, filename = vals[0], vals[1], vals[2], vals[3], vals[4]

        dialog = ModernEditDialog(self, orig_en, current_jp)
        self.wait_window(dialog)

        if dialog.result is not None and dialog.result != current_jp:
            new_jp = dialog.result
            for it in self.current_items:
                if it["en"] == orig_en:
                    it["jp"] = new_jp
                    it["status"] = "手動修正"
            self.render_grid_items()
            self.update_stat_badges()
            for child in self.grid_tree.get_children():
                if self.grid_tree.item(child, "values")[0] == orig_en:
                    self.grid_tree.selection_set(child)
                    self.grid_tree.see(child)
                    break
            if self.current_mod:
                tot = len(self.current_items)
                trans = sum(1 for it in self.current_items if it.get("jp"))
                pct = int(trans / tot * 100) if tot > 0 else 0
                self.update_mod_list_progress(self.current_mod["id"], pct)
                self.save_current_draft()
            self.status_var.set(f"編集保存: \"{orig_en}\" ➡ \"{new_jp}\"")

    def open_quickstart_dialog(self):
        dialog = QuickStartDialog(self)
        self.wait_window(dialog)

    def on_switch_to_ollama_banner(self):
        ollama = OllamaClient()
        installed = []
        try:
            if ollama.is_available():
                installed = ollama.get_models()
        except Exception:
            pass
        best_model = "gemma4:e4b"
        for pref in ["gemma4:e4b", "qwen2.5:7b", "llama3.1:8b", "qwen2.5:3b"]:
            for m in installed:
                if pref in m:
                    best_model = m
                    break
            if best_model != "gemma4:e4b":
                break
        if installed and best_model not in installed:
            best_model = installed[0]

        self.config["engine_type"] = "ollama"
        self.config["ollama_model"] = best_model
        ConfigManager.save(self.config)
        self.on_settings_updated()
        self.status_var.set(f"🦙 ローカルAI ({best_model}) に切り替えました！下の「一括AI翻訳を実行」をクリックして翻訳を開始できます。")

    def on_open_settings(self):
        dialog = ModernSettingsDialog(self)
        self.wait_window(dialog)

    def on_stop_translation(self):
        """ユーザーによる一括翻訳の中断要求"""
        if hasattr(self, "stop_event") and self.stop_event:
            self.stop_event.set()
            self.btn_stop_translate.configure(state="disabled", text="⏹️ 中断要求中...")
            self.status_var.set("⏹️ 翻訳の中断を要求しました... (反映処理中)")

    def on_translate_batch(self, selected_iids):
        """複数選択されたMODを順番にAI翻訳する一括連続処理"""
        selected_mods = []
        for iid in selected_iids:
            vals = self.mod_tree.item(iid, "values")
            mod_id = vals[2]
            m = next((mod for mod in self.all_mods if mod["id"] == mod_id), None)
            if m:
                selected_mods.append(m)

        if not selected_mods:
            return

        cfg = ConfigManager.load()
        engine_type = cfg.get("engine_type", "smart_dict")

        # 事前検証
        if engine_type == "ollama":
            ollama = OllamaClient()
            if not ollama.is_available() and not ollama.ensure_started(timeout_sec=5.0):
                messagebox.showerror("Ollama接続エラー", "ローカルAI (Ollama) が起動していないか、接続できません。")
                return
            target_model = cfg.get("ollama_model", "").strip()
            installed = ollama.get_models()
            def is_installed(t, m_list):
                t_low = t.lower().strip()
                for m in m_list:
                    ml = m.lower().strip()
                    if t_low == ml or f"{t_low}:latest" == ml or t_low == ml.split(":")[0]:
                        return True
                return False
            if not target_model or not is_installed(target_model, installed):
                messagebox.showwarning("モデル未検出", f"モデル「{target_model}」がOllamaにありません。設定からダウンロードしてください。")
                self.on_open_settings()
                return
        elif engine_type == "api":
            if cfg.get("api_provider") == "gemini" and not cfg.get("gemini_api_key", "").strip():
                messagebox.showwarning("APIキー未設定", "Gemini APIキーを設定してください。")
                self.on_open_settings()
                return

        ans = messagebox.askyesno(
            "複数MODの一括連続翻訳",
            f"選択された {len(selected_mods)} 個のMODを順番に自動翻訳します。\n\n"
            f"・各MODの翻訳結果は自動的にドラフト保存されます。\n"
            f"・途中で「⏹️ 中断」を押しても、それまでに翻訳されたMODは安全に保持されます。\n\n"
            f"一括翻訳を開始しますか？"
        )
        if not ans:
            return

        self.stop_event.clear()
        self.btn_translate.configure(state="disabled")
        self.btn_stop_translate.configure(state="normal", fg_color="#ef4444", text="⏹️ 中断 (停止)")
        self.btn_apply.configure(state="disabled")
        self.btn_export.configure(state="disabled")
        self.start_progress_animation(total=len(selected_mods))

        def batch_worker():
            total_mods = len(selected_mods)
            completed_mods = 0

            for idx, mod in enumerate(selected_mods):
                if self.stop_event.is_set():
                    break

                mod_id = mod["id"]
                mod_name = mod["name"]
                suffix = self.get_patch_suffix()
                user_patch = self.user_mods_dir / f"{mod_id}{suffix}"
                output_patch = self.base_dir / "output" / f"{mod_id}{suffix}"
                existing_patch = user_patch if user_patch.is_dir() else (output_patch if output_patch.is_dir() else None)

                # スキャン実行
                scan_res = scan_mod(
                    mod["path"], self.vanilla_dict,
                    existing_patch_dir=existing_patch,
                    workshop_dir=self.workshop_dir,
                    mod_id=mod_id, mod_name=mod_name,
                    target_lang=self.target_lang
                )

                items = []
                for inh in scan_res.get("inherited", []):
                    arch_label = "公式JSON" if inh.get("file_type") in ("json", "txt") else ("printMedia" if inh.get("file_type") == "printMedia" else "Lua/UI")
                    items.append({"en": inh["en"], "jp": inh["jp"], "key": inh.get("key", ""), "keys": inh.get("keys", []), "file_type": inh.get("file_type", ""), "rel_path": inh.get("rel_path", ""), "file": inh.get("file", ""), "arch": arch_label, "status": "既存継承"})
                for m_item in scan_res.get("matched", []):
                    arch_label = "公式JSON" if m_item.get("file_type") in ("json", "txt") else ("printMedia" if m_item.get("file_type") == "printMedia" else "Lua/UI")
                    items.append({"en": m_item["en"], "jp": m_item["jp"], "key": m_item.get("key", ""), "keys": m_item.get("keys", []), "file_type": m_item.get("file_type", ""), "rel_path": m_item.get("rel_path", ""), "file": m_item.get("file", ""), "arch": arch_label, "status": "公式一致"})
                for u in scan_res.get("unmatched", []):
                    arch_label = "公式JSON" if u.get("file_type") in ("json", "txt") else ("printMedia" if u.get("file_type") == "printMedia" else "Lua/UI")
                    items.append({"en": u["en"], "jp": "", "key": u.get("key", ""), "keys": u.get("keys", []), "file_type": u.get("file_type", ""), "rel_path": u.get("rel_path", ""), "file": u.get("file", ""), "arch": arch_label, "status": "未翻訳"})

                # 既存ドラフトの適用
                draft_map = self.get_draft_for_mod(mod_id)
                if draft_map:
                    for it in items:
                        en = it.get("en", "")
                        if en in draft_map:
                            saved_jp = draft_map[en].get("jp", "")
                            saved_st = draft_map[en].get("status", "AI翻訳")
                            if saved_jp:
                                it["jp"] = saved_jp
                                it["status"] = saved_st

                untranslated = [it for it in items if not it.get("jp")]
                if not untranslated:
                    tot_i = len(items)
                    self.after(0, lambda m_id=mod_id: self.update_mod_list_progress(m_id, 100))
                    completed_mods += 1
                    continue

                def progress_cb(current, total, text):
                    pct = int(current / max(total, 1) * 100)
                    overall_text = f"[{idx+1}/{total_mods}] {mod_name} ({pct}%): {text}"
                    self.after(0, lambda: self.update_progress(idx * 100 + pct, total_mods * 100, overall_text))

                translated_dict = run_translation_pipeline(
                    untranslated, self.vanilla_dict,
                    progress_callback=progress_cb,
                    config=cfg,
                    stop_event=self.stop_event
                )

                engine = cfg.get("engine_type", "smart_dict")
                base_status = "辞書翻訳" if engine == "smart_dict" else "AI翻訳"
                for it in items:
                    en = it.get("en", "")
                    if en in translated_dict:
                        it["jp"] = translated_dict[en]
                        it["status"] = base_status

                # ドラフトキャッシュ保存
                key = f"{mod_id}_{self.target_lang}"
                draft_save = {it["en"]: {"jp": it["jp"], "status": it.get("status", "AI翻訳")} for it in items if it.get("en") and it.get("jp")}
                self.mod_draft_cache[key] = draft_save
                self.save_draft_cache()

                # 進捗率更新
                tot_i = len(items)
                trans_i = sum(1 for it in items if it.get("jp"))
                pct_i = int(trans_i / tot_i * 100) if tot_i > 0 else 0
                self.after(0, lambda m_id=mod_id, p=pct_i: self.update_mod_list_progress(m_id, p))

                # もし現在詳細グリッドに表示中のMODならグリッドも即時反映
                if self.current_mod and self.current_mod["id"] == mod_id:
                    self.current_items = items
                    self.after(0, self.render_grid_items)
                    self.after(0, self.update_stat_badges)

                completed_mods += 1

            was_aborted = self.stop_event.is_set()
            def on_batch_finish():
                self.btn_translate.configure(state="normal")
                self.btn_stop_translate.configure(state="disabled", fg_color="#334155", text="⏹️ 中断 (停止)")
                self.btn_apply.configure(state="normal")
                self.btn_export.configure(state="normal")
                self.stop_progress_animation(was_aborted=was_aborted, count=completed_mods)
                if was_aborted:
                    self.status_var.set(f"⏹️ 一括連続翻訳を中断しました ({completed_mods}/{total_mods} MOD完了)")
                    messagebox.showinfo("中断完了", f"複数MODの一括翻訳を中断しました。\n\nそれまでに翻訳完了した {completed_mods} 個のMODデータは安全にドラフト保存されています。")
                else:
                    self.status_var.set(f"✓ 一括連続翻訳完了: 選択された {completed_mods} 個のMODをすべて翻訳しました！")
                    messagebox.showinfo("一括翻訳完了", f"選択された {completed_mods} 個のMODのAI翻訳がすべて完了しました！\n\n各MODの翻訳結果はドラフト保存されています。いつでも「ローカルMOD適用」や「ZIPエクスポート」を行えます。")

            self.after(0, on_batch_finish)

        threading.Thread(target=batch_worker, daemon=True).start()

    def on_translate_all(self):
        selected_iids = self.mod_tree.selection()
        if len(selected_iids) > 1:
            self.on_translate_batch(selected_iids)
            return

        if not self.current_items:
            messagebox.showinfo("案内", "MODが選択されていないか、翻訳対象がありません。")
            return

        untranslated = [it for it in self.current_items if not it.get("jp")]
        retrans_items = [
            it for it in self.current_items
            if it.get("jp") and it.get("status") not in ("公式一致", "手動修正")
        ]

        if not untranslated:
            if retrans_items:
                confirm = messagebox.askyesno(
                    "再翻訳の確認",
                    f"未翻訳の新規項目はありませんが、過去に翻訳された項目が {len(retrans_items)} 件あります。\n\n"
                    f"現在の翻訳エンジン/モデルで上書き再翻訳しますか？\n"
                    f"(※ 手動修正した項目や公式一致項目は保護されます)"
                )
                if confirm:
                    untranslated = retrans_items
                else:
                    return
            else:
                messagebox.showinfo("案内", "未翻訳の項目はありません。すべて翻訳済みです。")
                return

        cfg = ConfigManager.load()
        engine_type = cfg.get("engine_type", "smart_dict")

        # ── 事前検証 (Pre-flight Check) ──
        if engine_type == "ollama":
            ollama = OllamaClient()
            if not ollama.is_available():
                if not ollama.ensure_started(timeout_sec=5.0):
                    messagebox.showerror(
                        "Ollama接続エラー",
                        "ローカルAI (Ollama) が起動していないか、接続できません。\n\n"
                        "Windowsのタスクバー通知領域（右下）にアルパカ/ラマのアイコンが起動しているか確認してください。"
                    )
                    return

            target_model = cfg.get("ollama_model", "").strip()
            installed = ollama.get_models()

            def is_installed(target, model_list):
                t = target.lower().strip()
                for m in model_list:
                    m_low = m.lower().strip()
                    if t == m_low or f"{t}:latest" == m_low or t == m_low.split(":")[0]:
                        return True
                return False

            if not target_model or not is_installed(target_model, installed):
                installed_summary = ", ".join(installed) if installed else "（インストール済みモデルなし）"

                # PC内にすでにインストールされている適切な代替候補を探す
                candidate = None
                for pref in ["gemma4:e4b", "qwen2.5:7b", "llama3.1:8b", "qwen2.5:3b"]:
                    for m in installed:
                        if pref in m:
                            candidate = m
                            break
                    if candidate:
                        break
                if not candidate and installed:
                    candidate = installed[0]

                if candidate:
                    ans = messagebox.askyesno(
                        "モデル未検出・自動切替の確認",
                        f"現在設定されているモデル「{target_model}」はPC内のOllamaにまだダウンロードされていません。\n\n"
                        f"【PC内にインストール済みのモデル】\n{installed_summary}\n\n"
                        f"代わりにインストール済みの「{candidate}」を使って今すぐ翻訳を開始しますか？\n\n"
                        f"※「いいえ」を押すと設定画面が開き、希望モデルのダウンロードが行えます。"
                    )
                    if ans:
                        cfg["ollama_model"] = candidate
                        ConfigManager.save(cfg)
                        self.config = cfg
                        self.on_settings_updated()
                    else:
                        self.on_open_settings()
                        return
                else:
                    messagebox.showwarning(
                        "モデル未インストール",
                        f"設定されているモデル「{target_model}」がPC内に見つかりません。\n\n"
                        f"右上の「⚙️ 翻訳設定」から希望のモデルをダウンロードするか、インストール済みモデルを選択してください。"
                    )
                    self.on_open_settings()
                    return

        elif engine_type == "api":
            api_provider = cfg.get("api_provider", "gemini")
            if api_provider == "gemini" and not cfg.get("gemini_api_key", "").strip():
                messagebox.showwarning(
                    "Gemini APIキー未設定",
                    "Google Gemini APIキーが設定されていません。\n\n"
                    "右上の「⚙️ 翻訳設定」を開き、APIキーを入力してください。"
                )
                self.on_open_settings()
                return

        self.stop_event.clear()
        self.btn_translate.configure(state="disabled")
        self.btn_stop_translate.configure(state="normal", fg_color="#ef4444", text="⏹️ 中断 (停止)")
        self.btn_apply.configure(state="disabled")
        self.btn_export.configure(state="disabled")
        self.start_progress_animation(total=len(untranslated))

        def progress_cb(current, total, text):
            self.after(0, lambda: self.update_progress(current, total, text))

        def worker():
            translated_dict = run_translation_pipeline(
                untranslated, self.vanilla_dict, progress_callback=progress_cb, config=cfg, stop_event=self.stop_event
            )
            was_aborted = self.stop_event.is_set()
            self.after(0, lambda: self.finish_translation(translated_dict, was_aborted=was_aborted))

        threading.Thread(target=worker, daemon=True).start()

    def start_progress_animation(self, total: int):
        self.anim_is_running = True
        self.anim_current_progress = 0.0
        self.anim_target_progress = 0.0
        self.anim_spinner_idx = 0
        self.anim_pulse_tick = 0
        engine = self.config.get("engine_type", "smart_dict")
        action_name = "辞書照合" if engine == "smart_dict" else "AI翻訳"
        self.anim_active_text = f"{action_name}の準備中..."
        self.progress_bar.set(0)
        self.progress_bar.configure(progress_color="#3b82f6")
        self.progress_status_lbl.configure(text=f"⠋ {self.anim_active_text}", text_color="#38bdf8")
        self.progress_pct_lbl.configure(text=f"0% (0 / {total})", text_color="#cbd5e1")
        self._progress_animation_tick()

    def _progress_animation_tick(self):
        if not getattr(self, "anim_is_running", False) or getattr(self, "_closing", False):
            return

        # 1. なめらかな進捗値の線形補間 (Lerp)
        diff = self.anim_target_progress - self.anim_current_progress
        if abs(diff) > 0.003:
            self.anim_current_progress += diff * 0.25
        else:
            self.anim_current_progress = self.anim_target_progress
        self.progress_bar.set(self.anim_current_progress)

        # 2. スピナーアニメーション
        SPINNER_FRAMES = ["⠋", "⠙", "⠹", "⠸", "⠼", "⠴", "⠦", "⠧", "⠇", "⠏"]
        self.anim_spinner_idx = (self.anim_spinner_idx + 1) % len(SPINNER_FRAMES)
        sp = SPINNER_FRAMES[self.anim_spinner_idx]

        txt = getattr(self, "anim_active_text", "AI翻訳中...")
        if len(txt) > 46:
            txt = txt[:43] + "..."
        self.progress_status_lbl.configure(text=f"{sp} {txt}")

        # 3. 脈動するパルス・シマーカラーアニメーション
        PULSE_COLORS = [
            "#3b82f6", "#2563eb", "#38bdf8", "#06b6d4",
            "#38bdf8", "#60a5fa", "#818cf8", "#6366f1", "#4f46e5"
        ]
        self.anim_pulse_tick = (self.anim_pulse_tick + 1) % len(PULSE_COLORS)
        self.progress_bar.configure(progress_color=PULSE_COLORS[self.anim_pulse_tick])

        self.after(60, self._progress_animation_tick)

    def stop_progress_animation(self, was_aborted=False, count=0):
        self.anim_is_running = False
        if was_aborted:
            self.progress_bar.configure(progress_color="#f59e0b")
            self.progress_status_lbl.configure(text=f"⏹️ 中断しました ({count} 項目反映保持)", text_color="#fbbf24")
            self.progress_pct_lbl.configure(text_color="#fbbf24")
        else:
            self.progress_bar.configure(progress_color="#10b981")
            self.progress_bar.set(1.0)
            self.progress_status_lbl.configure(text=f"✓ 完了! ({count} 項目反映)", text_color="#34d399")
            self.progress_pct_lbl.configure(text="100%", text_color="#34d399")

    def update_progress(self, current, total, text):
        ratio = current / max(total, 1)
        self.anim_target_progress = ratio
        engine = self.config.get("engine_type", "smart_dict")
        action_name = "辞書翻訳中" if engine == "smart_dict" else "AI翻訳中"
        self.anim_active_text = f"{action_name}: \"{text}\""
        self.progress_pct_lbl.configure(text=f"{int(ratio * 100)}% ({current} / {total})")
        self.status_var.set(f"{action_name} ({current}/{total}): {text}")

    def finish_translation(self, translated_dict, was_aborted=False):
        self.btn_translate.configure(state="normal")
        self.btn_stop_translate.configure(state="disabled", fg_color="#334155", text="⏹️ 中断 (停止)")
        self.btn_apply.configure(state="normal")
        self.btn_export.configure(state="normal")
        self.stop_progress_animation(was_aborted=was_aborted, count=len(translated_dict))
        engine = self.config.get("engine_type", "smart_dict")
        base_status = "辞書翻訳" if engine == "smart_dict" else "AI翻訳"

        for it in self.current_items:
            en = it.get("en", "")
            if en in translated_dict:
                it["jp"] = translated_dict[en]
                it["status"] = base_status

        self.render_grid_items()
        self.update_stat_badges()
        if self.current_mod:
            tot = len(self.current_items)
            trans = sum(1 for it in self.current_items if it.get("jp"))
            pct = int(trans / tot * 100) if tot > 0 else 0
            self.update_mod_list_progress(self.current_mod["id"], pct)
            self.save_current_draft()

        action_name = "一括辞書翻訳" if engine == "smart_dict" else "一括AI翻訳"
        if was_aborted:
            self.status_var.set(f"⏹️ {action_name}を中断しました: {len(translated_dict)} 項目を反映保持しました。")
            messagebox.showinfo("中断完了", f"{action_name}を途中で中断しました。\n\nそれまでに翻訳された {len(translated_dict)} 項目はグリッドに保持されています。")
        else:
            self.status_var.set(f"{action_name}完了: {len(translated_dict)} 項目を翻訳しました。")
            if len(translated_dict) == 0 and engine == "smart_dict":
                messagebox.showinfo(
                    "スマート辞書照合結果",
                    "未翻訳の項目について、公式ゲーム辞書に一致するテキストが見つかりませんでした (0件)。\n\n"
                    "【原因】\n"
                    "現在「内蔵スマート辞書 (Smart Dict)」モードが動作しています。\n"
                    "残りの未翻訳テキスト（設定項目・台詞・長文など）はMOD独自の記述であるため、公式辞書には存在しません。\n\n"
                    "【解決策】\n"
                    "右上の「⚙️ 翻訳設定」を開き、翻訳エンジンを「🦙 Ollama (ローカルLLM)」または「Gemini / OpenAI API」に変更してください。\n"
                    "AI翻訳エンジンを有効にすると、残りのMOD独自文章を自動翻訳できます。"
                )
            else:
                messagebox.showinfo("完了", f"{len(translated_dict)} 項目の{action_name}が完了しました！")

    def on_apply_local(self):
        if not self.current_mod or not self.current_items:
            messagebox.showinfo(t("status_ready"), t("msg_no_mod_selected"))
            return

        translated_items = [it for it in self.current_items if it.get("jp")]
        if not translated_items:
            messagebox.showwarning("警告", t("msg_no_trans_items"))
            return

        out_mods_dir = self.user_mods_dir
        suffix = self.get_patch_suffix()
        patch_dir = generate_patch_mod(self.current_mod["id"], self.current_mod["name"], translated_items, out_mods_dir, target_lang=self.target_lang)

        tot = len(self.current_items)
        trans = sum(1 for it in self.current_items if it.get("jp"))
        pct = int(trans / tot * 100) if tot > 0 else 100
        self.update_mod_list_progress(self.current_mod["id"], pct)

        messagebox.showinfo(
            t("status_ready"),
            f"{t('msg_apply_success')}\n\n"
            f"MOD ID: {self.current_mod['id']}{suffix}\n"
            f"配置先:\n{patch_dir}\n\n"
            f"Project Zomboid を起動し、MOD画面で有効化してください。"
        )
        self.status_var.set(f"ローカル適用完了: {self.current_mod['id']}{suffix}")

    def on_export_zip(self):
        if not self.current_mod or not self.current_items:
            messagebox.showinfo(t("status_ready"), t("msg_no_mod_selected"))
            return

        translated_items = [it for it in self.current_items if it.get("jp")]
        temp_out = self.base_dir / "output"
        suffix = self.get_patch_suffix()
        patch_dir = generate_patch_mod(self.current_mod["id"], self.current_mod["name"], translated_items, temp_out, target_lang=self.target_lang)

        zip_dest = self.base_dir / f"{self.current_mod['id']}{suffix}.zip"
        shutil.make_archive(str(self.base_dir / f"{self.current_mod['id']}{suffix}"), "zip", temp_out, f"{self.current_mod['id']}{suffix}")

        messagebox.showinfo(
            t("status_ready"),
            f"{t('msg_export_success')}\n\n出力先:\n{zip_dest}\n\n"
            f"※ ZIP内にはSteamワークショップ投稿用の説明文（WORKSHOP_DESCRIPTION.txt）およびライセンス注意事項（README_LICENSE.txt）が同梱されています。"
        )
        self.status_var.set(f"ZIPエクスポート完了: {zip_dest.name}")

    def on_import_zip(self):
        zip_path = filedialog.askopenfilename(filetypes=[("ZIPファイル", "*.zip"), ("すべてのファイル", "*.*")])
        if not zip_path:
            return

        dest_dir = self.user_mods_dir
        dest_dir.mkdir(parents=True, exist_ok=True)
        shutil.unpack_archive(zip_path, dest_dir)

        messagebox.showinfo("インポート完了", f"翻訳MODを自動インストールしました！\n\n展開先:\n{dest_dir}\n\nゲームを起動して有効化してください。")
        self.status_var.set(f"インポート完了: {Path(zip_path).name}")
        self.scan_installed_mods()

    def on_open_manual(self):
        manual_path = self.base_dir / "MANUAL.html"
        if manual_path.is_file():
            lang = "en" if getattr(self, "ui_lang", "ja") == "en" else "ja"
            target_uri = f"{manual_path.as_uri()}#lang={lang}&mode=quick"
            webbrowser.open(target_uri)
        else:
            messagebox.showwarning("案内", "マニュアルファイル (MANUAL.html) が見つかりません。")

    def on_rebuild_dict(self):
        if not self.pz_dir:
            messagebox.showerror("エラー", "PZ本体ディレクトリが見つかりません。")
            return
        self.status_var.set("バニラ公式辞書を再構築中...")
        self.update_idletasks()
        build_master_dictionary(self.pz_dir, self.base_dir)
        self.load_dictionary_cache()
        messagebox.showinfo("完了", "マスター辞書の再構築が完了しました！")

    def on_main_window_close(self):
        self._closing = True
        self.destroy()

    def start_telemetry_monitor(self):
        """ハードウェアリソース (CPU, RAM, GPU, VRAM) を監視するバックグラウンドスレッド"""
        def telemetry_worker():
            import time
            while not getattr(self, "_closing", False):
                try:
                    # CPU
                    cpu_pct = psutil.cpu_percent(interval=None) if psutil else 0.0

                    # RAM
                    ram_pct = 0.0
                    ram_used_gb = 0.0
                    ram_tot_gb = 0.0
                    if psutil:
                        mem = psutil.virtual_memory()
                        ram_pct = mem.percent
                        ram_used_gb = mem.used / (1024 ** 3)
                        ram_tot_gb = mem.total / (1024 ** 3)

                    # GPU & VRAM (nvidia-smi)
                    gpu_pct = None
                    vram_used_gb = None
                    vram_tot_gb = None
                    vram_pct = None
                    try:
                        cflags = subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0
                        res = subprocess.run(
                            ["nvidia-smi", "--query-gpu=utilization.gpu,memory.used,memory.total", "--format=csv,noheader,nounits"],
                            capture_output=True, text=True, timeout=1, creationflags=cflags
                        )
                        if res.returncode == 0 and res.stdout.strip():
                            parts = [x.strip() for x in res.stdout.strip().split(",")]
                            if len(parts) >= 3:
                                gpu_pct = float(parts[0])
                                used_mb = float(parts[1])
                                tot_mb = float(parts[2])
                                vram_used_gb = used_mb / 1024.0
                                vram_tot_gb = tot_mb / 1024.0
                                vram_pct = (used_mb / max(tot_mb, 1.0)) * 100.0
                    except Exception:
                        pass

                    metrics = {
                        "cpu": cpu_pct,
                        "ram_pct": ram_pct,
                        "ram_used": ram_used_gb,
                        "ram_tot": ram_tot_gb,
                        "gpu": gpu_pct,
                        "vram_pct": vram_pct,
                        "vram_used": vram_used_gb,
                        "vram_tot": vram_tot_gb,
                    }
                    if not getattr(self, "_closing", False):
                        self.after(0, self.update_telemetry_ui, metrics)
                except Exception:
                    pass
                time.sleep(2.0)

        threading.Thread(target=telemetry_worker, daemon=True).start()

    def update_telemetry_ui(self, m: dict):
        if getattr(self, "_closing", False):
            return

        def get_color(pct):
            if pct is None:
                return "#64748b"
            if pct >= 90:
                return "#ef4444"
            if pct >= 75:
                return "#fbbf24"
            return "#e2e8f0"

        try:
            cpu = m.get("cpu", 0)
            self.hw_cpu_lbl.configure(text=f"💻 CPU: {cpu:.0f}%", text_color=get_color(cpu))

            ram_p = m.get("ram_pct", 0)
            ram_u = m.get("ram_used", 0)
            self.hw_ram_lbl.configure(text=f"🧠 RAM: {ram_p:.0f}% ({ram_u:.1f}G)", text_color=get_color(ram_p))

            gpu = m.get("gpu")
            if gpu is not None:
                self.hw_gpu_lbl.configure(text=f"🎮 GPU: {gpu:.0f}%", text_color=get_color(gpu))
            else:
                self.hw_gpu_lbl.configure(text="🎮 GPU: N/A", text_color="#64748b")

            vram_p = m.get("vram_pct")
            vram_u = m.get("vram_used")
            if vram_p is not None and vram_u is not None:
                self.hw_vram_lbl.configure(text=f"⚡ VRAM: {vram_p:.0f}% ({vram_u:.1f}G)", text_color=get_color(vram_p))
            else:
                self.hw_vram_lbl.configure(text="⚡ VRAM: N/A", text_color="#64748b")
        except Exception:
            pass


if __name__ == "__main__":
    app = ModernZTranzlatorApp()
    app.mainloop()
