pipeline {
    agent any
    environment {
        // CONFIRMED PATHS (Update these to match your server)
        FLUTTER_HOME = '/opt/flutter'
        ANDROID_SDK_ROOT = '/home/vagrant/VirtualBox/android-sdk'  // Use ANDROID_SDK_ROOT instead of ANDROID_HOME
        JAVA_HOME = '/usr/lib/jvm/java-11-openjdk-amd64'
        PATH = "${FLUTTER_HOME}/bin:${ANDROID_SDK_ROOT}/cmdline-tools/latest/bin:${ANDROID_SDK_ROOT}/platform-tools:${JAVA_HOME}/bin:${PATH}"
    }
    stages {
        stage('Verify Environment') {
            steps {
                sh '''
                # Print critical diagnostics
                echo "=== Environment Verification ==="
                echo "Flutter: $(which flutter)"
                echo "Android SDK: ${ANDROID_SDK_ROOT}"
                echo "Java: $(java -version 2>&1 | head -n 1)"
                echo "PATH: ${PATH}"
                
                # Verify SDK components exist
                ls ${ANDROID_SDK_ROOT}/platform-tools/adb || {
                    echo "❌ Missing Android platform-tools";
                    exit 1;
                }
                
                # Accept licenses non-interactively
                yes | ${ANDROID_SDK_ROOT}/cmdline-tools/latest/bin/sdkmanager --licenses
                '''
            }
        }

        stage('Build APK') {
            steps {
                sh '''
                # Set required env vars explicitly
                export ANDROID_SDK_ROOT="${ANDROID_SDK_ROOT}"
                export ANDROID_HOME="${ANDROID_SDK_ROOT}"  # Backwards compatibility
                
                flutter clean
                flutter pub get
                flutter build apk --release --verbose 2>&1 | tee build.log
                
                # Verify APK exists
                if [ ! -f "build/app/outputs/flutter-apk/app-release.apk" ]; then
                    echo "❌ APK not found in standard location!"
                    echo "=== Searching all build outputs ==="
                    find build -name "*.apk" || {
                        echo "=== Build Log Errors ===";
                        grep -i "error\\|fail\\|exception" build.log;
                        exit 1;
                    }
                fi
                '''
            }
            post {
                always {
                    archiveArtifacts artifacts: 'build.log', fingerprint: false
                }
            }
        }
    }
    post {
        always {
            sh '''
            echo "=== Final Environment ==="
            flutter doctor -v
            echo "=== Build Outputs ==="
            ls -la build/app/outputs/flutter-apk/ || echo "No build outputs found"
            '''
        }
    }
}