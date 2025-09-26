import { useEffect, useState } from 'react';
import designTokens from '../../../../ui/design_tokens.json';

export type DesignTokens = typeof designTokens;

export const tokens: DesignTokens = designTokens;

export function useDesignTokens(): DesignTokens {
  const [state, setState] = useState<DesignTokens>(tokens);

  useEffect(() => {
    setState(tokens);
  }, []);

  return state;
}

export function cssVariables(): Record<string, string> {
  const vars: Record<string, string> = {};

  for (const [groupName, groupValues] of Object.entries(tokens)) {
    for (const [tokenName, tokenValue] of Object.entries(groupValues)) {
      vars[`--dc-${groupName}-${tokenName}`] = tokenValue as string;
    }
  }

  return vars;
}
