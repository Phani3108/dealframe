"""
LoRA fine-tuning trainer — Phase 4.

Wraps HuggingFace PEFT + Transformers to fine-tune a causal LM
(default: Mistral-7B-Instruct) on the DealFrame extraction dataset.

All heavy dependencies (torch, transformers, peft, datasets) are imported
lazily so the module can be imported on any machine without GPU / HF packages.

Usage:
    from temporalos.finetuning.trainer import LoRATrainer, TrainerConfig
    config = TrainerConfig.from_settings()
    trainer = LoRATrainer(config)
    result = trainer.train(
        train_dataset_path="datasets/train.jsonl",
        val_dataset_path="datasets/val.jsonl",
        output_dir="models/v1",
    )
"""

from __future__ import annotations

import json
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


@dataclass
class TrainerConfig:
    base_model_id: str = "mistralai/Mistral-7B-Instruct-v0.3"
    lora_r: int = 8
    lora_alpha: int = 16
    lora_dropout: float = 0.05
    target_modules: list[str] = field(default_factory=lambda: ["q_proj", "v_proj"])
    epochs: int = 3
    learning_rate: float = 2e-4
    batch_size: int = 4
    max_length: int = 1024
    fp16: bool = False   # set True on CUDA
    gradient_accumulation_steps: int = 4
    warmup_ratio: float = 0.03
    logging_steps: int = 10
    save_steps: int = 50
    eval_steps: int = 50

    @classmethod
    def from_settings(cls) -> "TrainerConfig":
        from ..config import get_settings
        s = get_settings().finetuning
        return cls(
            base_model_id=s.base_model_id,
            lora_r=s.lora_r,
            lora_alpha=s.lora_alpha,
            lora_dropout=s.lora_dropout,
            target_modules=s.target_modules,
            epochs=s.epochs,
            learning_rate=s.learning_rate,
            batch_size=s.batch_size,
            max_length=s.max_length,
        )


@dataclass
class TrainingResult:
    experiment_id: str
    adapter_path: str
    train_loss: float
    val_loss: float
    epochs_completed: int
    total_steps: int
    duration_seconds: float
    success: bool
    error: str = ""

    def to_dict(self) -> dict:
        return {
            "experiment_id": self.experiment_id,
            "adapter_path": self.adapter_path,
            "train_loss": round(self.train_loss, 4),
            "val_loss": round(self.val_loss, 4),
            "epochs_completed": self.epochs_completed,
            "total_steps": self.total_steps,
            "duration_seconds": round(self.duration_seconds, 1),
            "success": self.success,
            "error": self.error,
        }


