pipeline {
    agent any
    environment {
        FLUTTER_HOME = '/opt/flutter'
        ANDROID_SDK_ROOT = '/home/vagrant/VirtualBox/android-sdk'
        PATH = "${FLUTTER_HOME}/bin:${ANDROID_SDK_ROOT}/cmdline-tools/latest/bin:${PATH}"
    }
    stages {
        stage('Migrate to Android v2 Embedding') {
            steps {
                sh '''
                # Backup current files
                cp android/app/src/main/AndroidManifest.xml android/app/src/main/AndroidManifest.xml.bak
                cp android/app/build.gradle android/app/build.gradle.bak

                # Update to v2 embedding
                flutter clean
                flutter create --platforms android --androidx .

                # Restore custom configurations
                grep -v "io.flutter.app" android/app/src/main/AndroidManifest.xml.bak > android/app/src/main/AndroidManifest.xml
                mv android/app/build.gradle.bak android/app/build.gradle
                '''
            }
        }

        stage('Build APK') {
            steps {
                sh '''
                flutter pub get
                flutter build apk --release --verbose 2>&1 | tee build.log

                if [ -f "build/app/outputs/flutter-apk/app-release.apk" ]; then
                    echo "✅ Build successful!"
                    ls -lh build/app/outputs/flutter-apk/app-release.apk
                else
                    echo "❌ Build failed!"
                    grep -i "error\\|fail\\|exception" build.log
                    exit 1
                fi
                '''
            }
        }
    }
}