pipeline {
    agent any
    environment {
        FLUTTER_HOME = '/opt/flutter'
        ARTIFACTORY_URL = 'https://trialjq29zm.jfrog.io/artifactory'
        // Workspace-local paths
        ANDROID_SDK = "${WORKSPACE}/android-sdk"
        PUB_CACHE = "${WORKSPACE}/.pub-cache"
        PATH = "${FLUTTER_HOME}/bin:${ANDROID_SDK}/cmdline-tools/latest/bin:${ANDROID_SDK}/platform-tools:${PATH}"
    }
    stages {
        stage('Setup Environment') {
            steps {
                sh '''
                # Create workspace directories
                mkdir -p "${ANDROID_SDK}" "${PUB_CACHE}"
                
                # Copy minimal required Android SDK components
                cp -r /home/vagrant/VirtualBox/android-sdk/cmdline-tools "${ANDROID_SDK}/"
                cp -r /home/vagrant/VirtualBox/android-sdk/platform-tools "${ANDROID_SDK}/"
                
                # Initialize pub cache
                flutter pub cache repair --cache-dir="${PUB_CACHE}"
                '''
            }
        }

        stage('Build APK') {
            steps {
                sh '''
                # Set environment variables
                export ANDROID_HOME="${ANDROID_SDK}"
                export PUB_CACHE="${PUB_CACHE}"
                
                # Build with verbose output
                flutter clean
                flutter pub get --verbose
                flutter build apk --release --verbose
                
                # Verify APK exists
                ls -la build/app/outputs/flutter-apk/app-release.apk
                '''
            }
            post {
                success {
                    archiveArtifacts artifacts: 'build/app/outputs/flutter-apk/app-release.apk'
                }
                failure {
                    archiveArtifacts artifacts: '**/build.log', fingerprint: false
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
                        def version = sh(script: "grep 'version:' pubspec.yaml | awk '{print \$2}'", returnStdout: true).trim()
                        def appName = sh(script: "grep 'name:' pubspec.yaml | awk '{print \$2}'", returnStdout: true).trim()
                        
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
            echo "=== Environment Status ==="
            flutter doctor -v
            echo "=== Build Artifacts ==="
            ls -la build/app/outputs/flutter-apk/
            '''
        }
    }
}