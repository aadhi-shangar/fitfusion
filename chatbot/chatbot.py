from transformers import AutoTokenizer, AutoModelForCausalLM
from .classifier import classify_query
from .filters import GREETINGS, OFFENSIVE_WORDS
import torch
import os

model_path = os.path.join(os.path.dirname(__file__), "distilgpt2-fitness")

# Load model and tokenizer
# model_path = "./distilgpt2-fitness"
tokenizer = AutoTokenizer.from_pretrained(model_path)
model = AutoModelForCausalLM.from_pretrained(model_path)
tokenizer.pad_token = tokenizer.eos_token

# Helper functions
def contains_offensive(text):
    text_lower = text.lower()
    return any(off_word in text_lower for off_word in OFFENSIVE_WORDS)

def is_greeting(text):
    text_lower = text.lower().strip()
    return any(greet in text_lower for greet in GREETINGS)

# Main function to be used in app.py
def process_user_input(user_input, user_data=None, recommendation_data=None):
    if not user_input:
        return "Please enter a valid question."

    if contains_offensive(user_input):
        return "Let’s keep things positive—I'm here to assist you with any fitness or health questions you have."

    if is_greeting(user_input):
        return "Hello! How can I assist you with fitness or health today?"

    category = classify_query(user_input)

    if category not in ["fitness", "health", "nutrition"]:
        return "I'm here to help with fitness and health-related questions. Please ask something in that area."

    input_text = user_input + "\n"
    inputs = tokenizer(input_text, return_tensors="pt")

    outputs = model.generate(
        **inputs,
        max_length=100,
        pad_token_id=tokenizer.eos_token_id,
        eos_token_id=tokenizer.eos_token_id,
        do_sample=True,
        temperature=0.7,
        top_p=0.9,
        repetition_penalty=1.2,
        num_return_sequences=1
    )

    generated_text = tokenizer.decode(outputs[0], skip_special_tokens=True)
    response = generated_text[len(input_text):].strip().split("\n")[0]
    return response
