"""
zTranzlator - MOD Static Text Scanner & Dictionary Matcher (Phase 3)
Type A/B/C の静的抽出、バニラ公式辞書突合、および
差分更新 (Incremental Update: 過去パッチの訳文自動継承・アーカイブ) に完全対応。
"""

import json
import re
import sys
from pathlib import Path
from typing import Dict, List, Optional, Any, Tuple


def robust_json_load(text_or_stream) -> dict:
    """末尾カンマやコメントを含む緩いJSONも確実にパースする"""
    if hasattr(text_or_stream, 'read'):
        text = text_or_stream.read()
    else:
        text = str(text_or_stream)
    text = re.sub(r'//.*', '', text)
    text = re.sub(r',\s*([}\]])', r'\1', text)
    return json.loads(text)


def load_vanilla_dict(dict_path: Path) -> dict:
    if not dict_path.is_file():
        print(f"[Error] 辞書ファイルが見つかりません: {dict_path}")
        return {}
    try:
        with open(dict_path, "r", encoding="utf-8") as f:
            return robust_json_load(f)
    except Exception as e:
        print(f"[Error] バニラ辞書ロード失敗: {e}")
        return {}


def is_meaningful_translation(en: str, jp: str) -> bool:
    """有効な日本語訳かどうかを判定 (英語のままのダミーエントリーや空文字を除外)"""
    if not jp or not str(jp).strip():
        return False
    # 原文と完全に一致している場合
    if str(en).strip() == str(jp).strip():
        # 日本語（ひらがな、カタカナ、漢字）が含まれていなければ未翻訳とみなす
        if not re.search(r'[\u3040-\u309F\u30A0-\u30FF\u4E00-\u9FFF]', str(jp)):
            return False
    return True


def find_workshop_translation_mods(workshop_dir: Optional[Path], target_mod_id: str, target_mod_name: str, target_lang: str = "JP") -> List[Path]:
    """ワークショップディレクトリから対象MOD用の翻訳MODを探索"""
    if not workshop_dir or not workshop_dir.is_dir():
        return []

    lang_keywords_map = {
        "JP": ("japanese", "jp", "日本語", "翻訳"),
        "KO": ("korean", "ko", "한국어", "한글", "번역"),
        "CN": ("chinese", "cn", "中文", "汉化"),
        "CH": ("chinese", "ch", "繁體", "漢化"),
        "ES": ("spanish", "es", "español", "traduccion", "traducción"),
        "RU": ("russian", "ru", "русский", "перевод"),
        "FR": ("french", "fr", "français", "traduction"),
        "DE": ("german", "de", "deutsch", "übersetzung"),
    }
    keywords = lang_keywords_map.get(target_lang, (target_lang.lower(), f"_{target_lang.lower()}"))

    matching_dirs = []
    # ワークショップ内のすべてのMODフォルダを探索
    for item in workshop_dir.iterdir():
        if not item.is_dir():
            continue
        # 直下または mods/* 配下
        candidate_subdirs = list(item.glob("mods/*"))
        if not candidate_subdirs:
            candidate_subdirs = [item]

        for m_dir in candidate_subdirs:
            if not m_dir.is_dir():
                continue
            # mod.info を確認 (ルートまたはバージョン配下)
            infos = list(m_dir.glob("mod.info")) + list(m_dir.glob("*/mod.info"))
            for info_file in infos:
                try:
                    with open(info_file, 'r', encoding='utf-8', errors='ignore') as f:
                        content = f.read()
                    req = ""
                    name = ""
                    mid = ""
                    for line in content.splitlines():
                        if line.startswith("require="):
                            req = line.split("=", 1)[1].strip()
                        elif line.startswith("name="):
                            name = line.split("=", 1)[1].strip()
                        elif line.startswith("id="):
                            mid = line.split("=", 1)[1].strip()

                    req_list = [r.strip().lower() for r in req.split(",")]
                    # 判定1: requireに対象MOD_IDが含まれる
                    if target_mod_id.lower() in req_list:
                        matching_dirs.append(m_dir)
                        break
                    # 判定2: 翻訳MOD名に対象MOD名またはIDが含まれる
                    if any(w in name.lower() for w in keywords):
                        if (target_mod_id.lower() in name.lower() or 
                            target_mod_name.lower() in name.lower() or 
                            target_mod_id.lower() in mid.lower()):
                            matching_dirs.append(m_dir)
                            break
                except Exception:
                    pass
    return matching_dirs


