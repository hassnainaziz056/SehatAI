import os
os.environ["HF_HUB_DISABLE_XET"] = "1"
os.environ["HF_HUB_ENABLE_HF_TRANSFER"] = "0"

import torch
from transformers import AutoModelForCausalLM, AutoTokenizer, TextStreamer

from knowledge_base.retriever import Retriever

class HealthcareChatbot:
    """
    A lightweight local LLM chatbot tailored for SehatAI.
    """
    def __init__(self, model_name: str = "Qwen/Qwen2.5-0.5B-Instruct"):
        print(f"\n[INFO] Loading tokenizer & model '{model_name}'... Please wait.")
        self.device = "cuda" if torch.cuda.is_available() else "cpu"
        
        # 1. Load the tokenizer responsible for translating text into numbers (tokens)
        tokenizer = AutoTokenizer.from_pretrained(model_name)
        assert tokenizer is not None, "Failed to load tokenizer."
        self.tokenizer = tokenizer
        
        # 2. Load the Neural Network model architecture and weights
        self.model = AutoModelForCausalLM.from_pretrained(
            model_name,
            dtype=torch.float32,
        ).to(self.device)
        
        # 3. Streamer to print generated tokens live to the console
        self.streamer = TextStreamer(self.tokenizer, skip_prompt=True, skip_special_tokens=True)
        
        # 4. System instructions setting persona and boundaries
        self.system_prompt = (
            "You are SehatAI, a helpful, empathetic, and knowledgeable multilingual healthcare assistant for rural communities. "
            "Provide clear, accurate health guidance. "
            "Always include a disclaimer that you are an AI and non-emergency advice only, urging medical consultation for serious symptoms."
        )
        
        # 5. Conversation history state for multi-turn chat context
        self.conversation_history = [
            {"role": "system", "content": self.system_prompt}
        ]

        # 6. Retriever for RAG — pulls relevant reference chunks from the
        # knowledge base before each response. Degrades gracefully (RAG off)
        # if the vector store hasn't been built yet.
        self.retriever = Retriever()
        if self.retriever.available:
            print("[INFO] RAG is active — responses will use the knowledge base.")
        else:
            print("[INFO] RAG is disabled — responses will use the model's own knowledge only.")

    def _build_retrieval_query(self, user_input: str) -> str:
        """
        Build the text actually sent to the retriever for vector search.

        Short follow-ups like "short it", "why", or "what about kids" carry
        almost no topical signal on their own — embedding them alone can
        match a completely unrelated chunk. To keep retrieval anchored to
        what's actually being discussed, we prepend the most recent
        assistant reply (if there is one) to the new message before
        searching. This only affects what gets searched for — it has no
        effect on conversation_history or on what the model sees as the
        conversation itself.
        """
        previous_assistant_turns = [
            msg["content"] for msg in self.conversation_history if msg["role"] == "assistant"
        ]
        if previous_assistant_turns:
            return f"{previous_assistant_turns[-1]}\n\n{user_input}"
        return user_input

    def generate_response(self, user_input: str) -> str:
        # Retrieve relevant reference chunks from the knowledge base, if any.
        # The search query includes recent context (see _build_retrieval_query)
        # so short follow-ups don't trigger an unrelated, out-of-context match.
        retrieval_query = self._build_retrieval_query(user_input)
        retrieved = self.retriever.retrieve(retrieval_query, top_k=2)

        if retrieved:
            context_block = "\n\n".join(
                f"[{chunk['topic']}]\n{chunk['text']}" for chunk in retrieved
            )
            augmented_input = (
                "Reference information (use only if relevant to the question, "
                "and answer in your own words, not by copying this text):\n\n"
                f"{context_block}\n\n"
                f"Patient question: {user_input}"
            )
        else:
            augmented_input = user_input

        # Append the ORIGINAL, unmodified user message to conversation memory.
        # The retrieved context is never stored here, so it doesn't pile up
        # across multiple turns.
        self.conversation_history.append({"role": "user", "content": user_input})

        # Build a temporary message list for this call only: everything up to
        # (but not including) the clean user turn we just appended, plus one
        # augmented version of it. This is discarded after generation — it's
        # never written back into self.conversation_history.
        messages_for_prompt = self.conversation_history[:-1] + [
            {"role": "user", "content": augmented_input}
        ]

        # Apply model-specific chat template (formats system, user, assistant markers)
        formatted_prompt = self.tokenizer.apply_chat_template(
            messages_for_prompt,
            tokenize=False,
            add_generation_prompt=True
        )
        
        # Tokenize prompt and convert to PyTorch Tensors
        inputs = self.tokenizer(str(formatted_prompt), return_tensors="pt").to(self.device)
        
        print("\nSehatAI: ", end="", flush=True)
        with torch.no_grad(): # Disable gradient calculation for efficient inference
            outputs = self.model.generate(
                **inputs,
                max_new_tokens=256,
                temperature=0.7,
                top_p=0.9,
                do_sample=True,
                streamer=self.streamer
            )
        
        # Extract newly generated tokens (slice out prompt tokens) and decode back to text
        input_length = inputs["input_ids"].shape[1]
        new_tokens = outputs[0][input_length:]
        response_text = self.tokenizer.decode(new_tokens, skip_special_tokens=True)
        
        # Store assistant response in conversation memory
        self.conversation_history.append({"role": "assistant", "content": response_text})
        return response_text