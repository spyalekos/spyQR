#!/usr/bin/env bash
set -euo pipefail

APP_NAME="SpyQR"
PROJECT_NAME="spyqr"
BUNDLE_ID="gr.spyalekos.spyqr"
OUTPUT_APK="build/apk/${APP_NAME}.apk"
ANDROID_STAGE="/tmp/spyqr_android_stage"
PHASE="${1:-all}"

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$PROJECT_DIR"

free_memory_guards() {
    echo "🧹 Ελευθέρωση μνήμης (τερματισμός Dart LSP & Gradle Daemons)..."
    pkill -9 -f "[d]art.*language-server" 2>/dev/null || true
    pkill -9 -f "[G]radleDaemon" 2>/dev/null || true
    pkill -9 -f "GradleWrapperMain" 2>/dev/null || true
    pkill -9 -f "org.gradle" 2>/dev/null || true
    pkill -9 -f "[k]otlin-compiler-daemon" 2>/dev/null || true
    rm -rf "$PROJECT_DIR/build/flutter" "$PROJECT_DIR/build/site-packages" 2>/dev/null || true
    sync
}

export JAVA_HOME="/usr/lib/jvm/java-17-openjdk-amd64"
export ANDROID_HOME="/home/user/Android/sdk"
export ANDROID_SDK_ROOT="/home/user/Android/sdk"
export PATH="/home/user/flutter/3.44.8/bin:$JAVA_HOME/bin:$ANDROID_SDK_ROOT/cmdline-tools/latest/bin:$ANDROID_SDK_ROOT/platform-tools:$PATH"

# Αυστηρός περιορισμός μνήμης (< 768 MB) & SerialGC για αποφυγή παγώματος συστήματος
JVM_LOW_MEM="-Xmx768m -Xms128m -XX:MaxMetaspaceSize=256m -XX:ReservedCodeCacheSize=64m -XX:+UseSerialGC -Dfile.encoding=UTF-8"
export _JAVA_OPTIONS="$JVM_LOW_MEM"
export GRADLE_OPTS="$JVM_LOW_MEM -Dorg.gradle.jvmargs=\"$JVM_LOW_MEM\" -Dorg.gradle.daemon=false -Dorg.gradle.parallel=false -Dorg.gradle.workers.max=1 -Dorg.gradle.vfs.watch=false -Dkotlin.incremental=false -Dkotlin.compiler.execution.strategy=in-process"
export FLET_CLI_NO_RICH_OUTPUT=1
export FLET_CLI_SKIP_FLUTTER_DOCTOR=1

VERSION="$(.venv/bin/python -c 'import tomllib; print(tomllib.load(open("pyproject.toml", "rb"))["project"]["version"])')"
BUILD_NUMBER="$(.venv/bin/python -c 'import tomllib; print(tomllib.load(open("pyproject.toml", "rb"))["tool"]["flet"].get("build_number", 1))')"

mkdir -p build/apk

