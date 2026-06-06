from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
SIGNED_OUT_SCREEN = REPO_ROOT / "mobile" / "src" / "screens" / "signed-out-screen.tsx"
SIGNED_OUT_PREVIEW = (
    REPO_ROOT / "mobile" / "src" / "components" / "signed-out-product-preview.tsx"
)
APP = REPO_ROOT / "mobile" / "App.tsx"
HOME_SCREEN = REPO_ROOT / "mobile" / "src" / "screens" / "home-screen.tsx"
DETAIL_SCREEN = REPO_ROOT / "mobile" / "src" / "screens" / "reel-detail-screen.tsx"
BOOKS = REPO_ROOT / "mobile" / "src" / "components" / "books.tsx"
CAPTURES = REPO_ROOT / "mobile" / "src" / "captures.ts"
PENDING_SOURCE = REPO_ROOT / "mobile" / "src" / "features" / "captures" / "pending-shared-source.ts"
SUPABASE = REPO_ROOT / "mobile" / "src" / "supabase.ts"
AUTH_ORBIT_REEL_PREVIEW = (
    REPO_ROOT / "mobile" / "assets" / "auth-orbit-reel-preview.png"
)
API = REPO_ROOT / "mobile" / "src" / "api.ts"


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


def test_release_one_state_copy_is_book_first() -> None:
    home_source = HOME_SCREEN.read_text()
    books_source = BOOKS.read_text()

    assert "Saved Reels" in home_source
    assert "No saved Reels yet" in home_source
    assert "Sources you saved so Mentioned can find the books inside." in home_source
    assert "Finding books..." in books_source
    assert "checking the saved source for book mentions" in books_source
    assert "The source is still saved." in books_source
    assert "reading the Instagram post" not in books_source
    assert "Saved items" not in home_source


def test_ready_detail_uses_source_hero_before_books() -> None:
    detail_source = DETAIL_SCREEN.read_text()
    books_source = BOOKS.read_text()
    captures_source = CAPTURES.read_text()
    api_source = API.read_text()

    ready_index = detail_source.index("capture.status === 'ready'")
    processing_index = detail_source.index("capture.status === 'processing'")
    source_hero_index = detail_source.index("<SourceHero")
    books_index = detail_source.index("<BooksMentioned")
    ready_block = detail_source[ready_index:processing_index]

    assert ready_index < source_hero_index < books_index
    assert "OriginalSourceSection" not in ready_block
    assert "SourceSummary" not in detail_source
    assert "Open source" in detail_source
    assert "sourceHeroPaper" in detail_source
    assert "coverImageUrl" in captures_source
    assert "cover_image_url" in captures_source
    assert "creatorHandle" in captures_source
    assert "source_creator_handle" in captures_source
    assert "source_creator_handle" in api_source
    assert "SourceNavIdentity" in detail_source
    assert "`@${capture.creatorHandle}`" in detail_source
    assert "detailNavAvatar" in detail_source
    assert "bookListSurface" in books_source
    assert "bookCoverImage" in books_source
    assert "showDivider" in books_source


def test_invalid_shared_content_has_visible_message() -> None:
    app_source = APP.read_text()
    screen_source = SIGNED_OUT_SCREEN.read_text()

    assert "INVALID_SHARED_SOURCE_MESSAGE" in app_source
    assert "Share an Instagram Reel or post link to save it." in app_source
    assert "shareLinkError" in app_source
    assert "shareLinkError ?? authError" in app_source
    assert "InlineMessage" in screen_source


def test_signed_out_preview_uses_native_reduced_motion_safe_orbit() -> None:
    preview_source = SIGNED_OUT_PREVIEW.read_text()

    assert AUTH_ORBIT_REEL_PREVIEW.exists()
    assert "AccessibilityInfo.isReduceMotionEnabled()" in preview_source
    assert "reduceMotionChanged" in preview_source
    assert "Animated.loop" in preview_source
    assert "useNativeDriver: true" in preview_source
    assert "authOrbitBook" in preview_source
    assert "authPreviewConnector" not in preview_source
    assert "gsap" not in preview_source.lower()
    assert "remotion" not in preview_source.lower()


def test_mobile_dev_auth_bypass_is_explicit_and_production_blocked() -> None:
    app_source = APP.read_text()
    api_source = API.read_text()
    captures_source = (REPO_ROOT / "mobile" / "src" / "features" / "captures" / "use-captures.ts").read_text()

    assert "EXPO_PUBLIC_AUTH_MODE" in api_source
    assert "isDevAuthEnabled" in api_source
    assert "devAccessToken" in api_source
    assert "Production mobile builds must not set EXPO_PUBLIC_AUTH_MODE=dev." in api_source
    assert "Production mobile builds must not define EXPO_PUBLIC_DEV_USER_ID." in api_source
    assert "setAccessTokenProvider(devAccessToken)" in app_source
    assert "isDevAuthEnabled" in captures_source
