// Platform-resolved at bundle time: auth-buttons.native.tsx (native Apple/Google
// button components) or auth-buttons.web.tsx (plain Pressable buttons). This
// declaration gives tsc the shared interface since it does not resolve platform
// extensions.
export type AuthButtonsProps = {
  isAppleLoading: boolean;
  isDisabled: boolean;
  onContinueApple: () => void;
  onContinueGoogle: () => void;
};

export function AuthButtons(props: AuthButtonsProps): JSX.Element;
