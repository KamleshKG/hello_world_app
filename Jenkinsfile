pipeline {
    agent any
    environment {
        FLUTTER_HOME = '/opt/flutter'
        ANDROID_HOME = '/home/vagrant/VirtualBox/android-sdk'
        PUB_CACHE = "${WORKSPACE}/.pub-cache"
        PATH = "${FLUTTER_HOME}/bin:${ANDROID_HOME}/cmdline-tools/latest/bin:${ANDROID_HOME}/platform-tools:${PATH}"
    }
    stages {
        stage('Setup Environment') {
            steps {
                sh '''
                mkdir -p "${PUB_CACHE}"
                flutter doctor -v
                '''
            }
        }

        stage('Build APK') {
            steps {
                sh '''
                flutter clean
                flutter pub get
                flutter build apk --release
                '''
            }
        }

        stage('Verify Artifacts') {
            steps {
                sh '''
                # Check standard APK locations
                if [ -f "build/app/outputs/flutter-apk/app-release.apk" ]; then
                    echo "Primary APK found"
                    ls -lh build/app/outputs/flutter-apk/app-release.apk
                elif [ -f "build/app/outputs/apk/release/app-release.apk" ]; then
                    echo "Secondary APK found"
                    ls -lh build/app/outputs/apk/release/app-release.apk
                else
                    echo "Searching for APKs..."
                    find build -name "*.apk" | while read apk; do
                        ls -lh "$apk"
                    done
                    echo "No APK files found!"
                    exit 1
                fi
                '''
            }
        }
    }
    post {
        always {
            sh '''
            echo "Workspace contents:"
            ls -la
            '''
        }
    }
}