def load_translation_sources(
    mod_id: str,
    mod_name: str,
    existing_patch_dir: Optional[Path] = None,
    workshop_dir: Optional[Path] = None,
    target_lang: str = "JP"
) -> Tuple[Dict[str, str], Dict[str, str]]:
    """
    ユーザー既存パッチおよびワークショップ内の既存翻訳MODから、
    key_dict (キー -> 訳文) と text_dict (英語原文 -> 訳文) を収集する。
    """
    key_dict = {}
    text_dict = {}

    def _collect_from_dir(target_dir: Path, source_label: str):
        # 1. zTranz_Dict_*.json
        for dict_json in target_dir.glob("**/zTranz_Dict_*.json"):
            try:
                with open(dict_json, "r", encoding="utf-8-sig", errors="ignore") as f:
                    data = robust_json_load(f)
                    if isinstance(data, dict):
                        for k, v in data.items():
                            if is_meaningful_translation(k, v):
                                text_dict[k] = v
                                key_dict[k] = v
            except Exception as e:
                print(f"  [Warn] {source_label} JSONパース失敗: {dict_json.name} ({e})")

        # 2. Translate/<target_lang>/*.json
        search_dirs = [f"**/Translate/{target_lang}/*.json"]
        if target_lang == "JP":
            search_dirs.append("**/Translate/JA/*.json")
        for tr_json in [f for p in search_dirs for f in target_dir.glob(p)]:
            try:
                with open(tr_json, "r", encoding="utf-8-sig", errors="ignore") as f:
                    data = robust_json_load(f)
                    if isinstance(data, dict):
                        for k, v in data.items():
                            if is_meaningful_translation(k, v):
                                key_dict[k] = v
                                text_dict[k] = v
            except Exception as e:
                print(f"  [Warn] {source_label} JSONパース失敗: {tr_json.name} ({e})")

        # 3. Translate/EN と Translate/<target_lang> のキー対訳マッピング
        en_files = list(target_dir.glob("**/Translate/EN/*.json"))
        for en_file in en_files:
            tr_file = en_file.parent.parent / target_lang / en_file.name
            if not tr_file.is_file() and target_lang == "JP":
                tr_file = en_file.parent.parent / "JA" / en_file.name
            if tr_file.is_file():
                try:
                    with open(en_file, "r", encoding="utf-8-sig", errors="ignore") as f_en:
                        d_en = robust_json_load(f_en)
                    with open(tr_file, "r", encoding="utf-8-sig", errors="ignore") as f_tr:
                        d_tr = robust_json_load(f_tr)
                    for k, en_text in d_en.items():
                        if k in d_tr and is_meaningful_translation(en_text, d_tr[k]):
                            text_dict[en_text.strip()] = d_tr[k].strip()
                except Exception:
                    pass

    # 1. ユーザー作成パッチ
    if existing_patch_dir and existing_patch_dir.is_dir():
        _collect_from_dir(existing_patch_dir, "既存パッチ")

    # 2. ワークショップ既存翻訳MOD (公式・有志MOD)
    if workshop_dir and workshop_dir.is_dir():
        ws_mods = find_workshop_translation_mods(workshop_dir, mod_id, mod_name, target_lang=target_lang)
        for m_dir in ws_mods:
            print(f"      [ライブラリ連携] ワークショップ既存翻訳MODを活用: {m_dir.name}")
            _collect_from_dir(m_dir, "ワークショップMOD")

    return key_dict, text_dict


