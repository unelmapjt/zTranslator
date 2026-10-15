"""
zTranzlator - Vanilla Master Dictionary Builder (Phase 1)
Project Zomboid Build 42 の公式英語(EN)と日本語(JP)を突合し、
高精度なマスター対訳辞書 (vanilla_dict.json) を自動生成するスクリプト。
"""

import json
import os
import sys
from pathlib import Path
from collections import defaultdict


DEFAULT_PZ_PATHS = [
    Path(r"C:\Program Files (x86)\Steam\steamapps\common\ProjectZomboid"),
    Path(r"C:\Program Files\Steam\steamapps\common\ProjectZomboid"),
    Path(r"D:\SteamLibrary\steamapps\common\ProjectZomboid"),
    Path(r"E:\SteamLibrary\steamapps\common\ProjectZomboid"),
]


def find_pz_directory() -> Path:
    """Project Zomboidのインストール先を特定する"""
    for p in DEFAULT_PZ_PATHS:
        if (p / "media" / "lua" / "shared" / "Translate").is_dir():
            return p
    return None


def clean_text(text: str) -> str:
    """前後の空白や特殊エスケープを正規化"""
    if not isinstance(text, str):
        return ""
    return text.strip()


def build_master_dictionary(pz_dir: Path, output_dir: Path, target_lang: str = "JP") -> Path:
    translate_dir = pz_dir / "media" / "lua" / "shared" / "Translate"
    en_dir = translate_dir / "EN"
    target_dir = translate_dir / target_lang

    if not en_dir.is_dir() or not target_dir.is_dir():
        print(f"[Error] Translateフォルダが見つかりません: {target_dir}")
        return None

    print(f"[1/4] PZ本体ディレクトリを確認: {pz_dir}")
    print(f"      ENフォルダ: {en_dir}")
    print(f"      {target_lang}フォルダ: {target_dir}")

    en_files = sorted(list(en_dir.glob("*.json")))
    print(f"[2/4] スキャン対象のJSONファイル数: {len(en_files)} 件")

    exact_dict = {}
    detailed_dict = defaultdict(lambda: {"translations": set(), "categories": set(), "keys": []})
    
    total_pairs = 0
    file_stats = {}

    for en_file in en_files:
        target_file = target_dir / en_file.name
        if not target_file.is_file():
            continue

        category = en_file.stem
        try:
            with open(en_file, "r", encoding="utf-8") as f:
                en_data = json.load(f)
            with open(target_file, "r", encoding="utf-8") as f:
                target_data = json.load(f)
        except Exception as e:
            print(f"  [Skip] パース失敗: {en_file.name} ({e})")
            continue

        matched_count = 0
        for key, en_val in en_data.items():
            if key not in target_data:
                continue

            target_val = target_data[key]
            en_str = clean_text(en_val)
            trans_str = clean_text(target_val)

            if not en_str or not trans_str:
                continue

            # 英語原文と訳文を記録
            detailed_dict[en_str]["translations"].add(trans_str)
            detailed_dict[en_str]["categories"].add(category)
            detailed_dict[en_str]["keys"].append(key)

            # exact_dict に登録（未登録なら採用）
            if en_str not in exact_dict:
                exact_dict[en_str] = trans_str

            matched_count += 1
            total_pairs += 1

        file_stats[category] = matched_count

    print(f"[3/4] 突合完了! 総キーペア数: {total_pairs} 件")
    print(f"      ユニーク英語フレーズ数: {len(detailed_dict)} 語")

    # 同音異義語（複数の訳が存在する単語）の集計
    homonyms = {}
    for en_str, data in detailed_dict.items():
        if len(data["translations"]) > 1:
            homonyms[en_str] = {
                "translations": list(data["translations"]),
                "categories": list(data["categories"]),
            }

    print(f"      同音異義語（文脈で訳が分かれる単語）: {len(homonyms)} 語")

    # JSON出力用に整形
    output_dir.mkdir(parents=True, exist_ok=True)

    # vanilla_dict_{target_lang}.json (高速引き用シンプル辞書)
    simple_dict_path = output_dir / f"vanilla_dict_{target_lang}.json"
    with open(simple_dict_path, "w", encoding="utf-8") as f:
        json.dump(exact_dict, f, ensure_ascii=False, indent=2)
    
    if target_lang == "JP":
        # 互換用 vanilla_dict.json
        with open(output_dir / "vanilla_dict.json", "w", encoding="utf-8") as f:
            json.dump(exact_dict, f, ensure_ascii=False, indent=2)

    print(f"[4/4] 保存完了:")
    print(f"      -> {simple_dict_path} ({simple_dict_path.stat().st_size // 1024} KB)")

    # 2. vanilla_dict_meta.json (文脈・カテゴリ情報付き詳細辞書)
    detailed_serializable = {}
    for en_str, data in detailed_dict.items():
        detailed_serializable[en_str] = {
            "default": exact_dict[en_str],
            "translations": list(data["translations"]),
            "categories": list(data["categories"]),
            "sample_keys": data["keys"][:3]
        }

    meta_dict_path = output_dir / "vanilla_dict_meta.json"
    with open(meta_dict_path, "w", encoding="utf-8") as f:
        json.dump({
            "version": "B42",
            "unique_terms": len(detailed_dict),
            "homonyms_count": len(homonyms),
            "terms": detailed_serializable,
            "homonyms": homonyms,
        }, f, ensure_ascii=False, indent=2)
    print(f"      -> {meta_dict_path} ({meta_dict_path.stat().st_size // 1024} KB)")

    # プレビュー表示
    print("\n--- 辞書サンプル (一部抜粋) ---")
    samples = [
        "Axe", "Can Opener", "M16 Magazine", "OPTIONS", "QUIT", 
        "First person", "Third person", "Aim", "Walk To"
    ]
    for s in samples:
        if s in exact_dict:
            print(f"  [〇] '{s}' ➡ '{exact_dict[s]}'")
        else:
            print(f"  [✕] '{s}' ➡ (バニラ辞書に未登録 / MOD独自用語)")

    return simple_dict_path


if __name__ == "__main__":
    target_pz = find_pz_directory()
    if len(sys.argv) > 1:
        target_pz = Path(sys.argv[1])

    if not target_pz or not target_pz.is_dir():
        print("[Error] Project Zomboidのインストールディレクトリが見つかりませんでした。")
        print("Usage: python dict_builder.py \"C:\\Path\\To\\ProjectZomboid\"")
        sys.exit(1)

    out_path = Path(__file__).parent
    build_master_dictionary(target_pz, out_path)
