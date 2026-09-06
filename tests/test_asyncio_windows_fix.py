import sys
import pytest
from unittest.mock import MagicMock

from core.runtime_env import patch_asyncio_windows_proactor


def test_patch_asyncio_windows_proactor_execution():
    """Verifica che la funzione venga eseguita senza errori."""
    res = patch_asyncio_windows_proactor()
    if sys.platform == "win32":
        assert res is True
    else:
        assert res is False


def test_safe_call_connection_lost_handles_connection_reset():
    """Verifica che _call_connection_lost gestisca ConnectionResetError su socket.shutdown."""
    if sys.platform != "win32":
        pytest.skip("Test specifico per Windows proactor")

    import asyncio.proactor_events
    patch_asyncio_windows_proactor()

    base_pipe = asyncio.proactor_events._ProactorBasePipeTransport

    # Crea un'istanza mockata con un socket che solleva ConnectionResetError su shutdown
    transport = MagicMock(spec=base_pipe)
    transport._called_connection_lost = False
    transport._protocol = MagicMock()
    mock_server = MagicMock()
    transport._server = mock_server

    mock_sock = MagicMock()
    mock_sock.fileno.return_value = 42
    mock_sock.shutdown.side_effect = ConnectionResetError(10054, "Connessione forzatamente interrotta")
    transport._sock = mock_sock

    # Invochiamo il metodo patchato passando l'istanza mockata
    base_pipe._call_connection_lost(transport, None)

    # Verifica che il protocollo sia stato notificato
    transport._protocol.connection_lost.assert_called_once_with(None)
    # Verifica che il socket sia stato comunque chiuso nonostante l'eccezione su shutdown
    mock_sock.close.assert_called_once()
    assert transport._sock is None
    # Verifica che il server sia stato staccato e azzerato
    mock_server._detach.assert_called_once()
    assert transport._server is None
    assert transport._called_connection_lost is True
