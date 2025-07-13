pipeline {
    agent any
    environment {
        FLUTTER_HOME = '/opt/flutter'
        PATH = "${FLUTTER_HOME}/bin:${PATH}"
        PUB_HOSTED_URL = 'https://trialjq29zm.jfrog.io/artifactory/api/pub/dart-pub-pub/'
        ARTIFACTORY_URL = 'https://trialjq29zm.jfrog.io/artifactory/flutter-app-releases-generic-local/' // Updated to your exact repo
    }
    stages {
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
                    
                    flutter pub get
                    flutter build apk --release --no-pub
                    '''
                }
            }
        }
        stage('Verify APK') {
            steps {
                sh '''
                # Debug file location
                echo "=== Build Output ==="
                find build -name "*.apk"
                ls -la build/app/outputs/flutter-apk/
                '''
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
                    # Publish with exact path
                    APK_PATH=$(find build -name "app-release.apk" | head -1)
                    if [ -f "$APK_PATH" ]; then
                        curl -u$JFROG_USER:$JFROG_PASS \
                             -T "$APK_PATH" \
                             "${ARTIFACTORY_URL}${BUILD_NUMBER}/app-release.apk"
                    else
                        echo "ERROR: APK not found at $APK_PATH"
                        exit 1
                    fi
                    '''
                }
            }
        }
    }
    post {
        always {
            sh '''
            # Archive whatever APK exists
            APK_PATH=$(find build -name "*.apk" | head -1)
            if [ -f "$APK_PATH" ]; then
                mkdir -p artifacts && cp "$APK_PATH" artifacts/
            fi
            '''
            archiveArtifacts artifacts: 'artifacts/*.apk', fingerprint: true
        }
    }
}