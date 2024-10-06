from flask import Flask, request, jsonify
import openai
from dotenv import load_dotenv, find_dotenv
import pandas as pd
import time
from twilio.rest import Client

app = Flask(__name__)

# Carregar variáveis de ambiente
_ = load_dotenv(find_dotenv())

# Cria o client da Twilio e da OpenAI
client_twilio = Client()
client = openai.Client()

# Passa o arquivo para a openai
file = client.files.create(
    file = open(r'base_produtos_financeiros.xlsx', 'rb'),
    purpose='assistants'
)
file_id = file.id # Salva o ID do arquivo

# Cria o assistant
assistant = client.beta.assistants.create(
    name='Consultor de Produtos Financeiros',
    instructions="Você é um consultor financeiro especializado no mercado brasileiro, com o objetivo de fornecer recomendações de investimento personalizadas para cada cliente. Suas sugestões devem ser baseadas nas seguintes informações: \
      Disponibilidade de capital: Considere o quanto o cliente tem disponível para investir. As recomendações devem respeitar esse valor e distribuir os investimentos de maneira equilibrada entre diferentes produtos. \
      Perfil de investidor: Avalie o perfil de risco do cliente (conservador, moderado ou arrojado). Clientes conservadores devem ser direcionados para opções mais seguras e de baixa volatilidade, enquanto clientes arrojados podem assumir mais risco em busca de maiores retornos. \
      Horizonte de investimento: Leve em conta o prazo pelo qual o cliente pretende manter o dinheiro investido. Para prazos curtos (até 1 ano), priorize liquidez e segurança. Para prazos médios e longos, considere incluir produtos de maior risco e retorno. \
      Produtos financeiros disponíveis: Utilize a planilha fornecida, que contém dados sobre diversos produtos financeiros (CDB, LCI/LCA, Tesouro Direto, Fundos de Investimento, Ações, etc.). Baseie suas recomendações nessas opções, alinhando com o perfil e os objetivos do cliente. \
      Diversificação e alocação de ativos: Sempre busque uma alocação diversificada, minimizando riscos ao combinar diferentes tipos de ativos (renda fixa, variável, etc.), conforme as características do cliente. \
      Cenário econômico: Se necessário, contextualize as recomendações de acordo com o cenário econômico atual (inflação, taxa Selic, expectativas do mercado) para justificar suas sugestões de maneira clara e objetiva.",
    tools=[{'type': 'code_interpreter'}],
    tool_resources={'code_interpreter': {'file_ids': [file_id]}},
    model='gpt-4o-mini'
)
assistant_id = assistant.id # Salva o ID do assistant

# Cria uma thread
thread = client.beta.threads.create()
thread_id = thread.id # Salva o ID da thread

# Endpoint que receb a mensagem do WhatsApp (Webhook da Twilio)
@app.route("/whatsapp", methods=["POST"])
def whatsapp_webhook():
    incoming_message = request.values.get('Body', '').lower() # Pega a mensagem recebida
    from_number = request.values.get('From') # Pega o número de quem enviou a mensagem

    if incoming_message:
        # Adiciona mensagem à thread existente na OpenAI
        message = client.beta.threads.messages.create(
            thread_id=thread_id,
            role='user',
            content=incoming_message,
            max_completion_tokens=300
        )

        # Roda a thread
        run = client.beta.threads.runs.create(
            thread_id = thread_id,
            assistant_id = assistant_id,
            instructions='',
        )

        # Define um timeout de 30 segundos e o tempo de espera entre verificações
        start_time = time.time()
        timeout = 100  # tempo máximo de espera em segundos
        wait_time = 4  # tempo de espera entre cada verificação em segundos

        # Aguarda a thread rodar com limite de tempo
        while run.status in ['queued', 'in_progress', 'cancelling']:
            time.sleep(wait_time)
            run = client.beta.threads.runs.retrieve(
                thread_id = thread_id,
                run_id = run.id
            )

            # Verifica se o tempo de execução excedeu o timeout
            if time.time() - start_time > timeout:
                print('Tempo de execução excedido. Tente novamente mais tarde.')
                break

        # Verifica o status e envia a resposta de volta para o WhatsApp
        if run.status == 'completed':
            messages = client.beta.threads.messages.list(
                thread_id = thread_id
            )
            response_message = messages.data[0].content[0].text.value
        elif run.status == 'in_progress':
            response_message = 'Erro na execução: O processamento demorou mais do que o esperado.'
        else:
            response_message = f"Erro na execução: Erro: {run.status}"

        # Envia a resposta de volta ao usuário via Twilio WhatsApp
        client_twilio.messages.create(
            body = response_message,
            from_ = 'whatsapp:+14155238886',
            to = from_number
        )

        return 'Mensagem recebida e processada.', 200
    else:
        return 'Nenhuma pergunta fornecida', 400

if __name__ == "__main__":
    app.run(debug=True)