"""
zTranzlator - Internationalization (i18n) & Multi-Language Support
アプリUI表示言語: 日本語(ja), English(en), 한국어(ko), 简体中文(zh-CN), Español(es)
MOD翻訳先言語: JP, KO, CN, CH, ES, RU, FR, DE, PL, PTBR, IT 等
"""

SUPPORTED_UI_LANGUAGES = {
    "ja": "日本語 (Japanese)",
    "en": "English",
    "ko": "한국어 (Korean)",
    "zh-CN": "简体中文 (Simplified Chinese)",
    "es": "Español (Spanish)",
}

SUPPORTED_TARGET_LANGUAGES = {
    "JP": {"name": "日本語", "en_name": "Japanese", "suffix": "_JA"},
    "KO": {"name": "한국어", "en_name": "Korean", "suffix": "_KO"},
    "CN": {"name": "简体中文", "en_name": "Simplified Chinese", "suffix": "_CN"},
    "CH": {"name": "繁體中文", "en_name": "Traditional Chinese", "suffix": "_CH"},
    "ES": {"name": "Español", "en_name": "Spanish", "suffix": "_ES"},
    "RU": {"name": "Русский", "en_name": "Russian", "suffix": "_RU"},
    "FR": {"name": "Français", "en_name": "French", "suffix": "_FR"},
    "DE": {"name": "Deutsch", "en_name": "German", "suffix": "_DE"},
    "PL": {"name": "Polski", "en_name": "Polish", "suffix": "_PL"},
    "PTBR": {"name": "Português (Brasil)", "en_name": "Brazilian Portuguese", "suffix": "_PTBR"},
    "IT": {"name": "Italiano", "en_name": "Italian", "suffix": "_IT"},
}