# UIテキストとして抽出する正規表現パターン (ホワイトリスト方式)
PATTERNS = [
    re.compile(r'setTitle\s*\(\s*["\']([^"\']+)["\']\s*\)'),
    re.compile(r'addTickBox\s*\([^,]+,\s*["\']([^"\']+)["\'](?:,[^,]+,\s*["\']([^"\']+)["\'])?'),
    re.compile(r'addTitle\s*\(\s*["\']([^"\']+)["\']\s*\)'),
    re.compile(r'addAction\s*\([^,]+,[^,]+,\s*["\']([^"\']+)["\']'),
    re.compile(r'addOption\s*\(\s*["\']([^"\']+)["\']\s*\)'),
    re.compile(r'addCombo\s*\([^,]+,[^,]+,[^,]+,[^,]+,[^,]+,\s*["\']([^"\']+)["\']'),
    re.compile(r'drawTextCentre\s*\(\s*["\']([^"\']+)["\']'),
    re.compile(r'["\']?(?:name|title|label|tooltip|desc|description)["\']?\s*=\s*["\']([^"\']+)["\']', re.IGNORECASE),
    re.compile(r'text\s*=\s*["\']([^"\']+)["\']'),
]

EXCLUDE_EXTS = {".png", ".jpg", ".txt", ".lua", ".ogg", ".wav", ".csv"}


def is_valid_ui_text(text: str) -> bool:
    text = text.strip()
    if not text or len(text) < 2:
        return False
    for ext in EXCLUDE_EXTS:
        if ext in text.lower():
            return False
    if text.islower() and " " not in text:
        return False
    if text.startswith("UI_") or text.startswith("ContextMenu_") or text.startswith("IGUI_") or text.startswith("Base."):
        return False
    # プログラム識別子・内部変数の除外 (末尾アンダースコア、空白なしアンダースコア)
    if text.endswith("_") or ("_" in text and " " not in text):
        return False
    # 内部クラス/スクリプト名 (例: SceneCommentary, BasicGuard) の除外
    for code_suffix in ("Card", "Female", "Guard", "State", "Handler", "Custom", "Commentary", "Compatibility"):
        if text.endswith(code_suffix) and " " not in text:
            return False
    return True


def clean_leading_bytecode(s: str) -> str:
    """バイトコード長ヘッダー等のゴミ文字やクォートを取り除く"""
    s = s.strip(' \t\r\n"\'`<>!*#%&+=')
    if len(s) >= 4 and s[0].isdigit() and s[1].isupper():
        s = s[1:]
    if len(s) >= 4 and s[0].isalpha() and s[1].isupper() and ' ' in s:
        # 例: HWhile the view is on... -> While the view is on...
        s = s[1:]
    return s.strip(' \t\r\n"\'`<>!*#%&+=')


def is_clean_ui_text(s: str) -> bool:
    """人間向けの英語UI文（説明文、ラベル、グループ名）か高精度判定"""
    s = clean_leading_bytecode(s)
    if len(s) < 3 or len(s) > 300:
        return False
    # 内部キー・クラス名・デバッグ除外
    if s.startswith(('keys.', 'pad.', 'zombie/', 'java/', 'viewpoint/', 'imgui/', 'me/', '[Viewpoint]', 'org/')):
        return False
    if any(s.startswith(p) for p in ['when ', 'every frame', 'while aiming a firearm']):
        return False
    if any(c in s for c in [';', '$', '\\']):
        return False
    # 定数名 (ALL_CAPS)
    if s.isupper() and ('_' in s or len(s) < 15):
        return False
    # キャメルケースのメソッド名
    if re.match(r'^[a-z]+[A-Z]', s) and ' ' not in s:
        return False
    # 1単語で小文字のみ
    if s.islower() and ' ' not in s:
        return False
    letters = sum(1 for c in s if c.isalpha())
    if letters / len(s) < 0.5:
        return False
    if '+' in s and ('SHIFT' in s or 'CTRL' in s):
        return False
    # UI文として適切か
    if '/' in s: # グループ名 (Controls/Camera, Keys/Views 等)
        return True
    if ' ' in s: # スペースを含む文・フレーズ
        return True
    if s in ['Screenshot', 'Viewpoint', 'Controller', 'Default', 'Clear', 'Cancel', 'Toggle', 'Views', 'Camera', 'Options', 'World', 'Controls', 'Keys', 'Debug']:
        return True
    return False


