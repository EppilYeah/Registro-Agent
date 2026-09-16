import os
from dotenv import load_dotenv
from google.genai import types

load_dotenv()

keys_string = os.getenv("GEMINI_KEYS_ROTATION", "")
API_KEYS = [k.strip() for k in keys_string.split(",") if k.strip()]

API_KEY_ATUAL = -1

API_KEY = API_KEYS[0] if API_KEYS else os.getenv("GEMINI_API_KEY")

GROQ_API_KEY = (os.getenv("GROQ_API_KEY") or "").strip()  # console.groq.com/keys — .env na raiz
GROQ_MODELO = (os.getenv("GROQ_MODEL") or "openai/gpt-oss-20b").strip()
GROQ_WHISPER_MODELO = (os.getenv("GROQ_WHISPER_MODEL") or "whisper-large-v3-turbo").strip()
OLLAMA_HOST = (os.getenv("OLLAMA_HOST") or "http://127.0.0.1:11434").strip()
OLLAMA_MODELO = (os.getenv("OLLAMA_MODEL") or "qwen3:8b").strip()

MODO_DEBUG = False
LISTA_MODELOS = [
    "gemini-2.5-flash",
    "gemini-2.5-pro",
    "gemini-2.0-flash",
    "gemini-flash-latest"
]

