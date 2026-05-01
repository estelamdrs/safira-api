from google import genai
from django.conf import settings
import json


class GeminiService:
    def __init__(self):
        self.client = genai.Client(api_key=settings.GEMINI_API_KEY)

    def summarize_email_gemini(self, subject: str, body: str) -> dict:
        prompt = f"""
        Você é um assistente de e-mails.

        Analise o e-mail abaixo e responda em JSON válido com:
        - resumo: resumo em até 3 frases
        - urgente: true ou false

        NÃO explique nada fora do JSON.

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
