from flask import Flask, request, session
from flask_socketio import SocketIO, emit
from google import genai
from google.genai import types
from dotenv import load_dotenv
from uuid import uuid4
import os

load_dotenv()

instrucoes = """
Você é um assistente virtual amigável e prestativo...
"""

client = genai.Client(api_key=os.getenv("GENAI_KEY"))

app = Flask(__name__)
app.secret_key = "uma_chave_secreta_muito_forte_padrao"
socketio = SocketIO(app, cors_allowed_origins="*")

active_chats = {}

def get_user_chat():
    # Verifica se a sessão do Flask já tem um session_id associado ao usuário
    if 'session_id' not in session:
        # Se não tiver, cria um novo identificador único usando uuid4 e armazena
        session['session_id'] = str(uuid4())
        print(f"Nova sessão Flask criada: {session['session_id']}")

    session_id = session['session_id']

    if session_id not in active_chats:
        print(f"Criando novo chat Gemini para session_id: {session_id}")
        try:
            chat_session = client.chats.create(
                model="gemini-2.0-flash",
                config=types.GenerateContentConfig(system_instruction=instrucoes)
            )
            active_chats[session_id] = chat_session
            print(f"Novo chat Gemini criado e armazenado para {session_id}")
        except Exception as e:
            app.logger.error(f"Erro ao criar chat Gemini para {session_id}: {e}")
            raise

    if session_id in active_chats and active_chats[session_id] is None:
        print(f"Recriando chat Gemini para session_id existente (estava None)")
        try:
            chat_session = client.chats.create(
                model="gemini-2.0-flash",
                config=types.GenerateContentConfig(system_instruction=instrucoes)
            )
            active_chats[session_id] = chat_session
        except Exception as e:
            app.logger.error(f"Erro ao recriar chat Gemini para {session_id}: {e}")
            raise

    return active_chats[session_id]

@socketio.on('connect')
def handle_connect():
    """
    Chamado quando um cliente se conecta via WebSocket.
    """
    print(f"Cliente conectado: {request.sid}")
    try:
        get_user_chat()
        user_session_id = session.get('session_id', 'N/A')
        print(f"Sessão Flask para {request.sid} usa session_id: {user_session_id}")
        emit('status_conexao', {'data': 'Conectado com sucesso!', 'session_id': user_session_id})
    except Exception as e:
        app.logger.error(f"Erro durante o evento connect para {request.sid}: {e}")
        emit('erro', {'erro': 'Falha ao inicializar a sessão de chat no servidor.'})

@socketio.on('enviar_mensagem')
def handle_enviar_mensagem(data): 
    try:
        mensagem_usuario = data.get("mensagem")
        app.logger.info(f"Mensagem recebida de {session.get('session_id', request.sid)}: {mensagem_usuario}")

        if not mensagem_usuario:
            emit('erro', {"erro": "Mensagem não pode ser vazia."})
            return

        user_chat = get_user_chat()
        if user_chat is None:
            emit('erro', {"erro": "Sessão de chat não pôde ser estabelecida."})
            return

        resposta_gemini = user_chat.send_message(mensagem_usuario)

        resposta_texto = (
            resposta_gemini.text
            if hasattr(resposta_gemini, 'text')
            else resposta_gemini.candidates[0].content.parts[0].text
        )

        emit('nova_mensagem', {"remetente": "bot", "texto": resposta_texto}, broadcast=False)
        app.logger.info(f"Resposta enviada para {session.get('session_id', request.sid)}")
    except Exception as e:
        app.logger.error(f"Erro ao processar 'enviar_mensagem' para {session.get('session_id', request.sid)}: {e}")
        emit('erro', {"erro": f"Ocorreu um erro no servidor: {str(e)}"})

@socketio.on('disconnect')
def handle_disconnect():
    print(f"Cliente desconectado: {request.sid}, session_id: {session.get('session_id', 'desconhecida')}")

if __name__ == "__main__":
    socketio.run(app, debug=True)
