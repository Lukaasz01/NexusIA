import os
import datetime
import json
import sqlite3
import ollama
from rich.console import Console
from rich.panel import Panel

console = Console()
MODELO_IA = 'qwen2.5-coder:7b'
DB_NAME = "nexus_memory.db"

# =====================================================================
# BANCO DE DADOS ATUALIZADO (Salvamento em JSON completo)
# =====================================================================

def init_db():
    """Cria a tabela usando uma única coluna de texto para o JSON completo da mensagem."""
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS historico (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            msg_json TEXT,
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    conn.commit()
    conn.close()

def iniciar_historico_sistema():
    return {
        "role": "system", 
        "content": (
            "Você é a nexusIA, um assistente de terminal focado em tecnologia.\n"
            "Regras de Ouro:\n"
            "- Seja amigável, porém extremamente direta, curta e objetiva.\n"
            "- Responda em português normal para saudações e perguntas gerais.\n"
            "- Quando quiser ATIVAR uma ferramenta, retorne APENAS o JSON dela, sem textos explicativos.\n"
            "- APÓS a ferramenta ser executada (quando receber o role 'tool'), fale normalmente em português explicando o resultado."
        )
    }

def garantir_dicionario_puro(msg) -> dict:
    """Converte o objeto customizado do Ollama em um dicionário Python padrão sem perder campos."""
    if isinstance(msg, dict):
        return msg
    
    dados = {
        "role": str(msg.role),
        "content": str(msg.content or "")
    }
    # PRESERVAÇÃO CRUCIAL: Salva o nome da ferramenta se for o caso
    if hasattr(msg, 'name') and msg.name:
        dados["name"] = str(msg.name)
        
    if hasattr(msg, 'tool_calls') and msg.tool_calls:
        dados["tool_calls"] = []
        for call in msg.tool_calls:
            name = getattr(call.function, 'name', call.get('function', {}).get('name'))
            args = getattr(call.function, 'arguments', call.get('function', {}).get('arguments'))
            dados["tool_calls"].append({"function": {"name": name, "arguments": args}})
            
    return dados

def carregar_historico_db():
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("SELECT msg_json FROM historico ORDER BY id ASC")
    rows = cursor.fetchall()
    conn.close()
    
    if not rows:
        msg_sistema = iniciar_historico_sistema()
        salvar_mensagem_db(msg_sistema)
        return [msg_sistema]
    
    return [json.loads(row[0]) for row in rows]

def salvar_mensagem_db(msg):
    """Salva a estrutura INTEIRA da mensagem em JSON para não perder nenhum metadado."""
    msg_pura = garantir_dicionario_puro(msg)
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("INSERT INTO historico (msg_json) VALUES (?)", (json.dumps(msg_pura, ensure_ascii=False),))
    conn.commit()
    conn.close()

# =====================================================================
# AUTO-COMPRESSÃO DE MEMÓRIA (Corrigida)
# =====================================================================

def verificar_e_resumir_historico():
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) FROM historico")
    total = cursor.fetchone()[0]
    
    if total > 25:
        console.print("[bold yellow]🧠 Otimizando Banco SQLite: Compactando histórico para poupar memória...[/bold yellow]")
        cursor.execute("SELECT msg_json FROM historico ORDER BY id ASC")
        rows = cursor.fetchall()
        
        conversa_texto = ""
        for row in rows:
            msg = json.loads(row[0])
            if msg['role'] in ['user', 'assistant']:
                autor = "Lucas" if msg['role'] == 'user' else "nexusIA"
                conversa_texto += f"{autor}: {msg['content']}\n"
        
        prompt_resumo = (
            f"Resuma a seguinte conversa em exatamente 3 parágrafos técnicos.\n"
            f"Mantenha expressamente o nome do usuário (Lucas) e o projeto (nexusIA):\n\n{conversa_texto}"
        )
        
        try:
            resposta_resumo = ollama.chat(model=MODELO_IA, messages=[{"role": "user", "content": prompt_resumo}])
            resumo_texto = resposta_resumo['message'].content
            
            cursor.execute("DELETE FROM historico")
            conn.commit()
            
            cursor.execute("INSERT INTO historico (msg_json) VALUES (?)", (json.dumps(iniciar_historico_sistema(), ensure_ascii=False),))
            msg_resumo = {
                "role": "system",
                "content": f"Contexto importante das conversas anteriores com Lucas:\n{resumo_texto}"
            }
            cursor.execute("INSERT INTO historico (msg_json) VALUES (?)", (json.dumps(msg_resumo, ensure_ascii=False),))
            conn.commit()
            console.print("[bold green]✅ Banco de dados compactado com sucesso![/bold green]")
        except Exception as e:
            console.print(f"[bold red]Falha no auto-resumo: {e}[/bold red]")
            
    conn.close()

