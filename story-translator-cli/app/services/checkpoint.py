import json
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, Optional

from app.models.schema import ChapterCheckpoint
from app.utils.logger import logger

class CheckpointManager:
    """Manages step-level progress checkpoints so workflow can resume if crashed."""

    def __init__(self, data_dir: Path):
        self.checkpoint_path = data_dir / "checkpoints.json"

    def _load_all(self) -> Dict[str, Dict[str, Any]]:
        if not self.checkpoint_path.exists():
            return {}
        try:
            with open(self.checkpoint_path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return {}

    def _save_all(self, data: Dict[str, Dict[str, Any]]):
        with open(self.checkpoint_path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

    def get_checkpoint(self, chapter_num: int) -> Optional[ChapterCheckpoint]:
        all_data = self._load_all()
        key = str(chapter_num)
        if key in all_data:
            return ChapterCheckpoint.model_validate(all_data[key])
        return None

    def update_checkpoint(self, chapter_num: int, step: str, title: str = ""):
        all_data = self._load_all()
        key = str(chapter_num)
        checkpoint = ChapterCheckpoint(
            chapter_num=chapter_num,
            step=step,
            chapter_title=title,
            updated_at=datetime.now().isoformat()
        )
        all_data[key] = checkpoint.model_dump()
        self._save_all(all_data)
        logger.debug(f"[Checkpoint] Chương {chapter_num} -> {step}")

    def is_step_completed(self, chapter_num: int, required_step: str) -> bool:
        """Step hierarchy: INGESTED -> GLOSSARY_SLOTTED -> TRANSLATED -> QC_AUDITED -> COMMITTED"""
        STEPS = ["INGESTED", "GLOSSARY_SLOTTED", "TRANSLATED", "QC_AUDITED", "COMMITTED"]
        cp = self.get_checkpoint(chapter_num)
        if not cp:
            return False
        
        if cp.step not in STEPS or required_step not in STEPS:
            return False
            
        return STEPS.index(cp.step) >= STEPS.index(required_step)
