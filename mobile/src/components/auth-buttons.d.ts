// Platform-resolved at bundle time: auth-buttons.native.tsx (Apple on iOS only,
// with a busy overlay while sign-in runs) or auth-buttons.web.tsx (both
// providers, no overlay). This declaration gives tsc the shared interface since
// it does not resolve platform extensions.
export type AuthButtonsProps = {
  isAppleLoading: boolean;
  isDisabled: boolean;
  onContinueApple: () => void;
  onContinueGoogle: () => void;
};

export function AuthButtons(props: AuthButtonsProps): JSX.Element;
