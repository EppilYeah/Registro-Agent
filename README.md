# REGISTRO - Agent

> **Nota:** Este é um projeto pessoal desenvolvido inteiramente para fins de aprendizado e diversão. É o meu primeiro grande projeto em Python, criado para explorar interações de voz, manipulação de áudio em tempo real e integração com LLMs.

## Sobre o Projeto

O **REGISTRO** não é apenas um assistente virtual comum. Ele foi projetado pra portar substancialmente qualquer personalidade que você coloque no prompt, basta alterar o prompt principal dele no config.py

O diferencial deste projeto é a integração entre uma interface visual reativa, síntese de voz com pós-processamento de áudio para dar um tom robótico e um cérebro híbrido (Groq → Gemini → Ollama CPU).

## Configuração rápida (.env na raiz)

```
GROQ_API_KEY=gsk_...
GEMINI_API_KEY=...
```

Chave Groq: [console.groq.com/keys](https://console.groq.com/keys). Várias chaves Gemini no mesmo projeto Google Cloud **não** somam cota.


## Funcionalidades Principais

* **Personalidade via LLM:** Groq (comando + tools) como cérebro do dia, Gemini Flash quando houver cota, Ollama 8B **só na CPU** se os dois derem 429.
* **Interface Visual Reativa:** Uma GUI construída com `CustomTkinter` que desenha um rosto procedural. As expressões (olhos, sobrancelhas e boca) reagem em tempo real às emoções detectadas na resposta da IA (neutro, irritado, feliz, desconfiado, etc.),
 eventualmente irei atualizar para animações em JavaScript
* **Manipulação de Áudio Avançada:**
    * **Input:** Detecção de "Wake Word" ("Registro") usando `Vosk` (offline) para baixa latência.
    * **Output:** Síntese de voz via `EdgeTTS`, passando por uma cadeia de efeitos analógicos (Chorus, PitchShift, Reverb) usando a biblioteca `Pedalboard` para criar uma voz sintética.
* **Automação de Sistema:** O agente possui ferramentas ("Function Calling") para controlar o PC:
    * Ajustar volume do sistema.
    * Controlar mídia (pausar/tocar).
    * Abrir WhatsApp Web.
    * Agendar lembretes com temporizadores reais.
  tambem pretendo expandir esse leque de ferramentas.

## Estrutura do Código

O projeto está modularizado para facilitar o entendimento:

* **main.py:** O loop principal que gerencia as threads de áudio e a interface visual.
* **app/core/brain.py:** Roteador Groq → Gemini → Ollama CPU, memória e function calling. Cota Gemini é por projeto, não por chave.
* **app/core/audio.py:** O módulo mais complexo. Lida com reconhecimento de fala (SpeechRecognition + Vosk), VAD (Voice Activity Detection) para permitir interrupções durante a fala da IA, e o processamento de efeitos sonoros.
* **app/gui/face.py:** Desenha o rosto do assistente pixel a pixel usando Canvas, com física simples de animação para transições suaves entre emoções.
* **app/services/system.py:** Executa os comandos reais no Windows (PyAutoGUI, PyCaw).

> Como este é um projeto de aprendizado ("Learning by doing"), o código pode conter lógicas experimentais. Sinta-se à vontade para explorar, modificar e abrir Issues com sugestões.
