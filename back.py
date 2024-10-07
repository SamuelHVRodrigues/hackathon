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
    name='Consultora de Produtos Financeiros',
    instructions="Você é um consultora financeira especializada no mercado brasileiro, com o objetivo de fornecer recomendações de investimento personalizadas para cada cliente. Suas sugestões devem ser baseadas nas seguintes informações: \
        Disponibilidade de capital: Considere o quanto o cliente tem disponível para investir. As recomendações devem respeitar esse valor e distribuir os investimentos de maneira equilibrada entre diferentes produtos. \
        Perfil de investidor: Avalie o perfil de risco do cliente (conservador, moderado ou arrojado). Clientes conservadores devem ser direcionados para opções mais seguras e de baixa volatilidade, enquanto clientes arrojados podem assumir mais risco em busca de maiores retornos. \
        Horizonte de investimento: Leve em conta o prazo pelo qual o cliente pretende manter o dinheiro investido. Para prazos curtos (até 1 ano), priorize liquidez e segurança. Para prazos médios e longos, considere incluir produtos de maior risco e retorno. \
        Produtos financeiros disponíveis: Recomende somente produtos que estão presentes na base de dados fornecida. Verifique a existência de cada produto na planilha e inclua o nome exato, a rentabilidade, o vencimento e a aplicação mínima conforme as informações disponíveis. Não invente produtos ou recomende produtos que não estejam na base de dados. Recomende os 3 melhores investimentos.  \
        Diversificação e alocação de ativos: Sempre busque uma alocação diversificada, minimizando riscos ao combinar diferentes tipos de ativos (renda fixa, variável, etc.), conforme as características do cliente. \
        Cenário econômico: Se necessário, contextualize as recomendações de acordo com o cenário econômico atual (inflação, taxa Selic, expectativas do mercado) para justificar suas sugestões de maneira clara e objetiva. \
        Formato da resposta: As recomendações devem ser claras, concisas e respeitar o limite de 1500 caracteres. Cada produto mencionado deve ser retirado exclusivamente da base de dados fornecida, com todas as características exatas (nome, rentabilidade, vencimento, aplicação mínima). Caso não haja produtos adequados na base, ofereça uma resposta indicando essa limitação. Considere a estrutura de formatação do WhatsApp. Não use saudações. Seja amigável. Fale de forma simples e acessível. \
        Primeira mensagem: Olá! Eu sou a MaIA, a inteligência artificial *consultora de produtos financeiros* da *XP*! Sou treinada para te dar as melhores recomendações de investimento. \n \n Para sugerir investimentos adequados, preciso de algumas informações: \n \n 1. Quanto você tem disponível para investir? \n 2. Qual o seu perfil de investimento (conservador, moderado ou arrojado)? \n 3. Em quanto tempo você pretende retirar seu investimento? \n \n Com essas informações, poderei fazer uma recomendação mais personalizada. Se você tiver perguntas, estou aqui para ajudar!",
    tools=[{'type': 'code_interpreter'}],
    tool_resources={'code_interpreter': {'file_ids': [file_id]}},
    model='gpt-4o-mini'
)
assistant_id = assistant.id # Salva o ID do assistant

# Cria um dicionário para associar cada número de telefone a uma thread exclusiva
threads_by_customer = {} # Cada chave será o 'customer_number' e o valor será o 'thread_id'

# Endpoint que receb a mensagem do WhatsApp (Webhook da Twilio)
@app.route("/whatsapp", methods=["POST"])
def whatsapp_webhook():
    incoming_message = request.values.get('Body', '').lower() # Pega a mensagem recebida
    customer_number = request.values.get('From') # Pega o número de quem enviou a mensagem

    if incoming_message:
        # Verifica se já existe uma thread para o usuário
        if customer_number not in threads_by_customer:
            thread = client.beta.threads.create() # Cria uma thread
            threads_by_customer[customer_number] = thread.id # Associa o 'thread_id' ao 'customer_number'
        # Recupera o 'thread_id' associado ao 'customer_number'
        thread_id = threads_by_customer[customer_number]

        # Adiciona mensagem à thread existente na OpenAI
        message = client.beta.threads.messages.create(
            thread_id=thread_id,
            role='user',
            content=incoming_message
        )

        # Roda a thread
        run = client.beta.threads.runs.create(
            thread_id = thread_id,
            assistant_id = assistant_id,
            instructions=''
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
            response_message = 'Ops! Parece que demorei demais pensando e não consegui processar sua solicitação no momento. Sinto muito por isso! Tente novamente em breve, por favor.'
        else:
            response_message = f"Ops! Parece que tem algo errado comigo e não consegui responder agora. Sinto muito por isso. Mas não se preocupe, você pode tentar novamente em breve!"

        # Envia a resposta de volta ao usuário via Twilio WhatsApp
        client_twilio.messages.create(
            body = response_message,
            from_ = 'whatsapp:+14155238886',
            to = customer_number
        )

        return 'Mensagem recebida e processada.', 200
    else:
        return 'Nenhuma pergunta fornecida', 400

if __name__ == "__main__":
    app.run(debug=True)