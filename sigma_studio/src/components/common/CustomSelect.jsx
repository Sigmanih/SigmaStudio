import React, { useState, useRef, useEffect } from 'react';
import { ChevronDown, Check, Search } from 'lucide-react';

export default function CustomSelect({
  value,
  onChange,
  options = [],
  placeholder = 'Seleziona un\'opzione...',
  disabled = false,
  searchable = false,
  icon = null,
  style = {},
  buttonStyle = {},
  menuStyle = {},
  variant = 'cyan', // 'cyan' | 'purple' | 'amber' | 'emerald'
}) {
  const [isOpen, setIsOpen] = useState(false);
  const [searchQuery, setSearchQuery] = useState('');
  const containerRef = useRef(null);
  const searchInputRef = useRef(null);

  // Normalize options to { value, label, badge, desc, icon }
  const normalizedOptions = options.map(opt => {
    if (typeof opt === 'string' || typeof opt === 'number') {
      return { value: String(opt), label: String(opt) };
    }
    return {
      value: opt.value ?? opt.id ?? '',
      label: opt.label ?? opt.name ?? opt.value ?? '',
      badge: opt.badge ?? opt.type,
      desc: opt.desc ?? opt.description,
      icon: opt.icon,
      color: opt.color,
    };
  });

  const selectedOption = normalizedOptions.find(opt => String(opt.value) === String(value));

  // Color variants
  const colorMap = {
    cyan: {
      border: 'rgba(0, 242, 254, 0.35)',
      focusBorder: '#00f2fe',
      glow: 'rgba(0, 242, 254, 0.25)',
      activeBg: 'rgba(0, 242, 254, 0.12)',
      activeText: '#00f2fe',
    },
    purple: {
      border: 'rgba(168, 85, 247, 0.35)',
      focusBorder: '#a855f7',
      glow: 'rgba(168, 85, 247, 0.25)',
      activeBg: 'rgba(168, 85, 247, 0.12)',
      activeText: '#c084fc',
    },
    amber: {
      border: 'rgba(250, 160, 60, 0.35)',
      focusBorder: '#faa03c',
      glow: 'rgba(250, 160, 60, 0.25)',
      activeBg: 'rgba(250, 160, 60, 0.12)',
      activeText: '#faa03c',
    },
    emerald: {
      border: 'rgba(16, 185, 129, 0.35)',
      focusBorder: '#10b981',
      glow: 'rgba(16, 185, 129, 0.25)',
      activeBg: 'rgba(16, 185, 129, 0.12)',
      activeText: '#10b981',
    },
  };

  const currentTheme = colorMap[variant] || colorMap.cyan;

  // Filter options based on search query
  const filteredOptions = normalizedOptions.filter(opt => {
    if (!searchQuery) return true;
    const q = searchQuery.toLowerCase();
    return (
      opt.label.toLowerCase().includes(q) ||
      String(opt.value).toLowerCase().includes(q) ||
      (opt.desc && opt.desc.toLowerCase().includes(q))
    );
  });

  // Close on outside click
  useEffect(() => {
    const handleOutsideClick = (e) => {
      if (containerRef.current && !containerRef.current.contains(e.target)) {
        setIsOpen(false);
        setSearchQuery('');
      }
    };
    const handleKeyDown = (e) => {
      if (e.key === 'Escape') {
        setIsOpen(false);
        setSearchQuery('');
      }
    };

    if (isOpen) {
      document.addEventListener('mousedown', handleOutsideClick);
      document.addEventListener('keydown', handleKeyDown);
      if (searchable && searchInputRef.current) {
        setTimeout(() => searchInputRef.current?.focus(), 50);
      }
    }
    return () => {
      document.removeEventListener('mousedown', handleOutsideClick);
      document.removeEventListener('keydown', handleKeyDown);
    };
  }, [isOpen, searchable]);

  const handleSelect = (optValue) => {
    onChange?.(optValue);
    setIsOpen(false);
    setSearchQuery('');
  };

  return (
    <div
      ref={containerRef}
      style={{
        position: 'relative',
        display: 'inline-block',
        width: '100%',
        userSelect: 'none',
        ...style,
      }}
    >
      {/* Trigger Button */}
      <button
        type="button"
        disabled={disabled}
        onClick={() => !disabled && setIsOpen(prev => !prev)}
        style={{
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          gap: '8px',
          width: '100%',
          minHeight: '36px',
          padding: '7px 12px',
          borderRadius: '9px',
          background: 'rgba(15, 23, 42, 0.75)',
          border: `1px solid ${isOpen ? currentTheme.focusBorder : currentTheme.border}`,
          boxShadow: isOpen ? `0 0 12px ${currentTheme.glow}` : 'none',
          color: selectedOption ? '#f8fafc' : '#94a3b8',
          fontSize: '0.78rem',
          fontWeight: 600,
          cursor: disabled ? 'not-allowed' : 'pointer',
          opacity: disabled ? 0.6 : 1,
          transition: 'all 0.2s ease',
          outline: 'none',
          textAlign: 'left',
          backdropFilter: 'blur(12px)',
          ...buttonStyle,
        }}
      >
        <div style={{ display: 'flex', alignItems: 'center', gap: '8px', overflow: 'hidden', flex: 1 }}>
          {icon && <span style={{ display: 'inline-flex', flexShrink: 0 }}>{icon}</span>}
          {selectedOption?.icon && (
            <span style={{ display: 'inline-flex', flexShrink: 0 }}>{selectedOption.icon}</span>
          )}
          <span
            style={{
              overflow: 'hidden',
              textOverflow: 'ellipsis',
              whiteSpace: 'nowrap',
              color: selectedOption ? '#ffffff' : '#94a3b8',
            }}
          >
            {selectedOption ? selectedOption.label : placeholder}
          </span>
          {selectedOption?.badge && (
            <span
              style={{
                fontSize: '0.62rem',
                fontWeight: 700,
                padding: '2px 6px',
                borderRadius: '4px',
                background: currentTheme.activeBg,
                color: currentTheme.activeText,
                border: `1px solid ${currentTheme.border}`,
                marginLeft: 'auto',
                flexShrink: 0,
              }}
            >
              {selectedOption.badge}
            </span>
          )}
        </div>

        <ChevronDown
          size={14}
          style={{
            color: isOpen ? currentTheme.activeText : '#94a3b8',
            transform: isOpen ? 'rotate(180deg)' : 'rotate(0deg)',
            transition: 'transform 0.2s ease',
            flexShrink: 0,
            marginLeft: '4px',
          }}
        />
      </button>

      {/* Dropdown Menu */}
      {isOpen && (
        <div
          style={{
            position: 'absolute',
            top: 'calc(100% + 5px)',
            left: 0,
            width: '100%',
            minWidth: '220px',
            maxHeight: '260px',
            zIndex: 9999,
            background: '#090d16',
            border: `1px solid ${currentTheme.border}`,
            borderRadius: '10px',
            boxShadow: '0 12px 36px rgba(0, 0, 0, 0.75)',
            backdropFilter: 'blur(20px)',
            display: 'flex',
            flexDirection: 'column',
            overflow: 'hidden',
            animation: 'fadeIn 0.15s ease-out',
            ...menuStyle,
          }}
        >
          {/* Search Box if list has > 5 options or searchable requested */}
          {(searchable || normalizedOptions.length > 6) && (
            <div
              style={{
                padding: '6px 8px',
                borderBottom: '1px solid rgba(255, 255, 255, 0.08)',
                background: 'rgba(255, 255, 255, 0.03)',
                display: 'flex',
                alignItems: 'center',
                gap: '6px',
              }}
            >
              <Search size={12} color="#94a3b8" />
              <input
                ref={searchInputRef}
                type="text"
                value={searchQuery}
                onChange={e => setSearchQuery(e.target.value)}
                placeholder="Filtra modelli..."
                onClick={e => e.stopPropagation()}
                style={{
                  width: '100%',
                  background: 'transparent',
                  border: 'none',
                  outline: 'none',
                  color: '#ffffff',
                  fontSize: '0.72rem',
                  fontFamily: 'inherit',
                }}
              />
            </div>
          )}

          {/* Options List */}
          <div
            style={{
              overflowY: 'auto',
              maxHeight: '210px',
              padding: '4px',
            }}
          >
            {filteredOptions.length === 0 ? (
              <div
                style={{
                  padding: '12px 14px',
                  fontSize: '0.72rem',
                  color: '#64748b',
                  textAlign: 'center',
                }}
              >
                Nessun modello trovato
              </div>
            ) : (
              filteredOptions.map(opt => {
                const isSelected = String(opt.value) === String(value);
                return (
                  <div
                    key={opt.value}
                    onClick={() => handleSelect(opt.value)}
                    style={{
                      display: 'flex',
                      alignItems: 'center',
                      justifyContent: 'space-between',
                      gap: '8px',
                      padding: '7px 10px',
                      borderRadius: '6px',
                      cursor: 'pointer',
                      fontSize: '0.74rem',
                      fontWeight: isSelected ? 700 : 500,
                      background: isSelected ? currentTheme.activeBg : 'transparent',
                      color: isSelected ? currentTheme.activeText : '#e2e8f0',
                      transition: 'background 0.12s ease, color 0.12s ease',
                      border: isSelected ? `1px solid ${currentTheme.border}` : '1px solid transparent',
                    }}
                    onMouseEnter={e => {
                      if (!isSelected) e.currentTarget.style.background = 'rgba(255, 255, 255, 0.06)';
                    }}
                    onMouseLeave={e => {
                      if (!isSelected) e.currentTarget.style.background = 'transparent';
                    }}
                  >
                    <div style={{ display: 'flex', flexDirection: 'column', gap: '2px', overflow: 'hidden' }}>
                      <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
                        {opt.icon && <span>{opt.icon}</span>}
                        <span style={{ overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                          {opt.label}
                        </span>
                      </div>
                      {opt.desc && (
                        <span style={{ fontSize: '0.62rem', color: '#64748b' }}>{opt.desc}</span>
                      )}
                    </div>

                    <div style={{ display: 'flex', alignItems: 'center', gap: '6px', flexShrink: 0 }}>
                      {opt.badge && (
                        <span
                          style={{
                            fontSize: '0.6rem',
                            fontWeight: 700,
                            padding: '1px 5px',
                            borderRadius: '4px',
                            background: isSelected ? 'rgba(0,0,0,0.3)' : 'rgba(255, 255, 255, 0.08)',
                            color: isSelected ? currentTheme.activeText : '#94a3b8',
                          }}
                        >
                          {opt.badge}
                        </span>
                      )}
                      {isSelected && <Check size={13} color={currentTheme.activeText} />}
                    </div>
                  </div>
                );
              })
            )}
          </div>
        </div>
      )}
    </div>
  );
}
