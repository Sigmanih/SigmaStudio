import React from 'react';
import { useApp } from '../../contexts/AppContext';

/**
 * TabHeader — Componente Header Universale per tutte le Tab del Kernel Sigma Studio.
 * 
 * Supporta:
 * - Badge tech pill (icona + label)
 * - Icona identificativa della tab con box retroilluminato
 * - Titolo ad alto impatto con testo a gradiente neon/accent
 * - Sottotitolo descrittivo ad alta leggibilità
 * - Area Azioni destra / comandi rapidi (auto-wrap responsive su mobile)
 * - Supporto sfondo grafico opzionale con overlay cyber-glass
 * - 100% ottimizzato per Desktop e Mobile (touch-friendly)
 */
export default function TabHeader({
  badge,
  badgeIcon: BadgeIcon,
  icon: TitleIcon,
  title,
  highlight,
  subtitle,
  description,
  tabs,
  actions,
  bannerImage,
  className = '',
  style = {},
  children
}) {
  const { theme } = useApp ? useApp() : { theme: 'dark' };
  const isLight = theme === 'light';

  const descText = subtitle || description;
  const cleanTitle = title ? String(title).replace(/[\s/&]+$/, '').trim() : '';

  return (
    <div 
      className={`sigma-tab-header ${className}`}
      style={{
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'space-between',
        padding: '6px 14px',
        borderBottom: isLight ? '1px solid rgba(0, 0, 0, 0.08)' : '1px solid rgba(255, 255, 255, 0.08)',
        background: isLight ? 'rgba(255, 255, 255, 0.85)' : 'rgba(10, 14, 26, 0.75)',
        backdropFilter: 'blur(10px)',
        WebkitBackdropFilter: 'blur(10px)',
        minHeight: '38px',
        boxSizing: 'border-box',
        flexShrink: 0,
        gap: '10px',
        flexWrap: 'wrap',
        position: 'sticky',
        top: 0,
        left: 0,
        right: 0,
        margin: 0,
        width: '100%',
        zIndex: 30,
        ...style
      }}
    >
      <div className="sigma-tab-header-left" style={{ display: 'flex', alignItems: 'center', gap: '8px', flexWrap: 'wrap', minWidth: 0, flex: 1 }}>
        {TitleIcon && (
          <div style={{
            width: '22px', height: '22px', borderRadius: '6px',
            background: isLight ? 'rgba(234, 88, 12, 0.15)' : 'rgba(0, 210, 255, 0.15)',
            border: isLight ? '1px solid rgba(234, 88, 12, 0.3)' : '1px solid rgba(0, 210, 255, 0.3)',
            display: 'flex', alignItems: 'center', justifyContent: 'center',
            color: isLight ? '#ea580c' : '#00d2ff',
            flexShrink: 0
          }}>
            <TitleIcon size={12} />
          </div>
        )}

        <span style={{ fontSize: '0.80rem', fontWeight: 800, color: isLight ? '#0f172a' : '#f1f5f9', letterSpacing: '0.2px', whiteSpace: 'nowrap' }}>
          {cleanTitle}
        </span>

        {highlight && (
          <span style={{
            fontSize: '0.62rem',
            padding: '2px 7px',
            borderRadius: '4px',
            background: isLight ? 'rgba(234, 88, 12, 0.10)' : 'rgba(0, 210, 255, 0.12)',
            color: isLight ? '#ea580c' : '#00d2ff',
            border: isLight ? '1px solid rgba(234, 88, 12, 0.25)' : '1px solid rgba(0, 210, 255, 0.25)',
            fontWeight: 700,
            whiteSpace: 'nowrap'
          }}>
            {highlight}
          </span>
        )}

        {tabs && tabs.length > 0 && (
          <div style={{
            display: 'inline-flex',
            alignItems: 'center',
            gap: '3px',
            background: isLight ? 'rgba(0,0,0,0.05)' : 'rgba(255,255,255,0.05)',
            padding: '2px',
            borderRadius: '6px',
            border: isLight ? '1px solid rgba(0,0,0,0.08)' : '1px solid rgba(255,255,255,0.08)'
          }}>
            {tabs.map(t => {
              const TabItemIcon = t.icon;
              return (
                <button
                  key={t.id}
                  onClick={t.onClick}
                  style={{
                    display: 'inline-flex',
                    alignItems: 'center',
                    gap: '4px',
                    padding: '2px 8px',
                    borderRadius: '4px',
                    border: 'none',
                    background: t.active ? (isLight ? '#ffffff' : 'rgba(0, 210, 255, 0.22)') : 'transparent',
                    color: t.active ? (isLight ? '#0f172a' : '#00d2ff') : (isLight ? '#64748b' : '#94a3b8'),
                    fontSize: '0.66rem',
                    fontWeight: t.active ? 700 : 500,
                    cursor: 'pointer',
                    boxShadow: t.active && isLight ? '0 1px 3px rgba(0,0,0,0.1)' : 'none',
                    transition: 'all 0.15s ease'
                  }}
                >
                  {TabItemIcon && <TabItemIcon size={11} />}
                  <span>{t.label}</span>
                </button>
              );
            })}
          </div>
        )}

        {badge && (
          <span style={{
            fontSize: '0.60rem',
            padding: '1px 6px',
            borderRadius: '4px',
            background: isLight ? 'rgba(0, 0, 0, 0.05)' : 'rgba(255, 255, 255, 0.06)',
            color: isLight ? '#64748b' : '#94a3b8',
            border: isLight ? '1px solid rgba(0, 0, 0, 0.08)' : '1px solid rgba(255, 255, 255, 0.08)',
            fontWeight: 700,
            textTransform: 'uppercase',
            letterSpacing: '0.5px',
            display: 'inline-flex',
            alignItems: 'center',
            gap: '4px',
            whiteSpace: 'nowrap'
          }}>
            {BadgeIcon && <BadgeIcon size={10} />}
            <span>{badge}</span>
          </span>
        )}

        {descText && (
          <span style={{ fontSize: '0.65rem', color: isLight ? '#64748b' : '#94a3b8', paddingLeft: '2px', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap', maxWidth: '520px' }}>
            • {descText}
          </span>
        )}
      </div>

      {actions && (
        <div className="sigma-tab-header-actions" style={{ display: 'flex', alignItems: 'center', gap: '8px', flexWrap: 'wrap', flexShrink: 0 }}>
          {actions}
        </div>
      )}

      {children}
    </div>
  );
}
