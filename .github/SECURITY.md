# Security Policy

## Versioni Supportate

| Versione | Supportata |
|:---------|:----------:|
| 8.x     | ✅         |
| < 8.0   | ❌         |

## Segnalare una Vulnerabilità

Se scopri una vulnerabilità di sicurezza in Sigma Studio, **non** aprire una
Issue pubblica su GitHub.

### Procedura di Responsible Disclosure

1. **Invia un'email** a: [INSERIRE EMAIL DI SICUREZZA]
2. **Includi**:
   - Descrizione della vulnerabilità
   - Passi per riprodurla
   - Impatto potenziale
   - Eventuale proof of concept
3. **Attendi conferma** di ricezione entro 48 ore
4. **Coordina** con noi la pubblicazione della fix

### Cosa aspettarsi

- Conferma di ricezione entro **48 ore**
- Valutazione iniziale entro **7 giorni**
- Aggiornamento sullo stato ogni **14 giorni**
- Riconoscimento pubblico (se lo desideri) al rilascio della fix

### Ambito

Rientrano in questa policy:
- Vulnerabilità nel kernel Python (`core/`)
- Vulnerabilità nel frontend React (`sigma_studio/`)
- Bypass del sandbox (`core/sandbox.py`)
- Esposizione di credenziali o dati sensibili
- Vulnerabilità nei server MCP

**Non** rientrano:
- Bug funzionali (usare le Issues normali)
- Vulnerabilità in dipendenze di terze parti (segnalare al progetto upstream)
- Attacchi che richiedono accesso fisico alla macchina

## Buone Pratiche di Sicurezza per gli Utenti

- Non esporre la porta 8000 su reti pubbliche senza autenticazione
- Mantieni le API key in `config/`, mai nel codice sorgente
- Aggiorna regolarmente le dipendenze
- Attiva la governance MCP per le operazioni sensibili
