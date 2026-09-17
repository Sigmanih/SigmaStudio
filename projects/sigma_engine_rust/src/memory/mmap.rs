// projects/sigma_engine_rust/src/memory/mmap.rs
// Allocatore zero-copy per caricamento pesi modello tramite memory mapping.
// Permette di accedere a file GGUF / SafeTensors di decine di GB senza caricare
// tutto in RAM fisica, lasciando al kernel OS la gestione del page-fault paging.

use std::fs::File;
use std::path::{Path, PathBuf};
use std::sync::Arc;
use memmap2::Mmap;
use serde::{Deserialize, Serialize};

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct MemoryMapMetadata {
    pub file_path: String,
    pub file_size_bytes: u64,
    pub page_size_bytes: usize,
    pub is_resident: bool,
}

pub struct ModelMemoryMap {
    path: PathBuf,
    mmap: Arc<Mmap>,
    size: u64,
}

impl ModelMemoryMap {
    /// Inizializza una mappa di memoria a sola lettura su file specificato.
    pub fn open<P: AsRef<Path>>(path: P) -> std::io::Result<Self> {
        let file = File::open(&path)?;
        let metadata = file.metadata()?;
        let size = metadata.len();
        
        // Safety: operazione read-only, non modifichiamo il buffer sottostante
        let mmap = unsafe { Mmap::map(&file)? };

        Ok(Self {
            path: path.as_ref().to_path_buf(),
            mmap: Arc::new(mmap),
            size,
        })
    }

    /// Ritorna la fetta di byte corrispondente all'intervallo specificato [offset .. offset + len].
    pub fn read_slice(&self, offset: usize, len: usize) -> Option<&[u8]> {
        if offset + len <= self.size as usize {
            Some(&self.mmap[offset..offset + len])
        } else {
            None
        }
    }

    /// Ritorna le statistiche e i metadati della mappa.
    pub fn metadata(&self) -> MemoryMapMetadata {
        MemoryMapMetadata {
            file_path: self.path.to_string_lossy().into_owned(),
            file_size_bytes: self.size,
            page_size_bytes: 4096, // Dimensione tipica pagina di memoria OS
            is_resident: true,
        }
    }

    /// Tenta di estrarre i metadati GGUF (magic "GGUF", versione, conteggio tensori e kv)
    pub fn parse_gguf_header(&self) -> Option<GgufHeader> {
        if self.size < 24 {
            return None;
        }
        let bytes = self.read_slice(0, 24)?;
        if &bytes[0..4] != b"GGUF" {
            return None;
        }
        let version = u32::from_le_bytes([bytes[4], bytes[5], bytes[6], bytes[7]]);
        let tensor_count = u64::from_le_bytes([
            bytes[8], bytes[9], bytes[10], bytes[11],
            bytes[12], bytes[13], bytes[14], bytes[15],
        ]);
        let metadata_kv_count = u64::from_le_bytes([
            bytes[16], bytes[17], bytes[18], bytes[19],
            bytes[20], bytes[21], bytes[22], bytes[23],
        ]);

        Some(GgufHeader {
            magic: "GGUF".to_string(),
            version,
            tensor_count,
            metadata_kv_count,
        })
    }

    /// Ritorna la dimensione totale in bytes del buffer mappato.
    pub fn size(&self) -> u64 {
        self.size
    }
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct GgufHeader {
    pub magic: String,
    pub version: u32,
    pub tensor_count: u64,
    pub metadata_kv_count: u64,
}
