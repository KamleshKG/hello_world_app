pipeline {
    agent any
    environment {
        // Confirmed paths from your system
        FLUTTER_HOME = '/opt/flutter'
        ANDROID_HOME = '/home/vagrant/VirtualBox/android-sdk' 
        PUB_CACHE = '/home/vagrant/VirtualBox/.pub-cache'
        
        // Path configuration
        PATH = "${FLUTTER_HOME}/bin:${ANDROID_HOME}/cmdline-tools/latest/bin:${ANDROID_HOME}/platform-tools:${PATH}"
        ARTIFACTORY_URL = 'https://trialjq29zm.jfrog.io/artifactory'
    }
    stages {
        stage('Environment Prep') {
            steps {
                sh '''
                # Set up pub cache
                mkdir -p ${PUB_CACHE}
                flutter pub cache repair
                
                # Verify Android SDK
                echo "Android SDK contents:"
                ls -la ${ANDROID_HOME}
                
                # Accept licenses
                yes | ${ANDROID_HOME}/cmdline-tools/latest/bin/sdkmanager --licenses
                '''
            }
        }

        stage('Build APK') {
            steps {
                sh '''
                # Clean and build with verbose logging
                flutter clean
                flutter pub get
                flutter build apk --release -v 2>&1 | tee build.log
                
                # Confirm APK exists in standard location
                if [ ! -f "build/app/outputs/flutter-apk/app-release.apk" ]; then
                    echo "Checking alternate locations..."
                    find build -name "*.apk" || echo "No APK files found"
                    exit 1
                fi
                '''
            }
            post {
                success {
                    archiveArtifacts artifacts: 'build/app/outputs/flutter-apk/app-release.apk', fingerprint: true
                }
                failure {
                    archiveArtifacts artifacts: 'build.log', fingerprint: false
                }
            }
        }

        stage('Publish to Artifactory') {
            when {
                expression { fileExists('build/app/outputs/flutter-apk/app-release.apk') }
            }
            steps {
                withCredentials([string(credentialsId: 'artifactory-token', variable: 'TOKEN')]) {
                    script {
                        def version = sh(
                            script: "grep 'version:' pubspec.yaml | awk '{print \$2}'", 
                            returnStdout: true
                        ).trim()
                        
                        def appName = sh(
                            script: "grep 'name:' pubspec.yaml | awk '{print \$2}'", 
                            returnStdout: true
                        ).trim()

                        sh """
                        curl -H "Authorization: Bearer $TOKEN" \
                             -X PUT "${ARTIFACTORY_URL}/flutter-app-releases-generic-local/${appName}/${version}/app-release.apk" \
                             -T build/app/outputs/flutter-apk/app-release.apk
                        """
                    }
                }
            }
        }
    }
    post {
        always {
            sh '''
            echo "=== Final Verification ==="
            echo "APK exists:"
            ls -la build/app/outputs/flutter-apk/app-release.apk || echo "APK not found"
            echo "Android SDK status:"
            ${ANDROID_HOME}/platform-tools/adb version
            '''
        }
    }
}