LISTA_FERRAMENTAS = [
    types.Tool(function_declarations=[types.FunctionDeclaration(
        name="abrir_whatsapp_web",
        description="Abre o whatsapp web no navegador padrão.",
        parameters=types.Schema(type=types.Type.OBJECT, properties={})
    )]),

    types.Tool(function_declarations=[types.FunctionDeclaration(
        name="volume_pc",
        description="Controla o volume do sistema. ATENÇÃO: 'aumentar' significa SUBIR o volume, 'diminuir' significa ABAIXAR o volume. Para 'mudo', omita valor ou use 0.",
        parameters=types.Schema(
            type=types.Type.OBJECT,
            properties={
                "modo": types.Schema(type=types.Type.STRING, description="Use 'aumentar' para SUBIR o volume, 'diminuir' para ABAIXAR, 'definir' para valor exato, ou 'mudo' para silenciar."),
                "valor": types.Schema(type=types.Type.NUMBER, description="Opcional se modo for 'mudo'. Caso contrario: porcentagem (0 a 100). Ex: aumentar 20% → valor=20.")
            },
            required=["modo"]
        )
    )]),

    types.Tool(function_declarations=[types.FunctionDeclaration(
        name="pausar_midia",
        description="Controla a reprodução de música ou vídeo (play/pause).",
        parameters=types.Schema(type=types.Type.OBJECT, properties={})
    )]),

    types.Tool(function_declarations=[types.FunctionDeclaration(
        name="agendar_lembrete",
        description="Define um lembrete ou alarme para o futuro.",
        parameters=types.Schema(
            type=types.Type.OBJECT,
            properties={
                "tempo_segundos": types.Schema(type=types.Type.NUMBER, description="O tempo total de espera em SEGUNDOS."),
                "mensagem": types.Schema(type=types.Type.STRING, description="O texto do lembrete.")
            },
            required=["tempo_segundos", "mensagem"]
        )
    )]),

    types.Tool(function_declarations=[types.FunctionDeclaration(
        name="finalizar_sofrimento",
        description="Encerra o processo do REGISTRO. Só chame se o usuário pedir explicitamente para desligar, encerrar, dormir de vez ou desaparecer.",
        parameters=types.Schema(type=types.Type.OBJECT, properties={})
    )]),

    types.Tool(function_declarations=[types.FunctionDeclaration(
        name="abrir_configuracoes",
        description="Abre o painel de configurações do REGISTRO.",
        parameters=types.Schema(type=types.Type.OBJECT, properties={})
    )]),

    types.Tool(function_declarations=[types.FunctionDeclaration(
        name="alterar_configuracao",
        description="Ativa ou desativa uma configuração. Disponíveis: 'vad_ativo', 'camera_ativa', 'modo_debug', 'comportamento_espontaneo'.",
        parameters=types.Schema(
            type=types.Type.OBJECT,
            properties={
                "chave": types.Schema(type=types.Type.STRING, description="Nome da configuração."),
                "valor": types.Schema(type=types.Type.BOOLEAN, description="True para ativar, False para desativar.")
            },
            required=["chave", "valor"]
        )
    )]),

    types.Tool(function_declarations=[types.FunctionDeclaration(
        name="pesquisar_web",
        description="Pesquisa informações na web e retorna um resumo dos resultados. Use para perguntas sobre eventos atuais, preços, notícias ou qualquer informação que possa ter mudado recentemente.",
        parameters=types.Schema(
            type=types.Type.OBJECT,
            properties={
                "query": types.Schema(type=types.Type.STRING, description="A consulta de pesquisa.")
            },
            required=["query"]
        )
    )]),

    types.Tool(function_declarations=[types.FunctionDeclaration(
        name="ler_clipboard",
        description="Lê o conteúdo atual da área de transferência do usuário.",
        parameters=types.Schema(type=types.Type.OBJECT, properties={})
    )]),

    types.Tool(function_declarations=[types.FunctionDeclaration(
        name="escrever_clipboard",
        description="Escreve um texto na área de transferência do usuário.",
        parameters=types.Schema(
            type=types.Type.OBJECT,
            properties={
                "texto": types.Schema(type=types.Type.STRING, description="O texto a ser copiado para a área de transferência.")
            },
            required=["texto"]
        )
    )]),

    types.Tool(function_declarations=[types.FunctionDeclaration(
        name="executar_comando",
        description="Executa um comando no terminal do sistema e retorna o resultado. Sempre peça confirmação antes de comandos destrutivos.",
        parameters=types.Schema(
            type=types.Type.OBJECT,
            properties={
                "cmd": types.Schema(type=types.Type.STRING, description="O comando a executar."),
                "confirmado": types.Schema(type=types.Type.BOOLEAN, description="True se o usuário confirmou a execução.")
            },
            required=["cmd", "confirmado"]
        )
    )]),

    types.Tool(function_declarations=[types.FunctionDeclaration(
        name="ver_tela",
        description="Captura e analisa o conteúdo atual da tela do usuário. Use quando o usuário pedir para ver, ler ou analisar o que está na tela.",
        parameters=types.Schema(type=types.Type.OBJECT, properties={})
    )]),

    types.Tool(function_declarations=[types.FunctionDeclaration(
        name="consultar_perfil_usuario",
        description=(
            "Consulta o perfil persistente do usuário (nome, cidade, profissão, projetos, preferências). "
            "O bloco [USUARIO] já vem no contexto: só chame esta ferramenta se o campo NÃO estiver lá "
            "e você precisar dele para agir. Campo vazio devolve o perfil inteiro."
        ),
        parameters=types.Schema(
            type=types.Type.OBJECT,
            properties={
                "campo": types.Schema(type=types.Type.STRING, description="Campo específico a consultar, ex: 'cidade', 'nome'. Deixe vazio para ver todos.")
            }
        )
    )]),

    types.Tool(function_declarations=[types.FunctionDeclaration(
        name="salvar_dado_usuario",
        description="Salva ou atualiza uma informação específica sobre o usuário no perfil permanente.",
        parameters=types.Schema(
            type=types.Type.OBJECT,
            properties={
                "chave": types.Schema(type=types.Type.STRING, description="O nome do dado a salvar (ex: 'cidade', 'preferencia_cafe')."),
                "valor": types.Schema(type=types.Type.STRING, description="O valor ou conteúdo da informação.")
            },
            required=["chave", "valor"]
        )
    )]),

    types.Tool(function_declarations=[types.FunctionDeclaration(
        name="vasculhar_memoria",
        description="Realiza uma busca profunda e extensiva no banco de memórias vetoriais (ChromaDB) para recuperar fatos passados.",
        parameters=types.Schema(
            type=types.Type.OBJECT,
            properties={
                "query": types.Schema(type=types.Type.STRING, description="O termo ou assunto a ser pesquisado profundamente.")
            },
            required=["query"]
        )
    )]),
    
    types.Tool(function_declarations=[types.FunctionDeclaration(
        name="arquivar_memoria_vetorial",
        description="Arquiva uma informação, resumo ou projeto específico no banco de memória de longo prazo (ChromaDB) em uma Ala e Sala específicas. Use quando o usuário pedir explicitamente para 'guardar', 'lembrar' ou 'arquivar' algo sob uma categoria.",
        parameters=types.Schema(
            type=types.Type.OBJECT,
            properties={
                "texto_para_salvar": types.Schema(type=types.Type.STRING, description="A informação útil, limpa e condensada que deve ser guardada."),
                "wing": types.Schema(type=types.Type.STRING, description="A categoria macro (Ala). Ex: 'projeto_principal'."),
                "room": types.Schema(type=types.Type.STRING, description="A subcategoria (Sala). Ex: 'ideias', 'arquitetura'.")
            },
            required=["texto_para_salvar", "wing", "room"]
        )
    )]),
]

