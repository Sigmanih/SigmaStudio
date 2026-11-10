"""Confini del workspace, buffer condivisi e protocollo di persistenza del worker."""
from pathlib import Path
from unittest.mock import MagicMock, patch

from core.harness import native_reads
from core.harness.fs_tools import read_file_slice
from core.engine.backends.llamaserver_backend import LlamaServerBackend


def test_lettura_nativa_conserva_la_finestra_e_rilascia_il_buffer(tmp_path):
    path=tmp_path/"large.txt"
    path.write_text("riga di prova\n"*50000,encoding="utf-8")
    def post(endpoint,body):
        if body["tool"]=="fast_read_file":
            return {"success":True,"result":{"success":True,"content":"riga di prova\nriga di prova",
                "total_lines":50000,"python_lines_compatible":True,"buffer_handle":42}}
        return {"success":True}
    with patch.object(native_reads,"_capabilities",return_value={"workspace_root":str(tmp_path)}), \
         patch.object(native_reads,"_post",side_effect=post) as calls:
        result=read_file_slice(str(path),offset=3,limit=2,workspace_root=str(tmp_path))
    assert result["native_slice"]
    assert result["content"]=="riga di prova\nriga di prova"
    assert result["numbered"]=="3\triga di prova\n4\triga di prova"
    assert result["total_lines"]==50000 and result["has_more"]
    assert calls.call_args.args[1]["params"]=={"op":"evict","handle":42}


def test_workspace_diverso_non_invia_il_percorso_al_kernel(tmp_path):
    file=tmp_path/"large.txt";file.write_bytes(b"x"*600000)
    with patch.object(native_reads,"_capabilities",return_value={"workspace_root":str(tmp_path/"altro")}), \
         patch.object(native_reads,"_post") as post:
        assert native_reads.try_read_slice(file,1,2,tmp_path) is None
    post.assert_not_called()


def test_limite_zero_ha_la_stessa_semantica_nativa_e_python(tmp_path):
    path=tmp_path/"large.txt";path.write_bytes(b"riga\n"*120000)
    with patch.object(native_reads,"try_read_slice",return_value=None) as native:
        result=read_file_slice(str(path),limit=0,workspace_root=str(tmp_path))
    assert native.call_args.args[2]==1
    assert result["returned_lines"]==1


def test_mapping_confinato_e_lunghezza_verificata(tmp_path):
    import pytest
    buffer=tmp_path/"buffer";buffer.write_bytes(b"sigma")
    assert native_reads.read_mapping({"path":str(buffer),"length":5},str(tmp_path),tmp_path)=="sigma"
    with pytest.raises(ValueError):
        native_reads.read_mapping({"path":str(buffer),"length":100},str(tmp_path),tmp_path)
    with pytest.raises(ValueError):
        native_reads.read_mapping({"path":str(tmp_path.parent/"fuori"),"length":1},str(tmp_path),tmp_path)


def test_checkpoint_usa_filename_json_e_rifiuta_uscita_dalla_directory(tmp_path):
    backend=LlamaServerBackend();backend._porta=12345;backend._processo=MagicMock()
    backend._settings={"slot_save_path":str(tmp_path),"parallel_slots":1}
    def post(path,body,timeout):
        assert path=="/slots/0?action=save"
        assert body=={"filename":"cache.bin"}
        (tmp_path/"cache.bin").write_bytes(b"kv")
        return {"n_saved":4,"n_written":2}
    with patch.object(backend,"_post",side_effect=post):
        assert backend.save_slot_kv(0,"cache.bin")
        assert not backend.save_slot_kv(0,"../fuori.bin")
        assert not backend.restore_slot_kv(0,"mancante.bin")


def test_ffi_libera_risposta_anche_se_json_non_valido():
    import ctypes
    from core.engine.backends import sigma_ffi
    data=ctypes.create_string_buffer(b"non-json")
    library=MagicMock();library.sigma_ffi_execute_tool_json.return_value=ctypes.addressof(data)
    with patch.object(sigma_ffi,"is_ffi_available",return_value=True),patch.object(sigma_ffi,"_LIB",library):
        assert sigma_ffi.execute_tool_ffi("json_query",{}) is None
    library.sigma_ffi_free_string.assert_called_once_with(ctypes.addressof(data))
