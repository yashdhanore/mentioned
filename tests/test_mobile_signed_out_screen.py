from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
SIGNED_OUT_SCREEN = REPO_ROOT / "mobile" / "src" / "screens" / "signed-out-screen.tsx"
APP = REPO_ROOT / "mobile" / "App.tsx"
SUPABASE = REPO_ROOT / "mobile" / "src" / "supabase.ts"


def test_signed_out_screen_does_not_offer_unsupported_apple_auth() -> None:
    screen_source = SIGNED_OUT_SCREEN.read_text()
    app_source = APP.read_text()
    supabase_source = SUPABASE.read_text()

    assert "Continue with Apple" not in screen_source
    assert "onContinueApple" not in screen_source
    assert "isAppleLoading" not in screen_source
    assert "handleSignIn('apple')" not in app_source
    assert "authProviderInFlight === 'apple'" not in app_source
    assert "Extract<Provider, 'google'>" in supabase_source
