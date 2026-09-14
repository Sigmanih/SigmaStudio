import { useState, useEffect } from 'react';

export default function Library({ user, onLogout }) {
  const [books, setBooks] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [filter, setFilter] = useState('all'); // 'all' | 'digital' | 'audio'

  useEffect(() => {
    fetchLibrary();
  }, []);

  const fetchLibrary = async () => {
    try {
      const res = await fetch('/api/library', {
        headers: { Authorization: `Bearer ${user.token}` },
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data.message || 'Errore nel caricamento della libreria');
      setBooks(data.books);
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  const filteredBooks = filter === 'all' ? books : books.filter((b) => b.type === filter);

  return (
    <div className="library-page">
      <header className="library-header">
        <div>
          <h1>La mia libreria</h1>
          <p>Ciao, {user.name}!</p>
        </div>
        <button onClick={onLogout} className="btn btn-outline">Esci</button>
      </header>

      <div className="filter-bar">
        <button className={`filter-btn ${filter === 'all' ? 'active' : ''}`} onClick={() => setFilter('all')}>Tutti</button>
        <button className={`filter-btn ${filter === 'digital' ? 'active' : ''}`} onClick={() => setFilter('digital')}>Libri digitali</button>
        <button className={`filter-btn ${filter === 'audio' ? 'active' : ''}`} onClick={() => setFilter('audio')}>Audiolibri</button>
      </div>

      {loading && <p className="loading">Caricamento in corso...</p>}
      {error && <p className="error">{error}</p>}

      {!loading && !error && (
        <div className="book-grid">
          {filteredBooks.length === 0 ? (
            <p className="empty-state">Nessun libro trovato.</p>
          ) : (
            filteredBooks.map((book) => (
              <article key={book.id} className={`book-card ${book.type}`}>
                <div className="book-cover">
                  {book.coverUrl ? (
                    <img src={book.coverUrl} alt={book.title} />
                  ) : (
                    <span className="placeholder-icon">{book.type === 'audio' ? '🎧' : '📖'}</span>
                  )}
                </div>
                <h3>{book.title}</h3>
                <p className="author">{book.author}</p>
                <span className={`badge ${book.type}`}>{book.type === 'audio' ? 'Audiolibro' : 'Libro digitale'}</span>
              </article>
            ))
          )}
        </div>
      )}
    </div>
  );
}
