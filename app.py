import os
import datetime
import json
import ollama
from rich.console import Console
from rich.panel import Panel

console = Console()
ARQUIVO_HISTORICO = "historico_nexus.json"
MODELO_IA = 'llama3.2:1b'  # Defina o modelo aqui (ex: 'qwen2.5-coder:3b' ou 'llama3.2:1b')

# =====================================================================
# FUNÇÕES DE SUPORTE E SEGURANÇA DE DADOS
# =====================================================================

def iniciar_historico():
    return [{
        "role": "system", 
        "content": (
            "Você é a nexusIA, um assistente de terminal objetivo.\n"
            "Se decidir usar uma ferramenta, responda APENAS com o JSON da função, sem textos extras."
        )
    }]

def garantir_dicionario_puro(mensagem_ollama) -> dict:
    """Conserta o bug de serialização convertendo objetos Message em dicionários puros."""
    if isinstance(mensagem_ollama, dict):
        return mensagem_ollama
    
    dados_puros = {
        "role": str(mensagem_ollama.role),
        "content": str(mensagem_ollama.content or "")
    }
    
    if hasattr(mensagem_ollama, 'tool_calls') and mensagem_ollama.tool_calls:
        dados_puros["tool_calls"] = []
        for call in mensagem_ollama.tool_calls:
            if hasattr(call, 'function'):
                dados_puros["tool_calls"].append({
                    "function": {
                        "name": str(call.function.name),
                        "arguments": call.function.arguments
                    }
                })
            else:
                dados_puros["tool_calls"].append(dict(call))
                
    return dados_puros

