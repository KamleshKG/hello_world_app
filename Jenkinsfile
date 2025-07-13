pipeline {
    agent any
    environment {
        // CONFIRMED ABSOLUTE PATHS
        FLUTTER_HOME = '/opt/flutter'
        ANDROID_SDK_ROOT = '/home/vagrant/VirtualBox/android-sdk'
        ANDROID_HOME = '/home/vagrant/VirtualBox/android-sdk'  // Legacy support
        JAVA_HOME = '/usr/lib/jvm/java-11-openjdk-amd64'
        
        PATH = "${FLUTTER_HOME}/bin:${ANDROID_SDK_ROOT}/cmdline-tools/latest/bin:${ANDROID_SDK_ROOT}/platform-tools:${JAVA_HOME}/bin:${PATH}"
    }
    stages {
        stage('Force SDK Detection') {
            steps {
                sh '''
                # Nuclear verification
                echo "=== FORCING SDK DETECTION ==="
                ls -la ${ANDROID_SDK_ROOT}/platform-tools/adb
                ${ANDROID_SDK_ROOT}/cmdline-tools/latest/bin/sdkmanager --list
                
                # Write local.properties file
                echo "sdk.dir=${ANDROID_SDK_ROOT}" > android/local.properties
                echo "ndk.dir=${ANDROID_SDK_ROOT}/ndk" >> android/local.properties
                '''
            }
        }

        stage('Build with Forced Paths') {
            steps {
                sh '''
                # Set ALL possible SDK variables
                export ANDROID_SDK_ROOT="${ANDROID_SDK_ROOT}"
                export ANDROID_HOME="${ANDROID_SDK_ROOT}"
                export ANDROID_NDK_HOME="${ANDROID_SDK_ROOT}/ndk"
                
                flutter clean
                flutter pub get
                flutter build apk --release --verbose
                
                # Verify beyond doubt
                if [ -f "build/app/outputs/flutter-apk/app-release.apk" ]; then
                    echo "✅ Build successful!"
                    ls -lh build/app/outputs/flutter-apk/app-release.apk
                else
                    echo "❌ Build failed - searching for errors..."
                    find . -name "*.log" -exec grep -l "error\\|fail\\|exception" {} \\;
                    exit 1
                fi
                '''
            }
        }
    }
}