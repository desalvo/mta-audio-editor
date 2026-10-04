from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_android_buildconfig_is_generated_for_version_name_usage():
    gradle = (ROOT / "mobile/android/app/build.gradle.kts").read_text(encoding="utf-8")
    main = (ROOT / "mobile/android/app/src/main/java/com/desalvo/mtaaudioeditor/mobile/MainActivity.java").read_text(encoding="utf-8")
    assert "buildFeatures" in gradle
    assert "buildConfig = true" in gradle
    assert "BuildConfig.VERSION_NAME" in main


def test_ios_15_uses_compatible_locale_api():
    controller = (ROOT / "mobile/ios/MTAEditorMobile/MobileWebViewController.swift").read_text(encoding="utf-8")
    project = (ROOT / "mobile/ios/MTAEditorMobile.xcodeproj/project.pbxproj").read_text(encoding="utf-8")
    assert "IPHONEOS_DEPLOYMENT_TARGET = 15.0" in project
    assert "Locale.current.language.languageCode" not in controller
    assert "Locale.current.languageCode" in controller


def test_ios_local_stem_sync_path_carries_model_id_and_uses_explicit_types():
    engine = (ROOT / "mobile/ios/MTAEditorMobile/LocalStemEngine.swift").read_text(encoding="utf-8")
    assert "private func separateSync(inputURL: URL, modelId: String, stemCount: Int" in engine
    assert "separateSync(inputURL: inputURL, modelId: modelId, stemCount: stemCount" in engine
    assert "MLModelMetadataKey.creatorDefinedKey" in engine
    assert "Swift.max(0, Swift.min(overlap, available - tailStart))" in engine
    assert "String.CompareOptions.regularExpression" in engine


def test_ci_has_early_mobile_compile_preflights():
    workflow = (ROOT / ".github/workflows/ci-cd.yml").read_text(encoding="utf-8")
    assert "Compile Android sources preflight" in workflow
    assert ":app:compileDebugJavaWithJavac" in workflow
    assert "Compile iOS sources preflight" in workflow
    assert "-destination 'generic/platform=iOS'" in workflow
    assert "CODE_SIGNING_ALLOWED=NO" in workflow
