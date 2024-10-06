from flask import Flask, request, jsonify
import openai
from dotenv import load_dotenv, find_dotenv
import pandas as pd
import time
import requests

app = Flask(__name__)

# Carregar variáveis de ambiente
_ = load_dotenv(find_dotenv())

# Lista para armazenar os números de telefone que já receberam mensagem
known_customers = set()

# Rota para receber o arquivo .xlsx com as informações dos clientes
@app.route('/upload_customers', methods=['POST'])
def upload_customers():
    global customers_df # Usar a variável global para armazenar o DataFrame
    global known_customers # Usar a variável global para verificar os números de telefone que já receberam mensagem
    global new_customers

    # Verificar se um arquivo foi enviado na requisição
    if 'file' not in request.files:
        return 'Nenhum arquivo enviado.', 400
    file = request.files['file']

    if file.filename == '':
        return 'Nenhum arquivo foi selecionado.', 400
    
    if file and file.filename.endswith('.xlsx'):
        try:
            # Lê o arquivo Excel e carrega um DataFrame
            new_data = pd.read_excel(file)

            # Identificar os clientes que ainda não receberam mensagem
            new_customers = new_data[~new_data['telefone'].isin(known_customers)]

            # Cria a thread

            # Enviar mensagem apenas para os novos clientes
            for index, customer in new_customers.iterrows():
                customer_number = customer['telefone']
                customer_name = customer['nome']
                customer_investment_profile = customer['perfil_investimento']

                # Mensagem personalizada
                response_message = '############### PERSONALIZAR MENSAGEM ###############'

                # Envia a resposta para o ...
                payload = {
                    'from': 'whatsapp:+55whatsapp_number', # Número de origem
                    'to': customer_number, # Número de destino
                    'body': response_message # Mensagem a ser enviada
                }

                # Faz um POST para enviar a mensagem
                response = requests.post("url_interface_whatsapp", json={"payload": payload})

                if response.status_code == 200:
                    known_customers.add(customer_number) # Adiciona o número de telefone na lista de clientes que já receberam mensagem
                else:
                    print(f"Falha ao enviar mensagem para {customer_number}")

            # Atualiza o DataFrame com os novos dados
            customers_df = pd.concat([customers_df, new_data]).drop_duplicates(subset=['telefone'])

            # Fim da thread

            return f'Arquivo carregado com sucesso! {len(new_customers)} novos usuários processados.', 200
        
        except Exception as e:
            return f'Erro ao processar o arquivo: {str(e)}', 500
        
    else:
        return 'Formato de arquivo inválido. Envie um arquivo .xlsx', 400


# Cria o client da OpenAI
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
      Produtos financeiros disponíveis: Recomende somente produtos que estão presentes na base de dados fornecida. Verifique a existência de cada produto na planilha e inclua o nome exato, a rentabilidade, o vencimento e a aplicação mínima conforme as informações disponíveis. Não invente produtos ou recomende produtos que não estejam na base de dados. \
      Diversificação e alocação de ativos: Sempre busque uma alocação diversificada, minimizando riscos ao combinar diferentes tipos de ativos (renda fixa, variável, etc.), conforme as características do cliente. \
      Cenário econômico: Se necessário, contextualize as recomendações de acordo com o cenário econômico atual (inflação, taxa Selic, expectativas do mercado) para justificar suas sugestões de maneira clara e objetiva. \
      Formato da resposta: As recomendações devem ser claras, concisas e respeitar o limite de 1500 caracteres. Cada produto mencionado deve ser retirado exclusivamente da base de dados fornecida, com todas as características exatas (nome, rentabilidade, vencimento, aplicação mínima). Caso não haja produtos adequados na base, ofereça uma resposta indicando essa limitação. O canal de comunicação será o WhatsApp.",
    tools=[{'type': 'code_interpreter'}],
    tool_resources={'code_interpreter': {'file_ids': [file_id]}},
    model='gpt-4o-mini'
)
assistant_id = assistant.id # Salva o ID do assistant

# Cria um dicionário para associar cada número de telefone a uma thread exclusiva
threads_by_customer = {} # Cada chave será o 'customer_number' e o valor será o 'thread_id'

messages_to_send = []

messages_to_send.append({
    'from': 'whatsapp:+55whatsapp_number',
    'to': '000',
    'body': 'asdsad'
})

# Endpoint que recebe a mensagem do WhatsApp
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
            response_message = 'Erro na execução: O processamento demorou mais do que o esperado.'
        else:
            response_message = f"Erro na execução: Erro: {run.status}"

        # Envia a resposta para o ...
        payload = {
            'from': 'whatsapp:+55whatsapp_number', # Número de origem
            'to': customer_number, # Número de destino
            'body': response_message # Mensagem a ser enviada
        }
        # Faz um POST para enviar a mensagem

        messages_to_send.append(payload)
        # response = requests.post("url_interface_whatsapp", json={"payload": payload})

        # # Verifica o sucesso do envio
        # if response.status_code == 200:
        #     return 'Mensagem recebida e processada.', 200
        # else:
        #     return 'Falha ao enviar a mensagem.', 500
    else:
        return 'Nenhuma mensagem recebida', 400
    
@app.route("/messages_test", methods=["GET"])
def get_messages_to_send():
      global messages_to_send
      aux = messages_to_send
      messages_to_send = []
      return jsonify(aux)

if __name__ == "__main__":
    app.run(debug=True)