STRINGS = {
    "app_title": {
        "ja": "zTranzlator — Project Zomboid Build 42 総合翻訳スイート",
        "en": "zTranzlator — Project Zomboid Build 42 Translation Suite",
        "ko": "zTranzlator — Project Zomboid Build 42 종합 번역 도구",
        "zh-CN": "zTranzlator — 僵尸毁灭工程 Build 42 综合翻译套件",
        "es": "zTranzlator — Suite de Traducción para Project Zomboid Build 42",
    },
    "btn_settings": {
        "ja": "⚙ 翻訳設定",
        "en": "⚙ Settings",
        "ko": "⚙ 번역 설정",
        "zh-CN": "⚙ 翻译设置",
        "es": "⚙ Ajustes",
    },
    "btn_manual": {
        "ja": "マニュアル (HTML)",
        "en": "Manual (HTML)",
        "ko": "매뉴얼 (HTML)",
        "zh-CN": "使用说明 (HTML)",
        "es": "Manual (HTML)",
    },
    "btn_import_zip": {
        "ja": "ZIPインポート",
        "en": "Import ZIP",
        "ko": "ZIP 가져오기",
        "zh-CN": "导入 ZIP",
        "es": "Importar ZIP",
    },
    "btn_rescan": {
        "ja": "再スキャン",
        "en": "Rescan",
        "ko": "다시 스캔",
        "zh-CN": "重新扫描",
        "es": "Reescanear",
    },
    "search_placeholder": {
        "ja": "MODを検索...",
        "en": "Search MODs...",
        "ko": "모드 검색...",
        "zh-CN": "搜索 MOD...",
        "es": "Buscar MODs...",
    },
    "col_mod_name": {
        "ja": "MOD名",
        "en": "Mod Name",
        "ko": "모드 이름",
        "zh-CN": "MOD名称",
        "es": "Nombre del MOD",
    },
    "col_progress": {
        "ja": "翻訳率",
        "en": "Progress",
        "ko": "진행률",
        "zh-CN": "进度",
        "es": "Progreso",
    },
    "col_id": {
        "ja": "ID",
        "en": "ID",
        "ko": "ID",
        "zh-CN": "ID",
        "es": "ID",
    },
    "col_en": {
        "ja": "原文 (English)",
        "en": "Original (English)",
        "ko": "원문 (English)",
        "zh-CN": "原文 (English)",
        "es": "Original (English)",
    },
    "col_trans": {
        "ja": "訳文 ({lang})",
        "en": "Translation ({lang})",
        "ko": "번역 ({lang})",
        "zh-CN": "译文 ({lang})",
        "es": "Traducción ({lang})",
    },
    "col_arch": {
        "ja": "根拠",
        "en": "Source",
        "ko": "근거",
        "zh-CN": "来源",
        "es": "Fuente",
    },
    "col_status": {
        "ja": "ステータス",
        "en": "Status",
        "ko": "상태",
        "zh-CN": "状态",
        "es": "Estado",
    },
    "col_file": {
        "ja": "出現ファイル",
        "en": "Source File",
        "ko": "발견된 파일",
        "zh-CN": "来源文件",
        "es": "Archivo de Origen",
    },
    "grid_search_placeholder": {
        "ja": "🔍 原文・訳文・タイプ・ファイルで絞り込み...",
        "en": "🔍 Filter by Original, Translation, Type, File...",
        "ko": "🔍 원문・번역・타입・파일로 검색...",
        "zh-CN": "🔍 按原文、译文、类型、文件筛选...",
        "es": "🔍 Filtrar por original, traducción, tipo, archivo...",
    },
    "btn_clear": {
        "ja": "✕ クリア",
        "en": "✕ Clear",
        "ko": "✕ 지우기",
        "zh-CN": "✕ 清除",
        "es": "✕ Limpiar",
    },
    "filter_all": {
        "ja": "すべて表示",
        "en": "Show All",
        "ko": "전체 표시",
        "zh-CN": "全部显示",
        "es": "Mostrar Todo",
    },
    "btn_translate_dict": {
        "ja": "一括辞書翻訳を実行 (内蔵)",
        "en": "Run Batch Dictionary Translation",
        "ko": "일괄 사전 번역 실행 (내장)",
        "zh-CN": "执行批量词典翻译 (内建)",
        "es": "Ejecutar Traducción de Diccionario",
    },
    "btn_translate_gemini": {
        "ja": "一括AI翻訳を実行 (Gemini)",
        "en": "Run Batch AI Translation (Gemini)",
        "ko": "일괄 AI 번역 실행 (Gemini)",
        "zh-CN": "执行批量AI翻译 (Gemini)",
        "es": "Ejecutar Traducción AI (Gemini)",
    },
    "btn_translate_openai": {
        "ja": "一括AI翻訳を実行 (クラウド)",
        "en": "Run Batch AI Translation (Cloud API)",
        "ko": "일괄 AI 번역 실행 (클라우드 API)",
        "zh-CN": "执行批量AI翻译 (云端API)",
        "es": "Ejecutar Traducción AI (API Cloud)",
    },
    "btn_translate_ollama": {
        "ja": "一括AI翻訳を実行 (Ollama)",
        "en": "Run Batch AI Translation (Ollama)",
        "ko": "일괄 AI 번역 실행 (Ollama)",
        "zh-CN": "执行批量AI翻译 (Ollama)",
        "es": "Ejecutar Traducción AI (Ollama)",
    },
    "btn_stop": {
        "ja": "⏹️ 中断 (停止)",
        "en": "⏹️ Stop",
        "ko": "⏹️ 중지",
        "zh-CN": "⏹️ 停止",
        "es": "⏹️ Detener",
    },
    "btn_apply_local": {
        "ja": "✨ ローカルMOD適用 (Zomboid/mods)",
        "en": "✨ Apply Local MOD (Zomboid/mods)",
        "ko": "✨ 로컬 모드 적용 (Zomboid/mods)",
        "zh-CN": "✨ 应用本地MOD (Zomboid/mods)",
        "es": "✨ Aplicar MOD Local (Zomboid/mods)",
    },
    "btn_export_zip": {
        "ja": "配布用ZIPエクスポート",
        "en": "Export Release ZIP",
        "ko": "배포용 ZIP 내보내기",
        "zh-CN": "导出发布用 ZIP",
        "es": "Exportar ZIP de Distribución",
    },
    "status_ready": {
        "ja": "準備完了",
        "en": "Ready",
        "ko": "준비 완료",
        "zh-CN": "就绪",
        "es": "Listo",
    },
    "sec_lang_settings": {
        "ja": "言語設定 (Language Settings)",
        "en": "Language Settings",
        "ko": "언어 설정 (Language Settings)",
        "zh-CN": "语言设置 (Language Settings)",
        "es": "Ajustes de Idioma (Language Settings)",
    },
    "lbl_ui_lang": {
        "ja": "アプリ表示言語 (UI Language):",
        "en": "App Interface Language:",
        "ko": "앱 UI 표시 언어:",
        "zh-CN": "应用界面语言 (UI Language):",
        "es": "Idioma de la Interfaz (UI):",
    },
    "lbl_target_lang": {
        "ja": "MOD翻訳先言語 (Target Language):",
        "en": "Target MOD Language:",
        "ko": "모드 번역 대상 언어:",
        "zh-CN": "MOD 目标翻译语言:",
        "es": "Idioma de Destino del MOD:",
    },
    "note_target_lang": {
        "ja": "※ 翻訳先言語を変更すると、ゲーム本体から対応する公式対訳辞書が自動ロードされます。",
        "en": "* Changing target language will automatically load official vanilla dictionary from the game.",
        "ko": "* 번역 대상 언어를 변경하면 게임 본체의 공식 대역 사전이 자동으로 로드됩니다.",
        "zh-CN": "* 更改目标语言将自动从游戏本体加载对应的官方对照词典。",
        "es": "* Cambiar el idioma de destino cargará automáticamente el diccionario oficial del juego.",
    },
    "sec_engine_settings": {
        "ja": "翻訳エンジンを選択してください",
        "en": "Select Translation Engine",
        "ko": "번역 엔진을 선택하세요",
        "zh-CN": "请选择翻译引擎",
        "es": "Selecciona el Motor de Traducción",
    },
    "rb_smart_dict": {
        "ja": "内蔵スマート辞書 (完全オフライン / 超高速)",
        "en": "Built-in Smart Dictionary (Fully Offline / Instant)",
        "ko": "내장 스마트 사전 (완전 오프라인 / 초고속)",
        "zh-CN": "内建智能词典 (完全离线 / 超高速)",
        "es": "Diccionario Inteligente Integrado (Sin Conexión / Instantáneo)",
    },
    "desc_smart_dict": {
        "ja": "公式バニラ対訳 35,000語＋定型ルール。GPU・APIキー不要で即動作。",
        "en": "Official vanilla pairs + specialized UI rules. Zero GPU or API key required.",
        "ko": "공식 바닐라 대역 35,000단어 + 정형 규칙. GPU나 API 키 없이 즉시 작동.",
        "zh-CN": "官方原版对照词典 + 专门UI规则。无需 GPU 或 API 密钥即可即刻运行。",
        "es": "Pares oficiales del juego + reglas UI. No requiere GPU ni claves API.",
    },
    "rb_ollama": {
        "ja": "Ollama ローカルLLM (完全プライベート / GPU推奨)",
        "en": "Ollama Local LLM (Fully Private / GPU Recommended)",
        "ko": "Ollama 로컬 LLM (완전한 비공개 / GPU 권장)",
        "zh-CN": "Ollama 本地LLM (完全私密 / 推荐GPU)",
        "es": "Ollama LLM Local (Privado / GPU Recomendada)",
    },
    "rb_cloud_api": {
        "ja": "クラウド AI API (GPU不要 / 最高品質 / 超高速)",
        "en": "Cloud AI API (No GPU Needed / Highest Quality / Fast)",
        "ko": "클라우드 AI API (GPU 불필요 / 최고 품질 / 초고속)",
        "zh-CN": "云端 AI API (无需GPU / 最高质量 / 极速)",
        "es": "API de IA en la Nube (Sin GPU / Máxima Calidad / Rápido)",
    },
    "btn_save_settings": {
        "ja": "💾 設定を保存",
        "en": "💾 Save Settings",
        "ko": "💾 설정 저장",
        "zh-CN": "💾 保存设置",
        "es": "💾 Guardar Ajustes",
    },
    "btn_cancel": {
        "ja": "キャンセル",
        "en": "Cancel",
        "ko": "취소",
        "zh-CN": "取消",
        "es": "Cancelar",
    },
    "msg_settings_saved": {
        "ja": "翻訳設定を保存しました！",
        "en": "Translation settings saved successfully!",
        "ko": "번역 설정이 저장되었습니다!",
        "zh-CN": "翻译设置已保存！",
        "es": "¡Ajustes de traducción guardados con éxito!",
    },
    "msg_apply_success": {
        "ja": "翻訳パッチMODをローカルに適用しました！",
        "en": "Translation patch MOD applied locally!",
        "ko": "번역 패치 모드가 로컬에 적용되었습니다!",
        "zh-CN": "翻译补丁MOD已成功应用到本地！",
        "es": "¡Parche de traducción aplicado localmente!",
    },
    "msg_export_success": {
        "ja": "配布用ZIPを作成しました！",
        "en": "Release ZIP created successfully!",
        "ko": "배포용 ZIP이 성공적으로 생성되었습니다!",
        "zh-CN": "发布用 ZIP 已成功创建！",
        "es": "¡ZIP de distribución creado con éxito!",
    },
    "msg_no_mod_selected": {
        "ja": "MODを選択してください。",
        "en": "Please select a MOD first.",
        "ko": "먼저 모드를 선택하세요.",
        "zh-CN": "请先选择一个 MOD。",
        "es": "Por favor, selecciona un MOD primero.",
    },
    "msg_no_trans_items": {
        "ja": "適用できる訳文がありません。先に翻訳を実行してください。",
        "en": "No translated items available. Please run translation first.",
        "ko": "적용할 수 있는 번역 내용이 없습니다. 먼저 번역을 실행하세요.",
        "zh-CN": "没有可应用的译文。请先执行翻译。",
        "es": "No hay elementos traducidos. Por favor ejecuta la traducción primero.",
    },
    "quickstart_title": {
        "ja": "🚀 かんたん初期セットアップ",
        "en": "🚀 Quick Start Setup",
        "ko": "🚀 빠른 초기 설정",
        "zh-CN": "🚀 快速初始设置",
        "es": "🚀 Configuración Rápida",
    },
    "quickstart_sub": {
        "ja": "MODの翻訳方法を選んでください。選択するとすぐに翻訳できます。",
        "en": "Choose your translation method. Ready to translate immediately.",
        "ko": "번역 방식을 선택하세요. 선택 후 바로 번역할 수 있습니다.",
        "zh-CN": "请选择翻译方式。选择后即可立即翻译。",
        "es": "Elige tu método de traducción. Listo para traducir de inmediato.",
    },
    "btn_quickstart": {
        "ja": "🚀 かんたん設定",
        "en": "🚀 Quick Setup",
        "ko": "🚀 빠른 설정",
        "zh-CN": "🚀 快速设置",
        "es": "🚀 Config. Rápida",
    },
}

_CURRENT_LANG = "ja"


def set_ui_language(lang_code: str):
    global _CURRENT_LANG
    if lang_code in SUPPORTED_UI_LANGUAGES:
        _CURRENT_LANG = lang_code


def get_ui_language() -> str:
    return _CURRENT_LANG


def t(key: str, **kwargs) -> str:
    """翻訳キーから現在のUI言語の文言を取得"""
    entry = STRINGS.get(key, {})
    text = entry.get(_CURRENT_LANG) or entry.get("ja") or entry.get("en") or key
    if kwargs:
        try:
            text = text.format(**kwargs)
        except Exception:
            pass
    return text
