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
  actions,
  bannerImage,
  className = '',
  style = {},
  children
}) {
  const { theme } = useApp ? useApp() : { theme: 'dark' };
  const isLight = theme === 'light';

  const descText = subtitle || description;

  const bgStyle = bannerImage ? {
    backgroundImage: isLight
      ? `linear-gradient(135deg, rgba(254, 252, 247, 0.90) 0%, rgba(246, 240, 228, 0.86) 100%), url("${bannerImage}")`
      : `linear-gradient(135deg, rgba(10, 14, 26, 0.90) 0%, rgba(14, 22, 42, 0.86) 100%), url("${bannerImage}")`
  } : {};

  return (
    <div 
      className={`sigma-tab-header ${bannerImage ? 'has-bg' : ''} ${className}`}
      style={{ ...bgStyle, ...style }}
    >
      <div className="sigma-tab-header-main">
        {badge && (
          <div className="sigma-tab-badge">
            {BadgeIcon && <BadgeIcon size={12} />}
            <span>{badge}</span>
          </div>
        )}

        <div className="sigma-tab-title-row">
          {TitleIcon && (
            <div className="sigma-tab-icon-wrapper">
              <TitleIcon size={20} />
            </div>
          )}
          <h1 className="sigma-tab-title">
            <span>{title}</span>
            {highlight && (
              <span className="sigma-tab-title-highlight">{highlight}</span>
            )}
          </h1>
        </div>

        {descText && (
          <p className="sigma-tab-subtitle">
            {descText}
          </p>
        )}
      </div>

      {actions && (
        <div className="sigma-tab-header-actions">
          {actions}
        </div>
      )}

      {children}
    </div>
  );
}
