pipeline {
    agent any
    environment {
        // Verified paths from your system
        FLUTTER_HOME = '/opt/flutter'
        ANDROID_SDK_ROOT = '/home/vagrant/VirtualBox/android-sdk'
        JAVA_HOME = '/usr/lib/jvm/java-11-openjdk-amd64'
        PATH = "${FLUTTER_HOME}/bin:${ANDROID_SDK_ROOT}/cmdline-tools/latest/bin:${ANDROID_SDK_ROOT}/platform-tools:${JAVA_HOME}/bin:${PATH}"
    }
    stages {
        stage('Pre-Build Diagnostics') {
            steps {
                sh '''
                echo "=== PRE-BUILD VERIFICATION ==="
                echo "System PATH: ${PATH}"
                echo "Flutter version:" && flutter --version
                echo "Android SDK components:" && ls ${ANDROID_SDK_ROOT}
                echo "Java version:" && java -version
                flutter doctor -v
                '''
            }
        }

        stage('Build with Debug') {
            steps {
                sh '''
                # Enable command echoing and exit on error
                set -ex

                # Clean and prepare
                flutter clean
                flutter pub get

                # Run build with maximum verbosity
                flutter build apk --release --verbose 2>&1 | tee build.log

                # Verify Gradle build actually ran
                if [ ! -d "build/app/intermediates" ]; then
                    echo "❌ Gradle build did not complete successfully!"
                    echo "Checking for Gradle errors..."
                    find . -name "*.log" -exec grep -l "FAILURE" {} \\;
                    exit 1
                fi
                '''
            }
            post {
                always {
                    archiveArtifacts artifacts: 'build.log', fingerprint: false
                    archiveArtifacts artifacts: '**/gradle.log', fingerprint: false
                }
            }
        }

        stage('Post-Build Analysis') {
            when {
                expression { !fileExists('build/app/outputs/flutter-apk/app-release.apk') }
            }
            steps {
                sh '''
                echo "=== BUILD FAILURE ANALYSIS ==="
                echo "Checking for any generated APKs..."
                find . -name "*.apk" | while read file; do
                    echo "Found APK at: ${file}"
                    ls -lh "${file}"
                done

                echo "Checking Gradle reports..."
                find android/app/build/reports -type f | while read file; do
                    echo "Gradle report: ${file}"
                    head -n 20 "${file}"
                done

                echo "Most recent errors from build log:"
                grep -A 20 -B 5 -i "error\\|fail\\|exception" build.log || echo "No obvious errors found"
                '''
            }
        }
    }
}