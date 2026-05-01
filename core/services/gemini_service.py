from google import genai
from django.conf import settings
import json


class GeminiService:
    def __init__(self):
        self.client = genai.Client(api_key=settings.GEMINI_API_KEY)

    def summarize_email_gemini(self, subject: str, body: str) -> dict:
        prompt = f"""
        Você é um assistente inteligente de e-mails.

        Analise o e-mail abaixo e responda APENAS com JSON válido.
        Não use markdown.
        Não use ```json.

        Classifique o e-mail em UMA das categorias:
        - academico
        - trabalho
        - financeiro
        - pessoal
        - marketing
        - spam
        - evento
        - sistema
        - outro

        Formato obrigatório:
        {{
        "resumo": "resumo em até 3 frases",
        "urgente": true,
        "categoria": "academico"
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
        except json.JSONDecodeError:
            return {
                "resumo": response.text,
                "urgente": False,
                "categoria": "outro",
                "erro_parse": True,
            }
        except Exception:
            return {
                "resumo": response.text,
                "urgente": False,
                "erro_parse": True,
            }
