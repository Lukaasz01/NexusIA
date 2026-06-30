import os
from dotenv import load_dotenv
from google import genai
from rich.console import Console
from rich.panel import Panel

# Carrega a chave API que salvamos no arquivo .env
load_dotenv()

# Inicializa o terminal bonitão
console = Console()

# Inicializa o cliente oficial da IA do Google
try:
    client = genai.Client()
except Exception as e:
    console.print(f"[bold red]Erro ao iniciar o cliente da IA: {e}[/bold red]")

def chamar_ia(pergunta: str) -> str:
    """Esta função envia a sua pergunta direto para o cérebro do Gemini."""
    try:
        response = client.models.generate_content(
            model='gemini-2.5-flash',
            contents=pergunta,
        )
        return response.text
    except Exception as e:
        return f"Erro ao nos comunicarmos com a IA: {e}"

def main():
    console.print("[bold magenta]🚀 nexusIA Conectada ao Cérebro Real! Digite 'sair' para encerrar.[/bold magenta]")
    console.print("----------------------------------------------------------------------")

    while True:
        try:
            user_input = console.input("\n[bold green]Você > [/bold green]")

            if user_input.lower() in ['sair', 'exit', 'quit']:
                console.print("[yellow]Até a próxima![/yellow]")
                break

            if not user_input.strip():
                continue

            # Mostra a animação enquanto a IA gera a resposta na nuvem
            with console.status("[bold cyan]Pensando...[/bold cyan]", spinner="dots"):
                resposta = chamar_ia(user_input)

            # Exibe a resposta real da IA na tela
            console.print(Panel(resposta, title="nexusIA", border_style="blue", expand=False))

        except KeyboardInterrupt:
            console.print("\n[yellow]Encerrando o programa...[/yellow]")
            break

if __name__ == "__main__":
    main()