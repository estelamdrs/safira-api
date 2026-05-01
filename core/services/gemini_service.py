from google import genai
from django.conf import settings
import json


class GeminiService:
    def __init__(self):
        self.client = genai.Client(api_key=settings.GEMINI_API_KEY)

    def summarize_email_gemini(self, subject: str, body: str) -> dict:
        prompt = f"""
        Você é um assistente de e-mails.

        Responda APENAS com JSON válido.
        Não use markdown.
        Não use ```json.

        Exemplo de formato obrigatório:
        {{
          "resumo": "resumo em até 3 frases",
          "urgente": true
        }}

        Assunto: {subject}

        Conteúdo:
        {body}
        """

        response = self.client.models.generate_content(
            model="gemini-2.5-flash-lite",
            contents=prompt,
        )

        try:
            return json.loads(response.text)
        except Exception:
            return {
                "resumo": response.text,
                "urgente": False,
                "erro_parse": True,
            }
