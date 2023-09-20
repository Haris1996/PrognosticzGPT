from flask import Flask, request, Response, stream_with_context
import openai
import os
import threading
import time

# Initialize Flask and OpenAI API
app = Flask(__name__)
openai.api_key = "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"

# In-memory storage for user history
user_histories = {}
user_last_active = {}

# Time after which to expire user data (in seconds)
TIMEOUT = 20 * 60  # 20 minutes

# Max tokens for a conversation
MAX_TOKENS = 4096

def cleanup_expired_users():
    while True:
        current_time = time.time()
        expired_users = [user for user, last_active in user_last_active.items() if current_time - last_active > TIMEOUT]
        
        for user in expired_users:
            if user in user_histories:
                del user_histories[user]
            if user in user_last_active:
                del user_last_active[user]
        
        time.sleep(60)  # Check every minute

def get_gpt_response(user_id, question):
    def generate():
        # Update user last active time
        user_last_active[user_id] = time.time()

        # Retrieve the user's conversation history, or initialize it
        conversation_history = user_histories.get(user_id, [])

        # Simplified token count
        estimated_tokens = sum(len(msg["content"]) for msg in conversation_history)
        
        # Remove oldest messages if the conversation is too long
        while estimated_tokens + len(question) > MAX_TOKENS:
            removed_message = conversation_history.pop(0)
            estimated_tokens -= len(removed_message["content"])

        # Append new message to the history
        conversation_history.append({"role": "user", "content": question})

        # Make API call
        chat_completion = openai.ChatCompletion.create(
            model="gpt-3.5-turbo",
            messages=conversation_history,
            stream=True,
        )
        
        for token in chat_completion:
            content = token["choices"][0]["delta"].get("content")
            if content is not None:
                conversation_history.append({"role": "assistant", "content": content})
                yield content

        user_histories[user_id] = conversation_history

    return Response(stream_with_context(generate()), content_type='text/plain')

@app.route('/process_data', methods=['POST'])
def process_data():
    data = request.get_json()
    user_id = data.get("user_id", "default_user")
    question = data.get("question", "")
    return get_gpt_response(user_id, question)

if __name__ == '__main__':
    cleanup_thread = threading.Thread(target=cleanup_expired_users)
    cleanup_thread.start()
    app.run(host='0.0.0.0')
