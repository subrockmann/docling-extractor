#!/usr/bin/env python3
"""
Batch-Extraktion mit Docling.

Eingabe:
  data/input/<dokument>

Pro Dokument werden die Quelldatei und alle Exporte in diesen Ordner verschoben/geschrieben:
  data/processed/<basename>/

Beispiel:
  data/input/rechnung.pdf
  -> data/processed/rechnung/rechnung.pdf
  -> data/processed/rechnung/rechnung.md
  -> data/processed/rechnung/rechnung.doclang
  -> data/processed/rechnung/rechnung_table_1.csv

Verwendung:
  uv run python docling_app.py

Abhängigkeiten:
  uv add docling pandas
"""

import json
import shutil
import sys
from pathlib import Path

import pandas as pd
from docling.document_converter import DocumentConverter

INPUT_DIR = Path("data/input")
PROCESSED_DIR = Path("data/processed")

# Konservativ halten; bei Bedarf um weitere von deiner Docling-Version unterstützte Formate ergänzen.
SUPPORTED_EXTENSIONS = {".pdf", ".docx", ".pptx", ".xlsx", ".html", ".htm", ".md", ".txt"}


def tables_to_dataframes(doc):
    """Liefert Docling-Tabellen als (Index, pandas.DataFrame)."""
    dataframes = []

    for index, table_item in enumerate(doc.tables, start=1):
        try:
            df = table_item.export_to_dataframe(doc=doc)
        except AttributeError:
            # Fallback für ältere/abweichende Docling-Versionen
            table_data = table_item.data
            df = table_data.export_to_dataframe(doc=doc)

        df = df.dropna(axis=0, how="all").dropna(axis=1, how="all")
        if not df.empty:
            dataframes.append((index, df))

    return dataframes


def unique_target_dir(base_name: str) -> Path:
    """Erzeugt einen kollisionsfreien Zielordner unter data/processed."""
    target = PROCESSED_DIR / base_name
    if not target.exists():
        return target

    suffix = 2
    while True:
        candidate = PROCESSED_DIR / f"{base_name}_{suffix}"
        if not candidate.exists():
            return candidate
        suffix += 1


def process_document(source_path: Path, converter: DocumentConverter) -> None:
    base_name = source_path.stem
    target_dir = unique_target_dir(base_name)
    target_dir.mkdir(parents=True, exist_ok=False)

    try:
        print(f"Verarbeite: {source_path.name}")
        result = converter.convert(str(source_path))

        # Exporte werden zuerst ins Zielverzeichnis geschrieben.
        md_path = target_dir / f"{base_name}.md"
        md_path.write_text(result.document.export_to_markdown(), encoding="utf-8")

        doclang_path = target_dir / f"{base_name}.doclang"
        doclang_path.write_text(
            json.dumps(result.document.export_to_dict(), ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

        for index, df in tables_to_dataframes(result.document):
            csv_path = target_dir / f"{base_name}_table_{index}.csv"
            df.to_csv(csv_path, index=False, sep=";", decimal=",", encoding="utf-8-sig")

        # Quelldatei erst nach erfolgreicher Extraktion verschieben.
        destination_file = target_dir / source_path.name
        shutil.move(str(source_path), str(destination_file))

        print(f"Fertig: {target_dir}")

    except Exception as error:
        # Der Input bleibt bei Fehlern unverändert in data/input.
        if target_dir.exists() and not any(target_dir.iterdir()):
            target_dir.rmdir()
        print(f"FEHLER bei {source_path.name}: {error}", file=sys.stderr)


def main() -> None:
    INPUT_DIR.mkdir(parents=True, exist_ok=True)
    PROCESSED_DIR.mkdir(parents=True, exist_ok=True)

    input_files = sorted(
        path
        for path in INPUT_DIR.iterdir()
        if path.is_file() and path.suffix.lower() in SUPPORTED_EXTENSIONS
    )

    if not input_files:
        print(f"Keine unterstützten Dateien in: {INPUT_DIR}")
        return

    converter = DocumentConverter()
    for source_path in input_files:
        process_document(source_path, converter)


if __name__ == "__main__":
    main()
