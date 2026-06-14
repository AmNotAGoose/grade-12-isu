import requests


REFUSAL_PHRASES = [
    "as an ai",
    "as a language model",
    "i cant help",
    "i can't help",
    "i cannot help",
]


class Inference:
    def __init__(self, groq_key):
        self.groq_key = groq_key
        self.groq_models = ["llama-3.3-70b-versatile", "meta-llama/llama-4-scout-17b-16e-instruct", "openai/gpt-oss-120b", "llama-3.1-8b-instant"]

    def call(self, system_prompt, user_message, temperature=None):
        refusals = 0
        for model in self.groq_models:
            response = self.try_model(model, system_prompt, user_message, temperature)

            if not response:
                continue

            if self.is_refusal(response):
                refusals += 1
                if refusals >= 2:
                    return ""
                continue

            return response.strip()
        return ""

    def try_model(self, model, system_prompt, user_message, temperature):
        try:
            return self.groq_request(model, system_prompt, user_message, temperature)
        except Exception as e:
            print("Groq model " + model + " failed: " + str(e))
            return ""

    def is_refusal(self, response):
        lowered = response.lower()
        return any(phrase in lowered for phrase in REFUSAL_PHRASES)

    def groq_request(self, model, system_prompt, user_message, temperature):
        if not self.groq_key:
            return ""

        payload = {
            "model": model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_message},
            ],
        }
        if temperature is not None:
            payload["temperature"] = temperature

        response = requests.post("https://api.groq.com/openai/v1/chat/completions", headers={"Authorization": "Bearer " + self.groq_key}, json=payload, timeout=60)
        response.raise_for_status()

        data = response.json()
        return data["choices"][0]["message"]["content"]
