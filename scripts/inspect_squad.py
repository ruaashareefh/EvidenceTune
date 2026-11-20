from datasets import load_dataset

# Load SQuAD 2.0 validation data
dataset = load_dataset(
    "rajpurkar/squad_v2",
    split="validation"
)

# Inspect one example
example = dataset[0]

print("Total examples:", len(dataset))
print("\nAvailable fields:", example.keys())
print("\nContext:", example["context"])
print("\nQuestion:", example["question"])
print("\nAnswers:", example["answers"])

unanswerable = next(
    example
    for example in dataset
    if len(example["answers"]["text"]) == 0
)

print("\n--- UNANSWERABLE EXAMPLE ---")
print("Context:", unanswerable["context"])
print("Question:", unanswerable["question"])
print("Answers:", unanswerable["answers"])
