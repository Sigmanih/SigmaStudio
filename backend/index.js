const express = require('express');
const bcrypt = require('bcryptjs');
const jwt = require('jsonwebtoken');
const cors = require('cors');

const app = express();
const PORT = 5000;
const JWT_SECRET = 'segreto-super-segreto-12345';

app.use(cors());
app.use(express.json());

// In-memory store per utenti e libri (in produzione usare un database)
let users = [];
let books = [
  { id: 1, title: 'Il Conte di Montecristo', author: 'Alexandre Dumas', type: 'digital' },
  { id: 2, title: 'I Promessi Sposi', author: 'Alessandro Manzoni', type: 'audio' },
  { id: 3, title: 'Orgoglio e Pregiudizio', author: 'Jane Austen', type: 'digital' },
];

// Middleware per autenticazione
function authMiddleware(req, res, next) {
  const token = req.headers.authorization?.split(' ')[1];
  if (!token) return res.status(401).json({ message: 'Token mancante' });
  try {
    req.user = jwt.verify(token, JWT_SECRET);
    next();
  } catch (err) {
    return res.status(401).json({ message: 'Token non valido' });
  }
}

// POST /api/register - Registrazione utente
app.post('/api/register', async (req, res) => {
  const { name, email, password } = req.body;
  if (!name || !email || !password) return res.status(400).json({ message: 'Campi obbligatori mancanti' });
  
  if (users.find(u => u.email === email)) {
    return res.status(409).json({ message: 'Email già registrata' });
  }

  const hashedPassword = await bcrypt.hash(password, 10);
  const newUser = { id: users.length + 1, name, email, password: hashedPassword };
  users.push(newUser);
  
  res.status(201).json({ message: 'Registrazione riuscita', user: { id: newUser.id, name, email } });
});

// POST /api/login - Login utente
app.post('/api/login', async (req, res) => {
  const { email, password } = req.body;
  const user = users.find(u => u.email === email);
  if (!user) return res.status(401).json({ message: 'Credenziali non valide' });

  const match = await bcrypt.compare(password, user.password);
  if (!match) return res.status(401).json({ message: 'Credenziali non valide' });

  const token = jwt.sign({ id: user.id, name: user.name, email: user.email }, JWT_SECRET, { expiresIn: '1h' });
  res.json({ token, user: { id: user.id, name: user.name, email: user.email } });
});

// GET /api/library - Libreria utente (autenticato)
app.get('/api/library', authMiddleware, (req, res) => {
  res.json(books);
});

app.listen(PORT, () => console.log(`Backend in ascolto su http://localhost:${PORT}`));
