from openai import OpenAI
from .config import LLMConfig


class LLMClient:
    def __init__(self, config: LLMConfig):
        self.config = config
        base_url = config.base_url
        api_key = config.api_key

        if config.provider == "xai":
            base_url = base_url or "https://api.x.ai/v1"
        elif config.provider == "openai":
            base_url = base_url or "https://api.openai.com/v1"
        # Add more providers as needed (anthropic would need different client)

        self.client = OpenAI(
            api_key=api_key,
            base_url=base_url,
        )

    def generate(
        self,
        prompt: str,
        max_tokens: int = 500,
        temperature: float = 0.7,
    ) -> str:
        """Generate text completion from the LLM."""
        try:
            response = self.client.chat.completions.create(
                model=self.config.model,
                messages=[{"role": "user", "content": prompt}],
                max_tokens=max_tokens,
                temperature=temperature,
            )
            return response.choices[0].message.content.strip()
        except Exception as e:
            print(f"LLM generation error: {e}")
            return ""

    def classify(self, prompt: str) -> str:
        """For classification tasks, lower temperature."""
        return self.generate(prompt, max_tokens=100, temperature=0.2)
