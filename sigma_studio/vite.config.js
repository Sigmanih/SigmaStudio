import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// Backend a cui inoltrare le API: si cambia con SIGMA_API per provare una
// seconda istanza senza toccare quella in uso.
const API_TARGET = process.env.SIGMA_API || 'http://127.0.0.1:8000'

// https://vite.dev/config/
export default defineConfig({
  plugins: [react()],

  build: {
    cssCodeSplit: false,
  },

  resolve: {
    // Un modulo in sviluppo non e' copiato dentro src/modules/: e' un
    // collegamento al repository dei moduli, cosi' una modifica fatta dentro
    // Sigma Studio arriva al repository che la deve ricevere.
    //
    // Senza questa opzione Vite risolve il collegamento al suo percorso reale
    // prima di risolvere gli import, e da li' i percorsi relativi del modulo
    // — '../../contexts/AppContext', '../common/TechSpaceCanvas' — puntano
    // dentro il repository dei moduli, dove il kernel non c'e'. La build
    // fallisce con UNRESOLVED_IMPORT su file che invece esistono.
    //
    // Con preserveSymlinks il modulo viene visto dove e' montato, e i suoi
    // import relativi tornano a significare quello che significano nella
    // copia installata: le due modalita' si comportano allo stesso modo.
    preserveSymlinks: true,
  },

  server: {
    proxy: {
      // 127.0.0.1 e non localhost: Node risolve localhost su ::1 e il server
      // ascolta solo su IPv4, quindi ogni chiamata API rispondeva 502.
      '/api': {
        target: API_TARGET,
        changeOrigin: true,
      },
      '/web_explorer': {
        target: API_TARGET,
        changeOrigin: true,
      },
      // Media generati (clip, miniature, audio) serviti dal backend sotto /data.
      '/data': {
        target: API_TARGET,
        changeOrigin: true,
      },
    },
  },
})
