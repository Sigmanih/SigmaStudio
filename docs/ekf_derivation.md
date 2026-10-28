# Filtro di Kalman Esteso (EKF): derivazione analitica completa

Il **Filtro di Kalman Esteso** (Extended Kalman Filter, EKF) è la generalizzazione del
classico Filtro di Kalman al caso in cui il sistema da stimare è descritto da modelli
**non lineari**. L'idea centrale è linearizzare localmente i modelli non lineari attorno
alla stima corrente tramite le **matrici Jacobiane**, e applicare poi la ricorsione
predizione-aggiornamento del filtro lineare alla linearizzazione ottenuta.

Il risultato è un filtro **sub-ottimo** (non più strettamente bayesiano) ma in pratica
molto efficace, a patto che le non linearità siano moderate e il rumore sia approssimato
come gaussiano.

---

## 1. Modello del sistema non lineare

Sia $\mathbf{x}_k \in \mathbb{R}^{n}$ lo **stato** al tempo discreto $k$, e
$\mathbf{z}_k \in \mathbb{R}^{m}$ l'**osservazione**. Il sistema è descritto da:

$$
\mathbf{x}_{k+1} = f(\mathbf{x}_k, \mathbf{u}_k) + \mathbf{w}_k
$$

$$
\mathbf{z}_k = h(\mathbf{x}_k) + \mathbf{v}_k
$$

dove:

- $f: \mathbb{R}^{n} \times \mathbb{R}^{p} \to \mathbb{R}^{n}$ è la **funzione di transizione**
  dello stato, non lineare in generale;
- $h: \mathbb{R}^{n} \to \mathbb{R}^{m}$ è la **funzione di osservazione**, non lineare in generale;
- $\mathbf{u}_k \in \mathbb{R}^{p}$ è il **vettore dei comandi** (input noti) al tempo $k$;
- $\mathbf{w}_k \sim \mathcal{N}(\mathbf{0}, \mathbf{Q}_k)$ è il **rumore di processo**, gaussiano
  a media nulla con covarianza $\mathbf{Q}_k \in \mathbb{R}^{n \times n}$;
- $\mathbf{v}_k \sim \mathcal{N}(\mathbf{0}, \mathbf{R}_k)$ è il **rumore di misura**, gaussiano a media
  nulla con covarianza $\mathbf{R}_k \in \mathbb{R}^{m \times m}$.

Si assume che $\mathbf{w}_k$ e $\mathbf{v}_k$ siano indipendenti tra loro e dalla distribuzione
a priori dello stato, e che la densità a priori di $\mathbf{x}_0$ sia gaussiana:
$\mathbf{x}_0 \sim \mathcal{N}(\hat{\mathbf{x}}_0, \mathbf{P}_0)$.

### Definizione delle matrici di rumore

| Simbolo | Dimensione | Significato fisico |
|:---|:---:|:---|
| $\mathbf{Q}_k$ | $n \times n$ | Covarianza del rumore di processo: incertezza intrinseca della dinamica |
| $\mathbf{R}_k$ | $m \times m$ | Covarianza del rumore di misura: incertezza dei sensori |

Entrambe le matrici sono **simmetriche semidefinite positive** ($\mathbf{Q}_k \succeq 0$,
$\mathbf{R}_k \succeq 0$) e, nella pratica, definite positive per garantire l'invertibilità
delle quantità che ne derivano.

---

## 2. Linearizzazione locale tramite le matrici Jacobiane

Poiché $f$ e $h$ sono non lineari, il filtro di Kalman classico non si applica direttamente.
L'EKF risolve il problema **linearizzando** i modelli attorno alla stima disponibile:

- per la **predizione**, si linearizza $f$ attorno alla stima a posteriori $\hat{\mathbf{x}}_k$;
- per l'**aggiornamento**, si linearizza $h$ attorno alla stima a priori
  $\hat{\mathbf{x}}_{k+1|k}$.

### 2.1 Jacobiana della dinamica (matrice $F_k$)

La matrice Jacobiana della transizione rispetto allo stato è:

$$
\mathbf{F}_k = \left. \frac{\partial f(\mathbf{x}, \mathbf{u})}{\partial \mathbf{x}} \right|_{\mathbf{x}=\hat{\mathbf{x}}_k,\; \mathbf{u}=\mathbf{u}_k}
\in \mathbb{R}^{n \times n}
$$

