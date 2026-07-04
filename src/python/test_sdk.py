# ============================================================================
# test_sdk.py - Script de teste para validar o GitHub Copilot SDK
# ============================================================================
# Execute com: python test_sdk.py
# ============================================================================

import asyncio

from copilot import CopilotClient, PermissionHandler


async def main():
    print("🚀 Testando GitHub Copilot SDK...")

    try:
        # Criar cliente
        print("\n1. Criando cliente...")
        client = CopilotClient()

        # Iniciar cliente
        print("2. Iniciando cliente...")
        await client.start()
        print("   ✓ Cliente iniciado com sucesso!")

        # Criar sessão
        print("\n3. Criando sessão...")
        session = await client.create_session(on_permission_request=PermissionHandler.approve_all)
        print(f"   ✓ Sessão criada: {session.session_id}")

        # Enviar mensagem
        print("\n4. Enviando mensagem de teste...")

        def handle_event(event):
            if event.type.value == "assistant.message":
                print(f"\n   🤖 Copilot: {event.data.content}")

        session.on(handle_event)

        # Usar send_and_wait para aguardar a resposta completa
        await session.send_and_wait(prompt="Say hello in Portuguese!")

        print("\n   ✓ Mensagem recebida com sucesso!")

        # Limpar
        print("\n5. Limpando recursos...")
        await session.disconnect()
        await client.stop()
        print("   ✓ Recursos liberados!")

        print("\n✅ Teste concluído com sucesso!")
        print("\nO GitHub Copilot SDK está funcionando corretamente.")
        print("Você pode executar o projeto completo com: python app.py")

    except Exception as e:
        print(f"\n❌ Erro: {e}")
        print("\nVerifique se você está autenticado com o GitHub CLI:")
        print("  gh auth login")
        return 1

    return 0


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    exit(exit_code)
