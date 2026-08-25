import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// https://vite.dev/config/
export default defineConfig({
  plugins: [react()],

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
      '/api': {
        target: 'http://localhost:8000',
        changeOrigin: true,
      },
      '/web_explorer': {
        target: 'http://localhost:8000',
        changeOrigin: true,
      },
    },
  },
})
