# tests/test_ipc_client_transport.py
import io
import json
import struct
import unittest
from unittest.mock import patch, MagicMock

from core.engine.backends.sigmarust_backend import SigmaRustClient


class TestIpcClientTransport(unittest.TestCase):
    def test_client_init_and_fallback(self):
        client = SigmaRustClient(endpoint_url="http://127.0.0.1:9999", timeout=0.5)
        # Se la named pipe o unix socket non sono presenti, il client attiva il fallback HTTP
        self.assertIn(client._transport, ("http", "named_pipe", "named_pipe_raw", "unix_socket"))
        client.close()

    def test_send_ipc_framing_mock(self):
        client = SigmaRustClient(endpoint_url="http://127.0.0.1:9999", timeout=0.5)
        
        # Simuliamo un handle stream bidirezionale
        mock_handle = MagicMock()
        resp_data = {"status": "ok", "token_ids": [10, 20, 30]}
        raw_resp = json.dumps(resp_data).encode("utf-8")
        resp_frame = struct.pack("<I", len(raw_resp)) + raw_resp
        
        # Simula lettura length (4 byte) poi body
        mock_handle.read.side_effect = [resp_frame[:4], resp_frame[4:]]
        
        client._transport = "named_pipe_raw"
        client._handle = mock_handle
        
        tokens = client.tokenize_ipc("hello world")
        self.assertEqual(tokens, [10, 20, 30])
        
        # Verifica che il pacchetto inviato contenga la lunghezza corretta in little endian
        written_data = b"".join(call.args[0] for call in mock_handle.write.call_args_list)
        msg_len = struct.unpack("<I", written_data[:4])[0]
        payload = json.loads(written_data[4:4 + msg_len].decode("utf-8"))
        self.assertEqual(payload["op"], "tokenize")
        self.assertEqual(payload["text"], "hello world")
        
        client.close()

    def test_tokenize_fallback_deterministic(self):
        client = SigmaRustClient(endpoint_url="http://127.0.0.1:9999", timeout=0.1)
        client._transport = "http"
        # Con server offline, tokenize restituisce hash CRC32 deterministici
        tokens = client.tokenize("test prompt tokenization")
        self.assertEqual(len(tokens), 3)
        self.assertTrue(all(isinstance(t, int) and t >= 0 for t in tokens))
        client.close()


if __name__ == "__main__":
    unittest.main()
