from __future__ import annotations

import json
import logging
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Any

LOGGER = logging.getLogger(__name__)


@dataclass
class DatasetCard:
    id: str
    name: str
    description: str
    category: str
    language: str
    file_count: int
    task_count: int
    submission_count: int
    enabled: bool
    tags: list[str]
    source_manifest: str
    default_tool_candidates: list[str]


class PresetLoaderError(RuntimeError):
    pass


class DatasetPresetLoader:
    def __init__(
        self,
        repo_root: Path,
        presets_dir: Path | None = None,
    ) -> None:
        self.repo_root = repo_root.resolve()
        self.presets_dir = (presets_dir or self.repo_root / "tools" / "datasets" / "presets").resolve()

    def load_all_cards(self) -> list[DatasetCard]:
        cards: list[DatasetCard] = []
        if not self.presets_dir.exists():
            LOGGER.warning("Preset directory does not exist: %s", self.presets_dir)
            return cards

        for preset_file in sorted(self.presets_dir.glob("*.json")):
            try:
                card = self._load_card_from_preset(preset_file)
                if card:
                    cards.append(card)
            except Exception as exc:
                LOGGER.exception("Failed to load preset %s: %s", preset_file, exc)

        return cards

    def load_card_by_id(self, dataset_id: str) -> DatasetCard:
        preset_file = self.presets_dir / f"{dataset_id}.json"
        if not preset_file.exists():
            raise PresetLoaderError(f"Preset not found: {dataset_id}")
        card = self._load_card_from_preset(preset_file)
        if not card:
            raise PresetLoaderError(f"Preset disabled or invalid: {dataset_id}")
        return card

    def _read_json(self, path: Path) -> dict[str, Any]:
        with path.open("r", encoding="utf-8") as fh:
            return json.load(fh)

    def _resolve_repo_relative(self, maybe_relative: str) -> Path:
        path = Path(maybe_relative)
        if path.is_absolute():
            return path
        return (self.repo_root / path).resolve()

    def _load_card_from_preset(self, preset_file: Path) -> DatasetCard | None:
        preset = self._read_json(preset_file)

        if not preset.get("enabled", True):
            return None

        preset_type = preset.get("type", "preset_manifest")
        if preset_type != "preset_manifest":
            raise PresetLoaderError(f"Unsupported preset type: {preset_type}")

        source_manifest_path = self._resolve_repo_relative(preset["source"])
        if not source_manifest_path.exists():
            raise PresetLoaderError(f"Source manifest does not exist: {source_manifest_path}")

        manifest = self._read_json(source_manifest_path)

        language = manifest.get("language") or preset.get("language", "mixed")
        file_count = int(manifest.get("java_file_count", 0))
        task_count = int(manifest.get("task_count", 0))
        submission_count = int(manifest.get("submission_count", 0))

        return DatasetCard(
            id=preset["id"],
            name=preset.get("name", manifest.get("dataset_name", preset["id"])),
            description=preset.get("description", ""),
            category=preset.get("category", "benchmark"),
            language=language.upper() if isinstance(language, str) else "MIXED",
            file_count=file_count,
            task_count=task_count,
            submission_count=submission_count,
            enabled=bool(preset.get("enabled", True)),
            tags=list(preset.get("tags", [])),
            source_manifest=str(source_manifest_path),
            default_tool_candidates=list(preset.get("default_tool_candidates", [])),
        )


def discover_repo_root() -> Path:
    here = Path(__file__).resolve()
    return here.parents[4]


def load_dataset_cards() -> list[dict[str, Any]]:
    loader = DatasetPresetLoader(repo_root=discover_repo_root())
    return [asdict(card) for card in loader.load_all_cards()]


def load_dataset_card(dataset_id: str) -> dict[str, Any]:
    loader = DatasetPresetLoader(repo_root=discover_repo_root())
    return asdict(loader.load_card_by_id(dataset_id))