def carregar_historico_salvo():
    if os.path.exists(ARQUIVO_HISTORICO):
        try:
            with open(ARQUIVO_HISTORICO, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return iniciar_historico()
    return iniciar_historico()

def salvar_historico_no_disco(historico):
    try:
        with open(ARQUIVO_HISTORICO, "w", encoding="utf-8") as f:
            json.dump(historico, f, indent=4, ensure_ascii=False)
    except Exception as e:
        console.print(f"[bold red]Erro ao salvar histórico: {e}[/bold red]")

# =====================================================================
# Mecanismo de Inteligência: COMPRESSÃO DE MEMÓRIA (Sua Ideia!)
# =====================================================================

def verificar_e_resumir_historico():
    """Se o histórico ficar muito longo, pede para a IA resumir tudo em 3 parágrafos e reinicia o contexto."""
    global historico_conversa
    
    # 10 prompts do usuário equivalem a cerca de 20~25 mensagens no histórico total (incluindo respostas e ferramentas)
    if len(historico_conversa) > 20:
        console.print("[bold yellow]🧠 nexusIA comprimindo memória para manter a eficiência técnica...[/bold yellow]")
        try:
            # Monta o texto legível da conversa para enviar como tarefa de resumo
            conversa_texto = ""
            for msg in historico_conversa[1:]:
                autor = "Usuário" if msg['role'] == 'user' else "nexusIA"
                conversa_texto += f"{autor}: {msg['content']}\n"
            
            prompt_resumo = (
                f"Resuma a seguinte conversa entre o Usuário e a IA em exatamente 3 parágrafos objetivos. "
                f"Guarde dados vitais como o nome do usuário (Lucas) e o projeto atual (nexusIA):\n\n{conversa_texto}"
            )
            
            resposta_resumo = ollama.chat(
                model=MODELO_IA,
                messages=[{"role": "user", "content": prompt_resumo}]
            )
            
            resumo_texto = resposta_resumo['message'].content
            
            # Reseta a lista e injeta o resumo compactado como nova diretriz
            historico_conversa = iniciar_historico()
            historico_conversa.append({
                "role": "system",
                "content": f"Contexto Compactado das conversas anteriores (Trate como fatos reais):\n{resumo_texto}"
            })
            salvar_historico_no_disco(historico_conversa)
            console.print("[bold green]✅ Memória otimizada com sucesso![/bold green]")
            
        except Exception as e:
            console.print(f"[bold red]Falha ao otimizar memória: {e}[/bold red]")

# =====================================================================
# FERRAMENTAS DO SISTEMA
# =====================================================================

def obter_data_hora() -> str:
    return datetime.datetime.now().strftime("%d/%m/%Y às %H:%M:%S")

def criar_arquivo(nome: str, conteudo: str) -> str:
    try:
        with open(nome, "w", encoding="utf-8") as f:
            f.write(conteudo)
        return f"Sucesso: O arquivo '{nome}' foi criado fisicamente no computador."
    except Exception as e:
        return f"Erro ao criar o arquivo: {e}"

ferramentas_disponiveis = [
    {
        'type': 'function',
        'function': {
            'name': 'obter_data_hora',
            'description': 'Use sempre que o usuário perguntar as horas, o dia ou a data atual.',
            'parameters': {'type': 'object', 'properties': {}}
        }
    },
    {
        'type': 'function',
        'function': {
            'name': 'criar_arquivo',
            'description': 'Use exclusivamente quando for solicitado criar ou salvar um arquivo físico.',
            'parameters': {
                'type': 'object',
                'properties': {
                    'nome': {'type': 'string'},
                    'conteudo': {'type': 'string'}
                },
                'required': ['nome', 'conteudo']
            }
        }
    }
]

# =====================================================================
# FLUXO PRINCIPAL DO PROJETO
# =====================================================================

historico_conversa = carregar_historico_salvo()

def enviar_mensagem_local(pergunta: str) -> str:
    global historico_conversa
    historico_conversa.append({"role": "user", "content": pergunta})
    
    try:
        response = ollama.chat(
            model=MODELO_IA,
            messages=historico_conversa,
            tools=ferramentas_disponiveis,
            options={'temperature': 0.1}
        )
        
        conteudo_resposta = response['message'].get('content', '')
        tool_calls = response['message'].get('tool_calls', [])
        
        # Interceptador caso o modelo exiba o JSON como texto puro na tela
        if not tool_calls and '{"name":' in conteudo_resposta:
            try:
                json_limpo = conteudo_resposta.replace("```json", "").replace("```", "").strip()
                dados_funcao = json.loads(json_limpo)
                tool_calls = [{'function': dados_funcao}]
            except Exception:
                pass

        if tool_calls:
            # Converte a mensagem da IA para formato limpo antes de salvar
            historico_conversa.append(garantir_dicionario_puro(response['message']))
            
            for call in tool_calls:
                nome_funcao = call['function']['name']
                argumentos = call['function']['arguments']
                
                console.print(f"[bold yellow]⚙️ [Python] Executando: {nome_funcao}()...[/bold yellow]")
                
                if nome_funcao == 'obter_data_hora':
                    resultado = obter_data_hora()
                elif nome_funcao == 'criar_arquivo':
                    txt_conteudo = argumentos.get('conteudo', '')
                    if isinstance(txt_conteudo, dict):
                        txt_conteudo = txt_conteudo.get('description', str(txt_conteudo))
                    resultado = criar_arquivo(argumentos.get('nome', 'arquivo.txt'), txt_conteudo)
                else:
                    resultado = "Função inválida."
                
                historico_conversa.append({
                    'role': 'tool',
                    'content': resultado,
                    'name': nome_funcao
                })
            
            resposta_final = ollama.chat(model=MODELO_IA, messages=historico_conversa)
            historico_conversa.append(garantir_dicionario_puro(resposta_final['message']))
            
            verificar_e_resumir_historico() # Verifica se atingiu o limite de memória
            salvar_historico_no_disco(historico_conversa)
            return resposta_final['message']['content']
        
        # Fluxo de texto convencional
        historico_conversa.append(garantir_dicionario_puro(response['message']))
        verificar_e_resumir_historico() # Verifica se atingiu o limite de memória
        salvar_historico_no_disco(historico_conversa)
        return conteudo_resposta
        
    except Exception as e:
        return f"Erro no motor da IA: {e}"

def main():
    global historico_conversa
    console.print("[bold magenta]🚀 nexusIA v6.0 (Gerenciamento de Contexto Ativo) Iniciada![/bold magenta]")
    console.print("----------------------------------------------------------------------")

    while True:
        try:
            user_input = console.input("\n[bold green]Você > [/bold green]").strip()

            if user_input.lower() in ['sair', 'exit', 'quit']:
                console.print("[yellow]Até a próxima![/yellow]")
                break

            if not user_input:
                continue

            if user_input.lower() == '/limpar':
                historico_conversa = iniciar_historico()
                if os.path.exists(ARQUIVO_HISTORICO):
                    os.remove(ARQUIVO_HISTORICO)
                console.print("[bold yellow]🧹 Histórico resetado fisicamente![/bold yellow]")
                continue

            with console.status("[bold cyan]nexusIA processando...[/bold cyan]", spinner="dots"):
                resposta = enviar_mensagem_local(user_input)

            console.print(Panel(resposta, title="nexusIA (Agente)", border_style="cyan", expand=False))

        except KeyboardInterrupt:
            console.print("\n[yellow]Encerrando...[/yellow]")
            break

if __name__ == "__main__":
    main()