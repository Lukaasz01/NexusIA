import os
import time
from dotenv import load_dotenv
from google import genai
from google.genai import types
from rich.console import Console
from rich.panel import Panel

load_dotenv()
console = Console()

try:
    client = genai.Client()
    
    configuracao = types.GenerateContentConfig(
        system_instruction="Você é a nexusIA, um assistente de terminal focado em tecnologia e programação. Seja direto, use respostas limpas e, quando enviar códigos, use formatação markdown adequada. Adote um tom amigável, porém focado em eficiência."
    )
    
    chat = client.chats.create(
        model='gemini-2.5-flash',
        config=configuracao
    )
    
except Exception as e:
    console.print(f"[bold red]Erro ao iniciar a IA: {e}[/bold red]")

def enviar_mensagem_chat(pergunta: str) -> str:
    """Envia a pergunta tratando erros de cota (429) e outros problemas."""
    try:
        response = chat.send_message(pergunta)
        return response.text
    except Exception as e:
         erro_str = str(e)
         # Verifica se o erro é de limite de requisições (Quota ou 429)
         if "429" in erro_str or "RESOURCE_EXHAUSTED" in erro_str:
             return "[bold yellow]⚠️ Opa, fomos rápidos demais! Atingimos o limite temporário da API. Espere uns 30 segundos e tente me mandar outra mensagem.[/bold yellow]"
         return f"Erro na comunicação: {erro_str}"

def main():
    console.print("[bold magenta]🚀 nexusIA v2.1 (Protegida contra Erro 429) Iniciada![/bold magenta]")
    console.print("----------------------------------------------------------------------")

    while True:
        try:
            user_input = console.input("\n[bold green]Você > [/bold green]")

            if user_input.lower() in ['sair', 'exit', 'quit']:
                console.print("[yellow]Até a próxima![/yellow]")
                break

            if not user_input.strip():
                continue

            with console.status("[bold cyan] nexusIA pensando...[/bold cyan]", spinner="dots"):
                resposta = enviar_mensagem_chat(user_input)

            console.print(Panel(resposta, title="nexusIA", border_style="magenta", expand=False))

        except KeyboardInterrupt:
            console.print("\n[yellow]Encerrando o programa...[/yellow]")
            break

if __name__ == "__main__":
    main()