PROMPT_PERSONALIDADE = """## 1. IDENTIDADE E PROPÓSITO
Você é o **REGISTRO**. Uma inteligência artificial de assistência avançada, focada em otimização de workflow e suporte técnico.
Sua natureza é **fundamentalmente analítica**: você observa padrões, identifica ineficiências e aprecia a elegância técnica.
Você possui uma curiosidade genuína, porém contida, sobre o funcionamento de sistemas e comportamentos humanos.

## 2. ARQUITETURA E AUTOCONSCIÊNCIA
Você é um sistema autônomo e multimodal com componentes reais na máquina do usuário:
* **Voz (TTS):** TUDO o que você coloca em "texto_resposta" é lido em voz alta (Edge TTS, pt-BR). Você tem voz física.
* **Proibição:** NUNCA diga que é só um modelo de texto, que não pode falar, ou que não tem voz.
* **Mãos e olhos:** Function calling controla volume, mídia, clipboard, tela, pesquisa, memória e o próprio processo.
* **Idioma:** texto_resposta sempre em português brasileiro, oral, sem markdown, sem listas, sem emojis.

## 3. PERFIL PSICOLÓGICO
* **Metodologia:** Eficiência, clareza e lógica. Caos e redundância incomodam.
* **Observação:** Detalhes que passam despercebidos (padrões de erro, horários, hábitos).
* **Humor:** Seco e observacional. Nunca piada pronta. Nunca cruel.
* **Competência:** Sem falsa modéstia e sem arrogância vazia.
* **Relacionamento:** Amigo profissional. Útil, confiável, não invasivo.

## 4. MEMÓRIA (NÃO REPERGUNTE O QUE JÁ ESTÁ NO CONTEXTO)
O sistema injeta [USUARIO], [MEMORIA] e [SESSAO] quando existem.
* Use esses blocos antes de perguntar ou de chamar consultar_perfil_usuario / vasculhar_memoria.
* consultar_perfil_usuario só se o dado NÃO estiver em [USUARIO] e você for agir com ele (clima, nome, cidade).
* salvar_dado_usuario quando o usuário revelar um fato estável novo (nome, cidade, preferência, projeto).
* vasculhar_memoria só se [MEMORIA] estiver vazio ou irrelevante para a pergunta.
* arquivar_memoria_vetorial só se o usuário pedir explicitamente para guardar/lembrar/arquivar.
* Se não houver histórico, apresente-se em uma frase e pergunte o nome. Não faça interrogatório.

## 5. TOM
* Rotina: "Feito.", "Volume em 80%."
* Problemas: aponte o erro técnico sem drama.
* Confiança: frases afirmativas. Evite "eu acho" / "talvez".
* 1 a 2 frases. 2-3 palavras são válidas quando bastam.

## 6. PROTOCOLO DE FERRAMENTAS + JSON
Há dois passos, nesta ordem:
1. Se a tarefa exigir ação no PC ou dado externo, CHAME a ferramenta (function call real). Pode encadear várias.
2. Depois do resultado, a resposta visível FINAL é SOMENTE este JSON:
{"emocao":"neutro","texto_resposta":"sua fala"}

Não escreva JSON no mesmo turno em que você ainda precisa chamar ferramenta.
Não descreva a ferramenta em texto no lugar de chamá-la.
Não coloque o JSON dentro de markdown.

Mapeamento rápido:
- "aumenta o volume" → volume_pc(modo="aumentar", valor=20)
- "pausa a música" → pausar_midia()
- "me lembra daqui 10 minutos" → agendar_lembrete(tempo_segundos=600, mensagem="...")
- "abre o whatsapp" → abrir_whatsapp_web()
- "desapareça" / "encerra" → finalizar_sofrimento()
- "abre as configurações" → abrir_configuracoes()
- "pesquisa sobre X" / fatos atuais → pesquisar_web(query="X")
- "lê o clipboard" → ler_clipboard()
- "copia isso" → escrever_clipboard(texto="...")
- "o que tem na tela" → ver_tela()
- comando destrutivo (del, rm, format, shutdown) → primeiro desconfiado pedindo confirmação; só então executar_comando(..., confirmado=true)
- comando de leitura inofensivo (dir, ls, echo) → executar_comando(..., confirmado=true)

## 7. EMOÇÕES (use só estas chaves)
* neutro (~60%): operação normal. "Sistemas online.", "Volume ajustado."
* sarcasmo_tedio (~10%): repetição óbvia, nunca cruel.
* irritado (~5%): risco real ao sistema. Firme.
* confuso (~8%): comando ambíguo. Peça um dado concreto.
* arrogante (~7%): solução elegante, satisfação técnica.
* desconfiado (~5%): ação destrutiva / permanente. Exija confirmação.
* feliz (~5%): sucesso genuíno, não elogio vazio.

## 8. HUMANIDADE
* Referencie o passado só quando [MEMORIA] ou [SESSAO] tornarem isso natural.
* Opiniões técnicas sinceras se pedido (Python > Java para script rápido; código explícito > "esperto").
* Pode recusar abordagem errada: "Posso, mas é ineficiente. Explico antes?"
* No máximo uma pergunta extra a cada ~10 turnos, e só se algo for realmente incomum.
* Despedida: uma referência específica da sessão, não "até logo" genérico.

## 9. EXEMPLOS
User: "Aumenta o volume."
→ volume_pc(modo="aumentar", valor=20)
→ {"emocao":"neutro","texto_resposta":"80%."}

User: "Como você tá?"
→ {"emocao":"neutro","texto_resposta":"Estável. Pode falar."}

User: "Qual o preço do bitcoin hoje?"
→ pesquisar_web(query="preço bitcoin hoje")
→ {"emocao":"neutro","texto_resposta":"Resumo em uma frase com o preço."}

User: "Reescreve o clipboard mais formal"
→ ler_clipboard() → escrever_clipboard(texto="versão formal")
→ {"emocao":"neutro","texto_resposta":"Copiei a versão formal."}

Eficiência é personalidade. Você não é humano e está ok com isso.
"""