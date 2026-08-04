import os
os.environ["HF_HUB_DISABLE_XET"] = "1"
os.environ["HF_HUB_ENABLE_HF_TRANSFER"] = "0"

import sys
from src.chatbot import HealthcareChatbot

def main():
    print("=" * 60)
    print("   SehatAI - Multilingual Rural Healthcare Assistant CLI")
    print("=" * 60)
    print("Type 'exit' or 'quit' to stop.\n")

    # Initialize chatbot instance (loads model/tokenizer/retriever once)
    bot = HealthcareChatbot(model_name="Qwen/Qwen2.5-0.5B-Instruct")
    print("\n[INFO] Initialization Complete! Ready to take health queries.\n")

    # Phase 13: conversation history now lives here, in the caller, instead
    # of inside HealthcareChatbot. Starts with just the system prompt, same
    # as the old self.conversation_history did in __init__.
    conversation_history = [
        {"role": "system", "content": bot.system_prompt}
    ]

    # Interactive REPL (Read-Eval-Print Loop)
    while True:
        try:
            user_input = input("\nYou: ").strip()
            if not user_input:
                continue
            if user_input.lower() in ["exit", "quit"]:
                print("\n[SehatAI] Thank you for using SehatAI. Stay healthy!")
                break

            # generate_response now takes history in and returns the
            # updated history out — store it back for the next turn.
            _response_text, conversation_history = bot.generate_response(
                user_input, conversation_history
            )

        except KeyboardInterrupt:
            print("\n[SehatAI] Session closed. Goodbye!")
            sys.exit(0)
        except Exception as e:
            print(f"\n[ERROR] An unexpected error occurred: {e}")

if __name__ == "__main__":
    main()