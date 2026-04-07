"""
Transfer-learning training skeleton for the INFERNAL X fire/smoke vision track.

This file is intentionally review-safe:
- it shows the intended pipeline
- it does not claim a completed trained model
- it can be filled in with real data loaders later
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List


@dataclass
class TrainConfig:
    dataset_root: Path
    train_manifest: Path
    val_manifest: Path
    test_manifest: Path
    image_size: int = 224
    num_classes: int = 5
    backbone: str = "resnet50"
    batch_size: int = 16
    epochs: int = 12
    learning_rate: float = 1e-4
    weight_decay: float = 1e-4


def load_manifest(path: Path) -> List[Dict]:
    if not path.exists():
        return []
    with path.open("r", encoding="utf-8") as handle:
        return [json.loads(line) for line in handle if line.strip()]


def build_model(backbone: str, num_classes: int):
    """
    Placeholder for a pretrained backbone plus classification head.
    Suggested implementation:
    - torchvision.models.resnet50(weights=...)
    - replace final FC layer with num_classes outputs
    """
    return {
        "backbone": backbone,
        "num_classes": num_classes,
        "status": "model_stub",
    }


def train_one_epoch(model, train_data):
    """
    Placeholder training loop.
    In the real version this would:
    - load images
    - run augmentation
    - compute loss
    - backpropagate
    - log metrics
    """
    return {"loss": 0.0, "accuracy": 0.0}


def evaluate(model, val_data):
    """
    Placeholder validation loop.
    """
    return {"val_loss": 0.0, "val_accuracy": 0.0}


def save_checkpoint(output_dir: Path, model, metrics: Dict):
    output_dir.mkdir(parents=True, exist_ok=True)
    payload = {
        "model": model,
        "metrics": metrics,
        "note": "scaffold_only_no_real_training_yet",
    }
    (output_dir / "checkpoint.json").write_text(json.dumps(payload, indent=2), encoding="utf-8")


def main():
    config = TrainConfig(
        dataset_root=Path("vision_training/dataset"),
        train_manifest=Path("vision_training/dataset/manifests/train.jsonl"),
        val_manifest=Path("vision_training/dataset/manifests/val.jsonl"),
        test_manifest=Path("vision_training/dataset/manifests/test.jsonl"),
    )

    train_data = load_manifest(config.train_manifest)
    val_data = load_manifest(config.val_manifest)
    model = build_model(config.backbone, config.num_classes)

    train_metrics = train_one_epoch(model, train_data)
    val_metrics = evaluate(model, val_data)
    metrics = {**train_metrics, **val_metrics}

    save_checkpoint(Path("vision_training/artifacts/checkpoints"), model, metrics)
    print(json.dumps({"status": "scaffold_complete", "metrics": metrics}, indent=2))


if __name__ == "__main__":
    main()
