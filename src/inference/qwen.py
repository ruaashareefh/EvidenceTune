
"""Reusable Qwen3 inference functions for EvidenceTune."""

import torch
from transformers import AutoModelForCausalLM, AutoTokenizer


MODEL_NAME = "Qwen/Qwen3-1.7B"

SYSTEM_PROMPT = (
    "Answer the question using only the provided context. "
    "If the context does not contain enough information, "
    "respond with exactly ABSTAIN. "
    "Otherwise, provide a short factual answer."
)


def load_qwen(model_name: str = MODEL_NAME):
    """Load the pretrained Qwen model and tokenizer."""

    tokenizer = AutoTokenizer.from_pretrained(model_name)

    model = AutoModelForCausalLM.from_pretrained(
        model_name,
        torch_dtype="auto",
        device_map="auto",
    )

    model.eval()

    return tokenizer, model


def generate_answer(
    model,
    tokenizer,
    context: str,
    question: str,
    max_new_tokens: int = 128,
) -> str:
    """Generate an evidence-grounded answer using Qwen."""

    # Step 1: Construct chat messages.
    messages = [
        {
            "role": "system",
            "content": SYSTEM_PROMPT,
        },
        {
            "role": "user",
            "content": (
                f"Context:\n{context}\n\n"
                f"Question:\n{question}"
            ),
        },
    ]

    # Step 2: Tokenize using Qwen's chat template.
    inputs = tokenizer.apply_chat_template(
        messages,
        tokenize=True,
        add_generation_prompt=True,
        enable_thinking=False,
        return_tensors="pt",
        return_dict=True,
    ).to(model.device)

    # Step 3: Generate output tokens.
    with torch.inference_mode():
        outputs = model.generate(
            **inputs,
            max_new_tokens=max_new_tokens,
            do_sample=False,
            pad_token_id=tokenizer.eos_token_id,
        )

    # Step 4: Extract generated tokens only.
    input_length = inputs["input_ids"].shape[-1]
    output_ids = outputs[0, input_length:]

    # Step 5: Decode into readable text.
    answer = tokenizer.decode(
        output_ids,
        skip_special_tokens=True,
    ).strip()

    return answer
