from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
SIGNED_OUT_SCREEN = REPO_ROOT / "mobile" / "src" / "screens" / "signed-out-screen.tsx"
APP = REPO_ROOT / "mobile" / "App.tsx"
PENDING_SOURCE = REPO_ROOT / "mobile" / "src" / "features" / "captures" / "pending-shared-source.ts"
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


def test_signed_out_screen_explains_pending_shared_source() -> None:
    screen_source = SIGNED_OUT_SCREEN.read_text()
    app_source = APP.read_text()
    pending_source = PENDING_SOURCE.read_text()

    assert "Sign in to save this shared source." in screen_source
    assert "pendingSharedSourceUrl" in screen_source
    assert "onDiscardPendingSharedSource" in screen_source
    assert "pendingSharedSourceStore.clear" in app_source
    assert "sourceUrl" in pending_source
    assert "createdAtMs" in pending_source
    assert "access_token" not in pending_source
    assert "refresh_token" not in pending_source


def test_pending_shared_source_intake_is_hardened() -> None:
    app_source = APP.read_text()
    pending_source = PENDING_SOURCE.read_text()

    assert "initialShareUrlProcessedRef" in app_source
    assert "sourceKey" in app_source
    assert "clearIfCurrent" in pending_source
    assert "setAuthError('Sign in to save this shared source.')" not in app_source
    assert 'setAuthError("Sign in to save this shared source.")' not in app_source
    assert "stored:${source.sourceUrl}" not in app_source
