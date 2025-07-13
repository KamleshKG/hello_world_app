pipeline {
    agent any
    environment {
        FLUTTER_HOME = '/opt/flutter'
        ANDROID_SDK_ROOT = '/home/vagrant/VirtualBox/android-sdk'
        JAVA_HOME = '/usr/lib/jvm/java-11-openjdk-amd64'
        PATH = "${FLUTTER_HOME}/bin:${ANDROID_SDK_ROOT}/cmdline-tools/latest/bin:${ANDROID_SDK_ROOT}/platform-tools:${JAVA_HOME}/bin:${PATH}"
    }
    stages {
        stage('Prepare Android Directory') {
            steps {
                sh '''
                mkdir -p android
                echo "sdk.dir=${ANDROID_SDK_ROOT}" > android/local.properties
                echo "ndk.dir=${ANDROID_SDK_ROOT}/ndk" >> android/local.properties
                cat android/local.properties
                '''
            }
        }

        stage('Build with Verified Paths') {
            steps {
                sh '''
                export ANDROID_SDK_ROOT="${ANDROID_SDK_ROOT}"
                export ANDROID_HOME="${ANDROID_SDK_ROOT}"
                export ANDROID_NDK_HOME="${ANDROID_SDK_ROOT}/ndk"
                
                flutter doctor -v
                flutter clean
                flutter pub get
                flutter build apk --release --verbose 2>&1 | tee build.log
                
                if [ -f "build/app/outputs/flutter-apk/app-release.apk" ]; then
                    echo "✅ Build successful!"
                    ls -lh build/app/outputs/flutter-apk/app-release.apk
                else
                    echo "❌ Build failed - checking logs..."
                    grep -i "error\\|fail\\|exception" build.log
                    find . -name "*.log" -print -exec head -n 20 {} \\;
                    exit 1
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
}