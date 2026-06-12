# Safira API

API desenvolvida para o TCC **Safira**, uma aplicação para organização inteligente de e-mails integrada ao Gmail.
A API é responsável por autenticar a conta Google, listar e-mails, aplicar marcadores, sugerir respostas e comparar análises geradas por modelos de linguagem.

## Tecnologias utilizadas

* Python
* Django
* Django REST Framework
* MySQL
* Gmail API
* Google OAuth 2.0
* Gemini API
* Ollama com modelo Llama 3.2

## Pré-requisitos

Antes de iniciar, instale:

* Python 3.12 ou superior
* MySQL
* Git
* Ollama
* Modelo `llama3.2`

## Clonando o repositório

```bash
git clone https://github.com/estelamdrs/safira-api.git
cd safira-api
```

## Criando o ambiente virtual

### Windows

```bash
python -m venv venv
venv\Scripts\activate
```

### Linux/macOS

```bash
python3 -m venv venv
source venv/bin/activate
```

## Instalando as dependências

```bash
pip install -r requirements.txt
```

## Configurando o banco de dados

Crie um banco MySQL local:

```sql
CREATE DATABASE safira_db CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
```

Depois, configure o arquivo `.env`.

## Variáveis de ambiente

Crie um arquivo `.env` na raiz do projeto com base no exemplo disponibilizado no arquivo `.env.example`.

As chaves `GOOGLE_CLIENT_ID`, `GOOGLE_CLIENT_SECRET` e `GEMINI_API_KEY` devem ser solicitadas à autora do projeto ou configuradas individualmente no Google Cloud/Gemini.

## Executando as migrations

```bash
python manage.py migrate
```

## Rodando o Ollama

Em um terminal separado, verifique se o modelo está instalado:

```bash
ollama list
```

Caso o modelo `llama3.2` não apareça, instale com:

```bash
ollama pull llama3.2
```

Para testar:

```bash
ollama run llama3.2
```

Depois de testar, saia com:

```text
/bye
```

## Rodando a API localmente

Com o ambiente virtual **ativado**:

```bash
python manage.py runserver
```

A API ficará disponível em:

```text
http://127.0.0.1:8000/api/
```

## Testando a API

Acesse no navegador:

```text
http://127.0.0.1:8000/api/health/
```

Resposta esperada:

```json
{
  "status": "ok",
  "message": "API do TCC funcionando com sucesso."
}
```

## Fluxo de autenticação Gmail

Para utilizar a integração com Gmail:

1. A API deve estar rodando em `http://127.0.0.1:8000`.
2. O front-end deve estar rodando em `http://127.0.0.1:5173`.
3. O e-mail do usuário precisa estar autorizado como usuário de teste no Google Cloud.
4. A URL de callback configurada no Google Cloud deve ser:

```text
http://127.0.0.1:8000/api/gmail/callback/
```

## Principais endpoints

### Health check

```http
GET /api/health/
```

### Autenticação Gmail

```http
GET /api/gmail/auth/
GET /api/gmail/callback/
GET /api/gmail/status/
POST /api/gmail/disconnect/
```

### E-mails

```http
GET /api/gmail/messages/
POST /api/gmail/messages/<message_id>/apply-label/
POST /api/gmail/messages/<message_id>/suggest-reply/
POST /api/gmail/messages/<message_id>/send-reply/
```

### LLM

```http
POST /api/llm/summarize-email/
POST /api/llm/summarize-email-llama/
POST /api/llm/compare-email/
POST /api/llm/register-preference/
GET /api/llm/stats/
```

## Observações importantes

* O arquivo `.env` não deve ser enviado ao GitHub.
* As chaves de API devem ser mantidas em segredo.
* O Gmail OAuth só funcionará para e-mails adicionados como usuários de teste no Google Cloud, caso o app ainda esteja em modo de teste.
* O Gemini pode apresentar erro de cota caso o limite gratuito seja atingido.
* O Llama depende do Ollama rodando localmente.

## Problemas comuns

### Erro de autenticação Gmail

Verifique:

* se o e-mail está cadastrado como usuário de teste;
* se `GOOGLE_REDIRECT_URI` está igual à URL cadastrada no Google Cloud;
* se a API está rodando na porta `8000`;
* se o front-end está rodando na porta `5173`.

### Erro ao usar Llama

Verifique se o Ollama está rodando:

```bash
curl http://localhost:11434/api/tags
```

Resposta esperada: uma lista contendo o modelo `llama3.2`.

### Erro de cota no Gemini

Caso apareça erro `429 RESOURCE_EXHAUSTED`, significa que a cota da API Gemini foi atingida. Nesse caso, aguarde a liberação da cota ou utilize a aba Llama para continuar os testes.
