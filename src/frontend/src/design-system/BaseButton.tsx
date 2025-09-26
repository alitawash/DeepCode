import React from 'react';
import { tokens } from './tokens';

type Intent = 'primary' | 'secondary' | 'danger';

const intentToColor: Record<Intent, { background: string; color: string }> = {
  primary: {
    background: tokens.color.primary,
    color: tokens.color.primary_text,
  },
  secondary: {
    background: tokens.color.surface,
    color: tokens.color.secondary_text,
  },
  danger: {
    background: tokens.color.danger,
    color: tokens.color.primary_text,
  },
};

export interface BaseButtonProps extends React.ButtonHTMLAttributes<HTMLButtonElement> {
  intent?: Intent;
}

export const BaseButton: React.FC<BaseButtonProps> = ({
  intent = 'primary',
  style,
  children,
  type: buttonType = 'button',
  ...rest
}) => {
  const palette = intentToColor[intent];

  return (
    <button
      {...rest}
      type={buttonType}
      style={{
        background: palette.background,
        color: palette.color,
        borderRadius: tokens.radius.md,
        border: `1px solid ${tokens.color.border}`,
        padding: `${tokens.spacing.sm} ${tokens.spacing.lg}`,
        fontFamily: tokens.typography.font_family,
        fontSize: tokens.typography.font_size_md,
        fontWeight: parseInt(tokens.typography.font_weight_semibold, 10),
        boxShadow: tokens.shadow.soft,
        cursor: 'pointer',
        transition: 'transform 0.2s ease, box-shadow 0.2s ease',
        ...style,
      }}
      onMouseEnter={(event) => {
        event.currentTarget.style.transform = 'translateY(-1px)';
      }}
      onMouseLeave={(event) => {
        event.currentTarget.style.transform = 'translateY(0)';
      }}
    >
      {children}
    </button>
  );
};
