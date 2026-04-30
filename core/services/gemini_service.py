from google import genai
from django.conf import settings

class GeminiService:
    def __init__(self):
        self.client = genai.Client(api_key=settings.GEMINI_API_KEY)

    def summarize_email_gemini(self, subject: str, body: str) -> str:
        prompt = f"""
        Você é um assistente de e-mails.

        Resuma o e-mail abaixo em até 3 frases, em português.
        Informe também se parece ser urgente.

        Assunto: {subject}

        Conteúdo:
        {body}
        """

        response = self.client.models.generate_content(
            model="gemini-2.5-flash-lite",
            contents=prompt,
        )

        return response.text
