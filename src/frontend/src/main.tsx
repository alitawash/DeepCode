import React from 'react';
import ReactDOM from 'react-dom/client';
import { BaseButton } from './design-system/BaseButton';
import { useDesignTokens } from './design-system/tokens';

const App: React.FC = () => {
  const tokens = useDesignTokens();

  return (
    <div
      style={{
        fontFamily: tokens.typography.font_family,
        background: tokens.color.background,
        minHeight: '100vh',
        padding: tokens.spacing.lg,
      }}
    >
      <header
        style={{
          background: tokens.color.surface,
          borderRadius: tokens.radius.lg,
          padding: tokens.spacing.lg,
          boxShadow: tokens.shadow.soft,
          border: `1px solid ${tokens.color.border}`,
        }}
      >
        <h1 style={{ margin: 0, color: tokens.color.secondary_text }}>DeepCode Orchestrator</h1>
        <p style={{ color: tokens.color.secondary }}>Async chat-only workflow controller.</p>
        <div style={{ display: 'flex', gap: tokens.spacing.sm }}>
          <BaseButton intent="primary">Approve</BaseButton>
          <BaseButton intent="secondary">Decline</BaseButton>
        </div>
      </header>
    </div>
  );
};

const root = document.getElementById('root');

if (root) {
  ReactDOM.createRoot(root).render(<App />);
}