Il suo elemento generico è $[\mathbf{F}_k]_{ij} = \dfrac{\partial f_i}{\partial x_j}$,
derivato parziale della $i$-esima componente di $f$ rispetto alla $j$-esima componente dello stato.

### 2.2 Jacobiana dell'osservazione (matrice $H_k$)

La matrice Jacobiana dell'osservazione rispetto allo stato è:

$$
\mathbf{H}_k = \left. \frac{\partial h(\mathbf{x})}{\partial \mathbf{x}} \right|_{\mathbf{x}=\hat{\mathbf{x}}_{k+1|k}}
\in \mathbb{R}^{m \times n}
$$

Il suo elemento generico è $[\mathbf{H}_k]_{ij} = \dfrac{\partial h_i}{\partial x_j}$.

> **Nota.** Se la dinamica dipende anche dal comando, si può introdurre la Jacobiana
> $\mathbf{B}_k = \left.\dfrac{\partial f}{\partial \mathbf{u}}\right|_{\hat{\mathbf{x}}_k}$ per modellare
> l'incertezza sui comandi; nella formulazione standard si assume $\mathbf{u}_k$ noto e certo.

---

## 3. Passo di predizione (time update)

Il passo di predizione propaga la stima e la sua incertezza dal tempo $k$ al tempo $k+1$,
anticipando lo stato prima di ricevere la nuova misura. È l'equivalente della **propagazione
della densità a priori** $p(\mathbf{x}_{k+1} \mid \mathbf{z}_{1:k})$.

### 3.1 Propagazione della media (stima a priori)

La stima predetta (a priori) si ottiene applicando il modello di transizione non lineare
alla stima filtrata al tempo $k$:

$$
\hat{\mathbf{x}}_{k+1|k} = f\!\left(\hat{\mathbf{x}}_{k|k},\, \mathbf{u}_k\right)
$$

Questa è la **media** della distribuzione a priori. In un filtro lineare sarebbe
$\hat{\mathbf{x}}_{k+1|k} = \mathbf{F}_k \hat{\mathbf{x}}_{k|k} + \mathbf{B}_k \mathbf{u}_k$; qui si usa la
funzione non lineare $f$ intera, non la sua linearizzazione.

### 3.2 Propagazione della covarianza (a priori)

La matrice di covarianza predetta si ottiene propagando la covarianza filtrata attraverso
la **linearizzazione** della dinamica. Sviluppando $f$ in serie di Taylor al primo ordine
dintorno a $\hat{\mathbf{x}}_{k|k}$:

$$
f(\mathbf{x}_{k+1}) \approx f(\hat{\mathbf{x}}_{k|k}) + \mathbf{F}_k (\mathbf{x}_{k+1} - \hat{\mathbf{x}}_{k|k})
$$

Poiché la trasformazione affine preserva la media e trasforma la covarianza per
congruenza, si ha:

$$
\mathbf{P}_{k+1|k} = \mathbf{F}_k \, \mathbf{P}_{k|k} \, \mathbf{F}_k^{\top} + \mathbf{Q}_k
$$

Il termine $\mathbf{F}_k \mathbf{P}_{k|k} \mathbf{F}_k^{\top}$ propaga l'incertezza dello stato attraverso la
dinamica linearizzata; il termine $\mathbf{Q}_k$ aggiunge l'incertezza del modello (rumore di
processo). La matrice $\mathbf{P}_{k+1|k}$ è simmetrica e definita positiva semidefinita.

> **Interpretazione.** La predizione è il passo in cui il filtro "si allarga": l'incertezza
cresce perché la dinamica non lineare e il rumore di processo introducono nuova incertezza.

## 4. Passo di aggiornamento (measurement update)

Il passo di aggiornamento fonde la misura $\mathbf{z}_{k+1}$ con la predizione per produrre la
stima filtrata (a posteriori) $\hat{\mathbf{x}}_{k+1|k+1}$. È l'equivalente della **propagazione della
densità a posteriori** $p(\mathbf{x}_{k+1} \mid \mathbf{z}_{1:k+1})$.

### 4.1 Innovazione (residuo di misura)

L'**innovazione** è la differenza tra la misura osservata e la misura predetta:

