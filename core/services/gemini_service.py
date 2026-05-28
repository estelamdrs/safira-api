from google import genai
from django.conf import settings
import json


class GeminiService:
    def __init__(self):
        self.client = genai.Client(api_key=settings.GEMINI_API_KEY)

    def summarize_email_gemini(
        self,
        subject: str,
        body: str,
        existing_labels: list[str] | None = None
    ) -> dict:
        existing_labels = existing_labels or []
        labels_text = "\n".join(f"- {label}" for label in existing_labels)

        prompt = f"""
        Você é a Safira, uma assistente inteligente de organização de e-mails.

        Sua função é analisar o conteúdo de um e-mail e produzir uma resposta estruturada para ajudar o usuário a entender, priorizar e organizar sua caixa de entrada.

        Marcadores já existentes no Gmail do usuário:
        {labels_text if labels_text else "- Nenhum marcador personalizado encontrado."}

        Regras gerais:
        - Responda APENAS com JSON válido.
        - Não use markdown.
        - Não use ```json.
        - Não invente informações que não estejam no e-mail.
        - Se alguma informação não estiver clara, indique isso no campo adequado.
        - Use linguagem objetiva, profissional e em português do Brasil.
        - Se algum marcador existente combinar semanticamente com o e-mail, reutilize esse marcador exatamente como escrito.
        - Se nenhum marcador existente fizer sentido, sugira um novo marcador curto e claro.
        - Não crie marcador novo se um existente já representar bem o assunto.
        - Se o e-mail não possui conteúdo textual relevante e contém anexos, classifique como "arquivos" e sugira o marcador "Arquivos".
        - Não tente inferir o conteúdo interno dos anexos, pois eles não foram lidos.

        Critérios de análise:
        1. Resumo:
        - Gere um resumo claro em até 3 frases.
        - Destaque o objetivo principal do e-mail.
        - Se houver prazo, compromisso, solicitação ou alerta, mencione no resumo.

        2. Urgência:
        - Considere urgente apenas quando houver prazo próximo, risco de perda de acesso, cobrança, solicitação de ação imediata, problema técnico, confirmação necessária ou impacto relevante para o usuário.
        - Se não houver indicação clara de urgência, marque como false.
        - Explique o motivo da decisão em uma frase curta.

        3. Categoria:
        Classifique o e-mail em UMA das categorias abaixo:
        - academico: assuntos de faculdade, TCC, orientação, pesquisa, artigos, aulas, atividades acadêmicas, eventos universitários.
        - trabalho: atividades profissionais, reuniões, demandas, projetos, compartilhamento de documentos de trabalho.
        - financeiro: pagamentos, cobranças, notas fiscais, bancos, compras, faturas, recibos.
        - pessoal: mensagens pessoais, família, amigos, assuntos não profissionais.
        - marketing: promoções, newsletters, campanhas, ofertas, divulgação comercial.
        - spam: conteúdo suspeito, irrelevante, repetitivo, golpe, phishing ou mensagens sem utilidade clara.
        - evento: convites, confirmação de presença, agenda, reuniões, webinars, datas marcadas.
        - sistema: alertas automáticos, notificações de login, segurança, alterações de conta, sistemas e plataformas.
        - arquivos: e-mails cujo conteúdo principal é envio, recebimento ou compartilhamento de arquivos/anexos/documentos.
        - outro: quando nenhuma categoria acima se aplica com segurança.

        4. Decisão:
        - A categoria deve representar o objetivo principal do e-mail, não apenas palavras soltas.
        - Se o e-mail for automático de plataforma, mas tratar de segurança/login, use "sistema".
        - Se o e-mail envolver TCC, orientação, universidade ou pesquisa, priorize "academico".
        - Se o e-mail for principalmente compartilhamento de arquivo, pasta, documento ou anexo, use "arquivos", salvo se houver contexto acadêmico ou financeiro mais forte.

        Formato obrigatório:
        {{
        "resumo": "resumo em até 3 frases",
        "urgente": true,
        "motivo_urgencia": "explique em uma frase curta por que é urgente ou por que não é",
        "categoria": "academico",
        "confianca": 0.95,
        "justificativa_categoria": "explique em uma frase curta por que essa categoria foi escolhida",
        "gmail_label": "nome do marcador escolhido ou sugerido",
        "usar_label_existente": true
        }}

        E-mail para análise:

        Assunto: {subject}

        Conteúdo:
        {body}
        """

        response = self.client.models.generate_content(
            model="gemini-2.5-flash-lite",
            contents=prompt,
        )

        text = response.text.strip()
        text = text.replace("```json", "").replace("```", "").strip()

        try:
            return json.loads(response.text)
        except Exception:
            return {
                "resumo": response.text,
                "urgente": False,
                "motivo_urgencia": "Não foi possível determinar",
                "categoria": "outro",
                "erro_parse": True,
            }

    def suggest_email_reply_gemini(self, subject, body):
        prompt = f"""
        Você é uma assistente inteligente de e-mails.

        Sua tarefa é sugerir uma resposta educada, objetiva e coerente
        para o e-mail abaixo.

        Regras:
        - Responda apenas com JSON válido
        - Não use markdown
        - Não use ```json
        - A resposta deve soar natural e humana
        - Se o e-mail for acadêmico, mantenha tom formal
        - Se o e-mail for pessoal, o tom pode ser mais leve
        - Nunca invente informações que não estejam no e-mail
        - Se o e-mail não exigir resposta, informe isso

        Formato obrigatório:
        {{
        "needs_reply": true,
        "suggested_reply": "texto da resposta sugerida"
        }}

        Assunto:
        {subject}

        Conteúdo:
        {body}
        """

        response = self.client.models.generate_content(
            model="gemini-2.5-flash-lite",
            contents=prompt,
        )

        cleaned_text = (
            response.text
            .replace("```json", "")
            .replace("```", "")
            .strip()
        )

        return json.loads(cleaned_text)