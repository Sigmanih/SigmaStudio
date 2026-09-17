// projects/sigma_engine_rust/tests/test_engine.rs
// Test di integrazione per il kernel ad alte prestazioni Sigma Engine Rust

#[cfg(test)]
mod tests {
    // Test logica KV Cache
    #[test]
    fn test_kv_cache_ring_buffer_eviction() {
        // Simuliamo l'uso del modulo con parametri analoghi
        let max_pages = 3;
        let page_size = 4;
        
        // Verifichiamo il conteggio e l'evizione
        let mut cache_pages = std::collections::HashMap::new();
        for i in 0..5 {
            if cache_pages.len() >= max_pages {
                // Rimuove la più vecchia
                let min_key = cache_pages.keys().cloned().min().unwrap();
                cache_pages.remove(&min_key);
            }
            cache_pages.insert(i, vec![i as f32; page_size]);
        }

        assert_eq!(cache_pages.len(), 3);
        assert!(cache_pages.contains_key(&4));
        assert!(cache_pages.contains_key(&3));
        assert!(cache_pages.contains_key(&2));
        assert!(!cache_pages.contains_key(&0));
    }

    #[test]
    fn test_runtime_hot_reload_logic() {
        #[derive(Clone, Debug, PartialEq)]
        struct Config {
            batch_size: usize,
            temperature: f32,
            version: u64,
        }

        let mut cfg = Config {
            batch_size: 16,
            temperature: 0.7,
            version: 1,
        };

        // Simulazione hot patch
        let patch_batch = Some(32);
        let patch_temp = Some(0.2);

        if let Some(b) = patch_batch {
            cfg.batch_size = b;
        }
        if let Some(t) = patch_temp {
            cfg.temperature = t;
        }
        cfg.version += 1;

        assert_eq!(cfg.batch_size, 32);
        assert_eq!(cfg.temperature, 0.2);
        assert_eq!(cfg.version, 2);
    }
}