$$
\mathbf{y}_{k+1} = \mathbf{z}_{k+1} - h\!\left(\hat{\mathbf{x}}_{k+1|k}\right)
\in \mathbb{R}^{m}
$$

L'innovazione misura quanto la nuova osservazione "sorprende" il filtro. La sua
covarianza (covarianza dell'innovazione) è:

$$
\mathbf{S}_{k+1} = \mathbf{H}_k \, \mathbf{P}_{k+1|k} \, \mathbf{H}_k^{\top} + \mathbf{R}_{k+1}
\in \mathbb{R}^{m \times m}
$$

Il termine $\mathbf{H}_k \mathbf{P}_{k+1|k} \mathbf{H}_k^{\top}$ è la covarianza della misura predetta (incertezza
dello stato proiettata nello spazio di osservazione); $\mathbf{R}_{k+1}$ aggiunge il rumore di misura.

### 4.2 Guadagno di Kalman

Il **guadagno di Kalman** determina quanto peso dare all'innovazione rispetto alla
predizione. Si ottiene minimizzando la tracci
[...]
}^{\top}
$$

Questa è la forma standard dell'aggiornamento della covarianza. Il termine $\mathbf{I} - \mathbf{K}_{k+1}\mathbf{H}_k$
rappresenta la "contrazione" dell'incertezza dovuta alla misura.

### 4.5 Forma di Joseph (stabilità numerica)

La forma standard può perdere simmetria e definita-positività per errori di arrotondamento.
La **forma di Joseph** è algebricamente equivalente ma numericamente più stabile:

$$
\mathbf{P}_{k+1|k+1} = (\mathbf{I} - \mathbf{K}_{k+1}\mathbf{H}_k)\, \mathbf{P}_{k+1|k} \, (\mathbf{I} - \mathbf{K}_{k+1}\mathbf{H}_k)^{\top}
+ \mathbf{K}_{k+1}\, \mathbf{R}_{k+1} \, \mathbf{K}_{k+1}^{\top}
$$

Questa forma garantisce che $\mathbf{P}_{k+1|k+1}$ resti simmetrica e definita positiva semidefinita anche
in presenza di errori di arrotondamento, ed è preferita nelle implementazioni reali.

## 5. Riepilogo delle matrici e dei vettori

| Simbolo | Dimensione | Significato fisico |
|:---|:---:|:---|
| $\mathbf{x}_k$ | $n \times 1$ | Vettore di stato (posizione, velocità, ecc.) |
| $\mathbf{z}_k$ | $m \times 1$ | Vettore di osservazione (misura del sensore) |
| $\mathbf{u}_k$ | $p \times 1$ | Vettore di comando/controllo noto |
| $\mathbf{F}_k$ | $n \times n$ | Jacobiana della dinamica $f$ rispetto a $\mathbf{x}$ (transizione linearizzata) |
| $\mathbf{H}_k$ | $m \times n$ | Jacobiana dell'osservazione $h$ rispetto a $\mathbf{x}$ (modello di misura linearizzato) |
| $\mathbf{Q}_k$ | $n \times n$ | Covarianza del rumore di processo (incertezza del modello) |
| $\mathbf{R}_{k+1}$ | $m \times m$ | Covarianza del rumore di misura (precisione del sensore) |
| $\mathbf{P}_{k|k}$ | $n \times n$ | Covarianza a posteriori (dopo l'aggiornamento al tempo $k$) |
| $\mathbf{P}_{k+1|k}$ | $n \times n$ | Covarianza a priori (dopo la predizione, prima della misura) |
| $\mathbf{K}_{k+1}$ | $n \times m$ | Guadagno di Kalman (peso ottimale tra predizione e misura) |
| $\mathbf{S}_{k+1}$ | $m \times m$ | Covarianza dell'innovazione (incertezza del residuo di misura) |
| $\mathbf{y}_{k+1}$ | $m \times 1$ | Innovazione (residuo tra misura osservata e predetta) |

Tutte le matrici di covarianza ($\mathbf{Q}_k$, $\mathbf{R}_{k+1}$, $\mathbf{P}$, $\mathbf{S}_{k+1}$) sono
**simmetriche e definite positive semidefinite**; il guadagno $\mathbf{K}_{k+1}$ bilancia in modo
ottimo (in senso minimo-varianza) la fiducia nella predizione rispetto alla misura.
