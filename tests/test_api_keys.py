import os
import requests
from dotenv import load_dotenv

load_dotenv()
api_key = os.getenv("CEREBRAS_API_KEY")

def ask_cerebras(prompt):
    # Ensure this URL is exactly correct
    url = "https://api.cerebras.ai/v1/chat/completions"
    
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json"
    }

    payload = {
        "model": "llama3.1-8b", 
        "messages": [
            {"role": "user", "content": prompt}
        ]
    }

    try:
        response = requests.post(url, headers=headers, json=payload)
        
        if response.status_code == 200:
            data = response.json()
            # Note the [0] index for choices
            return data['choices'][0]['message']['content']
        else:
            print(f"❌ Error {response.status_code}: {response.text}")
            return None
    except Exception as e:
        print(f"❌ Script Error: {e}")
        return None


print(ask_cerebras("Explain agents in 5 words."))