def extract_from_jar(jar_path: Path) -> dict:
    """JARファイル内のUI設定クラスから人間向けUTF-8文字列定数を抽出"""
    import zipfile
    extracted = {}
    # Viewpointおよび一般的なMODのUIクラス対象
    ui_name_patterns = [
        'keys.class', 'settingswindow.class', 'padslua.class', 'keyslua.class',
        'framecapslua.class', 'lootlua.class', 'options.class', 'ui.class',
        'menu.class', 'settings.class', 'config.class'
    ]
    try:
        with zipfile.ZipFile(jar_path, 'r') as z:
            for filename in z.namelist():
                if not filename.endswith(".class") or not filename.startswith("viewpoint/"):
                    continue
                lower_f = filename.lower()
                # UIクラスまたはUIパッケージに限定
                is_ui_class = any(p in lower_f for p in ui_name_patterns) or ('/ui/' in lower_f) or ('/options/' in lower_f)
                if not is_ui_class:
                    continue

                data = z.read(filename)
                raw_strings = re.findall(b'[\x20-\x7E]{3,}', data)
                for b_str in raw_strings:
                    try:
                        s = b_str.decode('utf-8', errors='ignore').strip()
                    except Exception:
                        continue
                    if is_clean_ui_text(s):
                        clean_s = clean_leading_bytecode(s)
                        if len(clean_s) >= 4 and not clean_s.startswith(('java/', '[Viewpoint]', 'org/')):
                            if clean_s not in extracted:
                                extracted[clean_s] = []
                            extracted[clean_s].append(f"{jar_path.name}:{Path(filename).name}")
    except Exception as e:
        print(f"  [Warn] JARスキャン失敗: {jar_path.name} ({e})")
    return extracted


