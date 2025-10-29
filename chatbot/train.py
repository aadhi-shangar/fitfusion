from transformers import AutoModelForCausalLM, AutoTokenizer, TrainingArguments, Trainer, DataCollatorForLanguageModeling
from datasets import load_dataset

# Load model and tokenizer
model_name = "./distilgpt2-fitness"
model = AutoModelForCausalLM.from_pretrained(model_name)
tokenizer = AutoTokenizer.from_pretrained(model_name)
tokenizer.pad_token = tokenizer.eos_token  # GPT2 doesn't have a pad token

# Load your dataset (replace with your filename)
dataset = load_dataset("json", data_files="fitness_data.json")

# Tokenization function
def tokenize_function(examples):
    inputs = [ins + "\n" + out for ins, out in zip(examples["instruction"], examples["output"])]
    return tokenizer(inputs, truncation=True, padding="max_length", max_length=256)

# Tokenize dataset
tokenized_dataset = dataset.map(tokenize_function, batched=True)

# Data collator for causal LM (mlm=False)
data_collator = DataCollatorForLanguageModeling(tokenizer=tokenizer, mlm=False)

# Training args
training_args = TrainingArguments(
    output_dir="./distilgpt2-fitness",
    per_device_train_batch_size=2,
    num_train_epochs=3,
    save_safetensors=False,  # 👈 add this line
    logging_dir="./logs",
    logging_steps=10,
    save_total_limit=1,
)

# Custom Trainer to disable pin_memory warning
class CustomTrainer(Trainer):
    def get_train_dataloader(self):
        dataloader = super().get_train_dataloader()
        dataloader.pin_memory = False  # Disable pin_memory to fix warning
        return dataloader

# Initialize trainer (removed tokenizer arg to silence warning)
trainer = CustomTrainer(
    model=model,
    args=training_args,
    train_dataset=tokenized_dataset["train"],
    data_collator=data_collator,
)

# Train!
trainer.train()
# Save model and tokenizer manually
trainer.save_model("./distilgpt2-fitness")  # saves pytorch_model.bin and config
tokenizer.save_pretrained("./distilgpt2-fitness")
