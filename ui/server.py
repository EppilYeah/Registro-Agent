from flask import Flask, render_template
from flask_socketio import SocketIO
import threading
import time

app = Flask(__name__)
app.config['SECRET_KEY'] = 'segredo_do_registro'
socketio = SocketIO(app)

@app.route('/')
def index():
    return render_template('index.html')

def teste_conexao():
    while True:
        time.sleep(5)
        print("[UI] Teste: enviando 'falando'")
        socketio.emit('mudar_estado', {'emocao': 'falando'})
        
        time.sleep(5)
        print("[UI] Teste: enviando 'neutro'")
        socketio.emit('mudar_estado', {'emocao': 'neutro'})

if __name__ == '__main__':
    threading.Thread(target=teste_conexao, daemon=True).start()
    
    socketio.run(app, debug=True)