def scan_mod(
    mod_dir: Path,
    vanilla_dict: dict,
    existing_patch_dir: Optional[Path] = None,
    workshop_dir: Optional[Path] = None,
    mod_id: str = "",
    mod_name: str = "",
    target_lang: str = "JP"
) -> dict:
    # Build 42 MOD構造対応 (mod.info がある common/ または 42/ が渡された場合は親MODルートに解決)
    if mod_dir.name.lower() in ("common", "42"):
        mod_dir = mod_dir.parent

    # mod_id, mod_name の自動補完
    if not mod_id or not mod_name:
        for info_f in list(mod_dir.glob("mod.info")) + list(mod_dir.glob("*/mod.info")):
            try:
                with open(info_f, "r", encoding="utf-8", errors="ignore") as f:
                    for line in f:
                        if not mod_id and line.startswith("id="):
                            mod_id = line.split("=", 1)[1].strip()
                        elif not mod_name and line.startswith("name="):
                            mod_name = line.split("=", 1)[1].strip()
            except Exception:
                pass
        if not mod_id:
            mod_id = mod_dir.name
        if not mod_name:
            mod_name = mod_dir.name

    print(f"\n[スキャン] MODフォルダを解析中: {mod_dir.name} ({mod_id}) [対象言語: {target_lang}]")

    # 差分更新 & ワークショップ翻訳ライブラリから辞書を収集
    key_dict, text_dict = load_translation_sources(
        mod_id=mod_id,
        mod_name=mod_name,
        existing_patch_dir=existing_patch_dir,
        workshop_dir=workshop_dir,
        target_lang=target_lang
    )
    if key_dict or text_dict:
        print(f"      [ライブラリ照合] キー辞書: {len(key_dict)} 項目, 原文辞書: {len(text_dict)} 項目を活用可能")

    # 探索対象
    translate_en_files = list(mod_dir.glob("**/Translate/EN/*.json")) + list(mod_dir.glob("**/Translate/EN/*_EN.txt"))
    print_media_files = list(mod_dir.glob("**/printMedia/txt/*.txt"))
    lua_files = list(mod_dir.glob("**/*.lua"))
    jar_files = list(mod_dir.glob("**/*.jar"))

    print(f"      検出: Translate(EN) {len(translate_en_files)} 件, printMedia {len(print_media_files)} 件, Lua {len(lua_files)} 件, JAR {len(jar_files)} 件")

    mod_type = "type_c"
    if translate_en_files:
        mod_type = "type_a"
    elif print_media_files:
        mod_type = "type_b"

    extracted_strings = {}

    # 1. タイプA: Translate/EN/ のスキャン
    for t_file in translate_en_files:
        rel_path = t_file.relative_to(mod_dir)
        try:
            if t_file.suffix.lower() == ".json":
                with open(t_file, "r", encoding="utf-8", errors="ignore") as f:
                    data = robust_json_load(f)
                for k, v in data.items():
                    if isinstance(v, str) and v.strip():
                        text = v.strip()
                        if text not in extracted_strings:
                            extracted_strings[text] = {
                                "key": k,
                                "keys": set(),
                                "sources": [],
                                "file_type": "json",
                                "rel_path": str(rel_path)
                            }
                        extracted_strings[text]["keys"].add(k)
                        extracted_strings[text]["sources"].append(str(rel_path))
            else:
                # レガシーTXT
                with open(t_file, "r", encoding="utf-8", errors="ignore") as f:
                    for line in f:
                        line = line.strip()
                        if "=" in line and not line.startswith("--"):
                            k, v = line.split("=", 1)
                            v = v.strip().strip('",')
                            if v:
                                if v not in extracted_strings:
                                    extracted_strings[v] = {
                                        "key": k.strip(),
                                        "keys": set(),
                                        "sources": [],
                                        "file_type": "txt",
                                        "rel_path": str(rel_path)
                                    }
                                extracted_strings[v]["keys"].add(k.strip())
                                extracted_strings[v]["sources"].append(str(rel_path))
        except Exception as e:
            print(f"  [Warn] Translateパース失敗: {t_file.name} ({e})")

    # 2. タイプB: printMedia/txt/*.txt のスキャン
    for p_file in print_media_files:
        rel_path = p_file.relative_to(mod_dir)
        try:
            with open(p_file, "r", encoding="utf-8", errors="ignore") as f:
                content = f.read().strip()
            if content and len(content) > 5:
                if content not in extracted_strings:
                    extracted_strings[content] = {"key": p_file.stem, "keys": {p_file.stem}, "sources": [], "file_type": "printMedia", "rel_path": str(rel_path)}
                extracted_strings[content]["sources"].append(str(rel_path))
        except Exception:
            pass

    # 3. タイプC: Luaスクリプトのスキャン
    for file_path in lua_files:
        rel_path = file_path.relative_to(mod_dir)
        try:
            with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
                content = f.read()
        except Exception:
            continue

        for pat in PATTERNS:
            for match in pat.finditer(content):
                for group in match.groups():
                    if group and is_valid_ui_text(group):
                        text = group.strip()
                        if text not in extracted_strings:
                            extracted_strings[text] = {"key": "", "keys": set(), "sources": [], "file_type": "lua", "rel_path": str(rel_path)}
                        extracted_strings[text]["sources"].append(str(rel_path))

    # 4. タイプC: JARファイルのスキャン
    for jar_path in jar_files:
        jar_strings = extract_from_jar(jar_path)
        for text, sources in jar_strings.items():
            if text not in extracted_strings:
                extracted_strings[text] = {"key": "", "keys": set(), "sources": [], "file_type": "jar", "rel_path": str(jar_path.name)}
            extracted_strings[text]["sources"].extend(sources)

    matched = []
    unmatched = []
    inherited = []
    deprecated = []

    # ルールベース翻訳エンジンの読み込み (循環参照防止)
    from translator_engine import RuleBasedTranslator

    # 突合処理 (優先順位: 1. キー完全一致 > 2. 原文ライブラリ一致 > 3. バニラ公式辞書 > 4. ルールベース > 5. 未翻訳)
    for text, info in sorted(extracted_strings.items()):
        file_hint = Path(info["sources"][0]).name if info["sources"] else ""
        item_key = info.get("key", "")
        keys_list = sorted(list(info.get("keys", set())))
        if not keys_list and item_key:
            keys_list = [item_key]
        entry = {
            "en": text,
            "key": item_key,
            "keys": keys_list,
            "file_type": info.get("file_type", ""),
            "rel_path": info.get("rel_path", ""),
            "file": file_hint,
        }

        # 1. キー完全一致 (最優先: ワークショップ公式・既存パッチ)
        if item_key and item_key in key_dict and is_meaningful_translation(text, key_dict[item_key]):
            entry["jp"] = key_dict[item_key]
            entry["status"] = "公式一致"
            inherited.append(entry)

        # 2. 原文テキスト完全一致 (既存パッチ・ライブラリ)
        elif text in text_dict and is_meaningful_translation(text, text_dict[text]):
            entry["jp"] = text_dict[text]
            entry["status"] = "既存継承"
            inherited.append(entry)

        # 3. バニラ公式辞書一致
        elif text in vanilla_dict and is_meaningful_translation(text, vanilla_dict[text]):
            entry["jp"] = vanilla_dict[text]
            entry["status"] = "公式一致"
            matched.append(entry)

        # 4. ルールベース翻訳 (日本語対象時のみ: 複合単語、叫び声、定型UI)
        else:
            rule_jp = RuleBasedTranslator.translate(text, vanilla_dict=vanilla_dict) if target_lang == "JP" else None
            if rule_jp and is_meaningful_translation(text, rule_jp):
                entry["jp"] = rule_jp
                entry["status"] = "公式一致"
                matched.append(entry)
            else:
                entry["jp"] = ""
                entry["status"] = "未翻訳"
                unmatched.append(entry)

    # 過去パッチにあったが今回削除された旧キー（非破壊アーカイブ）
    for old_k, old_v in text_dict.items():
        if old_k not in extracted_strings and not any(e["key"] == old_k for e in inherited):
            deprecated.append({
                "en": old_k,
                "jp": old_v,
                "key": old_k,
                "file_type": "deprecated",
                "rel_path": "",
                "file": "旧パッチ",
                "status": "廃止キー (温存)"
            })

    result_data = {
        "mod_dir": str(mod_dir),
        "mod_type": mod_type,
        "total_extracted": len(extracted_strings),
        "inherited_count": len(inherited),
        "matched_count": len(matched),
        "unmatched_count": len(unmatched),
        "deprecated_count": len(deprecated),
        "inherited": inherited,
        "matched": matched,
        "unmatched": unmatched,
        "deprecated": deprecated,
    }
    return result_data


if __name__ == "__main__":
    dict_file = Path(__file__).parent / "vanilla_dict.json"
    v_dict = load_vanilla_dict(dict_file)
    if len(sys.argv) > 1:
        target = Path(sys.argv[1])
        res = scan_mod(target, v_dict)
        print(f"完了: 継承 {res['inherited_count']} 件, 一致 {res['matched_count']} 件, 未翻訳 {res['unmatched_count']} 件")
    else:
        print("Usage: python mod_scanner.py <path_to_mod_folder>")
