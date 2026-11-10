"""La politica comune non presume capacità dal nome del modello."""
from dataclasses import replace
import json
import os
from pathlib import Path
import subprocess
import sys
from unittest.mock import MagicMock

import pytest

from core.engine.acceleration import CacheIdentity, RuntimeCapabilities, acceleration_plan
from core.engine.model_inspector import ModelFacts
from core.engine.prefix_cache import PrefixKVCache


@pytest.mark.parametrize("architecture", ["llama", "qwen35", "gemma", "mamba", "future_architecture"])
def test_la_famiglia_non_inventa_capacita(architecture):
    caps=RuntimeCapabilities(runtime="custom")
    plan=acceleration_plan(caps,model=ModelFacts(path="model",name="model",model_type=architecture))
    assert plan["effective_parallelism"]==1
    assert not any(feature["supported"] for feature in plan["features"].values())
    assert plan["model"]["architecture"]==architecture


def test_slot_richiesti_non_superano_il_runtime():
    caps=RuntimeCapabilities(runtime="worker",parallel_slots=4,logits_owner="gpu_worker")
    assert acceleration_plan(caps,requested_parallelism=12)["effective_parallelism"]==4
    assert acceleration_plan(caps,requested_parallelism=2)["effective_parallelism"]==2
    assert acceleration_plan(caps)["features"]["logits_processing"]["owner"]=="gpu_worker"
    with pytest.raises(ValueError):RuntimeCapabilities(runtime="bad",parallel_slots=True)


@pytest.mark.parametrize("field",list(CacheIdentity.__dataclass_fields__))
def test_ogni_componente_semantica_isola_la_cache(field):
    identity=CacheIdentity(checkpoint="weights-v1",tokenizer="tokenizer-v1",template="template-v1",runtime="abi-v1")
    assert identity.digest()!=replace(identity,**{field:"changed"}).digest()


def test_namespace_diverso_invalida_anche_lo_stesso_nome_modello():
    cache=PrefixKVCache()
    cache.configure("model",1024,namespace="adapter-a")
    cache.store(list(range(100)),MagicMock(),"model")
    cache.configure("model",1024,namespace="adapter-b")
    assert cache.take(list(range(101)),"model")== (None,0)


def test_metadati_portabili_fra_processi_e_slot_confinato(tmp_path):
    cache=PrefixKVCache();cache.configure("model",1024,namespace="revision")
    slot="../../outside"
    cache.store([1,2,3],object(),"model",slot=slot)
    saved=cache.save_to_disk(slot,dest_dir=tmp_path)
    assert saved.parent==tmp_path
    script="from core.engine.prefix_cache import PrefixKVCache; from pathlib import Path; import sys,json; c=PrefixKVCache(); c.configure('model',1024,namespace='revision'); print(json.dumps(c.load_from_disk('../../outside',src_dir=Path(sys.argv[1]))))"
    child=subprocess.run([sys.executable,"-c",script,str(tmp_path)],capture_output=True,text=True,
                         env={**os.environ,"PYTHONHASHSEED":"47"},timeout=15)
    assert child.returncode==0,child.stderr
    assert json.loads(child.stdout.strip().splitlines()[-1])==[1,2,3]
    content=json.loads(saved.read_text());content["tokens"]=[-1];saved.write_text(json.dumps(content))
    assert cache.load_from_disk(slot,src_dir=tmp_path) is None


def test_backend_spento_non_promette_cache():
    from core.engine.backends.llamaserver_backend import LlamaServerBackend
    plan=LlamaServerBackend().acceleration_plan()
    assert plan["runtime"]["evidence"]=="not_loaded"
    assert not plan["features"]["prefix_reuse"]["supported"]
