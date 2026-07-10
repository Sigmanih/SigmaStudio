// Minimal markdown to HTML - no dependencies, no HTML entities, no crashes
export function simpleMarkdown(t) {
  try {
    if (!t) return '';
    if (typeof t !== 'string') t = String(t);
    if (!t) return '';

    var s = t;
    
    // Bold
    s = s.replace(/\*\*(.+?)\*\*/g, '<b>$1</b>');
    
    // Italic
    s = s.replace(/\*(.+?)\*/g, '<i>$1</i>');
    
    // Headings
    s = s.replace(/^#### (.+)$/gm, '<h4>$1</h4>');
    s = s.replace(/^### (.+)$/gm, '<h3>$1</h3>');
    s = s.replace(/^## (.+)$/gm, '<h2>$1</h2>');
    s = s.replace(/^# (.+)$/gm, '<h1>$1</h1>');
    
    // Newlines to <br>
    s = s.replace(/\n/g, '<br>');
    
    // Wrap in <p> if not a heading
    if (s.indexOf('<h') !== 0) {
      s = '<p>' + s + '</p>';
    }

    return s;
  } catch (e) {
    return String(t).replace(/\n/g, '<br>');
  }
}