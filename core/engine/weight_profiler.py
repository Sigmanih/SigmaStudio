# ==============================================================================
# core/engine/weight_profiler.py — Weight Saliency Analyzer & Layer Partitioner
# Calculates parameter significance and allocates layers across memory tiers
# (Tier 0: Primary VRAM, Tier 1: Secondary VRAM, Tier 2: RAM, Tier 3: Disk Shards)
# ==============================================================================
from typing import Dict, Any, List, Tuple
from core.logger import get_logger

log = get_logger(__name__)


class WeightSaliencyProfiler:
    """Analyzes model layer significance and determines optimal multi-tier hardware placement."""

    @classmethod
    def calculate_layer_saliency(cls, num_layers: int, is_moe: bool = False, num_experts: int = 8) -> List[Dict[str, Any]]:
        """
        Estimates the cognitive saliency of each layer in a transformer model.
        Empirical LLM research shows:
        - Layer 0 (Embedding & First Attention blocks) has critical syntactic representation.
        - Final layers (Penultimate & LM Head) have critical semantic decoding representation.
        - Middle MLP layers and non-routed MoE experts have lower latency-criticality and can be streamed.
        """
        saliency_scores = []
        for i in range(num_layers):
            # U-curve / Bathtub curve of layer sensitivity
            rel_pos = i / max(num_layers - 1, 1)
            if rel_pos < 0.2:
                # Early layers: High priority
                score = 1.0 - (rel_pos * 2.0)
            elif rel_pos > 0.8:
                # Late layers: Very high priority
                score = 0.6 + ((rel_pos - 0.8) * 2.0)
            else:
                # Middle layers: Moderate priority, suitable for RAM/Disk streaming
                score = 0.5 - abs(rel_pos - 0.5) * 0.4

            saliency_scores.append({
                "layer_index": i,
                "layer_name": f"model.layers.{i}",
                "saliency_score": round(max(score, 0.1), 3),
                "is_moe": is_moe,
                "num_experts": num_experts if is_moe else 1,
                "estimated_size_mb": 450 if not is_moe else 1200
            })
        return saliency_scores

    @classmethod
    def partition_model_layers(
        cls,
        total_layers: int,
        vram_primary_gb: float,
        vram_secondary_gb: float = 0.0,
        system_ram_gb: float = 16.0,
        model_size_gb: float = 8.0,
        is_moe: bool = False
    ) -> Dict[str, Any]:
        """
        Partitions the transformer layers across the 4 memory tiers based on VRAM/RAM capacity.
        """
        layer_saliency = cls.calculate_layer_saliency(total_layers, is_moe=is_moe)
        
        # Sort layers by saliency
        sorted_by_saliency = sorted(layer_saliency, key=lambda x: x["saliency_score"], reverse=True)
        
        avg_layer_size_gb = model_size_gb / max(total_layers, 1)
        
        # 1. Fill Tier 0 (Primary VRAM) - reserving 1.5GB for KV cache and context
        usable_vram_0 = max(vram_primary_gb - 1.5, 0.5)
        max_tier0_layers = int(usable_vram_0 / max(avg_layer_size_gb, 0.01))
        
        # 2. Fill Tier 1 (Secondary VRAM)
        usable_vram_1 = max(vram_secondary_gb - 0.5, 0.0)
        max_tier1_layers = int(usable_vram_1 / max(avg_layer_size_gb, 0.01))
        
        # 3. Fill Tier 2 (System RAM) - reserving 4GB for OS/App
        usable_ram = max(system_ram_gb - 4.0, 1.0)
        max_tier2_layers = int(usable_ram / max(avg_layer_size_gb, 0.01))
        
        tier0_layers = []
        tier1_layers = []
        tier2_layers = []
        tier3_layers = []
        
        assigned_indices = set()
        
        # Assign Tier 0 (Top Saliency)
        for layer in sorted_by_saliency[:max_tier0_layers]:
            tier0_layers.append(layer["layer_index"])
            assigned_indices.add(layer["layer_index"])
            
        # Assign Tier 1 (Secondary Saliency)
        remaining = [l for l in sorted_by_saliency if l["layer_index"] not in assigned_indices]
        for layer in remaining[:max_tier1_layers]:
            tier1_layers.append(layer["layer_index"])
            assigned_indices.add(layer["layer_index"])
            
        # Assign Tier 2 (Host RAM)
        remaining = [l for l in sorted_by_saliency if l["layer_index"] not in assigned_indices]
        for layer in remaining[:max_tier2_layers]:
            tier2_layers.append(layer["layer_index"])
            assigned_indices.add(layer["layer_index"])
            
        # Assign Tier 3 (Multi-Drive Disk Sharded Streaming)
        remaining = [l for l in sorted_by_saliency if l["layer_index"] not in assigned_indices]
        for layer in remaining:
            tier3_layers.append(layer["layer_index"])
            assigned_indices.add(layer["layer_index"])

        tier0_layers.sort()
        tier1_layers.sort()
        tier2_layers.sort()
        tier3_layers.sort()

        return {
            "total_layers": total_layers,
            "tier0_primary_vram": {
                "layer_indices": tier0_layers,
                "count": len(tier0_layers),
                "estimated_memory_gb": round(len(tier0_layers) * avg_layer_size_gb, 2)
            },
            "tier1_secondary_vram": {
                "layer_indices": tier1_layers,
                "count": len(tier1_layers),
                "estimated_memory_gb": round(len(tier1_layers) * avg_layer_size_gb, 2)
            },
            "tier2_host_ram": {
                "layer_indices": tier2_layers,
                "count": len(tier2_layers),
                "estimated_memory_gb": round(len(tier2_layers) * avg_layer_size_gb, 2)
            },
            "tier3_disk_shards": {
                "layer_indices": tier3_layers,
                "count": len(tier3_layers),
                "estimated_memory_gb": round(len(tier3_layers) * avg_layer_size_gb, 2),
                "streaming_mode": "multi_drive_striped" if len(tier3_layers) > 0 else "disabled"
            }
        }
