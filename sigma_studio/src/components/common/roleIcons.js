// ==============================================================================
// Icone dei ruoli in lucide-react
// I manifesti dichiarano emoji o nomi di icona: le emoji cambiano disegno tra
// Windows e Raspberry Pi e non seguono il tema, quindi la UI le traduce in lucide.
// ==============================================================================
import {
  Atom, Bot, Building2, Camera, ChartBar, CircleCheck, CircuitBoard, Clapperboard,
  Code, Cpu, FlaskConical, Film, MessageSquare, Music, Palette, PenTool, Scissors,
  ShieldCheck, Stethoscope, Wrench
} from 'lucide-react';

// Ordine significativo: le parole piu' specifiche vengono prima di quelle generiche
// ("code_architect" deve diventare Code, non Building2).
const RULES = [
  [/montat|editor video|tagli|scissor|✂/, Scissors],
  [/proof|review|revisor|qualit|audit|✅/, CircleCheck],
  [/test|\bqa\b|sicurez|🛡/, ShieldCheck],
  [/code|cod|dev|programm|svilupp|💻/, Code],
  [/fotograf|\bdop\b|camera|📷/, Camera],
  [/regis|clapper|🎬/, Clapperboard],
  [/scenegg|scrittur|storia|✍|📝/, PenTool],
  [/film|🎞/, Film],
  [/fisic|physic|math|matemat|scienz|atom|⚛/, Atom],
  [/sound|audio|music|🎵|🎧/, Music],
  [/viz|grafic|chart|dati|📊|📈/, ChartBar],
  [/design|palette|art|🎨/, Palette],
  [/hardware|kicad|elettron|pcb|circuit/, CircuitBoard],
  [/medic|clin|farmac|salut|🩺|🧪/, Stethoscope],
  [/lab|chimic/, FlaskConical],
  [/admin|sistem|wrench|🔧/, Wrench],
  [/architect|kernel|🏗/, Building2],
  [/cpu|⚡/, Cpu],
  [/assistan|chat|message|💬/, MessageSquare]
];

export const resolveRoleLucide = (role = {}) => {
  const text = `${role.id || ''} ${role.filename || ''} ${role.name || ''} ${role.title || ''} ${role.role || ''} ${role.icon || ''}`.toLowerCase();
  for (const [pattern, Icon] of RULES) {
    if (pattern.test(text)) return Icon;
  }
  return Bot;
};