class LoRATrainer:
    """
    LoRA fine-tuning trainer.

    In real use with GPU + HuggingFace installed, this runs full SFT training.
    When the packages are unavailable (CPU-only boxes, CI), it raises
    ImportError so callers can detect and skip gracefully.
    """

    def __init__(self, config: TrainerConfig | None = None) -> None:
        self._config = config or TrainerConfig()

    def train(
        self,
        train_dataset_path: str | Path,
        val_dataset_path: str | Path,
        output_dir: str | Path,
        experiment_id: str = "",
        dry_run: bool = False,
    ) -> TrainingResult:
        """
        Fine-tune the base model on the provided JSONL dataset.

        Parameters
        ----------
        train_dataset_path : path to training JSONL
        val_dataset_path   : path to validation JSONL
        output_dir         : save adapter weights here
        experiment_id      : associated registry ID (metadata only)
        dry_run            : if True, skip actual training (for tests/CI)
        """
        start = time.time()
        output_dir = Path(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)

        if dry_run:
            return self._dry_run_result(experiment_id, str(output_dir), start)

        try:
            return self._real_train(
                train_dataset_path, val_dataset_path, output_dir, experiment_id, start
            )
        except ImportError as exc:
            return TrainingResult(
                experiment_id=experiment_id,
                adapter_path="",
                train_loss=0.0,
                val_loss=0.0,
                epochs_completed=0,
                total_steps=0,
                duration_seconds=time.time() - start,
                success=False,
                error=f"Missing dependency: {exc}. Install with: pip install temporalos[finetuning]",
            )

    # ── Internal ──────────────────────────────────────────────────────────────

    def _real_train(
        self,
        train_path: str | Path,
        val_path: str | Path,
        output_dir: Path,
        experiment_id: str,
        start: float,
    ) -> TrainingResult:
        """Actual PEFT/Transformers training path — requires GPU packages."""
        import torch
        from datasets import Dataset
        from peft import LoraConfig, TaskType, get_peft_model
        from transformers import AutoModelForCausalLM, AutoTokenizer, TrainingArguments
        from trl import SFTTrainer

        cfg = self._config

        # ── Load tokenizer + model ─────────────────────────────────────────
        tokenizer = AutoTokenizer.from_pretrained(cfg.base_model_id)
        tokenizer.pad_token = tokenizer.eos_token

        model = AutoModelForCausalLM.from_pretrained(
            cfg.base_model_id,
            torch_dtype=torch.float16 if cfg.fp16 else torch.float32,
            device_map="auto",
        )

        lora_cfg = LoraConfig(
            task_type=TaskType.CAUSAL_LM,
            r=cfg.lora_r,
            lora_alpha=cfg.lora_alpha,
            lora_dropout=cfg.lora_dropout,
            target_modules=cfg.target_modules,
        )
        model = get_peft_model(model, lora_cfg)

        # ── Load dataset ───────────────────────────────────────────────────
        train_ds = _load_jsonl_as_hf_dataset(train_path, tokenizer, cfg.max_length)
        val_ds = _load_jsonl_as_hf_dataset(val_path, tokenizer, cfg.max_length)

        # ── Training arguments ─────────────────────────────────────────────
        training_args = TrainingArguments(
            output_dir=str(output_dir),
            num_train_epochs=cfg.epochs,
            per_device_train_batch_size=cfg.batch_size,
            per_device_eval_batch_size=cfg.batch_size,
            gradient_accumulation_steps=cfg.gradient_accumulation_steps,
            learning_rate=cfg.learning_rate,
            fp16=cfg.fp16,
            warmup_ratio=cfg.warmup_ratio,
            logging_steps=cfg.logging_steps,
            save_steps=cfg.save_steps,
            eval_steps=cfg.eval_steps,
            evaluation_strategy="steps",
            load_best_model_at_end=True,
            metric_for_best_model="eval_loss",
            report_to="none",
        )

        trainer = SFTTrainer(
            model=model,
            args=training_args,
            train_dataset=train_ds,
            eval_dataset=val_ds,
            dataset_text_field="text",
        )

        train_output = trainer.train()
        model.save_pretrained(str(output_dir))
        tokenizer.save_pretrained(str(output_dir))

        # Extract metrics from trainer state
        final_metrics = trainer.state.log_history
        train_loss = next(
            (m["loss"] for m in reversed(final_metrics) if "loss" in m), 0.0
        )
        val_loss = next(
            (m["eval_loss"] for m in reversed(final_metrics) if "eval_loss" in m), 0.0
        )

        return TrainingResult(
            experiment_id=experiment_id,
            adapter_path=str(output_dir),
            train_loss=train_loss,
            val_loss=val_loss,
            epochs_completed=cfg.epochs,
            total_steps=train_output.global_step,
            duration_seconds=time.time() - start,
            success=True,
        )

    def _dry_run_result(
        self, experiment_id: str, output_dir: str, start: float
    ) -> TrainingResult:
        """Simulate a completed training run for testing / CI."""
        # Write a minimal adapter_config.json so the directory looks like a real checkpoint
        marker = Path(output_dir) / "adapter_config.json"
        marker.write_text(
            json.dumps({
                "base_model_name_or_path": self._config.base_model_id,
                "peft_type": "LORA",
                "r": self._config.lora_r,
                "lora_alpha": self._config.lora_alpha,
                "__dry_run__": True,
            }),
            encoding="utf-8",
        )
        return TrainingResult(
            experiment_id=experiment_id,
            adapter_path=output_dir,
            train_loss=0.42,
            val_loss=0.51,
            epochs_completed=self._config.epochs,
            total_steps=100,
            duration_seconds=time.time() - start,
            success=True,
        )


# ── Dataset helpers ────────────────────────────────────────────────────────────

def _load_jsonl_as_hf_dataset(path: str | Path, tokenizer: Any, max_length: int) -> Any:
    """Load a JSONL dataset file as a HuggingFace Dataset with formatted text."""
    from datasets import Dataset

    records = []
    with Path(path).open("r", encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            ex = json.loads(line)
            text = (
                f"[INST] {ex['instruction']}\n\n{ex['input']} [/INST]\n{ex['output']}</s>"
            )
            records.append({"text": text})

    return Dataset.from_list(records)
