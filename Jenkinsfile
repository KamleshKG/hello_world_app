pipeline {
    agent any
    environment {
        // Essential paths - UPDATE THESE TO MATCH YOUR SERVER
        FLUTTER_HOME = '/opt/flutter'
        ANDROID_HOME = '/home/vagrant/VirtualBox/android-sdk' 
        JAVA_HOME = '/usr/lib/jvm/java-11-openjdk-amd64'
        PUB_CACHE = "${WORKSPACE}/.pub-cache"
        
        // Configure PATH
        PATH = "${FLUTTER_HOME}/bin:${ANDROID_HOME}/cmdline-tools/latest/bin:${ANDROID_HOME}/platform-tools:${JAVA_HOME}/bin:${PATH}"
    }
    stages {
        stage('Setup Environment') {
            steps {
                sh '''
                # Verify critical paths
                echo "=== Environment ==="
                echo "Flutter: $(which flutter)"
                echo "Android SDK: ${ANDROID_HOME}"
                echo "Java: $(java -version 2>&1 | head -n 1)"
                
                # Initialize Flutter
                flutter doctor -v
                flutter pub cache repair
                '''
            }
        }

        stage('Resolve Dependencies') {
            steps {
                sh '''
                # Check for outdated packages
                flutter pub outdated
                
                # Force dependency resolution
                flutter pub upgrade --major-versions
                flutter pub get
                '''
            }
        }

        stage('Build APK') {
            steps {
                sh '''
                # Build with SDK verification
                flutter clean
                flutter build apk --release --verbose 2>&1 | tee build.log
                
                # Verify output
                ls -la build/app/outputs/flutter-apk/app-release.apk || {
                    echo "APK not found! Searching..."
                    find build -name "*.apk" || exit 1
                }
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
            echo "=== Final Status ==="
            flutter doctor -v
            echo "=== Build Output ==="
            ls -la build/app/outputs/flutter-apk/
            '''
        }
    }
}