run_phase1_stage() {
    free_memory_guards
    echo "=== ΦΑΣΗ 1: Προετοιμασία Εξωτερικού Stage ($ANDROID_STAGE) & Python Wheels ==="
    mkdir -p "$ANDROID_STAGE/src" "$ANDROID_STAGE/assets" "$ANDROID_STAGE/build"

    # Διατήρηση ήδη κατεβασμένου build_python_3.14.7 αν υπάρχει στο /tmp/spyqr_android_stage/flutter
    if [ -d "$ANDROID_STAGE/flutter" ] && [ ! -d "$ANDROID_STAGE/build/flutter" ]; then
        mv "$ANDROID_STAGE/flutter" "$ANDROID_STAGE/build/flutter"
    fi
    if [ -d "$ANDROID_STAGE/site-packages" ] && [ ! -d "$ANDROID_STAGE/build/site-packages" ]; then
        mv "$ANDROID_STAGE/site-packages" "$ANDROID_STAGE/build/site-packages"
    fi

    cp -f pyproject.toml README.md "$ANDROID_STAGE/"
    cp -rf src/* "$ANDROID_STAGE/src/"
    cp -rf assets/* "$ANDROID_STAGE/assets/" 2>/dev/null || true
    mkdir -p "$ANDROID_STAGE/src/assets"
    cp -rf assets/* "$ANDROID_STAGE/src/assets/" 2>/dev/null || true
    sync

    .venv/bin/python - "$ANDROID_STAGE" "$PROJECT_NAME" "$APP_NAME" "$BUNDLE_ID" "$VERSION" "$BUILD_NUMBER" <<'PYSTAGE'
import argparse
import sys
from flet_cli.commands.build import Command

stage_dir, project_name, app_name, bundle_id, version, build_number = sys.argv[1:7]

class StageOnlyBuildCommand(Command):
    def run_flutter(self):
        print("✅ Ολοκληρώθηκε το Python/Flet staging (παράκαμψη flutter build στη Φάση 1).")

    def copy_build_output(self):
        pass

parser = argparse.ArgumentParser()
cmd = StageOnlyBuildCommand(parser)
opts = parser.parse_args([
    "apk",
    stage_dir,
    "--project", project_name,
    "--product", app_name,
    "--artifact", app_name,
    "--org", "gr.spyalekos",
    "--bundle-id", bundle_id,
    "--build-version", version,
    "--build-number", build_number,
    "--arch", "arm64-v8a",
    "--module-name", "main",
    "--no-compile-app",
    "--cleanup-app",
    "--cleanup-packages",
    "--no-rich-output",
    "--skip-flutter-doctor",
    "--yes",
])
try:
    cmd.handle(opts)
except SystemExit as e:
    if e.code not in (0, None):
        raise
PYSTAGE

    sync
    free_memory_guards
    echo "✅ ΦΑΣΗ 1 ολοκληρώθηκε. Ελεύθερη μνήμη:"
    free -h
}

run_phase2_patch() {
    free_memory_guards
    echo "=== ΦΑΣΗ 2: Ενσωμάτωση Native ZXing Scanner & Low-RAM Gradle Ρυθμίσεων ==="
    local flutter_dir="${ANDROID_STAGE}/build/flutter"
    local android_dir="${flutter_dir}/android"
    local app_dir="${android_dir}/app"
    local main_dir="${app_dir}/src/main"
    local package_dir="${main_dir}/kotlin/gr/spyalekos/spyqr"
    local manifest="${main_dir}/AndroidManifest.xml"
    local gradle_kts="${app_dir}/build.gradle.kts"
    local pubspec="${flutter_dir}/pubspec.yaml"

    if [ ! -d "$flutter_dir" ]; then
        echo "❌ Δεν βρέθηκε το $flutter_dir. Τρέξτε πρώτα τη Φάση 1."
        exit 1
    fi

    if [ -f "$pubspec" ] && grep -q "jni: 1.0.0" "$pubspec"; then
        sed -i 's/jni: 1.0.0/jni: 1.1.0/g' "$pubspec"
    fi

    mkdir -p "$package_dir"

    if [ -f "$gradle_kts" ]; then
        echo "🩹 Patching build.gradle.kts (ZXing, DuplicatesStrategy, R8/Lint disable για οικονομία RAM)..."
        .venv/bin/python - "$gradle_kts" <<'PYGRADLE'
import sys

path = sys.argv[1]
with open(path, "r", encoding="utf-8") as f:
    content = f.read()

# Disable R8 minification & resource shrinking in release to save ~600MB RAM
if "isMinifyEnabled = false" not in content:
    content = content.replace(
        'signingConfig = signingConfigs.getByName("debug")',
        'isMinifyEnabled = false\n            isShrinkResources = false\n            signingConfig = signingConfigs.getByName("debug")',
    )

# Disable lintVitalRelease during assembleRelease to save ~400MB RAM
if "checkReleaseBuilds = false" not in content:
    content = content.replace(
        "android {",
        "android {\n    lint {\n        checkReleaseBuilds = false\n        abortOnError = false\n    }",
        1,
    )

if "zxing-android-embedded" not in content:
    content += """

dependencies {
    implementation("com.journeyapps:zxing-android-embedded:4.3.0")
    implementation("com.google.zxing:core:3.5.3")
}

tasks.withType<Copy>().configureEach {
    duplicatesStrategy = org.gradle.api.file.DuplicatesStrategy.EXCLUDE
}
tasks.withType<Sync>().configureEach {
    duplicatesStrategy = org.gradle.api.file.DuplicatesStrategy.EXCLUDE
}
"""

with open(path, "w", encoding="utf-8") as f:
    f.write(content)
PYGRADLE
    fi

    if [ -f "$manifest" ]; then
        echo "🩹 Patching AndroidManifest.xml (CAMERA permission & spyqr://scan deep-link)..."
        .venv/bin/python - "$manifest" <<'PYMANIFEST'
import sys

path = sys.argv[1]
with open(path, "r", encoding="utf-8") as f:
    content = f.read()

content = content.replace('android:launchMode="singleTop"', 'android:launchMode="singleTask"')

if "android.permission.CAMERA" not in content:
    content = content.replace(
        "<application",
        '<uses-permission android:name="android.permission.CAMERA" />\n    <application',
        1,
    )

if 'xmlns:tools=' not in content:
    content = content.replace(
        '<manifest xmlns:android="http://schemas.android.com/apk/res/android">',
        '<manifest xmlns:android="http://schemas.android.com/apk/res/android" xmlns:tools="http://schemas.android.com/tools">',
        1,
    )

if 'android:scheme="spyqr"' not in content:
    intent_filter = """            <intent-filter>
                <action android:name="android.intent.action.VIEW" />
                <category android:name="android.intent.category.DEFAULT" />
                <category android:name="android.intent.category.BROWSABLE" />
                <data android:scheme="spyqr" android:host="scan" />
            </intent-filter>
        </activity>"""
    content = content.replace("</activity>", intent_filter, 1)

if "com.journeyapps.barcodescanner.CaptureActivity" not in content:
    capture_act = """        <activity
            android:name="com.journeyapps.barcodescanner.CaptureActivity"
            android:screenOrientation="fullSensor"
            tools:replace="screenOrientation" />
    </application>"""
    content = content.replace("</application>", capture_act, 1)

with open(path, "w", encoding="utf-8") as f:
    f.write(content)
PYMANIFEST
    fi

    echo "🩹 Εγγραφή native MainActivity.kt (ZXing 1D/2D Camera & Image File Scanner)..."
    cat > "${package_dir}/MainActivity.kt" <<'KOTLIN'
package gr.spyalekos.spyqr

import android.content.Intent
import android.graphics.Bitmap
import android.graphics.BitmapFactory
import android.net.Uri
import android.os.Bundle
import android.util.Log
import android.widget.Toast
import com.google.zxing.BinaryBitmap
import com.google.zxing.DecodeHintType
import com.google.zxing.MultiFormatReader
import com.google.zxing.RGBLuminanceSource
import com.google.zxing.common.GlobalHistogramBinarizer
import com.google.zxing.common.HybridBinarizer
import com.google.zxing.integration.android.IntentIntegrator
import com.google.zxing.integration.android.IntentResult
import io.flutter.embedding.android.FlutterActivity
import org.json.JSONObject
import java.io.File
import java.util.EnumMap

class MainActivity : FlutterActivity() {
    private var lastBackTime: Long = 0

    override fun onBackPressed() {
        val currentTime = System.currentTimeMillis()
        if (currentTime - lastBackTime < 2000) {
            super.onBackPressed()
        } else {
            lastBackTime = currentTime
            Toast.makeText(
                this,
                "Πατήστε ξανά Πίσω για έξοδο από το SpyQR",
                Toast.LENGTH_SHORT
            ).show()
        }
    }

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        handleScanIntent(intent)
    }

    override fun onNewIntent(intent: Intent) {
        super.onNewIntent(intent)
        setIntent(intent)
        handleScanIntent(intent)
    }

    override fun onActivityResult(requestCode: Int, resultCode: Int, data: Intent?) {
        val result: IntentResult? = IntentIntegrator.parseActivityResult(requestCode, resultCode, data)
        if (result != null) {
            val contents = result.contents
            if (contents.isNullOrBlank()) {
                Toast.makeText(this, "Η σάρωση ακυρώθηκε.", Toast.LENGTH_SHORT).show()
                return
            }
            writeScanResult(code = contents, format = result.formatName ?: "QR_CODE", error = null)
            return
        }
        super.onActivityResult(requestCode, resultCode, data)
    }

    private fun handleScanIntent(sourceIntent: Intent?) {
        val uri: Uri = sourceIntent?.data ?: return
        if (uri.scheme == "spyqr" && uri.host == "scan") {
            when (uri.path) {
                "/start", "", null -> {
                    sourceIntent.data = null
                    launchScanner()
                }
                "/file" -> {
                    val filePath = uri.getQueryParameter("path")
                    sourceIntent.data = null
                    if (!filePath.isNullOrEmpty()) {
                        decodeBitmapFile(filePath)
                    }
                }
            }
        }
    }

    private fun launchScanner() {
        val integrator = IntentIntegrator(this)
        integrator.setDesiredBarcodeFormats(IntentIntegrator.ALL_CODE_TYPES)
        integrator.setPrompt("Σαρώστε κωδικό QR ή Barcode (1D/2D)")
        integrator.setCameraId(0)
        integrator.setBeepEnabled(true)
        integrator.setBarcodeImageEnabled(false)
        integrator.setOrientationLocked(false)
        integrator.initiateScan()
    }

    private fun writeScanResult(code: String?, format: String?, error: String?) {
        val json = JSONObject()
        if (code != null) {
            json.put("code", code)
            json.put("format", format ?: "QR_CODE")
        }
        if (error != null) {
            json.put("error", error)
        }
        json.put("ts", System.currentTimeMillis())
        val payload = json.toString()

        val targets = mutableListOf<File>()
        targets.add(File(filesDir, ".spyqr_scan_result.json"))
        targets.add(File(File(filesDir, "data"), ".spyqr_scan_result.json"))
        getExternalFilesDir(null)?.let { targets.add(File(it, ".spyqr_scan_result.json")) }
        File(filesDir.parentFile, "app_flutter").let { targets.add(File(it, ".spyqr_scan_result.json")) }

        for (target in targets) {
            try {
                target.parentFile?.mkdirs()
                target.writeText(payload, Charsets.UTF_8)
            } catch (_: Exception) {
            }
        }
    }

    private fun decodeBitmapFile(filePath: String) {
        Thread {
            try {
                val imgFile = File(filePath)
                if (!imgFile.exists()) {
                    writeScanResult(null, null, "FILE_NOT_FOUND")
                    return@Thread
                }
                val boundsOpts = BitmapFactory.Options().apply { inJustDecodeBounds = true }
                BitmapFactory.decodeFile(filePath, boundsOpts)
                var sampleSize = 1
                val maxDim = maxOf(boundsOpts.outWidth, boundsOpts.outHeight)
                while (maxDim / sampleSize > 1600) {
                    sampleSize *= 2
                }
                val decodeOpts = BitmapFactory.Options().apply {
                    inSampleSize = sampleSize
                    inPreferredConfig = Bitmap.Config.ARGB_8888
                }
                val bitmap = BitmapFactory.decodeFile(filePath, decodeOpts)
                if (bitmap == null) {
                    writeScanResult(null, null, "DECODE_FAILED")
                    return@Thread
                }

                val width = bitmap.width
                val height = bitmap.height
                val pixels = IntArray(width * height)
                bitmap.getPixels(pixels, 0, width, 0, 0, width, height)
                bitmap.recycle()

                val source = RGBLuminanceSource(width, height, pixels)
                val hints = EnumMap<DecodeHintType, Any>(DecodeHintType::class.java)
                hints[DecodeHintType.TRY_HARDER] = java.lang.Boolean.TRUE
                hints[DecodeHintType.ALSO_INVERTED] = java.lang.Boolean.TRUE
                val reader = MultiFormatReader()
                reader.setHints(hints)

                var rawResult = try {
                    reader.decodeWithState(BinaryBitmap(HybridBinarizer(source)))
                } catch (e: Exception) {
                    null
                }

                if (rawResult == null) {
                    rawResult = try {
                        reader.decodeWithState(BinaryBitmap(GlobalHistogramBinarizer(source)))
                    } catch (e: Exception) {
                        null
                    }
                }

                if (rawResult != null) {
                    writeScanResult(rawResult.text, rawResult.barcodeFormat.name, null)
                } else {
                    writeScanResult(null, null, "NOT_FOUND")
                }
            } catch (e: Exception) {
                Log.e("SpyQRScan", "Error decoding image file", e)
                writeScanResult(null, null, "NOT_FOUND")
            }
        }.start()
    }
}
KOTLIN

    cat > "${android_dir}/gradle.properties" <<EOF
org.gradle.jvmargs=$JVM_LOW_MEM
android.useAndroidX=true
android.enableJetifier=false
org.gradle.daemon=false
org.gradle.parallel=false
org.gradle.workers.max=1
org.gradle.vfs.watch=false
kotlin.incremental=false
kotlin.compiler.execution.strategy=in-process
EOF

    cat > "${android_dir}/local.properties" <<EOF
sdk.dir=/home/user/Android/sdk
flutter.sdk=/home/user/flutter/3.44.8
flutter.buildMode=release
flutter.versionName=${VERSION}
flutter.versionCode=${BUILD_NUMBER}
EOF

    echo "🎨 Ενημέρωση Android launcher icons από το assets/icon.png..."
    .venv/bin/python - "${main_dir}/res" "assets/icon.png" <<'PYICONS'
import os
import sys
from PIL import Image

res_dir, icon_path = sys.argv[1:3]
if os.path.exists(icon_path):
    img = Image.open(icon_path).convert("RGBA")
    mipmap_targets = {
        "mipmap-mdpi": (48, 48),
        "mipmap-hdpi": (72, 72),
        "mipmap-xhdpi": (96, 96),
        "mipmap-xxhdpi": (144, 144),
        "mipmap-xxxhdpi": (192, 192),
    }
    drawable_targets = {
        "drawable-mdpi": (108, 108),
        "drawable-hdpi": (162, 162),
        "drawable-xhdpi": (216, 216),
        "drawable-xxhdpi": (324, 324),
        "drawable-xxxhdpi": (432, 432),
    }
    for folder, size in mipmap_targets.items():
        out_folder = os.path.join(res_dir, folder)
        os.makedirs(out_folder, exist_ok=True)
        resized = img.resize(size, Image.Resampling.LANCZOS)
        resized.save(os.path.join(out_folder, "ic_launcher.png"), "PNG")
        resized.save(os.path.join(out_folder, "ic_launcher_round.png"), "PNG")
    for folder, size in drawable_targets.items():
        out_folder = os.path.join(res_dir, folder)
        os.makedirs(out_folder, exist_ok=True)
        resized = img.resize(size, Image.Resampling.LANCZOS)
        resized.save(os.path.join(out_folder, "ic_launcher_foreground.png"), "PNG")
    print(f"✅ Δημιουργήθηκαν επιτυχώς όλα τα μεγέθη launcher icons στο {res_dir}")
PYICONS

    echo "📦 Ανανέωση build/python-app bundle..."
    rm -rf "${ANDROID_STAGE}/build/python-app"
    mkdir -p "${ANDROID_STAGE}/build/python-app/assets"
    cp -r src/* "${ANDROID_STAGE}/build/python-app/"
    cp -r assets/* "${ANDROID_STAGE}/build/python-app/assets/" 2>/dev/null || true

    echo "📦 Εκτέλεση flutter pub get στο εξωτερικό stage..."
    (cd "$flutter_dir" && /home/user/flutter/3.44.8/bin/flutter --no-version-check --suppress-analytics pub get --no-precompile)

    sync
    free_memory_guards
    echo "✅ ΦΑΣΗ 2 ολοκληρώθηκε. Ελεύθερη μνήμη:"
    free -h
}

run_phase3_flutter_assemble() {
    free_memory_guards
    echo "=== ΦΑΣΗ 3: Standalone Flutter AOT Compile (libapp.so & flutter_assets ΧΩΡΙΣ Gradle στη μνήμη) ==="
    local flutter_dir="${ANDROID_STAGE}/build/flutter"
    local out_dir="${flutter_dir}/build/app/intermediates/flutter/release"
    mkdir -p "$out_dir"

    (
        cd "$flutter_dir"
        /home/user/flutter/3.44.8/bin/flutter --no-version-check --suppress-analytics assemble \
            --depfile "${out_dir}/flutter_build.d" \
            --output "${out_dir}" \
            -dTargetFile=lib/main.dart \
            -dTargetPlatform=android \
            -dBuildMode=release \
            -dTrackWidgetCreation=true \
            -dTreeShakeIcons=true \
            -dAndroidArchs=android-arm64 \
            -dMinSdkVersion=24 \
            android_aot_bundle_release_android-arm64
    )

    sync
    free_memory_guards
    ls -lh "${out_dir}/arm64-v8a/app.so"
    echo "✅ ΦΑΣΗ 3 ολοκληρώθηκε. Ελεύθερη μνήμη:"
    free -h
}

run_phase4_gradle_package() {
    free_memory_guards
    echo "=== ΦΑΣΗ 4: Standalone Gradle APK Packaging (ΧΩΡΙΣ compileFlutterBuildRelease / gen_snapshot) ==="
    local flutter_dir="${ANDROID_STAGE}/build/flutter"
    local android_dir="${flutter_dir}/android"

    echo "📦 Συγχρονισμός κώδικα Python στο ${ANDROID_STAGE}/build/python-app..."
    rm -rf "${ANDROID_STAGE}/build/python-app"
    mkdir -p "${ANDROID_STAGE}/build/python-app/assets"
    cp -r src/* "${ANDROID_STAGE}/build/python-app/"
    cp -r assets/* "${ANDROID_STAGE}/build/python-app/assets/" 2>/dev/null || true

    cat > "${android_dir}/local.properties" <<EOF
sdk.dir=/home/user/Android/sdk
flutter.sdk=/home/user/flutter/3.44.8
flutter.buildMode=release
flutter.versionName=${VERSION}
flutter.versionCode=${BUILD_NUMBER}
EOF

    cat > "${android_dir}/gradle.properties" <<EOF
org.gradle.jvmargs=$JVM_LOW_MEM
android.useAndroidX=true
android.enableJetifier=false
org.gradle.daemon=false
org.gradle.parallel=false
org.gradle.workers.max=1
org.gradle.vfs.watch=false
kotlin.incremental=false
kotlin.compiler.execution.strategy=in-process
EOF

    export SERIOUS_PYTHON_VERSION="3.14"
    export SERIOUS_PYTHON_SITE_PACKAGES="${ANDROID_STAGE}/build/site-packages"
    export SERIOUS_PYTHON_APP="${ANDROID_STAGE}/build/python-app"
    export SERIOUS_PYTHON_BUNDLE_ID="$BUNDLE_ID"

    (
        cd "$android_dir"
        if [ ! -f gradlew ]; then
            cp -rf /home/user/flutter/3.44.8/bin/cache/artifacts/gradle_wrapper/* .
        fi
        chmod +x gradlew
        ./gradlew assembleRelease \
            -Ptarget-platform=android-arm64 \
            -x compileFlutterBuildRelease \
            -x lintVitalRelease \
            -x downloadDistArchive_armeabi-v7a \
            -x downloadDistArchive_x86_64 \
            -x downloadDartBridge_armeabi-v7a \
            -x downloadDartBridge_x86_64 \
            --no-daemon \
            --max-workers=1 \
            -Dorg.gradle.jvmargs="$JVM_LOW_MEM" \
            -Dorg.gradle.daemon=false \
            -Dorg.gradle.parallel=false \
            -Dorg.gradle.workers.max=1 \
            -Dkotlin.incremental=false \
            -Dkotlin.compiler.execution.strategy=in-process
    )

    sync
    free_memory_guards

    APK_CANDIDATE=""
    for CANDIDATE in \
        "${flutter_dir}/build/app/outputs/flutter-apk/app-release.apk" \
        "${android_dir}/app/build/outputs/flutter-apk/app-release.apk" \
        "$(find "$ANDROID_STAGE" -name '*.apk' -print -quit)"; do
        if [ -n "$CANDIDATE" ] && [ -f "$CANDIDATE" ]; then
            APK_CANDIDATE="$CANDIDATE"
            break
        fi
    done

    if [ -z "$APK_CANDIDATE" ] || [ ! -f "$APK_CANDIDATE" ]; then
        echo "❌ Δεν βρέθηκε τελικό APK."
        exit 1
    fi

    cp -f "$APK_CANDIDATE" "$OUTPUT_APK"
    sync
    ls -lh "$OUTPUT_APK"
    echo "✅ APK έτοιμο: $OUTPUT_APK"
}

case "$PHASE" in
    phase1) run_phase1_stage ;;
    phase2) run_phase2_patch ;;
    phase3) run_phase3_flutter_assemble ;;
    phase4) run_phase4_gradle_package ;;
    all)
        run_phase1_stage
        run_phase2_patch
        run_phase3_flutter_assemble
        run_phase4_gradle_package
        ;;
    *)
        echo "Χρήση: $0 [all|phase1|phase2|phase3|phase4]"
        exit 1
        ;;
esac
