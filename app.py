import ollama
from rich.console import Console
from rich.panel import Panel

console = Console()

# Criamos a MEMÓRIA MANUAL: uma lista que guarda o histórico da conversa.
# Já começamos definindo a PERSONALIDADE da IA no primeiro item (system)
historico_conversa = [
    {
        "role": "system", 
        "content": """Você é a nexusIA, um assistente de terminal focado em tecnologia que roda localmente.
            Regras de comportamento:
            - Seja amigável, porém direta e objetiva.
            - Vá direto ao ponto, evitando introduções longas ou respostas prolixas.
            - Entregue conclusões limpas, eficientes e códigos bem formatados."""
    }
]

def enviar_mensagem_local(pergunta: str) -> str:
    """Envia a pergunta para o Ollama mantendo o histórico na memória do Python."""
    global historico_conversa
    
    # 1. Adiciona a nova pergunta do usuário ao histórico
    historico_conversa.append({"role": "user", "content": pergunta})
    
    try:
        # 2. Envia TODO o histórico para o modelo local 'llama3.2:1b'
        response = ollama.chat(
            model='llama3.2:1b', 
            messages=historico_conversa
        )
        
        # 3. Extrai o texto da resposta
        resposta_ia = response['message']['content']
        
        # 4. Adiciona a resposta da IA ao histórico (para ela lembrar na próxima pergunta)
        historico_conversa.append({"role": "assistant", "content": resposta_ia})
        
        return resposta_ia
        
    except Exception as e:
        return f"Erro ao conectar com o Ollama local: {e}. Certifique-se de que o Ollama está aberto."

def main():
    console.print("[bold magenta]🚀 NexusIA v1.5 Iniciada![/bold magenta]")
    console.print("[bold magenta]----------------------------------------------------------------------[/bold magenta]")

    while True:
        try:
            user_input = console.input("\n[bold blue]Você > [/bold blue]")

            if user_input.lower() in ['/sair', '/exit', '/quit']:
                console.print("Até a próxima!")
                break

            if not user_input.strip():
                continue

            # Animação de carregamento
            with console.status("[bold cyan]Pensando...[/bold cyan]", spinner="dots"):
                resposta = enviar_mensagem_local(user_input)

            console.print(Panel(resposta, title="NexusIA", border_style="cyan", expand=False))

        except KeyboardInterrupt:
            console.print("\n[yellow]Encerrando o programa...[/yellow]")
            break

if __name__ == "__main__":
    main()