import { Image, Clapperboard, AudioLines, Music, Mic, Radio, SlidersHorizontal, Cpu, Sparkles,
  MessageSquare, Users, Wrench, Terminal, Settings, Palette, Activity, CircuitBoard, Mail,
  Send, MonitorPlay, Workflow, Brain, Gauge, BookOpen, Calendar, House, Globe, Network, Blocks } from 'lucide-react';

const icons = { Image, Clapperboard, AudioLines, Music, Mic, Radio, SlidersHorizontal, Cpu, Sparkles,
  MessageSquare, Users, Wrench, Terminal, Settings, Palette, Activity, CircuitBoard, Mail,
  Send, MonitorPlay, Workflow, Brain, Gauge, BookOpen, Calendar, House, Globe, Network, Blocks };
export default function WorkspaceIcon({ name, size = 18 }) {
  const Icon = icons[name] || Blocks;
  return <Icon size={size} aria-hidden="true" />;
}