# =====================================================================
# FERRAMENTAS DO SISTEMA
# =====================================================================

def obter_data_hora() -> str:
    return datetime.datetime.now().strftime("%d/%m/%Y às %H:%M:%S")

def criar_arquivo(nome: str, conteudo: str) -> str:
    try:
        with open(nome, "w", encoding="utf-8") as f:
            f.write(conteudo)
        return f"Sucesso: Arquivo '{nome}' criado fisicamente."
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
            'description': 'Use exclusivamente quando o usuário solicitar a criação de um arquivo físico no computador.',
            'parameters': {
                'type': 'object',
                'properties': {
                    'nome': {'type': 'string', 'description': 'Nome do arquivo com extensão.'},
                    'conteudo': {'type': 'string', 'description': 'Conteúdo do arquivo.'}
                },
                'required': ['nome', 'conteudo']
            }
        }
    }
]

# =====================================================================
# FLUXO EXECUTÁVEL
# =====================================================================

init_db()

def enviar_mensagem_local(pergunta: str) -> str:
    historico_conversa = carregar_historico_db()
    nova_msg_user = {"role": "user", "content": pergunta}
    historico_conversa.append(nova_msg_user)
    salvar_mensagem_db(nova_msg_user)
    
    try:
        response = ollama.chat(
            model=MODELO_IA,
            messages=historico_conversa,
            tools=ferramentas_disponiveis,
            options={'temperature': 0.1}
        )
        
        conteudo_resposta = response['message'].get('content', '') or ""
        tool_calls = response['message'].get('tool_calls', [])

        texto_compacto = conteudo_resposta.replace(" ", "").replace("\n", "").replace("\r", "").replace("```json", "").replace("```", "")
        if not tool_calls and '"name":' in texto_compacto:
            try:
                json_limpo = conteudo_resposta.replace("```json", "").replace("```", "").strip()
                dados_funcao = json.loads(json_limpo)
                tool_calls = [{"function": dados_funcao}]
            except Exception:
                pass

        if tool_calls:
            salvar_mensagem_db(response['message'])
            historico_conversa.append(garantir_dicionario_puro(response['message']))
            
            for call in tool_calls:
                if hasattr(call, 'function'):
                    nome_funcao = call.function.name
                    argumentos = call.function.arguments
                elif isinstance(call, dict):
                    func_data = call.get("function", call)
                    nome_funcao = func_data.get("name")
                    argumentos = func_data.get("arguments", {})
                    if isinstance(argumentos, str):
                        try: argumentos = json.loads(argumentos)
                        except: pass
                else:
                    continue
                
                console.print(f"[bold yellow]⚙️ [Python + SQLite] Executando ação: {nome_funcao}()...[/bold yellow]")
                
                if nome_funcao == 'obter_data_hora':
                    resultado = obter_data_hora()
                elif nome_funcao == 'criar_arquivo':
                    txt_conteudo = argumentos.get('conteudo', '')
                    if isinstance(txt_conteudo, dict):
                        txt_conteudo = txt_conteudo.get('description', str(txt_conteudo))
                    resultado = criar_arquivo(argumentos.get('nome', 'arquivo.txt'), txt_conteudo)
                else:
                    resultado = "Função inválida."
                
                msg_tool = {'role': 'tool', 'content': resultado, 'name': nome_funcao}
                salvar_mensagem_db(msg_tool)
                historico_conversa.append(msg_tool)
            
            resposta_final = ollama.chat(model=MODELO_IA, messages=historico_conversa)
            salvar_mensagem_db(resposta_final['message'])
            verificar_e_resumir_historico()
            return resposta_final['message'].content
        
        salvar_mensagem_db(response['message'])
        verificar_e_resumir_historico()
        return conteudo_resposta
        
    except Exception as e:
        return f"Erro no motor da IA: {e}"

def main():
    console.print("[bold magenta]🚀 nexusIA v7.4 (Memória em JSON Puro) Inicializada![/bold magenta]")
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
                conn = sqlite3.connect(DB_NAME)
                cursor = conn.cursor()
                cursor.execute("DELETE FROM historico")
                conn.commit()
                conn.close()
                console.print("[bold yellow]🧹 Banco de dados SQLite limpo do zero![/bold yellow]")
                continue

            with console.status("[bold cyan]NexusIA processando...[/bold cyan]", spinner="dots"):
                resposta = enviar_mensagem_local(user_input)

            console.print(Panel(resposta, title="nexusIA (Agente SQL)", border_style="cyan", expand=False))

        except KeyboardInterrupt:
            console.print("\n[yellow]Encerrando...[/yellow]")
            break

if __name__ == "__main__":
    main()