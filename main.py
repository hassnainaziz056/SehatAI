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
    
    # Initialize chatbot instance
    bot = HealthcareChatbot(model_name="Qwen/Qwen2.5-0.5B-Instruct")
    print("\n[INFO] Initialization Complete! Ready to take health queries.\n")
    
    # Interactive REPL (Read-Eval-Print Loop)
    while True:
        try:
            user_input = input("\nYou: ").strip()
            if not user_input:
                continue
            if user_input.lower() in ["exit", "quit"]:
                print("\n[SehatAI] Thank you for using SehatAI. Stay healthy!")
                break
            
            bot.generate_response(user_input)
            
        except KeyboardInterrupt:
            print("\n[SehatAI] Session closed. Goodbye!")
            sys.exit(0)
        except Exception as e:
            print(f"\n[ERROR] An unexpected error occurred: {e}")

if __name__ == "__main__":
    main()
