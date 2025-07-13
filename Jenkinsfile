pipeline {
    agent any
    environment {
        FLUTTER_HOME = '/opt/flutter'
        PATH = "${FLUTTER_HOME}/bin:${PATH}"
        PUB_HOSTED_URL = 'https://trialjq29zm.jfrog.io/artifactory/api/pub/dart-pub-pub/'
        ARTIFACTORY_URL = 'https://trialjq29zm.jfrog.io/artifactory/flutter-app-releases-generic-local/'
    }
    stages {
        stage('Setup') {
            steps {
                sh '''
                flutter doctor -v
                flutter clean
                '''
            }
        }
        stage('Build') {
            steps {
                withCredentials([string(credentialsId: 'artifactory-token', variable: 'TOKEN')]) {
                    sh '''
                    # Configure Dart auth
                    mkdir -p ~/.config/dart
                    cat > ~/.config/dart/pub-credentials.json <<EOF
                    {
                      "accessToken":"$TOKEN",
                      "refreshToken":"$TOKEN",
                      "tokenEndpoint":"$PUB_HOSTED_URL",
                      "scopes":["$PUB_HOSTED_URL"],
                      "expiration":9999999999999
                    }
                    EOF
                    
                    # Build with verbose logging
                    flutter pub get
                    flutter build apk --release --verbose
                    
                    # Verify APK exists
                    APK_PATH="build/app/outputs/flutter-apk/app-release.apk"
                    if [ ! -f "$APK_PATH" ]; then
                        echo "ERROR: APK not found at $APK_PATH"
                        echo "Build directory contents:"
                        find . -name build -type d | xargs ls -laR
                        exit 1
                    fi
                    '''
                }
            }
        }
        stage('Publish') {
            steps {
                withCredentials([usernamePassword(
                    credentialsId: 'jfrog-creds',
                    usernameVariable: 'JFROG_USER',
                    passwordVariable: 'JFROG_PASS'
                )]) {
                    sh '''
                    APK_PATH="build/app/outputs/flutter-apk/app-release.apk"
                    curl -u$JFROG_USER:$JFROG_PASS \
                         -T "$APK_PATH" \
                         "${ARTIFACTORY_URL}${BUILD_NUMBER}/app-release.apk"
                    '''
                }
            }
        }
    }
    post {
        always {
            sh '''
            mkdir -p artifacts
            cp build/app/outputs/flutter-apk/*.apk artifacts/ || true
            '''
            archiveArtifacts artifacts: 'artifacts/*.apk', fingerprint: true
        }
    }
}