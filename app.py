import os
import datetime
import json
import sqlite3
import ollama
from rich.console import Console
from rich.panel import Panel

console = Console()
MODELO_IA = 'qwen2.5-coder:3b'
DB_NAME = "nexus_memory.db"

# =====================================================================
# BANCO DE DADOS (SQLite)
# =====================================================================

def init_db():
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS historico (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            role TEXT,
            content TEXT,
            tool_calls TEXT,
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
            "Regras:\n"
            "- Seja amigável, porém extremamente direta, curta e objetiva.\n"
            "- Se decidir usar uma ferramenta, responda APENAS com o JSON da função, sem textos extras."
        )
    }

def carregar_historico_db():
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("SELECT role, content, tool_calls FROM historico ORDER BY id ASC")
    rows = cursor.fetchall()
    conn.close()
    
    if not rows:
        msg_sistema = iniciar_historico_sistema()
        salvar_mensagem_db(msg_sistema)
        return [msg_sistema]
    
    historico = []
    for role, content, tool_calls in rows:
        msg = {"role": role, "content": content}
        if tool_calls:
            msg["tool_calls"] = json.loads(tool_calls)
        historico.append(msg)
    return historico

def salvar_mensagem_db(msg):
    role = getattr(msg, 'role', msg.get('role'))
    content = getattr(msg, 'content', msg.get('content')) or ""
    
    tool_calls = None
    if hasattr(msg, 'tool_calls') and msg.tool_calls:
        tool_calls = []
        for call in msg.tool_calls:
            name = getattr(call.function, 'name', call.get('function', {}).get('name'))
            args = getattr(call.function, 'arguments', call.get('function', {}).get('arguments'))
            tool_calls.append({"function": {"name": name, "arguments": args}})
    elif isinstance(msg, dict) and 'tool_calls' in msg:
        tool_calls = msg['tool_calls']
        
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    tc_json = json.dumps(tool_calls, ensure_ascii=False) if tool_calls else None
    cursor.execute("INSERT INTO historico (role, content, tool_calls) VALUES (?, ?, ?)", (role, content, tc_json))
    conn.commit()
    conn.close()

# =====================================================================
# AUTO-COMPRESSÃO DE MEMÓRIA (SQLite)
# =====================================================================

def verificar_e_resumir_historico():
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) FROM historico")
    total = cursor.fetchone()[0]
    
    if total > 20:
        console.print("[bold yellow]🧠 Otimizando Banco SQLite: Compactando histórico para poupar memória...[/bold yellow]")
        cursor.execute("SELECT role, content FROM historico ORDER BY id ASC")
        rows = cursor.fetchall()
        
        conversa_texto = ""
        for role, content in rows:
            if role in ['user', 'assistant']:
                autor = "Lucas" if role == 'user' else "nexusIA"
                conversa_texto += f"{autor}: {content}\n"
        
        prompt_resumo = (
            f"Resuma a seguinte conversa em exatamente 3 parágrafos técnicos.\n"
            f"Mantenha fatos como o nome do usuário (Lucas) e o projeto (nexusIA):\n\n{conversa_texto}"
        )
        
        try:
            resposta_resumo = ollama.chat(
                model=MODELO_IA,
                messages=[{"role": "user", "content": prompt_resumo}]
            )
            resumo_texto = resposta_resumo['message'].content
            
            cursor.execute("DELETE FROM historico")
            cursor.execute("INSERT INTO historico (role, content) VALUES (?, ?)", (
                "system", 
                f"Você é a nexusIA. Contexto resumido das conversas anteriores com Lucas:\n{resumo_texto}"
            ))
            conn.commit()
            console.print("[bold green]✅ Banco de dados compactado e indexado com sucesso![/bold green]")
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
# FLUXO EXECUTÁVEL PRINCIPAL
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

        # 🔥 BLINDAGEM: Se o Ollama não capturou a ferramenta nativamente, nós extraímos do texto
        if not tool_calls and '{"name":' in conteudo_resposta:
            try:
                json_limpo = conteudo_resposta.replace("```json", "").replace("```", "").strip()
                dados_funcao = json.loads(json_limpo)
                tool_calls = [{"function": dados_funcao}]
            except Exception:
                pass

        if tool_calls:
            salvar_mensagem_db(response['message'])
            historico_conversa.append(response['message'])
            
            for call in tool_calls:
                # Trata dinamicamente se veio como Objeto do Ollama ou Dicionário do nosso interceptador
                if hasattr(call, 'function') or (isinstance(call, dict) and 'function' in call and not isinstance(call['function'], dict)):
                    nome_funcao = call.function.name
                    argumentos = call.function.arguments
                else:
                    nome_funcao = call.get('function', {}).get('name')
                    argumentos = call.get('function', {}).get('arguments', {})
                
                console.print(f"[bold yellow]⚙️ [Python + SQLite] Executando ação: {nome_funcao}()...[/bold yellow]")
                
                if nome_funcao == 'obter_data_hora':
                    resultado = obter_data_hora()
                elif nome_funcao == 'criar_arquivo':
                    # Evita o erro de dicionários aninhados que o Llama/Qwen pequenos geram
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
    console.print("[bold magenta]🚀 nexusIA v7.1 (Blindagem de Ferramentas SQL) Inicializada![/bold magenta]")
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

            with console.status("[bold cyan]nexusIA processando...[/bold cyan]", spinner="dots"):
                resposta = enviar_mensagem_local(user_input)

            console.print(Panel(resposta, title="nexusIA (Agente SQL)", border_style="cyan", expand=False))

        except KeyboardInterrupt:
            console.print("\n[yellow]Encerrando...[/yellow]")
            break

if __name__ == "__main__":
    main()