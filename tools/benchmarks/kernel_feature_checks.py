"""Prove live dei collegamenti del kernel con runtime e filesystem temporanei."""
from concurrent.futures import ThreadPoolExecutor
import json
import os
from pathlib import Path
import statistics
import time
import urllib.error
import urllib.request


def post(base,path,body,token=""):
    headers={"Content-Type":"application/json"}
    if token:headers["X-Sigma-Token"]=token
    request=urllib.request.Request(base+path,data=json.dumps(body).encode(),headers=headers)
    with urllib.request.urlopen(request,timeout=60) as response:return json.load(response)


def check_features(worker,kernel,token,workspace:Path,model_file:Path,slots:int):
    from tools.benchmarks.sigma_inference_comparison import misura
    result={}
    texts=["Ciao, citta e più lingue!","def esempio(x):\n    return x + 1","", "<|im_start|>assistant"]
    pairs=[]
    for text in texts:
        direct=post(worker,"/tokenize",{"content":text,"add_special":False})["tokens"]
        proxied=post(kernel,"/api/engine/tokenize",{"text":text},token)["tokens"]
        if direct!=proxied:raise AssertionError("ID del tokenizer diversi dal worker")
        pairs.append(len(direct))
    result["tokenizer"]={"samples":len(texts),"exact_ids":True,"token_counts":pairs}
    statuses=[]
    for base,key in [(worker,""),(kernel,token)]:
        try:
            value=post(base,"/v1/embeddings",{"input":"Sigma"},key)
            statuses.append(200)
            if not value.get("data"):raise AssertionError("Embedding mancante")
        except urllib.error.HTTPError as error:statuses.append(error.code)
    if statuses[0]!=statuses[1]:raise AssertionError(f"Stato embedding differente: {statuses}")
    result["embedding"]={"worker_status":statuses[0],"proxy_status":statuses[1],"synthetic":False}

    prompt="Spiega brevemente il contenuto.\n"+("Un programma efficiente misura memoria e tempi prima di scegliere un algoritmo.\n"*24)
    body={"model":model_file.stem,"messages":[{"role":"user","content":prompt}],
        "max_tokens":8,"temperature":0,"seed":123,"stream":True,"stream_options":{"include_usage":True},
        "chat_template_kwargs":{"enable_thinking":False},"id_slot":0}
    cold=misura(kernel,{**body,"cache_prompt":False},token)
    warm=misura(kernel,{**body,"cache_prompt":True},token)
    result["kv_reuse"]={"cold_ttft_ms":cold["ttft_ms"],"warm_ttft_ms":warm["ttft_ms"],
        "cold_timings":cold["timings"],"warm_timings":warm["timings"],
        "proxy_reused_tokens":warm["proxy_telemetry"].get("kv_tokens_reused"),
        "outputs_match":cold["output_sha256"]==warm["output_sha256"]}
    checkpoint="slot-0.kv"
    saved=post(kernel,"/api/engine/session/cache",{"action":"save","slot_id":0,"filename":checkpoint},token)
    erased=post(kernel,"/api/engine/session/cache",{"action":"erase","slot_id":0},token)
    restored=post(kernel,"/api/engine/session/cache",{"action":"restore","slot_id":0,"filename":checkpoint},token)
    if restored["result"].get("n_restored",0)<=0:raise AssertionError("Checkpoint non ripristinato")
    result["checkpoint"]={"save":saved["result"],"erase":erased["result"],"restore":restored["result"]}
    negotiation=post(kernel,"/api/engine/upstream",{"upstream_url":worker,"parallel_slots":slots},token)
    jobs=[{**body,"messages":[{"role":"user","content":f"Descrivi in italiano il vantaggio numero {i} della programmazione strutturata."}],
           "max_tokens":32,"cache_prompt":False} for i in range(2)]
    for job in jobs:job.pop("id_slot",None)
    started=time.perf_counter();sequential=[misura(kernel,job,token) for job in jobs];sequential_ms=(time.perf_counter()-started)*1000
    started=time.perf_counter()
    with ThreadPoolExecutor(max_workers=2) as executor:
        futures=[executor.submit(misura,kernel,job,token) for job in jobs]
        parallel=[future.result(timeout=90) for future in futures]
    parallel_ms=(time.perf_counter()-started)*1000
    result["batching"]={"worker_slots":slots,"proxy_slots":negotiation["parallel_slots"],
        "sequential_ms":sequential_ms,"concurrent_ms":parallel_ms,
        "speedup":sequential_ms/parallel_ms,
        "outputs_match":all(a["output_sha256"]==b["output_sha256"] for a,b in zip(sequential,parallel))}
    result["batching"]["outputs"]=[{"sequential":a["output"],"concurrent":b["output"]} for a,b in zip(sequential,parallel)]
    if not result["batching"]["outputs_match"]:
        # Verifica se il cambiamento numerico dipende dal batching del worker stesso.
        reference=[misura(worker,job) for job in jobs]
        with ThreadPoolExecutor(max_workers=2) as executor:
            concurrent=list(executor.map(lambda job:misura(worker,job),jobs))
        result["batching"]["direct_worker_outputs_match"]=all(a["output_sha256"]==b["output_sha256"] for a,b in zip(reference,concurrent))
        result["batching"]["direct_worker_outputs"]=[{"sequential":a["output"],"concurrent":b["output"]} for a,b in zip(reference,concurrent)]

    # Il modello numerico isola il collegamento nativo dalla qualita' linguistica di Sigma.
    from tools.benchmarks.gguf_fixture import tiny_llama
    fixture=workspace/"native-fixture.gguf";fixture.write_bytes(tiny_llama())
    post(kernel,"/api/engine/native/load",{"path":str(fixture),"kv_budget_mb":1},token)
    request={"tokens":[0,1],"max_tokens":2,"session_id":"feature-check"}
    first=post(kernel,"/api/engine/native/generate",request,token)
    second=post(kernel,"/api/engine/native/generate",request,token)
    if first["generation"]["token_ids"]!=second["generation"]["token_ids"] or second["generation"]["kv_tokens_reused"]!=1:
        raise AssertionError("Cache del runtime nativo incoerente")
    result["native_http"]={"first":first,"second":second}

    keys=("SIGMA_RUST_ENGINE_URL","SIGMA_ENGINE_TOKEN","SIGMA_WORKSPACE_ROOT","SIGMA_RUST_PIPE_NAME","SIGMA_RUST_HOST_WORKSPACE","SIGMA_NATIVE_READ_MMAP")
    previous={key:os.environ.get(key) for key in keys}
    try:
        os.environ.update(SIGMA_RUST_ENGINE_URL=kernel,SIGMA_ENGINE_TOKEN=token,SIGMA_WORKSPACE_ROOT=str(workspace),
            SIGMA_RUST_HOST_WORKSPACE=str(workspace),SIGMA_RUST_PIPE_NAME=rf"\\.\pipe\sigma_bench_{kernel.rsplit(':',1)[1]}")
        from core.engine.backends.sigmarust_backend import NamedPipeClient
        client=NamedPipeClient(endpoint_url=kernel,timeout=2)
        try:
            ipc=client.tokenize_ipc(texts[0])
            exact=post(worker,"/tokenize",{"content":texts[0],"add_special":False})["tokens"]
            if ipc!=exact:raise AssertionError("Tokenizer IPC non collegato")
            result["ipc_tokenizer"]={"transport":client._transport,"exact_ids":True}
        finally:client.close()
        from core.engine.backends.sigma_ffi import execute_tool_ffi,load_native_ffi,generate_native_ffi
        ffi=execute_tool_ffi("json_query",{"data":{"value":42},"path":"value"})
        if not ffi or ffi.get("result",{}).get("result")!=42:raise AssertionError("Tool FFI non collegato")
        loaded=load_native_ffi(str(fixture),1)
        generated=generate_native_ffi([0,1],2,"feature-check")
        if not loaded or not loaded.get("success") or generated.get("generation",{}).get("token_ids")!=first["generation"]["token_ids"]:
            raise AssertionError("Inferenza FFI non coerente con HTTP")
        unsupported=load_native_ffi(str(model_file),128)
        result["ffi"]={"tool":ffi,"native_generation":generated,
                       "sigma_pure_rust_supported":bool(unsupported and unsupported.get("success")),
                       "sigma_native_error":(unsupported or {}).get("error")}
        from core.harness import native_reads
        from core.harness.fs_tools import read_file_slice
        native_reads._cached.clear()
        source=workspace/"large-source.txt";source.write_text((("riga per la verifica del trasferimento nativo "*8)+"\n")*5000,encoding="utf-8")
        def measure_read(force_local,limit):
            os.environ["SIGMA_RUST_HOST_WORKSPACE"]=str(workspace/"disabled") if force_local else str(workspace)
            measurements=[];value=None
            for _ in range(5):
                start=time.perf_counter_ns();value=read_file_slice(str(source),offset=100,limit=limit,workspace_root=str(workspace))
                measurements.append((time.perf_counter_ns()-start)/1e6)
            return statistics.median(measurements),value
        local_ms,local=measure_read(True,150)
        native_ms,native=measure_read(False,150)
        os.environ["SIGMA_NATIVE_READ_MMAP"]="1"
        map_local_ms,map_local=measure_read(True,1000)
        map_ms,mapped=measure_read(False,1000)
        if native["content"]!=local["content"] or mapped["content"]!=map_local["content"] or not mapped.get("native_slice"):
            raise AssertionError("Lettura nativa non collegata o diversa dal riferimento")
        result["native_reads"]={"local_ms":local_ms,"native_ms":native_ms,"mapped_local_ms":map_local_ms,"mapped_ms":map_ms,
            "transport":native.get("native_transport"),"mapped_transport":mapped.get("native_transport"),
            "same_window":True}
    finally:
        from core.engine.backends.sigma_ffi import _execute_json_ffi
        _execute_json_ffi({"op":"native_unload"})
        for key,value in previous.items():
            if value is None:os.environ.pop(key,None)
            else:os.environ[key]=value
    return result
