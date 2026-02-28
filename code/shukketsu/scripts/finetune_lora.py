"""LoRA fine-tune Nemotron 3 Nano 30B for improved tool calling.

Uses Unsloth for memory-efficient QLoRA training on ChatML-format data.
Optionally exports the fine-tuned model to GGUF for ollama serving.

Requirements:
    pip install --break-system-packages "unsloth[local]"

GPU requirements:
    - 8-bit LoRA: ~60GB VRAM (GB10 128GB unified memory works)
    - 4-bit QLoRA: ~30GB VRAM
    - Requires CUDA support for the GPU architecture (Blackwell sm_121
      may need PyTorch nightly with CUDA 12.8+)

Usage:
    python3 -m shukketsu.scripts.finetune_lora
    python3 -m shukketsu.scripts.finetune_lora --epochs 5 --lr 1e-4
    python3 -m shukketsu.scripts.finetune_lora --export-gguf
    python3 -m shukketsu.scripts.finetune_lora --train data/scratch/train.jsonl
"""

import argparse
import logging
import sys
from pathlib import Path

logger = logging.getLogger(__name__)

# Unsloth's pre-converted model — avoids downloading full BF16 weights
MODEL_NAME = "unsloth/Nemotron-3-Nano-30B-A3B"
OUTPUT_DIR = "models/shukketsu-nemotron-lora"
GGUF_DIR = "models/shukketsu-nemotron-gguf"
TRAIN_FILE = "data/scratch/train.jsonl"
EVAL_FILE = "data/scratch/eval.jsonl"

# LoRA target modules for Nemotron 3 Nano (MoE architecture)
# Includes in_proj/out_proj for MoE expert layers.
# Router layer is NOT fine-tuned (disabled by default in Unsloth).
TARGET_MODULES = [
    "q_proj", "k_proj", "v_proj", "o_proj",
    "gate_proj", "up_proj", "down_proj",
    "in_proj", "out_proj",
]


def _check_gpu():
    """Check GPU availability and report."""
    try:
        import torch
    except ImportError:
        logger.error("PyTorch not installed. Install with CUDA support first.")
        sys.exit(1)

    if not torch.cuda.is_available():
        logger.error(
            "CUDA not available. LoRA training requires a CUDA-capable GPU. "
            "On GB10 Blackwell (sm_121), ensure PyTorch is built with CUDA 12.8+ "
            "and sm_121 support."
        )
        sys.exit(1)

    device_name = torch.cuda.get_device_name(0)
    vram_gb = torch.cuda.get_device_properties(0).total_mem / (1024**3)
    logger.info("GPU detected: %s (%.1f GB)", device_name, vram_gb)
    return device_name, vram_gb


def _check_training_data(train_path: Path, eval_path: Path):
    """Verify training data exists and has content."""
    for path, label in [(train_path, "train"), (eval_path, "eval")]:
        if not path.exists():
            logger.error(
                "%s file not found: %s. Run prepare-training-data first.",
                label.capitalize(), path,
            )
            sys.exit(1)
        line_count = sum(1 for _ in path.open())
        if line_count == 0:
            logger.error("%s file is empty: %s", label.capitalize(), path)
            sys.exit(1)
        logger.info("%s data: %d examples from %s", label.capitalize(), line_count, path)


