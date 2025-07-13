pipeline {
    agent any
    environment {
        // Use workspace-relative paths instead of system paths
        FLUTTER_HOME = '/opt/flutter'
        ANDROID_SDK = "${WORKSPACE}/android-sdk"  // Local copy
        PUB_CACHE = "${WORKSPACE}/.pub-cache"
        
        PATH = "${FLUTTER_HOME}/bin:${ANDROID_SDK}/cmdline-tools/latest/bin:${ANDROID_SDK}/platform-tools:${PATH}"
        ARTIFACTORY_URL = 'https://trialjq29zm.jfrog.io/artifactory'
    }
    stages {
        stage('Prepare Workspace') {
            steps {
                sh '''
                # Create local directories with proper permissions
                mkdir -p "${ANDROID_SDK}" "${PUB_CACHE}"
                
                # Copy essential Android SDK components (if needed)
                # cp -r /home/vagrant/VirtualBox/android-sdk/cmdline-tools "${ANDROID_SDK}/"
                # cp -r /home/vagrant/VirtualBox/android-sdk/platform-tools "${ANDROID_SDK}/"
                
                # Set up pub cache
                flutter pub cache repair --cache-dir="${PUB_CACHE}"
                '''
            }
        }

        stage('Build APK') {
            steps {
                sh '''
                # Use local paths that Jenkins can access
                export ANDROID_HOME="${ANDROID_SDK}"
                export PUB_CACHE="${PUB_CACHE}"
                
                flutter clean
                flutter pub get
                flutter build apk --release
                
                # Verify build output
                ls -la build/app/outputs/flutter-apk/app-release.apk
                '''
            }
            post {
                success {
                    archiveArtifacts artifacts: 'build/app/outputs/flutter-apk/app-release.apk'
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
            echo "=== Build Artifacts ==="
            ls -la build/app/outputs/flutter-apk/
            '''
        }
    }
}