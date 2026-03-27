# AI Model Retraining Guide: Spatial & Safety Operations

If the Llama 3 (or equivalent) backbone struggles to produce consistent, high-logic structured JSON representing pathfinding or hazard suppression, fine-tuning is necessary. 

### Why Retrain?
Standard instruct models are conversational. The `AEGIS OVERSEER` requires a model that operates purely on spatial arrays, grid coordinates, and logical state machines (Survival probability, route intersections, hazard tracking). 

### Recommended Model
- **Base:** `Meta-Llama-3.1-8B-Instruct` (Currently deployed via Ollama for log summaries and spatial tracking)
- **Architecture:** Causal LM
- **Quantization:** 4-bit or 8-bit (QLoRA) for local consumer hardware (RTX 4090 / RTX 3090).

### Dataset Preparation
You must generate a synthetic dataset converting building states into the specific JSON format `server.py` expects.

**Format example (JSONL):**
```json
{"messages": [
  {"role": "system", "content": "You are AEGIS, a God-Level Safety LLM. Output only valid JSON."},
  {"role": "user", "content": "Grid: 100x100. Fire at (45,50), (46,50). 55 Personnel active. ID 12 trapped at (44,50). Evaluate."},
  {"role": "assistant", "content": "{\"decisions\":[{\"person_id\":\"12\",\"action\":\"SHELTER_IN_PLACE\",\"target\":null,\"reasoning\":\"Fire intersects all exit routes.\"}]} "}
]}
```

Generate 10,000 to 50,000 of these scenarios spanning:
1. Fire blocking primary exits.
2. Group dynamic congestion (10+ people clogging a 1-tile corridor).
3. Phase 2: Water Sprinkler activation.

### Training Script (HuggingFace SFT Trainer)
Using Unsloth (optimized fine-tuning library) is highly recommended for speed.

```python
from unsloth import FastLanguageModel
import torch
from trl import SFTTrainer
from transformers import TrainingArguments
from datasets import load_dataset

model, tokenizer = FastLanguageModel.from_pretrained(
    model_name = "unsloth/Meta-Llama-3.1-8B-Instruct-bnb-4bit",
    max_seq_length = 2048,
    dtype = None,
    load_in_4bit = True,
)

model = FastLanguageModel.get_peft_model(
    model,
    r = 16, # Rank
    target_modules = ["q_proj", "k_proj", "v_proj", "o_proj",
                      "gate_proj", "up_proj", "down_proj",],
    lora_alpha = 16,
    lora_dropout = 0,
    bias = "none",
    use_gradient_checkpointing = True,
)

dataset = load_dataset("json", data_files="aegis_spatial_data.jsonl", split="train")

trainer = SFTTrainer(
    model = model,
    tokenizer = tokenizer,
    train_dataset = dataset,
    dataset_text_field = "text", # Assumes you formatted messages into a template string beforehand
    max_seq_length = 2048,
    args = TrainingArguments(
        per_device_train_batch_size = 2,
        gradient_accumulation_steps = 4,
        warmup_steps = 5,
        max_steps = 200,
        learning_rate = 2e-4,
        fp16 = not torch.cuda.is_bf16_supported(),
        bf16 = torch.cuda.is_bf16_supported(),
        logging_steps = 1,
        optim = "adamw_8bit",
        weight_decay = 0.01,
        lr_scheduler_type = "linear",
        seed = 3407,
        output_dir = "outputs",
    ),
)

trainer.train()
model.save_pretrained_merged("aegis-llama3-spatial", tokenizer, save_method = "merged_16bit",)
```

### Deployment
Once merged into a `.gguf` file or safetensors, you can load this specific model path in `server.py` replacing `llama3.1` via Ollama (`ollama create aegis-custom -f Modelfile`).