def main():
    parser = argparse.ArgumentParser(
        description="LoRA fine-tune Nemotron 3 Nano 30B for tool calling"
    )
    parser.add_argument(
        "--model", type=str, default=MODEL_NAME,
        help=f"HuggingFace model ID (default: {MODEL_NAME})",
    )
    parser.add_argument(
        "--train", type=str, default=TRAIN_FILE,
        help=f"Training data JSONL (default: {TRAIN_FILE})",
    )
    parser.add_argument(
        "--eval", type=str, default=EVAL_FILE,
        help=f"Evaluation data JSONL (default: {EVAL_FILE})",
    )
    parser.add_argument(
        "--output", type=str, default=OUTPUT_DIR,
        help=f"Output directory for LoRA adapter (default: {OUTPUT_DIR})",
    )
    parser.add_argument(
        "--epochs", type=int, default=3,
        help="Number of training epochs (default: 3)",
    )
    parser.add_argument(
        "--lr", type=float, default=2e-4,
        help="Learning rate (default: 2e-4)",
    )
    parser.add_argument(
        "--batch-size", type=int, default=1,
        help="Per-device batch size (default: 1)",
    )
    parser.add_argument(
        "--grad-accum", type=int, default=4,
        help="Gradient accumulation steps (default: 4)",
    )
    parser.add_argument(
        "--max-seq-length", type=int, default=8192,
        help="Maximum sequence length (default: 8192)",
    )
    parser.add_argument(
        "--lora-r", type=int, default=16,
        help="LoRA rank (default: 16)",
    )
    parser.add_argument(
        "--lora-alpha", type=int, default=32,
        help="LoRA alpha (default: 32)",
    )
    parser.add_argument(
        "--load-in-4bit", action="store_true", default=True,
        help="Use 4-bit quantization (default: True)",
    )
    parser.add_argument(
        "--load-in-8bit", action="store_true",
        help="Use 8-bit quantization instead of 4-bit",
    )
    parser.add_argument(
        "--export-gguf", action="store_true",
        help="Export to GGUF format after training (for ollama)",
    )
    parser.add_argument(
        "--gguf-output", type=str, default=GGUF_DIR,
        help=f"GGUF output directory (default: {GGUF_DIR})",
    )
    parser.add_argument(
        "--gguf-quant", type=str, default="q4_k_m",
        help="GGUF quantization method (default: q4_k_m)",
    )
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO)

    # Pre-flight checks
    _check_gpu()
    _check_training_data(Path(args.train), Path(args.eval))

    # Late imports — these are heavy dependencies
    try:
        from unsloth import FastLanguageModel
    except ImportError:
        logger.error(
            "Unsloth not installed. Run: "
            "pip install --break-system-packages 'unsloth[local]'"
        )
        sys.exit(1)

    try:
        from datasets import load_dataset
        from trl import SFTConfig, SFTTrainer
    except ImportError:
        logger.error(
            "datasets or trl not installed. Run: "
            "pip install --break-system-packages datasets trl"
        )
        sys.exit(1)

    # Determine quantization mode
    load_in_4bit = not args.load_in_8bit
    quant_label = "8-bit" if args.load_in_8bit else "4-bit"
    logger.info(
        "Loading %s with %s quantization, max_seq_length=%d...",
        args.model, quant_label, args.max_seq_length,
    )

    # Load model
    model, tokenizer = FastLanguageModel.from_pretrained(
        model_name=args.model,
        max_seq_length=args.max_seq_length,
        load_in_4bit=load_in_4bit,
        load_in_8bit=args.load_in_8bit,
        trust_remote_code=True,
    )

    # Apply LoRA adapters
    logger.info(
        "Applying LoRA (r=%d, alpha=%d) to %d target modules...",
        args.lora_r, args.lora_alpha, len(TARGET_MODULES),
    )
    model = FastLanguageModel.get_peft_model(
        model,
        r=args.lora_r,
        lora_alpha=args.lora_alpha,
        target_modules=TARGET_MODULES,
        lora_dropout=0,
        bias="none",
        use_gradient_checkpointing="unsloth",
        random_state=3407,
    )

    # Load dataset
    logger.info("Loading training data...")
    dataset = load_dataset("json", data_files={
        "train": args.train,
        "eval": args.eval,
    })
    logger.info(
        "Dataset: %d train, %d eval",
        len(dataset["train"]), len(dataset["eval"]),
    )

    # Training config
    output_path = Path(args.output)
    output_path.mkdir(parents=True, exist_ok=True)

    training_args = SFTConfig(
        output_dir=str(output_path),
        per_device_train_batch_size=args.batch_size,
        gradient_accumulation_steps=args.grad_accum,
        num_train_epochs=args.epochs,
        learning_rate=args.lr,
        warmup_steps=10,
        logging_steps=10,
        eval_strategy="epoch",
        save_strategy="epoch",
        bf16=True,
        max_seq_length=args.max_seq_length,
        seed=3407,
    )

    trainer = SFTTrainer(
        model=model,
        tokenizer=tokenizer,
        train_dataset=dataset["train"],
        eval_dataset=dataset["eval"],
        args=training_args,
    )

    # Train
    logger.info(
        "Starting training: %d epochs, batch=%d, grad_accum=%d, lr=%s",
        args.epochs, args.batch_size, args.grad_accum, args.lr,
    )
    trainer.train()

    # Save adapter
    model.save_pretrained(str(output_path))
    tokenizer.save_pretrained(str(output_path))
    logger.info("LoRA adapter saved to %s", output_path)

    # Optional GGUF export
    if args.export_gguf:
        gguf_path = Path(args.gguf_output)
        gguf_path.mkdir(parents=True, exist_ok=True)
        logger.info(
            "Exporting to GGUF (%s) at %s...", args.gguf_quant, gguf_path,
        )
        model.save_pretrained_gguf(
            str(gguf_path),
            tokenizer,
            quantization_method=args.gguf_quant,
        )
        logger.info("GGUF export complete: %s", gguf_path)
        print(
            "\nTo register with ollama:\n"
            "  ollama create shukketsu-nemotron -f models/Modelfile\n"
            "\nThen update .env:\n"
            "  LLM__MODEL=shukketsu-nemotron\n"
        )

    print(f"\nTraining complete. Adapter saved to {output_path}")
    if not args.export_gguf:
        print(
            "To export to GGUF for ollama, re-run with --export-gguf\n"
            "or run: python3 -m shukketsu.scripts.finetune_lora --export-gguf"
        )


if __name__ == "__main__":
    main()
