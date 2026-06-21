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
USE_CAPTURES = REPO_ROOT / "mobile" / "src" / "features" / "captures" / "use-captures.ts"


def test_signed_out_screen_offers_sign_in_with_apple() -> None:
    screen_source = SIGNED_OUT_SCREEN.read_text()
    app_source = APP.read_text()
    supabase_source = SUPABASE.read_text()
    native_buttons_source = (
        REPO_ROOT / "mobile" / "src" / "components" / "auth-buttons.native.tsx"
    ).read_text()
    web_buttons_source = (
        REPO_ROOT / "mobile" / "src" / "components" / "auth-buttons.web.tsx"
    ).read_text()

    assert "AuthButtons" in screen_source
    assert "onContinueApple" in screen_source
    assert "isAppleLoading" in screen_source
    assert "Continue with Apple" in native_buttons_source
    assert "Continue with Apple" in web_buttons_source
    assert "handleSignIn('apple')" in app_source
    assert "authProviderInFlight === 'apple'" in app_source
    assert "'google' | 'apple'" in supabase_source


def test_signed_out_screen_explains_pending_shared_source() -> None:
    screen_source = SIGNED_OUT_SCREEN.read_text()
    app_source = APP.read_text()
    pending_source = PENDING_SOURCE.read_text()

    assert "Sign in to save this shared post." in screen_source
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
    empty_state_source = (
        REPO_ROOT / "mobile" / "src" / "components" / "empty-state.tsx"
    ).read_text()

    assert "Saved posts" in home_source
    assert "Posts you save so Mentioned can find the books inside." in home_source
    assert "Finding books..." in books_source
    assert "Mentioned is checking this post for book recommendations." in books_source
    assert "The post is still saved." in books_source
    assert "Sure looks empty out here" in empty_state_source
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
    assert "Open post" in detail_source
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
    captures_source = USE_CAPTURES.read_text()

    assert "EXPO_PUBLIC_AUTH_MODE" in api_source
    assert "isDevAuthEnabled" in api_source
    assert "devAccessToken" in api_source
    assert "Production mobile builds must not set EXPO_PUBLIC_AUTH_MODE=dev." in api_source
    assert "Production mobile builds must not define EXPO_PUBLIC_DEV_USER_ID." in api_source
    assert "setAccessTokenProvider(devAccessToken)" in app_source
    assert "isDevAuthEnabled" in captures_source


def test_saved_reels_home_refresh_uses_job_list_only() -> None:
    captures_source = USE_CAPTURES.read_text()

    refresh_start = captures_source.index("const refreshCaptures = useCallback")
    refresh_end = captures_source.index("useEffect(() => {", refresh_start)
    refresh_block = captures_source[refresh_start:refresh_end]

    assert "listAllJobs()" in refresh_block
    assert "mergeJobListItemsWithCaptures" in refresh_block
    assert "Promise.all" not in refresh_block
    assert "getJob(" not in refresh_block
    assert "const job = await getJob(jobId)" in captures_source
