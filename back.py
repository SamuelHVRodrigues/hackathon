from flask import Flask, request, jsonify
import openai
from dotenv import load_dotenv, find_dotenv
import pandas as pd
import time

app = Flask(__name__)

# Carregar a base de dados que foi tratada em outro arquivo
df = pd.read_csv(r'############# PATH DO ARQUIVO #############')

# Carregar variáveis de ambiente
_ = load_dotenv(find_dotenv())

# Cria o client da openai
client = openai.Client()

# Passa o arquivo para a openai
file = client.files.create(
    file = open(r'############# PATH DO ARQUIVO #############', 'rb'),
    purpose='assistants'
)
file_id = file.id # Salva o ID do arquivo

# Cria o assistant
assistant = client.beta.assistants.create(
    name='Consultor de Produtos Financeiros',
    instructions="############# INSERIR INSTRUÇÕES #############",
    tools=[{'type': 'code_interpreter'}],
    tool_resources={'code_interpreter': {'file_ids': [file_id]}},
    model='gpt-4o-mini'
)
assistant_id = assistant.id # Salva o ID do assistant

# Cria uma thread
thread = client.beta.threads.create()
thread_id = thread.id # Salva o ID da thread

# Requisição para a API da OpenAI
@app.route("/ask", methods=["POST"])
def ask_openai():
    data = request.json
    question = data.get("question", "")
    
    if question:
        # Adiciona mensagem à thread existente
        message = client.beta.threads.messages.create(
            thread_id=thread_id,
            role='user',
            content=question
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

        # Verifica o status para dar o retorno
        if run.status == 'completed':
            messages = client.beta.threads.messages.list(
                thread_id = thread_id
            )

            return jsonify({'answer': messages.data[0].content[0].text.value})
        elif run.status == 'in_progress':
            return jsonify({'answer': 'Erro na execução: O processamento demorou mais do que o esperado.'})
        else:
            answer = f"Erro na execução: Erro: {run.status}"
            return jsonify({'answer': answer})
    else:
        return jsonify({"error": "Nenhuma pergunta fornecida"}), 400

if __name__ == "__main__":
    app.run(debug=True)